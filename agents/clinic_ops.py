"""
Clinic Ops agent — David local-ai-agents patterns, WhatWay-shaped.

- Controlled tools only (agents/tools.py)
- Local Ollama for short proposal summaries (optional)
- Stage to data/pending_ops.json — never auto-push
- Telegram poll for your approve/reject/apply
- After approve + apply → commit to refugee-resources GitHub

Chicago-first; set CITY_SCOPE=national for US-wide.

Examples:
  CITY_SCOPE=national python -m agents.clinic_ops --run
  python -m agents.clinic_ops --notify
  python -m agents.clinic_ops --poll          # long-poll Telegram
  python -m agents.clinic_ops --approve op_ab12
  python -m agents.clinic_ops --apply op_ab12
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from agents import clinic_discovery as discovery
from agents import tools as ops_tools

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass

PENDING_PATH = DATA / "pending_ops.json"


def _github_files() -> Dict[str, str]:
    from agents.geo_scope import category_files_for_state, raw_github_url

    return {k: raw_github_url(v) for k, v in category_files_for_state().items()}


GITHUB_FILES = _github_files()

CITY_SCOPE = os.environ.get("CITY_SCOPE", "chicago").lower()  # chicago | national
CHICAGO_ZIP = re.compile(r"\b60\d{3}\b")
US_ZIP = re.compile(r"\b\d{5}(?:-\d{4})?\b")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _op_id() -> str:
    return "op_" + secrets.token_hex(3)


def _load_pending() -> Dict[str, Any]:
    if PENDING_PATH.exists():
        try:
            return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"updated_at": None, "items": [], "scope": CITY_SCOPE}


def _save_pending(payload: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _now()
    payload["scope"] = CITY_SCOPE
    PENDING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def zip_in_scope(zip_code: str, address: str = "") -> bool:
    text = f"{zip_code} {address}"
    if CITY_SCOPE == "national":
        return bool(US_ZIP.search(text)) or bool(address.strip())
    return bool(CHICAGO_ZIP.search(text))


def fetch_github_index() -> Dict[str, Dict[str, str]]:
    """
    name_lower → {name, phone, website, file_key}
    Used to detect duplicates vs field updates.
    """
    index: Dict[str, Dict[str, str]] = {}
    for key, url in GITHUB_FILES.items():
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            text = r.text
        except Exception as e:
            print(f"GitHub fetch warning ({key}): {e}")
            continue
        current: Optional[Dict[str, str]] = None
        for line in text.splitlines():
            m = re.match(r"^\s*\d+\.\s+(.+)$", line)
            if m:
                if current and current.get("name"):
                    index[current["name"].lower()] = current
                current = {"name": m.group(1).strip(), "phone": "", "website": "", "file_key": key}
                continue
            if not current:
                continue
            s = line.strip()
            if s.startswith("📞") or s.lower().startswith("phone"):
                current["phone"] = re.sub(r"^(📞|phone)\s*:?\s*", "", s, flags=re.I).strip()
            elif s.startswith("🌐") or s.startswith("http"):
                current["website"] = re.sub(r"^🌐\s*", "", s).strip()
        if current and current.get("name"):
            index[current["name"].lower()] = current
    return index


def ollama_summarize(item: Dict[str, Any]) -> str:
    """Optional local LLM blurb for Telegram (skip if Ollama down)."""
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL") or "llama3"
    prompt = (
        "In one short sentence for a human approver, summarize this clinic change. "
        "Mention if NEW or UPDATE and the key fields.\n"
        + json.dumps(
            {
                "status": item.get("status"),
                "name": item.get("name"),
                "address": item.get("address"),
                "phone": item.get("phone"),
                "website": item.get("website"),
                "field_updates": item.get("field_updates"),
            },
            ensure_ascii=False,
        )
    )
    try:
        native = base.replace("/v1", "") + "/api/chat"
        body = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": "You help approve clinic directory edits. Be brief."},
                {"role": "user", "content": prompt},
            ],
        }
        r = requests.post(native, json=body, timeout=20)
        r.raise_for_status()
        data = r.json()
        return (data.get("message") or {}).get("content") or ""
    except Exception:
        return ""


def verify_proposal(item: Dict[str, Any], github_index: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """New clinics or field updates — human still approves via Telegram."""
    checks = []
    name = (item.get("name") or "").strip()
    address = item.get("address") or ""
    zip_code = item.get("zip") or ""
    phone = item.get("phone") or ""
    website = item.get("website") or ""
    existing = github_index.get(name.lower()) if name else None

    if not name:
        checks.append({"ok": False, "code": "missing_name", "detail": "Name required"})
        return {
            **item,
            "verification": {"passed": False, "checks": checks, "verified_at": _now()},
            "status": "rejected_auto",
            "region": CITY_SCOPE,
        }

    field_updates: Dict[str, str] = {}
    if existing:
        # Treat as update if phone/website/hours differ
        if phone and phone != (existing.get("phone") or ""):
            field_updates["phone"] = phone
        if website:
            clean_web = website if website.startswith("http") else f"https://{website}"
            if clean_web.rstrip("/") != (existing.get("website") or "").rstrip("/"):
                field_updates["website"] = clean_web
        if item.get("hours"):
            field_updates["hours"] = str(item["hours"])
        if not field_updates:
            checks.append({"ok": False, "code": "duplicate", "detail": "Already listed; no field changes"})
            status = "rejected_auto"
        else:
            checks.append({"ok": True, "code": "update", "detail": f"Update fields: {list(field_updates)}"})
            status = "proposed_update"
            item["category"] = existing.get("file_key") or "healthcare"
    else:
        checks.append({"ok": True, "code": "unique_name", "detail": "Not in GitHub lists"})
        status = "proposed"
        item.setdefault("category", "healthcare")

    if not zip_in_scope(zip_code, address):
        checks.append(
            {"ok": False, "code": "out_of_scope", "detail": f"Outside scope ({CITY_SCOPE})"}
        )
        if status != "proposed_update":
            status = "rejected_auto"
    else:
        checks.append({"ok": True, "code": "in_scope", "detail": f"Within {CITY_SCOPE}"})

    if phone and re.search(r"\d{3}.*\d{3}.*\d{4}", phone):
        checks.append({"ok": True, "code": "phone_format", "detail": "Phone looks valid"})
    elif phone:
        checks.append({"ok": False, "code": "phone_format", "detail": "Phone format unclear"})

    if website:
        try:
            p = urlparse(website if "://" in website else f"https://{website}")
            checks.append(
                {"ok": bool(p.netloc), "code": "website", "detail": "URL parseable" if p.netloc else "Bad URL"}
            )
        except Exception:
            checks.append({"ok": False, "code": "website", "detail": "Bad URL"})

    hard_fail = status == "rejected_auto"
    from agents.geo_scope import infer_state

    out = {
        **item,
        "field_updates": field_updates or None,
        "verification": {"passed": not hard_fail, "checks": checks, "verified_at": _now()},
        "status": status,
        "region": CITY_SCOPE,
        "state": infer_state(address, zip_code=zip_code, explicit=str(item.get("state") or "")),
    }
    return out


def format_github_block(item: Dict[str, Any], next_id: int = 999) -> str:
    from core.labels import humanize_services

    services = item.get("services") or []
    services_s = humanize_services(services)
    langs = item.get("languages") or []
    langs_s = ", ".join(langs) if isinstance(langs, list) else str(langs)
    return ops_tools.draft_github_block(
        name=item.get("name") or "Unknown",
        address=item.get("address") or "",
        phone=item.get("phone") or "",
        website=item.get("website") or "",
        services=services_s,
        languages=langs_s,
        hours=str(item.get("hours") or ""),
        next_id=next_id,
    )


def run_ops(csv_url: Optional[str] = None) -> Dict[str, Any]:
    url = (
        csv_url
        or os.environ.get("GOOGLE_FORMS_CSV_URL")
        or os.environ.get("GOOGLE_SHEETS_CSV_URL")
    )
    if not url:
        sample = DATA / "sample_clinic_form.csv"
        if sample.exists():
            url = str(sample)
        else:
            return {"ok": False, "error": "Set GOOGLE_FORMS_CSV_URL or pass --url"}

    rows = discovery.fetch_csv(url)
    raw_proposals = discovery.propose_new_clinics(rows)
    github_index = fetch_github_index()

    verified = [verify_proposal(p, github_index) for p in raw_proposals]
    pending = _load_pending()
    existing_ops = {(i.get("name") or "").lower() + "|" + (i.get("status") or "") for i in pending.get("items", [])}

    added = 0
    for item in verified:
        if item.get("status") not in ("proposed", "proposed_update"):
            continue
        key = (item.get("name") or "").lower() + "|" + item["status"]
        if key in existing_ops:
            continue
        item["op_id"] = _op_id()
        item["github_draft"] = format_github_block(item)
        item["source_csv"] = url
        item["needs_approval"] = True
        item["llm_summary"] = ollama_summarize(item)
        pending.setdefault("items", []).append(item)
        existing_ops.add(key)
        added += 1

    _save_pending(pending)

    discovery_payload = {
        "ok": True,
        "fetched_rows": len(rows),
        "new_proposals": len([v for v in verified if v.get("status") in ("proposed", "proposed_update")]),
        "updated_at": _now(),
        "source_url": url,
        "scope": CITY_SCOPE,
        "proposals": [v for v in verified if v.get("status") in ("proposed", "proposed_update")],
    }
    (DATA / "proposed_clinics.json").write_text(
        json.dumps(discovery_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "ok": True,
        "scope": CITY_SCOPE,
        "fetched_rows": len(rows),
        "verified": len(verified),
        "added_to_pending": added,
        "pending_path": str(PENDING_PATH),
        "awaiting_telegram": [
            {"op_id": i["op_id"], "name": i.get("name"), "status": i.get("status")}
            for i in pending.get("items", [])
            if i.get("status") in ("proposed", "proposed_update")
        ],
    }


def list_pending(status: str = "proposed") -> List[Dict[str, Any]]:
    pending = _load_pending()
    if status == "all":
        return list(pending.get("items", []))
    if status in ("proposed", "open"):
        return [
            i
            for i in pending.get("items", [])
            if i.get("status") in ("proposed", "proposed_update")
        ]
    return [i for i in pending.get("items", []) if i.get("status") == status]


def approve(op_or_name: str) -> Dict[str, Any]:
    pending = _load_pending()
    found = None
    key = op_or_name.strip().lower()
    for item in pending.get("items", []):
        if item.get("op_id", "").lower() == key or (item.get("name") or "").lower() == key:
            item["status"] = "approved"
            item["approved_at"] = _now()
            found = item
            break
    if not found:
        return {"ok": False, "error": f"Not found: {op_or_name}"}
    _save_pending(pending)
    return {
        "ok": True,
        "op_id": found.get("op_id"),
        "name": found.get("name"),
        "message": "Approved. Telegram `apply {op_id}` or CLI --apply to push GitHub.",
        "github_draft": found.get("github_draft"),
        "field_updates": found.get("field_updates"),
    }


def main():
    parser = argparse.ArgumentParser(description="Clinic Ops + Telegram approval (WhatWay)")
    parser.add_argument("--run", action="store_true", help="Fetch CSV, verify, stage pending")
    parser.add_argument(
        "--discover-new",
        action="store_true",
        help="Stage NEW education/resettlement orgs (Ollama verify) for Telegram approve",
    )
    parser.add_argument(
        "--category",
        action="append",
        choices=["healthcare", "education", "resettlement"],
        help="With --discover-new: limit categories (repeatable)",
    )
    parser.add_argument("--url", default=None, help="CSV URL or local path")
    parser.add_argument("--list", action="store_true", help="List open proposals")
    parser.add_argument("--approve", metavar="OP_OR_NAME", help="Approve by op_id or name")
    parser.add_argument("--notify", action="store_true", help="Send open proposals to Telegram")
    parser.add_argument("--poll", action="store_true", help="Poll Telegram for approve/reject/apply")
    parser.add_argument("--poll-seconds", type=int, default=3600, help="Poll duration (0=forever)")
    parser.add_argument("--apply", metavar="OP_ID", help="Push an approved op to GitHub")
    parser.add_argument(
        "--apply-all",
        action="store_true",
        help="Push ALL approved ops to GitHub (drain the queue after Telegram approves)",
    )
    parser.add_argument("--dry-run", action="store_true", help="With --apply/--apply-all: preview only")
    parser.add_argument("--scope", default=None, help="chicago | national")
    parser.add_argument("--limit", type=int, default=20, help="With --discover-new: max new orgs to stage")
    args = parser.parse_args()

    global CITY_SCOPE
    if args.scope:
        CITY_SCOPE = args.scope.lower()

    if args.discover_new:
        from agents import discover_new

        result = discover_new.scan(
            args.category or ["education", "resettlement"],
            limit=args.limit,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.run:
        result = run_ops(args.url)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise SystemExit(1)
    elif args.list:
        items = list_pending("open")
        print(json.dumps({"count": len(items), "items": items}, indent=2, ensure_ascii=False))
    elif args.approve:
        print(json.dumps(approve(args.approve), indent=2, ensure_ascii=False))
    elif args.notify:
        from agents import telegram_bridge

        items = list_pending("open")
        print(json.dumps(telegram_bridge.notify_pending(items), indent=2))
    elif args.poll:
        from agents import telegram_bridge

        telegram_bridge.poll_loop(seconds=args.poll_seconds)
    elif args.apply_all:
        from agents import github_apply

        result = github_apply.apply_all_approved(dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result.get("ok"):
            raise SystemExit(1)
    elif args.apply:
        from agents import github_apply

        print(json.dumps(github_apply.apply_approved(args.apply, dry_run=args.dry_run), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
