"""Shared core used by Streamlit chat and WhatsApp API."""

from .pipeline import search_resources, format_whatsapp_reply

__all__ = ["search_resources", "format_whatsapp_reply"]
