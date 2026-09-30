"""Shared core used by Streamlit chat and WhatsApp API."""

from . import env as env  # noqa: F401 — maps legacy AIDR_* vars onto WHATWAY_*

from .pipeline import search_resources, format_whatsapp_reply

__all__ = ["env", "search_resources", "format_whatsapp_reply"]
