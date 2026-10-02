"""
Shared search + reply pipeline for Streamlit chat and WhatsApp.

No Streamlit UI side-effects  -  safe to import from FastAPI.
Loads local JSON first (fast/offline), then optionally refreshes from GitHub.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import i18n
from core.retrieval import retrieve

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

CATEGORY_FILES = {
    "Healthcare": "healthcare.json",
    "Education": "education.json",
    "Resettlement / Legal / Shelter": "resettlement_legal_shelter.json",
}

SERVICE_HINTS = {
    "Healthcare": {
        "dental": ["dental", "dentist", "teeth", "tooth", "oral"],
        "pediatric": ["pediatric", "children", "child", "kid", "kids", "youth"],
        "mental health": ["mental", "counseling", "therapy", "psychiatry"],
        "women's health": ["women", "obgyn", "prenatal", "midwifery"],
        "immunization": ["immunization", "vaccination", "shots", "vaccine"],
    },
    "Education": {
        "ESL": ["esl", "english", "language", "tutoring"],
        "GED/Citizenship": ["ged", "citizenship", "literacy"],
        "Youth Programs": ["after-school", "after school", "youth"],
    },
    "Resettlement / Legal / Shelter": {
        "Legal Services": ["legal", "law", "attorney", "immigration", "asylum", "daca"],
        "Shelter/Housing": ["shelter", "housing", "homeless"],
        "Benefits Assistance": ["benefits", "snap", "medicaid"],
        "Resettlement Services": ["resettlement", "case management", "employment"],
    },
}


def load_items(category: str) -> List[Dict[str, Any]]:
    """Load and de-duplicate all local state datasets for a category."""
    fname = CATEGORY_FILES.get(category)
    if not fname:
        return []

    stem = Path(fname).stem
    paths = [DATA_DIR / fname, *sorted(DATA_DIR.glob(f"{stem}_[A-Z][A-Z].json"))]
    records: List[Dict[str, Any]] = []
    seen = set()
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or "").strip()
                    if not name or name.startswith("#"):
                        continue
                    key = (
                        str(item.get("state") or "").upper(),
                        str(item.get("id") or ""),
                        name.lower(),
                        str(item.get("address") or "").lower(),
                    )
                    if key not in seen:
                        seen.add(key)
                        records.append(item)
        except Exception:
            pass
    if records:
        return records

    # Fallback: data_loader (may hit GitHub; Streamlit cache if available)
    try:
        import data_loader

        return data_loader.load_category_data(category) or []
    except Exception:
        return []


def detect_zip(query: str) -> Optional[str]:
    m = re.search(r"\b(60\d{3})\b", query or "")
    if m:
        return m.group(1)
    try:
        import neighborhood_mapping

        _, zips = neighborhood_mapping.expand_neighborhood_query(query)
        if zips:
            return zips[0]
    except Exception:
        pass
    return None


def detect_service(query: str, category: str) -> Optional[str]:
    q = (query or "").lower()
    for service, words in SERVICE_HINTS.get(category, {}).items():
        if any(w in q for w in words):
            return service
    return None


def detect_category(query: str, default: str = "Healthcare") -> str:
    q = (query or "").lower()
    if any(w in q for w in ["esl", "english class", "ged", "school", "tutoring"]):
        return "Education"
    if any(w in q for w in ["legal", "asylum", "immigration", "shelter", "housing", "snap"]):
        return "Resettlement / Legal / Shelter"
    if any(w in q for w in ["dental", "clinic", "doctor", "health", "pediatric", "mental"]):
        return "Healthcare"
    return default


def detect_state(query: str) -> Optional[str]:
    q = f" {(query or '').lower()} "
    if " illinois " in q or re.search(r"\bIL\b", query or ""):
        return "IL"
    if " indiana " in q or re.search(r"\bIN\b", query or ""):
        return "IN"
    zip_code = detect_zip(query)
    if zip_code and zip_code.startswith("60"):
        return "IL"
    if re.search(r"\b(?:46|47)\d{3}\b", query or ""):
        return "IN"
    return None


def detect_language_filter(query: str) -> Optional[str]:
    q = (query or "").lower()
    aliases = {
        "arabic": ("arabic", "العربية"),
        "spanish": ("spanish", "español"),
        "french": ("french", "français"),
        "polish": ("polish", "polski"),
        "mandarin": ("mandarin", "chinese", "中文"),
        "urdu": ("urdu", "اردو"),
        "hindi": ("hindi", "हिन्दी"),
        "ukrainian": ("ukrainian", "українська"),
        "swahili": ("swahili", "kiswahili"),
    }
    for canonical, names in aliases.items():
        if any(name in q for name in names):
            return canonical
    return None


def _blob(item: Dict[str, Any]) -> str:
    parts = [
        item.get("name") or "",
        item.get("address") or "",
        item.get("zip") or item.get("zip_code") or "",
        item.get("services_text") or "",
        item.get("search_blob") or item.get("_search_blob") or "",
    ]
    services = item.get("services") or []
    if isinstance(services, list):
        parts.append(" ".join(str(s) for s in services))
    else:
        parts.append(str(services))
    langs = item.get("languages") or []
    if isinstance(langs, list):
        parts.append(" ".join(str(s) for s in langs))
    else:
        parts.append(str(langs))
    return " ".join(parts).lower()


def _item_zip(item: Dict[str, Any]) -> str:
    z = item.get("zip") or item.get("zip_code") or ""
    if z:
        return str(z)
    m = re.search(r"\b(60\d{3})\b", item.get("address") or "")
    return m.group(1) if m else ""


def rank_items(
    items: List[Dict[str, Any]],
    query: str,
    zip_code: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    q = (query or "").lower().strip()
    terms = [t for t in re.split(r"\W+", q) if len(t) >= 3]
    scored: List[Tuple[float, Dict[str, Any]]] = []

    for item in items:
        blob = _blob(item)
        iz = _item_zip(item)

        if zip_code and iz and iz != zip_code:
            # Soft filter: keep but penalize non-matching ZIPs
            zip_penalty = 2.0
        elif zip_code and iz == zip_code:
            zip_penalty = 0.0
        else:
            zip_penalty = 0.5 if zip_code else 0.0

        score = 0.0
        if service:
            svc = str(item.get("services") or "").lower() + " " + blob
            if service.lower() in svc or any(
                w in svc for w in SERVICE_HINTS.get("Healthcare", {}).get(service, [service.lower()])
            ):
                score += 5.0
            else:
                # Prefer service match when user asked for one
                score -= 1.0

        for term in terms:
            if term in blob:
                score += 1.5
            if term in (item.get("name") or "").lower():
                score += 2.0

        if zip_code and iz == zip_code:
            score += 4.0

        score -= zip_penalty
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def format_resource_line(item: Dict[str, Any], idx: int, lang: str = "en") -> str:
    name = item.get("name") or "Resource"
    address = item.get("address") or ""
    phone = item.get("phone") or ""
    website = item.get("website") or ""
    call_label = i18n.t("call", lang)

    lines = [f"*{idx}. {name}*"]
    if address:
        # Data sometimes already includes a pin emoji
        addr = address.lstrip("📍 ").strip()
        lines.append(f"📍 {addr}")
    if phone:
        lines.append(f"📞 {call_label}: {phone}")
    if website:
        lines.append(f"🔗 {website}")
    source_id = item.get("source_id")
    verified = item.get("last_verified")
    if source_id and verified:
        lines.append(f"✓ {verified} · {source_id}")
    elif source_id:
        lines.append(f"Source: {source_id}")
    return "\n".join(lines)


def format_whatsapp_reply(
    results: List[Dict[str, Any]],
    lang: str = "en",
    intro: Optional[str] = None,
) -> str:
    if not results:
        return i18n.t("no_results", lang)

    parts = [intro or i18n.t("found_n", lang, n=len(results)), ""]
    for i, item in enumerate(results, 1):
        parts.append(format_resource_line(item, i, lang))
        parts.append("")
    parts.append(i18n.t("more_hint", lang))
    return "\n".join(parts).strip()


def search_resources(
    query: str,
    category: Optional[str] = None,
    language: str = "en",
    limit: int = 3,
    use_llm: bool = True,
    state: Optional[str] = None,
    language_filter: Optional[str] = None,
    use_semantic: bool = True,
) -> Dict[str, Any]:
    """
    End-to-end search used by chat + WhatsApp.

    Returns:
      {
        category, query, zip, service, language,
        results: [...],
        text: whatsapp-ready reply,
        intro: short intro,
        llm_used: bool
      }
    """
    lang = i18n.normalize_lang(language)
    category = category or detect_category(query)
    zip_code = detect_zip(query)
    service = detect_service(query, category)
    state = state or detect_state(query)
    language_filter = language_filter or detect_language_filter(query)

    llm_used = False
    intro = None
    understood = query

    if use_llm:
        try:
            import llm_service

            if llm_service.is_llm_available():
                intent = llm_service.detect_intent(query)
                llm_used = bool(intent.get("llm_available", True))
                if intent.get("category") in CATEGORY_FILES:
                    category = intent["category"]
                if intent.get("zip_code"):
                    zip_code = intent["zip_code"]
                if intent.get("service_type"):
                    service = intent["service_type"]
                if intent.get("language_filter"):
                    language_filter = str(intent["language_filter"]).lower()
                if language in (None, "", "auto", "Auto-detect") and intent.get("user_language"):
                    lang = i18n.normalize_lang(intent["user_language"])
                understood = intent.get("understood_need") or query
        except Exception:
            llm_used = False

    items = load_items(category)
    retrieval = retrieve(
        items,
        query,
        limit=limit,
        state=state,
        language=language_filter,
        zip_code=zip_code,
        service=service,
        use_semantic=use_semantic,
    )
    results = retrieval.items

    # Prefer LLM intro when available
    if use_llm and results:
        try:
            import llm_service

            if llm_service.is_llm_available():
                intro = llm_service.generate_response(query, results, category)
                if lang != "en":
                    intro = llm_service.translate_response_if_needed(intro, i18n.CODE_TO_NAME.get(lang, lang), include_english=False)
                llm_used = True
        except Exception:
            pass

    if not intro:
        intro = i18n.t("found_n", lang, n=len(results)) if results else i18n.t("no_results", lang)

    text = format_whatsapp_reply(results, lang=lang, intro=intro)

    return {
        "category": category,
        "query": query,
        "understood": understood,
        "zip": zip_code,
        "service": service,
        "language": lang,
        "results": results,
        "intro": intro,
        "text": text,
        "llm_used": llm_used,
        "retrieval": {
            "mode": retrieval.mode,
            "semantic_available": retrieval.semantic_available,
            "source_ids": retrieval.source_ids,
        },
    }
