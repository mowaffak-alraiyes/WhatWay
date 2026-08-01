"""
Light privacy helpers for IRB-friendly logging (no raw phones/IPs in logs).
"""

from __future__ import annotations

import hashlib
import re


_PHONE_TAIL = re.compile(r"(\d{4})\s*$")


def hash_identifier(value: str, *, length: int = 16) -> str:
    """SHA-256 hex digest (truncated) for logs / pseudonymous IDs."""
    raw = (value or "").strip().encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return digest[: max(8, length)]


def mask_phone(value: str) -> str:
    """Keep last 4 digits only, e.g. whatsapp:+1***1113 or ***1113."""
    s = (value or "").strip()
    if not s:
        return "(empty)"
    m = _PHONE_TAIL.search(re.sub(r"\D", "", s))
    tail = m.group(1) if m else "????"
    if s.lower().startswith("whatsapp:"):
        return f"whatsapp:+***{tail}"
    if s.startswith("+"):
        return f"+***{tail}"
    return f"***{tail}"


def truncate_user_text(text: str, max_len: int = 2000) -> str:
    """Cap inbound chat length to avoid abuse / oversized payloads."""
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[:max_len]
