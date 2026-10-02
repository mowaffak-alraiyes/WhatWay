"""Shared private-Ollama connection settings.

Secrets are read at request time so Streamlit, FastAPI, and tests can share one
configuration without copying credentials or logging them.
"""

from __future__ import annotations

import os
from typing import Dict


def openai_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")


def native_base_url() -> str:
    base = openai_base_url()
    return base[:-3] if base.endswith("/v1") else base


def bearer_token() -> str:
    return os.environ.get("OLLAMA_AUTH_TOKEN", "").strip()


def access_headers() -> Dict[str, str]:
    """Headers for a private origin protected by Cloudflare Access."""
    headers: Dict[str, str] = {}
    client_id = os.environ.get("OLLAMA_CF_ACCESS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("OLLAMA_CF_ACCESS_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        headers["CF-Access-Client-Id"] = client_id
        headers["CF-Access-Client-Secret"] = client_secret
    return headers


def native_headers(*, json_content: bool = False) -> Dict[str, str]:
    headers = access_headers()
    if json_content:
        headers["Content-Type"] = "application/json"
    token = bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
