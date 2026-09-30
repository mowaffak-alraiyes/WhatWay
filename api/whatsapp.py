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

import base64
import hashlib
import hmac
import os
import core.env  # noqa: F401 — maps legacy AIDR_* vars onto WHATWAY_*
from typing import Any, Dict, Optional
import requests
from fastapi import APIRouter, Form, Header, HTTPException, Query, Request, Response

from api.rate_limit import allow as rate_allow
from core.pipeline import search_resources
from core.privacy import hash_identifier, mask_phone, truncate_user_text

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])

# In-memory session: hashed phone -> last category / language (fine for spike)
_SESSIONS: Dict[str, Dict[str, str]] = {}
_MAX_BODY = 2000


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return default


def _session(phone: str) -> Dict[str, str]:
    key = hash_identifier(phone, length=32)
    if key not in _SESSIONS:
        _SESSIONS[key] = {
            "category": "Healthcare",
            "language": _env("WHATSAPP_DEFAULT_LANG", default="en") or "en",
        }
    return _SESSIONS[key]


def _handle_message(phone: str, body: str) -> str:
    text = truncate_user_text(body or "", _MAX_BODY)
    if not text:
        return "Send a message like: dental 60629"

    # Per-sender cap (hashed) — keeps pilot cheap + stops spam loops
    ok, retry = rate_allow(hash_identifier(phone), scope="whatsapp")
    if not ok:
        return f"You're sending messages too quickly. Try again in ~{retry}s."

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


def _validate_twilio_signature(
    url: str,
    form: Dict[str, str],
    signature: Optional[str],
    auth_token: str,
) -> bool:
    """Twilio RequestValidator algorithm (HMAC-SHA1) without adding the twilio package."""
    if not signature or not auth_token:
        return False
    pieces = url + "".join(f"{k}{v}" for k, v in sorted(form.items()))
    digest = hmac.new(auth_token.encode("utf-8"), pieces.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _send_twilio(to: str, body: str) -> None:
    sid = _env("TWILIO_ACCOUNT_SID")
    token = _env("TWILIO_AUTH_TOKEN")
    from_num = _env("TWILIO_WHATSAPP_FROM", default="whatsapp:+14155238886")
    if not sid or not token:
        # Echo-only mode for local spike without credentials — never log raw phone
        print(f"[twilio-dry-run] to={mask_phone(to)} body_len={len(body or '')}")
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
        print(f"[meta-dry-run] to={mask_phone(to)} body_len={len(body or '')}")
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
        r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
        ollama_ok = r.status_code == 200
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
    request: Request,
    From: str = Form(""),
    Body: str = Form(""),
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature"),
):
    """Twilio WhatsApp webhook (form-urlencoded)."""
    auth_token = _env("TWILIO_AUTH_TOKEN")
    skip_sig = os.environ.get("WHATWAY_SKIP_TWILIO_SIGNATURE", "").strip() in ("1", "true", "yes")
    # When credentials are configured, require a valid Twilio signature.
    # Local dry-run (no token) skips validation so simulate/dev still works.
    if auth_token and not skip_sig:
        form = dict(await request.form())
        url = str(request.url)
        # Prefer public URL behind ngrok/proxy when provided
        fwd_proto = request.headers.get("x-forwarded-proto")
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if fwd_proto and fwd_host:
            url = f"{fwd_proto}://{fwd_host}{request.url.path}"
            if request.url.query:
                url = f"{url}?{request.url.query}"
        if not _validate_twilio_signature(url, {k: str(v) for k, v in form.items()}, x_twilio_signature, auth_token):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        From = str(form.get("From", From))
        Body = str(form.get("Body", Body))

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
    verify = _env("META_VERIFY_TOKEN")
    if not verify:
        raise HTTPException(status_code=403, detail="META_VERIFY_TOKEN not configured")
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
    """Local smoke test — disabled unless WHATWAY_ENABLE_SIMULATE=1."""
    if os.environ.get("WHATWAY_ENABLE_SIMULATE", "").strip() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Not found")
    phone = str(payload.get("from", "test"))[:64]
    body = truncate_user_text(str(payload.get("body", "")), _MAX_BODY)
    reply = _handle_message(phone, body)
    return {"from": mask_phone(phone) if phone != "test" else phone, "body": body, "reply": reply}
