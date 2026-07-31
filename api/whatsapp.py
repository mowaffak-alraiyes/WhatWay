"""
WhatsApp webhook spike — Twilio AND Meta Cloud API.

Same search/LLM path as the Streamlit chat via core.pipeline.search_resources.

Env / secrets:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM   (Twilio)
  META_WHATSAPP_TOKEN, META_WHATSAPP_PHONE_NUMBER_ID, META_VERIFY_TOKEN  (Meta)
  Ollama must be running locally for AI replies (OLLAMA_MODEL=llama3)
  WHATSAPP_DEFAULT_LANG=en

Run locally:
  uvicorn api.main:app --reload --port 8000
  ngrok http 8000   # expose /webhooks/whatsapp/twilio or /webhooks/whatsapp/meta
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Form, Header, HTTPException, Query, Request, Response

from core.pipeline import search_resources

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])

# In-memory session: phone -> last category / language (fine for spike)
_SESSIONS: Dict[str, Dict[str, str]] = {}


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return default


def _session(phone: str) -> Dict[str, str]:
    if phone not in _SESSIONS:
        _SESSIONS[phone] = {
            "category": "Healthcare",
            "language": _env("WHATSAPP_DEFAULT_LANG", default="en") or "en",
        }
    return _SESSIONS[phone]


def _handle_message(phone: str, body: str) -> str:
    text = (body or "").strip()
    if not text:
        return "Send a message like: dental 60629"

    sess = _session(phone)
    lower = text.lower()

    # Lightweight commands
    if lower.startswith("lang "):
        sess["language"] = text.split(maxsplit=1)[1].strip()
        return f"Language set to {sess['language']}. Ask for a resource anytime."
    if lower in ("health", "healthcare", "salud"):
        sess["category"] = "Healthcare"
        return "Category: Healthcare. Try: dental 60629"
    if lower in ("education", "edu", "esl"):
        sess["category"] = "Education"
        return "Category: Education. Try: ESL 60629"
    if lower in ("legal", "shelter", "housing"):
        sess["category"] = "Resettlement / Legal / Shelter"
        return "Category: Legal & Shelter. Try: immigration help 60608"

    result = search_resources(
        query=text,
        category=sess.get("category"),
        language=sess.get("language", "en"),
        limit=3,
        use_llm=True,
    )
    if result.get("category"):
        sess["category"] = result["category"]
    return result["text"]


def _send_twilio(to: str, body: str) -> None:
    sid = _env("TWILIO_ACCOUNT_SID")
    token = _env("TWILIO_AUTH_TOKEN")
    from_num = _env("TWILIO_WHATSAPP_FROM", default="whatsapp:+14155238886")
    if not sid or not token:
        # Echo-only mode for local spike without credentials
        print(f"[twilio-dry-run] to={to} body={body[:200]}")
        return
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    requests.post(
        url,
        data={"From": from_num, "To": to, "Body": body[:1500]},
        auth=(sid, token),
        timeout=20,
    )


def _send_meta(to: str, body: str) -> None:
    token = _env("META_WHATSAPP_TOKEN", "WHATSAPP_TOKEN")
    phone_id = _env("META_WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        print(f"[meta-dry-run] to={to} body={body[:200]}")
        return
    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body[:4096]},
        },
        timeout=20,
    )


@router.get("/health")
def whatsapp_health():
    ollama_ok = False
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5) as r:
            ollama_ok = r.status == 200
    except Exception:
        pass
    return {
        "ok": True,
        "twilio_configured": bool(_env("TWILIO_ACCOUNT_SID") and _env("TWILIO_AUTH_TOKEN")),
        "meta_configured": bool(_env("META_WHATSAPP_TOKEN") and _env("META_WHATSAPP_PHONE_NUMBER_ID")),
        "ollama": ollama_ok,
    }


@router.post("/twilio")
async def twilio_webhook(
    From: str = Form(""),
    Body: str = Form(""),
):
    """Twilio WhatsApp webhook (form-urlencoded)."""
    reply = _handle_message(From, Body)
    # Twilio can also use TwiML; we send outbound + empty 200 for sandbox simplicity
    try:
        _send_twilio(From, reply)
    except Exception as e:
        print(f"Twilio send error: {e}")
    # TwiML response as backup (works even without REST send in some setups)
    safe = (
        reply.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe[:1400]}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")


@router.get("/meta")
async def meta_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Meta Cloud API webhook verification."""
    verify = _env("META_VERIFY_TOKEN", default="bridgecare-verify")
    if hub_mode == "subscribe" and hub_verify_token == verify:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/meta")
async def meta_webhook(request: Request):
    """Meta Cloud API inbound messages."""
    payload: Dict[str, Any] = await request.json()
    try:
        entry = (payload.get("entry") or [])[0]
        changes = (entry.get("changes") or [])[0]
        value = changes.get("value") or {}
        messages = value.get("messages") or []
        if not messages:
            return {"ok": True}
        msg = messages[0]
        phone = msg.get("from", "")
        body = (msg.get("text") or {}).get("body", "")
        reply = _handle_message(phone, body)
        _send_meta(phone, reply)
    except Exception as e:
        print(f"Meta webhook error: {e}")
    return {"ok": True}


@router.post("/simulate")
async def simulate(payload: Dict[str, Any]):
    """Local smoke test without Twilio/Meta credentials."""
    phone = payload.get("from", "test")
    body = payload.get("body", "")
    reply = _handle_message(phone, body)
    return {"from": phone, "body": body, "reply": reply}
