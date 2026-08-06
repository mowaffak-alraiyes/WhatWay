"""
Confidence tiers for Aidr ops auto-apply / Telegram ask.

  high  + known source → auto-apply to GitHub (no ❤ needed)
  medium              → ask for ❤ (then auto-apply on heart)
  low / reddit-only   → ask for ❤, or skip if AIDR_SKIP_LOW_CONFIDENCE=1

Env:
  AIDR_AUTO_APPLY_HIGH=1          # default on — auto-apply high+known
  AIDR_AUTO_APPLY_ON_HEART=1      # default on — ❤ → approve + apply
  AIDR_SKIP_LOW_CONFIDENCE=0      # set 1 to never notify low/reddit
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple


KNOWN_SOURCES = (
    "enrich_contacts",
    "hrsa",
    "hrsa_xlsx",
    "hrsa_finder",
    "sheet",
    "sibling_listing",
    "parent_org",
    "parent_org_map",
    "duckduckgo_html",
    "discover_new_seeds",
    "google_forms_csv",
    "sams",
    "haymarket",
    "lawndale",
    "achn",
    "howardbrown",
    "https://",  # org-site scrape URLs often stored as source
    "http://",
)


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def source_is_known(item: Dict[str, Any]) -> bool:
    src = (item.get("source") or "").lower()
    if not src:
        return False
    if "reddit" in src:
        return False
    for k in KNOWN_SOURCES:
        if k.lower() in src:
            return True
    # bare org domain as source from enrich
    if "." in src and " " not in src.strip():
        return True
    return False


def confidence_of(item: Dict[str, Any]) -> str:
    v = item.get("verification") or {}
    c = (v.get("confidence") or item.get("confidence") or "").lower().strip()
    if c in ("high", "medium", "low", "unchecked"):
        if c == "unchecked":
            return "medium"
        return c
    src = (item.get("source") or "").lower()
    # HRSA Find-a-HC / Excel imports are treated as high when no Ollama score
    if "hrsa" in src:
        return "high"
    # Infer from source if Ollama didn't run
    if source_is_known(item):
        return "medium"
    if "reddit" in src:
        return "low"
    return "low"


def tier_action(item: Dict[str, Any]) -> str:
    """
    Return one of: auto_apply | ask | skip
    """
    conf = confidence_of(item)
    known = source_is_known(item)
    src = (item.get("source") or "").lower()
    reddit = "reddit" in src

    if conf == "high" and known and _env_flag("AIDR_AUTO_APPLY_HIGH", True):
        return "auto_apply"
    if conf == "low" or reddit:
        if _env_flag("AIDR_SKIP_LOW_CONFIDENCE", False):
            return "skip"
        return "ask"
    # medium / unchecked / high-but-unknown
    return "ask"


def should_auto_apply_on_heart() -> bool:
    return _env_flag("AIDR_AUTO_APPLY_ON_HEART", True)


def tier_label(item: Dict[str, Any]) -> str:
    conf = confidence_of(item)
    known = "known" if source_is_known(item) else "unverified"
    action = tier_action(item)
    return f"{conf}/{known} → {action}"


def drain_auto_apply(
    items: Optional[List[Dict[str, Any]]] = None,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Approve + apply every open op whose tier is high+known.
    If items is None, scans all open pending_ops.
    Returns counts + github_apply result. Safe no-op when none qualify.
    """
    from pathlib import Path
    import json
    import time

    root = Path(__file__).resolve().parent.parent
    pending_path = root / "data" / "pending_ops.json"

    def _load() -> Dict[str, Any]:
        if pending_path.exists():
            try:
                return json.loads(pending_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"items": []}

    def _save(payload: Dict[str, Any]) -> None:
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    pending = _load()
    open_statuses = ("proposed", "proposed_update")
    if items is None:
        candidates = [i for i in pending.get("items") or [] if i.get("status") in open_statuses]
    else:
        # refresh from disk by op_id so we mutate the live pending records
        want = {i.get("op_id") for i in items if i.get("op_id")}
        candidates = [
            i
            for i in pending.get("items") or []
            if i.get("op_id") in want and i.get("status") in open_statuses
        ]

    auto_items = [i for i in candidates if tier_action(i) == "auto_apply"]
    ask_items = [i for i in candidates if tier_action(i) == "ask"]
    skipped = [i for i in candidates if tier_action(i) == "skip"]

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "auto_apply": len(auto_items),
            "ask": len(ask_items),
            "skip": len(skipped),
            "sample": [
                {"op_id": i.get("op_id"), "name": i.get("name"), "source": i.get("source")}
                for i in auto_items[:15]
            ],
        }

    if not auto_items:
        return {
            "ok": True,
            "auto_apply": 0,
            "ask": len(ask_items),
            "skip": len(skipped),
            "apply": None,
        }

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    auto_ids = set()
    for item in auto_items:
        item["status"] = "approved"
        item["approved_at"] = now
        item["approved_via"] = "auto_high_known"
        auto_ids.add(item.get("op_id"))
    _save(pending)

    from agents import github_apply

    apply_result = github_apply.apply_all_approved(dry_run=False)
    return {
        "ok": bool(apply_result.get("ok")),
        "auto_apply": len(auto_ids),
        "ask": len(ask_items),
        "skip": len(skipped),
        "op_ids": sorted(x for x in auto_ids if x),
        "apply": {
            "total": apply_result.get("total"),
            "succeeded": apply_result.get("succeeded"),
            "failed": apply_result.get("failed"),
            "error": apply_result.get("error"),
        },
    }
