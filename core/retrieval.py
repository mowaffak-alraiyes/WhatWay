"""Grounded hybrid retrieval for WhatWay resource records.

The canonical records stay in structured JSON. Retrieval may rank those
records, but it never generates or edits contact details. Semantic ranking is
optional and uses Ollama's native embedding endpoint when it is available.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core import ollama


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_EMBEDDING_CACHE: Dict[Tuple[str, str], List[float]] = {}
_CACHE_LOCK = threading.Lock()
_LOADED_CACHE_MODELS = set()


@dataclass(frozen=True)
class RetrievalResult:
    items: List[Dict[str, Any]]
    mode: str
    source_ids: List[str]
    semantic_available: bool


def _tokens(value: str) -> List[str]:
    return [token.lower() for token in _TOKEN_RE.findall(value or "") if len(token) > 1]


def resource_text(item: Dict[str, Any]) -> str:
    """Return only fields useful for semantic service matching.

    Phone numbers and free-form verification notes are intentionally excluded.
    """
    values: List[str] = [
        str(item.get("name") or ""),
        str(item.get("services_text") or ""),
    ]
    for key in ("services", "subcategories", "languages", "availability_badges"):
        value = item.get(key) or []
        if isinstance(value, list):
            values.extend(str(part).replace("_", " ") for part in value)
        else:
            values.append(str(value))
    return " | ".join(value for value in values if value).strip()


def _resource_id(item: Dict[str, Any], index: int) -> str:
    value = str(item.get("id") or "").strip()
    if value:
        state = str(item.get("state") or "XX").strip().upper()
        return f"{state}:{value}"
    stable = f"{item.get('name', '')}|{item.get('address', '')}|{index}"
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def hard_filter(
    items: Iterable[Dict[str, Any]],
    *,
    state: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Apply metadata constraints before lexical or semantic scoring."""
    wanted_state = (state or "").strip().upper()
    wanted_language = (language or "").strip().lower()
    if wanted_language in {"", "auto", "en", "english"}:
        wanted_language = ""

    filtered: List[Dict[str, Any]] = []
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name or name.startswith("#"):
            continue
        if item.get("active") is False or item.get("status") in {"closed", "inactive"}:
            continue
        if wanted_state and str(item.get("state") or "").upper() != wanted_state:
            continue
        if wanted_language:
            languages = {str(v).strip().lower() for v in (item.get("languages") or [])}
            if wanted_language not in languages:
                continue
        filtered.append(item)
    return filtered


def _bm25_scores(items: Sequence[Dict[str, Any]], query: str) -> List[float]:
    query_tokens = _tokens(query)
    if not items or not query_tokens:
        return [0.0] * len(items)

    docs = [_tokens(resource_text(item)) for item in items]
    average_length = sum(len(doc) for doc in docs) / max(1, len(docs))
    frequencies: Dict[str, int] = {}
    for term in set(query_tokens):
        frequencies[term] = sum(1 for doc in docs if term in doc)

    scores: List[float] = []
    k1, b = 1.5, 0.75
    for item, doc in zip(items, docs):
        score = 0.0
        length_norm = 1 - b + b * len(doc) / max(1.0, average_length)
        for term in query_tokens:
            tf = doc.count(term)
            if not tf:
                continue
            df = frequencies.get(term, 0)
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * length_norm)
        name_tokens = set(_tokens(str(item.get("name") or "")))
        score += sum(1.25 for term in query_tokens if term in name_tokens)
        scores.append(score)
    return scores


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _ollama_embed(texts: Sequence[str]) -> Optional[List[List[float]]]:
    if not texts:
        return []
    model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    payload = json.dumps({"model": model, "input": list(texts)}).encode("utf-8")
    request = urllib.request.Request(
        f"{ollama.native_base_url()}/api/embed",
        data=payload,
        headers=ollama.native_headers(json_content=True),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8.0) as response:
            body = json.loads(response.read().decode("utf-8"))
        embeddings = body.get("embeddings")
        if isinstance(embeddings, list) and len(embeddings) == len(texts):
            return embeddings
    except Exception:
        return None
    return None


def _embedding_cache_path() -> Path:
    configured = os.environ.get("WHATWAY_EMBEDDING_CACHE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parent.parent / ".cache" / "ollama_embeddings.json"


def _load_disk_cache(model: str) -> None:
    """Load public resource embeddings once per model and process."""
    with _CACHE_LOCK:
        if model in _LOADED_CACHE_MODELS:
            return
        _LOADED_CACHE_MODELS.add(model)

    path = _embedding_cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or payload.get("model") != model:
            return
        vectors = payload.get("vectors") or {}
        with _CACHE_LOCK:
            for digest, vector in vectors.items():
                if isinstance(vector, list) and vector:
                    _EMBEDDING_CACHE[(model, digest)] = [float(value) for value in vector]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return


def _save_disk_cache(model: str) -> None:
    """Atomically persist embeddings; query text and chat history are absent."""
    path = _embedding_cache_path()
    with _CACHE_LOCK:
        vectors = {
            digest: vector
            for (cached_model, digest), vector in _EMBEDDING_CACHE.items()
            if cached_model == model
        }
    if not vectors:
        return
    payload = {"version": 1, "model": model, "vectors": vectors}
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(payload, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _semantic_scores(items: Sequence[Dict[str, Any]], query: str) -> Optional[List[float]]:
    model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    _load_disk_cache(model)
    documents = [resource_text(item) for item in items]
    keys = [(model, hashlib.sha256(text.encode("utf-8")).hexdigest()) for text in documents]
    with _CACHE_LOCK:
        missing_indexes = [i for i, key in enumerate(keys) if key not in _EMBEDDING_CACHE]

    added_vectors = False
    for start in range(0, len(missing_indexes), 64):
        indexes = missing_indexes[start : start + 64]
        vectors = _ollama_embed([documents[i] for i in indexes])
        if vectors is None:
            return None
        with _CACHE_LOCK:
            for index, vector in zip(indexes, vectors):
                _EMBEDDING_CACHE[keys[index]] = vector
                added_vectors = True

    if added_vectors:
        _save_disk_cache(model)

    query_vectors = _ollama_embed([query])
    if not query_vectors:
        return None
    query_vector = query_vectors[0]
    with _CACHE_LOCK:
        return [_cosine(query_vector, _EMBEDDING_CACHE[key]) for key in keys]


def retrieve(
    items: Sequence[Dict[str, Any]],
    query: str,
    *,
    limit: int = 3,
    state: Optional[str] = None,
    language: Optional[str] = None,
    zip_code: Optional[str] = None,
    service: Optional[str] = None,
    use_semantic: bool = True,
) -> RetrievalResult:
    """Retrieve grounded records with hard filters and hybrid ranking."""
    candidates = hard_filter(items, state=state, language=language)
    expanded_query = " ".join(part for part in (query, service or "") if part).strip()
    lexical = _bm25_scores(candidates, expanded_query)
    semantic = _semantic_scores(candidates, expanded_query) if use_semantic and candidates else None

    ranked: List[Tuple[float, int, Dict[str, Any]]] = []
    for index, (item, lexical_score) in enumerate(zip(candidates, lexical)):
        score = lexical_score
        if semantic is not None:
            # Lexical evidence remains primary; embeddings improve recall for
            # conversational wording and synonyms.
            score += max(0.0, semantic[index]) * 2.5

        item_zip = str(item.get("zip_code") or item.get("zip") or "")[:5]
        if zip_code and item_zip == str(zip_code)[:5]:
            score += 4.0
        elif zip_code:
            score -= 0.5

        if service:
            service_tokens = _tokens(service)
            item_tokens = set(_tokens(resource_text(item)))
            if any(token in item_tokens for token in service_tokens):
                score += 2.0

        if score > 0 or not expanded_query:
            ranked.append((score, index, item))

    ranked.sort(key=lambda value: (-value[0], value[1]))
    selected = [item for _, _, item in ranked[: max(1, limit)]]
    source_ids = [_resource_id(item, index) for index, item in enumerate(selected)]
    return RetrievalResult(
        items=selected,
        mode="hybrid" if semantic is not None else "lexical",
        source_ids=source_ids,
        semantic_available=semantic is not None,
    )
