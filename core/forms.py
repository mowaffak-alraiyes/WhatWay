"""
Google Forms used for clinic corrections / staff updates.

Fillable form URLs (public):
- Community report: incorrect hours, closed, languages, etc.
- Clinic staff update request

The discovery agent still needs a published CSV of *responses*
(GOOGLE_FORMS_CSV_URL) — Forms view links cannot be scraped for answers.
"""

from __future__ import annotations

import os
from typing import Optional

FORM_COMMUNITY_REPORT = (
    "https://docs.google.com/forms/d/e/1FAIpQLScZUiy0MirYBsbjPC50_AyZ2I6BdnjmnYKCQOcUUGximAmNVw/viewform"
)
FORM_CLINIC_UPDATE = (
    "https://docs.google.com/forms/d/e/1FAIpQLSdHExiaL4A0-gbHOF2swbdlLQQIUPf0WINCaZrJsQDrliuUwA/viewform"
)


def _secret(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st

        return st.secrets.get(key, default) or default
    except Exception:
        return default


def community_report_url(clinic_name: Optional[str] = None) -> str:
    base = _secret("GOOGLE_FORM_COMMUNITY_REPORT", FORM_COMMUNITY_REPORT)
    # Google prefill needs entry IDs; append name as a hint in the hash for now
    if clinic_name:
        from urllib.parse import quote

        return f"{base}?usp=pp_url#{quote(clinic_name)}"
    return base


def clinic_update_url(clinic_name: Optional[str] = None) -> str:
    base = _secret("GOOGLE_FORM_CLINIC_UPDATE", FORM_CLINIC_UPDATE)
    if clinic_name:
        from urllib.parse import quote

        return f"{base}?usp=pp_url#{quote(clinic_name)}"
    return base
