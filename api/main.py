"""
WhatWay API: WhatsApp webhooks + health/search endpoints.

Deploy on Railway / Render / Fly (not Streamlit Cloud).
Streamlit UI stays separate; both share core.pipeline.
"""

from __future__ import annotations

import os
import core.env  # noqa: F401, maps legacy AIDR_* vars onto WHATWAY_*
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import requests

# Load .env from project root when running locally
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from api.rate_limit import allow as rate_allow, per_minute_limit
from api.schemas import SearchRequest, SearchResponse
from api.whatsapp import router as whatsapp_router
from core.pipeline import search_resources
from core import ollama
from core.privacy import hash_identifier, truncate_user_text

app = FastAPI(
    title="WhatWay API",
    description="Refugee resource search + WhatsApp webhooks",
    version="0.1.0",
)


def _cors_origins() -> list:
    raw = (os.environ.get("WHATWAY_CORS_ORIGINS") or "").strip()
    if not raw:
        # Safe local defaults (Streamlit). Override via WHATWAY_CORS_ORIGINS for deploy.
        return [
            "http://localhost:8501",
            "http://127.0.0.1:8501",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(whatsapp_router)


@app.get("/")
def root():
    return {
        "service": "WhatWay API",
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
    ollama_models = []
    try:
        r = requests.get(
            f"{ollama.native_base_url()}/api/tags",
            headers=ollama.native_headers(),
            timeout=1.5,
        )
        ollama_ok = r.status_code == 200
        if ollama_ok:
            ollama_models = [
                str(model.get("name") or "")
                for model in (r.json().get("models") or [])
                if model.get("name")
            ]
    except Exception:
        pass
    chat_model = os.environ.get("OLLAMA_MODEL", "llama3")
    embedding_model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

    def installed(name: str) -> bool:
        wanted = name.split(":", 1)[0]
        return any(model.split(":", 1)[0] == wanted for model in ollama_models)

    return {
        "ok": True,
        "ollama": ollama_ok,
        "rag": {
            "chat_model": chat_model,
            "chat_model_ready": ollama_ok and installed(chat_model),
            "embedding_model": embedding_model,
            "embedding_model_ready": ollama_ok and installed(embedding_model),
        },
        "neon": bool(os.environ.get("NEON_PASSWORDLESS_TOKEN") or os.environ.get("DATABASE_URL")),
    }


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, request: Request):
    """Same path as chat/WhatsApp: useful for demos and future Vercel frontend."""
    client = request.client.host if request.client else "unknown"
    ok, retry = rate_allow(
        hash_identifier(client),
        per_minute=per_minute_limit("WHATWAY_RATE_LIMIT_SEARCH_PER_MIN", 30),
        scope="search",
    )
    if not ok:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Retry in {retry}s.")

    query = truncate_user_text(payload.query, 2000)
    return search_resources(
        query=query,
        category=payload.category,
        language=payload.language,
        limit=payload.limit,
        use_llm=payload.use_llm,
        state=payload.state,
        language_filter=payload.language_filter,
        use_semantic=payload.use_semantic,
    )
