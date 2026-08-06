"""Human-readable service / specialty labels (never snake_case in UI or GitHub drafts)."""

from __future__ import annotations

import re
from typing import Iterable, List, Union

# Canonical display names for common keys we write from HRSA / scrapers
_SERVICE_ALIASES = {
    "primary_care": "Primary Care",
    "primary care": "Primary Care",
    "dental": "Dental",
    "mental_health": "Mental Health",
    "mental health": "Mental Health",
    "behavioral_health": "Behavioral Health",
    "womens_health": "Women's Health",
    "women's health": "Women's Health",
    "pediatrics": "Pediatrics",
    "pediatric": "Pediatrics",
    "urgent_care": "Urgent Care",
    "hiv_sti": "HIV / STI",
    "family_planning": "Family Planning",
    "substance_use": "Substance Use",
    "sliding_fee": "Sliding Fee",
    "sliding_scale": "Sliding Scale",
}


def humanize_service_label(raw: str) -> str:
    """Turn primary_care / Primary_care → Primary Care; leave prose alone."""
    s = (raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"^(🏥\s*)?Services?:\s*", "", s, flags=re.I).strip()
    key = re.sub(r"\s+", " ", s.replace("_", " ").strip().lower())
    # Single token / short snake-ish label
    if key in _SERVICE_ALIASES:
        return _SERVICE_ALIASES[key]
    compact = key.replace(" ", "_")
    if compact in _SERVICE_ALIASES:
        return _SERVICE_ALIASES[compact]
    # primary_care style still present
    if "_" in (raw or "") or (s.islower() and " " not in s and len(s) < 40):
        return s.replace("_", " ").title()
    return s


def humanize_services(value: Union[str, Iterable[str], None]) -> str:
    """Join one or many service values into a GitHub/UI-friendly Services: line body."""
    if value is None:
        return ""
    if isinstance(value, str):
        parts = re.split(r"[,;|•·]+", value)
    else:
        parts = list(value)
    out: List[str] = []
    seen = set()
    for p in parts:
        label = humanize_service_label(str(p))
        if not label:
            continue
        k = label.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(label)
    return ", ".join(out)
