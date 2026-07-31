"""
Fuzzy spelling helpers for Aidr search prompts.

Replaces a hard-coded misspelling map: corrections come from RapidFuzz
against a domain vocabulary (services, neighborhoods, common ask words).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

from rapidfuzz import fuzz, process

# Seed vocabulary — expanded at runtime with synonyms / neighborhoods / dataset labels
_DOMAIN_SEED = {
    # healthcare
    "dental", "dentist", "pediatric", "pediatrics", "therapy", "therapist",
    "counseling", "clinic", "clinics", "hospital", "primary", "care",
    "mental", "health", "women", "womens", "prenatal", "pharmacy",
    "urgent", "medicaid", "medicare", "free", "walk-in", "walkin",
    "cardiology", "endocrinology", "pulmonology", "obstetrics", "gynecology",
    # education
    "english", "esl", "school", "class", "classes", "ged", "citizenship",
    "literacy", "tutoring", "workforce", "training",
    # legal / shelter
    "legal", "lawyer", "attorney", "immigration", "asylum", "daca",
    "shelter", "housing", "homeless", "emergency", "food", "pantry",
    # common ask words
    "help", "need", "find", "near", "close", "open", "today", "now",
    "chicago", "illinois", "arabic", "spanish", "urdu", "polish",
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


@lru_cache(maxsize=1)
def build_vocabulary(
    extra: Tuple[str, ...] = (),
) -> Tuple[str, ...]:
    """Build / cache the correction vocabulary."""
    vocab = set(_DOMAIN_SEED)
    vocab.update(w.lower() for w in extra if w and len(w) > 1)

    try:
        import neighborhood_mapping as nm

        for name in nm.get_all_neighborhoods():
            vocab.update(_tokenize(name))
    except Exception:
        pass

    # Drop tiny / non-alpha noise
    cleaned = {w for w in vocab if re.fullmatch(r"[a-z][a-z'-]{1,}", w)}
    return tuple(sorted(cleaned))


def refresh_vocabulary_from_items(
    items: Optional[Iterable[dict]] = None,
    extra: Tuple[str, ...] = (),
) -> None:
    """Fold live dataset service / subcategory labels into the vocab cache."""
    extras: List[str] = list(extra)
    if items:
        for it in list(items)[:300]:
            for s in it.get("services") or []:
                extras.extend(_tokenize(str(s).replace("_", " ")))
            for s in it.get("subcategories") or []:
                extras.extend(_tokenize(str(s)))
            extras.extend(_tokenize(str(it.get("name") or "")))
    build_vocabulary.cache_clear()
    build_vocabulary(tuple(sorted(set(extras))))


def suggest_word(word: str, vocab: Optional[Tuple[str, ...]] = None, *, min_score: int = 78) -> Optional[str]:
    """Return best vocab match for a single token, or None if OK / no good match."""
    w = (word or "").lower().strip(".,!?;:")
    if not w or w.isdigit() or len(w) < 3:
        return None
    # Keep ZIPs / codes alone
    if re.fullmatch(r"\d{4,5}", w):
        return None

    vocab = vocab or build_vocabulary()
    if w in vocab:
        return None

    # Short tokens need a softer cutoff (halp→help is ratio 75)
    cutoff = 72 if len(w) <= 5 else min_score
    matches = process.extract(
        w,
        vocab,
        scorer=fuzz.ratio,
        score_cutoff=min(cutoff, 65),
        limit=8,
    )
    if not matches:
        return None

    # Prefer common ask-words on near-ties; then closer length
    ask_boost = {
        "help", "need", "find", "near", "close", "open", "school", "class",
        "clinic", "dental", "legal", "english", "therapy",
    }

    def rank(m):
        suggestion, score, _ = m
        length_pen = abs(len(suggestion) - len(w))
        boost = 3 if suggestion in ask_boost else 0
        # Prefer shared character positions (nead→need beats nead→near)
        pos = sum(1 for a, b in zip(w, suggestion) if a == b)
        end = 1 if suggestion[-1:] == w[-1:] else 0
        return (score + boost, pos + end, -length_pen)

    matches = sorted(matches, key=rank, reverse=True)
    suggestion, score, _ = matches[0]
    if suggestion == w:
        return None
    # Accept if strong ratio OR short edit (e.g. klas→class ~66)
    if score >= cutoff or (len(w) <= 6 and score >= 65 and abs(len(suggestion) - len(w)) <= 2):
        return suggestion
    return None


def check_query(query: str, *, min_score: int = 78) -> Dict[str, object]:
    """
    Spell-check a search prompt.

    Returns:
      {
        "original": str,
        "corrected": str,
        "fixes": [(bad, good), ...],
        "flagged": bool,
      }
    """
    original = query or ""
    tokens = re.findall(r"[A-Za-z']+|\d+|[^\w\s]+|\s+", original)
    vocab = build_vocabulary()
    fixes: List[Tuple[str, str]] = []
    out_parts: List[str] = []

    for tok in tokens:
        if re.fullmatch(r"[A-Za-z']+", tok):
            low = tok.lower()
            suggestion = suggest_word(low, vocab, min_score=min_score)
            if suggestion:
                # Preserve capitalization style of the original token
                if tok.isupper():
                    repl = suggestion.upper()
                elif tok[0].isupper():
                    repl = suggestion.capitalize()
                else:
                    repl = suggestion
                fixes.append((tok, repl))
                out_parts.append(repl)
            else:
                out_parts.append(tok)
        else:
            out_parts.append(tok)

    corrected = "".join(out_parts).strip()
    # Dedupe fixes by lowercased bad word
    seen = set()
    uniq_fixes: List[Tuple[str, str]] = []
    for bad, good in fixes:
        key = bad.lower()
        if key not in seen:
            seen.add(key)
            uniq_fixes.append((bad, good))

    return {
        "original": original,
        "corrected": corrected if uniq_fixes else original,
        "fixes": uniq_fixes,
        "flagged": bool(uniq_fixes),
    }
