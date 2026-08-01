"""
Telegram approval bridge — borrow local-ai-agents polling pattern.

- Bot polls Telegram (no open inbound ports)
- Only TELEGRAM_ALLOWED_CHAT_IDS can approve/reject
- Side effects: mark pending_ops approved/rejected; optional GitHub apply is separate

Setup:
  1. Message @BotFather → create bot → TELEGRAM_BOT_TOKEN
  2. Message your bot once, then get chat id:
       curl "https://api.telegram.org/bot$TOKEN/getUpdates"
  3. Set TELEGRAM_ALLOWED_CHAT_IDS=123456789
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass

OFFSET_PATH = DATA / "telegram_offset.txt"
PENDING_PATH = DATA / "pending_ops.json"

API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _allowed_chats() -> set:
    raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS") or ""
    return {c.strip() for c in raw.split(",") if c.strip()}


def _load_offset() -> Optional[int]:
    if OFFSET_PATH.exists():
        try:
            return int(OFFSET_PATH.read_text().strip())
        except Exception:
            return None
    return None


def _save_offset(offset: int) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    OFFSET_PATH.write_text(str(offset), encoding="utf-8")


def api(method: str, **params) -> Dict[str, Any]:
    token = _token()
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN")
    url = API.format(token=token, method=method)
    r = requests.post(url, json=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description") or "Telegram API error")
    return data.get("result")


def send_message(chat_id: str, text: str, parse_mode: Optional[str] = None) -> Any:
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text[:4000]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return api("sendMessage", **payload)


def notify_pending(items: List[Dict[str, Any]], chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Push pending proposals to your Telegram for approval."""
    from agents.tools import format_telegram_card

    allowed = _allowed_chats()
    targets = [chat_id] if chat_id else list(allowed)
    if not targets:
        return {"ok": False, "error": "Set TELEGRAM_ALLOWED_CHAT_IDS"}

    sent = 0
    for item in items:
        if item.get("status") not in ("proposed", "proposed_update"):
            continue
        card = format_telegram_card(item)
        for tid in targets:
            send_message(tid, card)
            sent += 1
            time.sleep(0.35)  # be gentle
    return {"ok": True, "messages_sent": sent, "chats": targets}


def _load_pending() -> Dict[str, Any]:
    if PENDING_PATH.exists():
        try:
            return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}


def _save_pending(payload: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def set_status(op_id: str, status: str) -> Tuple[bool, str, Optional[Dict]]:
    pending = _load_pending()
    for item in pending.get("items", []):
        if item.get("op_id") == op_id:
            item["status"] = status
            item[f"{status}_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _save_pending(pending)
            return True, f"Marked {op_id} as {status}", item
    return False, f"Unknown op_id: {op_id}", None


def handle_command(text: str, chat_id: str) -> str:
    """Parse approve/reject/list from Telegram text."""
    allowed = _allowed_chats()
    # Fail closed: empty allowlist means nobody can command (misconfigured .env).
    if not allowed or str(chat_id) not in allowed:
        return "Unauthorized chat."

    t = (text or "").strip()
    low = t.lower()

    if low in ("/start", "/help", "help"):
        return (
            "Aidr clinic ops\n"
            "• `list` — pending proposals\n"
            "• `approve op_xxxx` — approve\n"
            "• `reject op_xxxx` — reject\n"
            "• `apply op_xxxx` — push approved draft to GitHub\n"
        )

    if low == "list":
        pending = _load_pending()
        rows = [
            i
            for i in pending.get("items", [])
            if i.get("status") in ("proposed", "proposed_update", "approved")
        ]
        if not rows:
            return "No pending items."
        lines = []
        for i in rows[:20]:
            lines.append(f"{i.get('op_id')} [{i.get('status')}] {i.get('name')}")
        return "\n".join(lines)

    m = re.match(r"^(approve|reject|apply)\s+(op_[\w]+)$", low)
    if not m:
        return "Try: `list` / `approve op_…` / `reject op_…` / `apply op_…`"

    action, op_id = m.group(1), m.group(2)
    if action == "approve":
        ok, msg, _ = set_status(op_id, "approved")
        return msg if ok else msg
    if action == "reject":
        ok, msg, _ = set_status(op_id, "rejected")
        return msg if ok else msg
    if action == "apply":
        from agents import github_apply

        result = github_apply.apply_approved(op_id)
        return json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
    return "Unknown command"


def poll_once(timeout: int = 25) -> Dict[str, Any]:
    """One long-poll cycle (scheduler / cron friendly)."""
    offset = _load_offset()
    params: Dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    updates = api("getUpdates", **params) or []
    handled = 0
    for upd in updates:
        upd_id = upd.get("update_id", 0)
        _save_offset(upd_id + 1)
        msg = upd.get("message") or {}
        text = msg.get("text") or ""
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        if not text or not chat_id:
            continue
        reply = handle_command(text, chat_id)
        try:
            send_message(chat_id, reply)
        except Exception as e:
            print(f"Telegram reply error: {e}")
        handled += 1
    return {"ok": True, "updates": len(updates), "handled": handled}


def poll_loop(seconds: int = 3600) -> None:
    """Poll until wall-clock seconds elapse (or forever if seconds<=0)."""
    end = time.time() + seconds if seconds > 0 else None
    print("Telegram poll started…")
    while end is None or time.time() < end:
        try:
            result = poll_once(timeout=25)
            if result.get("handled"):
                print(result)
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(5)
