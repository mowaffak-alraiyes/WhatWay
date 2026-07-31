"""
Aidr API — WhatsApp webhooks + health/search endpoints.

Deploy on Railway / Render / Fly (not Streamlit Cloud).
Streamlit UI stays separate; both share core.pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from project root when running locally
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from api.whatsapp import router as whatsapp_router
from core.pipeline import search_resources

app = FastAPI(
    title="Aidr API",
    description="Refugee resource search + WhatsApp webhooks",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router)


@app.get("/")
def root():
    return {
        "service": "Aidr API",
        "docs": "/docs",
        "whatsapp": {
            "twilio": "/webhooks/whatsapp/twilio",
            "meta": "/webhooks/whatsapp/meta",
            "simulate": "/webhooks/whatsapp/simulate",
            "health": "/webhooks/whatsapp/health",
        },
    }


@app.get("/health")
def health():
    ollama_ok = False
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5) as r:
            ollama_ok = r.status == 200
    except Exception:
        pass
    return {
        "ok": True,
        "ollama": ollama_ok,
        "neon": bool(os.environ.get("NEON_PASSWORDLESS_TOKEN") or os.environ.get("DATABASE_URL")),
    }


@app.post("/search")
def search(payload: dict):
    """Same path as chat/WhatsApp — useful for demos and future Vercel frontend."""
    return search_resources(
        query=payload.get("query", ""),
        category=payload.get("category"),
        language=payload.get("language", "en"),
        limit=int(payload.get("limit", 3)),
        use_llm=bool(payload.get("use_llm", True)),
    )
