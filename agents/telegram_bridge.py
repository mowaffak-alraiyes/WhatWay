"""
Telegram approval bridge — borrow local-ai-agents polling pattern.

- Bot polls Telegram (no open inbound ports)
- Only TELEGRAM_ALLOWED_CHAT_IDS can approve/reject
- React ❤ / ❤️ = approve · 👎 = reject (text commands still work)
- Side effects: mark pending_ops approved/rejected; optional GitHub apply is separate
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
MSG_MAP_PATH = DATA / "telegram_msg_map.json"

API = "https://api.telegram.org/bot{token}/{method}"

APPROVE_EMOJIS = {"❤", "❤️", "♥️", "💗", "💖", "💕", "😍", "🥰"}
REJECT_EMOJIS = {"👎", "💔", "❌", "❎"}


def _token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _safe_err(err: Any) -> str:
    """Never leak GitHub PATs / clone URLs into Telegram replies."""
    from agents.github_apply import redact_secrets

    return redact_secrets(str(err))


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


def _load_msg_map() -> Dict[str, str]:
    """chat_id:message_id → op_id"""
    if MSG_MAP_PATH.exists():
        try:
            return json.loads(MSG_MAP_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_msg_map(payload: Dict[str, str]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    # keep map from growing forever
    if len(payload) > 500:
        keys = list(payload.keys())[-400:]
        payload = {k: payload[k] for k in keys}
    MSG_MAP_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def notify_pending(
    items: List[Dict[str, Any]],
    chat_id: Optional[str] = None,
    *,
    digest_by_state: bool = True,
) -> Dict[str, Any]:
    """Push pending proposals to your Telegram for approval (react ❤ / 👎).

    When digest_by_state=True, send one digest per US state before individual cards.
    """
    from agents.tools import format_telegram_card, format_telegram_digest
    from agents.geo_scope import group_by_state, state_of

    allowed = _allowed_chats()
    targets = [chat_id] if chat_id else list(allowed)
    if not targets:
        return {"ok": False, "error": "Set TELEGRAM_ALLOWED_CHAT_IDS"}

    open_items = [i for i in items if i.get("status") in ("proposed", "proposed_update")]
    msg_map = _load_msg_map()
    sent = 0
    digests = 0

    if digest_by_state and open_items:
        for st, group in sorted(group_by_state(open_items).items()):
            digest = format_telegram_digest(st, group)
            for tid in targets:
                send_message(tid, digest)
                digests += 1

    for item in open_items:
        # ensure state stamped for cards
        if not item.get("state"):
            item["state"] = state_of(item)
        card = format_telegram_card(item)
        for tid in targets:
            result = send_message(tid, card)
            mid = result.get("message_id") if isinstance(result, dict) else None
            if mid is not None and item.get("op_id"):
                msg_map[f"{tid}:{mid}"] = item["op_id"]
            sent += 1

    _save_msg_map(msg_map)
    return {
        "ok": True,
        "messages_sent": sent,
        "digests_sent": digests,
        "items": len(open_items),
        "states": sorted(group_by_state(open_items).keys()) if open_items else [],
    }


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


def approve_apply_all(
    *,
    state: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Approve every open proposed/proposed_update (optionally filtered by state), then apply all."""
    from agents.geo_scope import state_of
    from agents import github_apply

    pending = _load_pending()
    st_filter = (state or "").strip().upper() or None
    to_approve: List[Dict[str, Any]] = []
    for item in pending.get("items") or []:
        if item.get("status") not in ("proposed", "proposed_update"):
            continue
        item_st = (item.get("state") or state_of(item)).upper()
        if st_filter and item_st != st_filter:
            continue
        to_approve.append(item)

    if not to_approve:
        scope = f" for {st_filter}" if st_filter else ""
        return {
            "ok": True,
            "approved_count": 0,
            "apply": {"ok": True, "total": 0, "succeeded": 0, "failed": 0},
            "message": f"No open proposals{scope} to approve-apply.",
        }

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "approved_count": len(to_approve),
            "states": sorted({(i.get("state") or state_of(i)).upper() for i in to_approve}),
            "sample": [i.get("op_id") for i in to_approve[:10]],
            "message": f"Would approve+apply {len(to_approve)} ops"
            + (f" ({st_filter})" if st_filter else ""),
        }

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for item in to_approve:
        item["status"] = "approved"
        item["approved_at"] = now
        item["approved_via"] = "approve_all"
    _save_pending(pending)

    apply_result = github_apply.apply_all_approved(dry_run=False)
    return {
        "ok": bool(apply_result.get("ok")),
        "approved_count": len(to_approve),
        "state": st_filter,
        "apply": {
            "total": apply_result.get("total"),
            "succeeded": apply_result.get("succeeded"),
            "failed": apply_result.get("failed"),
            "error": apply_result.get("error"),
        },
        "message": (
            f"Approved {len(to_approve)}"
            + (f" ({st_filter})" if st_filter else "")
            + f" → applied {apply_result.get('succeeded', 0)}/"
            + f"{apply_result.get('total', 0)} to GitHub"
        ),
    }


def handle_command(text: str, chat_id: str) -> str:
    """Parse approve/reject/list from Telegram text."""
    allowed = _allowed_chats()
    if not allowed or str(chat_id) not in allowed:
        return "Unauthorized chat."

    t = (text or "").strip()
    low = t.lower()

    if low in ("/start", "/help", "help"):
        return (
            "Aidr clinic ops\n"
            "• React ❤ on a card = approve\n"
            "• React 👎 on a card = reject\n"
            "• `list` - pending proposals\n"
            "• `approve op_xxxx` / `reject op_xxxx`\n"
            "• `apply op_xxxx` - push approved draft to GitHub\n"
            "• `approve all` / `approve-apply all` - approve+apply entire open batch\n"
            "• `approve all IN` - same, only that state (IL/IN/CO/CA/...)\n"
            "• Overnight worker keeps finding edu/legal + missing contacts\n"
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
            st = i.get("state") or ""
            lines.append(
                f"{i.get('op_id')} [{i.get('status')}] [{st}] [{i.get('category')}] {i.get('name')}"
            )
        more = len(rows) - 20
        if more > 0:
            lines.append(f"… +{more} more - `approve all` or `approve all IN` to drain")
        return "\n".join(lines)

    # Batch approve+apply: approve all | approve-apply all | approve all IN
    m_all = re.match(
        r"^(?:approve(?:-apply)?|apply)\s+all(?:\s+([a-z]{2}))?$",
        low,
    )
    if m_all:
        st = (m_all.group(1) or "").upper() or None
        # Preview count if they typed "approve all?" — treat ? as dry hint via trailing ?
        try:
            result = approve_apply_all(state=st, dry_run=False)
        except Exception as e:
            return f"Approve-all failed: {_safe_err(e)}"
        apply = result.get("apply") or {}
        lines = [
            f"✅ {result.get('message')}",
            f"Approved: {result.get('approved_count')}",
            f"GitHub apply: {apply.get('succeeded')}/{apply.get('total')} ok"
            + (f", {apply.get('failed')} failed" if apply.get("failed") else ""),
        ]
        if apply.get("error"):
            lines.append(f"Error: {_safe_err(apply['error'])}")
        return "\n".join(lines)

    m = re.match(r"^(approve|reject|apply)\s+(op_[\w]+)$", low)
    if not m:
        return (
            "React ❤ / 👎 on a card, or:\n"
            "`list` / `approve op_…` / `reject op_…` / `apply op_…`\n"
            "`approve all` / `approve all IN`"
        )

    action, op_id = m.group(1), m.group(2)
    if action == "approve":
        ok, msg, item = set_status(op_id, "approved")
        from agents.confidence import should_auto_apply_on_heart

        if ok and should_auto_apply_on_heart():
            try:
                from agents import github_apply

                result = github_apply.apply_approved(op_id, dry_run=False)
                if result.get("ok"):
                    return f"{msg}\n✅ Auto-applied to GitHub."
                return f"{msg}\nApply failed: {_safe_err(result.get('error') or result)}"
            except Exception as e:
                return f"{msg}\nApply error: {_safe_err(e)}"
        return msg
    if action == "reject":
        ok, msg, _ = set_status(op_id, "rejected")
        return msg
    if action == "apply":
        from agents import github_apply

        try:
            result = github_apply.apply_approved(op_id)
            if isinstance(result, dict) and result.get("ok"):
                return (
                    f"✅ Applied {op_id} to GitHub.\n"
                    f"{result.get('commit_msg') or result.get('msg') or ''}"
                ).strip()
            err = result.get("error") if isinstance(result, dict) else result
            return f"Apply failed: {_safe_err(err)}"
        except Exception as e:
            return f"Apply error: {_safe_err(e)}"
    return "Unknown command"


def _reaction_emojis(reactions: Any) -> set:
    out = set()
    for r in reactions or []:
        if isinstance(r, dict):
            if r.get("type") == "emoji" and r.get("emoji"):
                out.add(r["emoji"])
            # custom emoji / paid — ignore
    return out


def handle_reaction(upd: Dict[str, Any]) -> Optional[str]:
    """
    Heart → approve, thumbs-down → reject.
    Returns a short reply text for the chat, or None.
    """
    mr = upd.get("message_reaction") or {}
    chat = mr.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    allowed = _allowed_chats()
    if not allowed or chat_id not in allowed:
        return None

    message_id = mr.get("message_id")
    if message_id is None:
        return None

    new_e = _reaction_emojis(mr.get("new_reaction"))
    old_e = _reaction_emojis(mr.get("old_reaction"))
    added = new_e - old_e
    if not added:
        # still honor current new set (user toggled)
        added = new_e
    if not added:
        return None

    msg_map = _load_msg_map()
    op_id = msg_map.get(f"{chat_id}:{message_id}")
    if not op_id:
        # fallback: try any key ending with :message_id
        for k, v in msg_map.items():
            if k.endswith(f":{message_id}"):
                op_id = v
                break
    if not op_id:
        return None

    if added & APPROVE_EMOJIS:
        ok, msg, item = set_status(op_id, "approved")
        name = (item or {}).get("name") or op_id
        from agents.confidence import should_auto_apply_on_heart

        if should_auto_apply_on_heart():
            try:
                from agents import github_apply

                result = github_apply.apply_approved(op_id, dry_run=False)
                if result.get("ok"):
                    return (
                        f"✅❤ Applied {op_id} ({name}) to GitHub.\n"
                        f"{result.get('msg') or result.get('commit_msg') or ''}".strip()
                    )
                return (
                    f"✅ Approved {op_id} ({name}), but apply failed: "
                    f"{_safe_err(result.get('error') or result)}. Try `apply {op_id}`."
                )
            except Exception as e:
                return (
                    f"✅ Approved {op_id} ({name}), apply error: {_safe_err(e)}. "
                    f"Try `apply {op_id}`."
                )
        return f"✅ Approved {op_id} ({name}) via ❤. Reply `apply {op_id}` to push GitHub."
    if added & REJECT_EMOJIS:
        ok, msg, item = set_status(op_id, "rejected")
        name = (item or {}).get("name") or op_id
        return f"🚫 Rejected {op_id} ({name}) via 👎."
    return None


def poll_once(timeout: int = 25) -> Dict[str, Any]:
    """One long-poll cycle — messages + reactions."""
    offset = _load_offset()
    params: Dict[str, Any] = {
        "timeout": timeout,
        "allowed_updates": ["message", "message_reaction"],
    }
    if offset is not None:
        params["offset"] = offset
    updates = api("getUpdates", **params) or []
    handled = 0
    for upd in updates:
        upd_id = upd.get("update_id", 0)
        _save_offset(upd_id + 1)

        if "message_reaction" in upd:
            reply = handle_reaction(upd)
            if reply:
                chat_id = str((upd.get("message_reaction") or {}).get("chat", {}).get("id", ""))
                try:
                    if chat_id:
                        send_message(chat_id, reply)
                except Exception as e:
                    print(f"Telegram reaction reply error: {e}")
                handled += 1
            continue

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
    print("Telegram poll started (❤ approve · 👎 reject)…")
    while end is None or time.time() < end:
        try:
            result = poll_once(timeout=25)
            if result.get("handled"):
                print(result)
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(5)
