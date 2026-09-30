"""
Chicago helpers (SAMS + sheet/HRSA notes).

Prefer the full scanner:
  python -m agents.enrich_contacts --scan --hrsa data/hrsa_il.csv

This module keeps one-off Chicago staging helpers.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import core.env  # noqa: F401, maps legacy AIDR_* vars onto WHATWAY_*
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PENDING_PATH = DATA / "pending_ops.json"

# User-provided Chicago sheet (must be shared as "Anyone with the link can view")
DEFAULT_SHEET_ID = os.environ.get(
    "WHATWAY_CONTACTS_SHEET_ID",
    "1VwLC6tBZIIIw6ePhR90_C8cT_frZDq8uythPjhLkoP0",
)
SHEET_CSV_TMPL = (
    "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
)

HRSA_DOWNLOADS = "https://data.hrsa.gov/data/download?hmpgtitle=hmpg-hrsa-data"

SAMS_OFFICIAL = {
    "name": "SAMS Free Specialty Clinic (Willowbrook, IL)",
    "field_updates": {
        "address": "16W631 91st St, Door #12, Willowbrook, IL 60527 (inside Anne M. Jeans Elementary School)",
        "phone": "(630) 474-4724",
        "website": "https://samscommunityclinic.org/",
        "email": "samsfreeclinic@gmail.com",
        "hours": "Open 2 days/month (1st Saturday & 3rd Sunday of the month)",
        "services": "Services: Adult primary care; Cardiology; Obstetrics/Gynecology; Endocrinology; Pulmonology",
    },
    "source": "https://samscommunityclinic.org/",
    "category": "healthcare",
}


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
    return {"updated_at": None, "items": [], "scope": "chicago"}


def _save_pending(payload: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _now()
    payload["scope"] = "chicago"
    PENDING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def stage_update(
    name: str,
    field_updates: Dict[str, str],
    *,
    source: str,
    category: str = "healthcare",
    notes: str = "",
) -> Dict[str, Any]:
    pending = _load_pending()
    name_n = _norm_name(name)
    # Dedupe open proposals for same clinic
    for it in pending.get("items") or []:
        if (
            _norm_name(it.get("name") or "") == name_n
            and it.get("status") in ("proposed_update", "pending", "approved")
            and it.get("field_updates")
        ):
            it["field_updates"] = {**(it.get("field_updates") or {}), **field_updates}
            it["source"] = source
            it["notes"] = notes or it.get("notes")
            it["updated_at"] = _now()
            _save_pending(pending)
            return it

    item = {
        "op_id": _op_id(),
        "kind": "proposed_update",
        "status": "proposed_update",
        "category": category,
        "name": name,
        "field_updates": field_updates,
        "source": source,
        "notes": notes,
        "city_scope": "chicago",
        "created_at": _now(),
    }
    pending.setdefault("items", []).append(item)
    _save_pending(pending)
    return item


def stage_sams() -> Dict[str, Any]:
    """Stage SAMS update from samscommunityclinic.org."""
    return stage_update(
        SAMS_OFFICIAL["name"],
        SAMS_OFFICIAL["field_updates"],
        source=SAMS_OFFICIAL["source"],
        category=SAMS_OFFICIAL["category"],
        notes="Official SAMS Community Clinic site  -  address moved from Kingery Hwy to 91st St school location.",
    )


def fetch_sheet_rows(sheet_id: str = DEFAULT_SHEET_ID, gid: str = "0") -> List[Dict[str, str]]:
    url = SHEET_CSV_TMPL.format(sheet_id=quote(sheet_id, safe=""), gid=gid)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    text = r.text
    if "<html" in text[:200].lower():
        raise RuntimeError(
            "Sheet export returned HTML (likely not publicly shared). "
            "Share the sheet as 'Anyone with the link can view', or download CSV and use --sheet-file."
        )
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _pick(row: Dict[str, str], *keys: str) -> str:
    lower = {re.sub(r"\s+", " ", k.strip().lower()): v for k, v in row.items() if k}
    for key in keys:
        for k, v in lower.items():
            if key in k and (v or "").strip():
                return (v or "").strip()
    return ""


def stage_from_sheet_rows(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Map flexible sheet columns → proposed updates (Chicago ZIPs preferred)."""
    staged: List[Dict[str, Any]] = []
    for row in rows:
        name = _pick(row, "name", "clinic", "organization", "org")
        if not name:
            continue
        phone = _pick(row, "phone", "tel", "telephone")
        website = _pick(row, "website", "url", "web", "site")
        address = _pick(row, "address", "street", "location")
        email = _pick(row, "email", "e-mail")
        zip_code = _pick(row, "zip", "zipcode", "postal")
        blob = f"{address} {zip_code}"
        # Chicago-first: keep IL 60xxx or explicit Chicago / Willowbrook / suburbs with 60
        if zip_code and not re.search(r"\b60\d{3}\b", zip_code):
            if "chicago" not in blob.lower() and "illinois" not in blob.lower() and "il" not in blob.lower():
                continue
        updates = {}
        if phone:
            updates["phone"] = phone
        if website:
            updates["website"] = website
        if address:
            updates["address"] = address
        if email:
            updates["email"] = email
        if not updates:
            continue
        staged.append(
            stage_update(
                name,
                updates,
                source=f"google_sheet:{DEFAULT_SHEET_ID}",
                notes="Staged from Chicago contacts sheet",
            )
        )
    return staged


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage Chicago clinic contact enrichments")
    ap.add_argument("--sams", action="store_true", help="Stage SAMS from samscommunityclinic.org")
    ap.add_argument("--sheet", action="store_true", help="Pull public Google Sheet CSV and stage rows")
    ap.add_argument("--sheet-file", type=str, help="Local CSV path instead of live sheet export")
    ap.add_argument("--sheet-id", type=str, default=DEFAULT_SHEET_ID)
    ap.add_argument("--gid", type=str, default="0")
    ap.add_argument(
        "--hrsa-note",
        action="store_true",
        help="Print how to use HRSA downloads for Chicago FQHC phone/website fills",
    )
    args = ap.parse_args()

    if args.hrsa_note or not any([args.sams, args.sheet, args.sheet_file]):
        print(
            "HRSA Chicago enrichment path\n"
            f"  1. Open {HRSA_DOWNLOADS}\n"
            "  2. Download Health Center Service Delivery Sites (or Health Centers) CSV\n"
            "  3. Filter State=IL / City≈Chicago (ZIPs 60xxx)\n"
            "  4. Match org names to resources/healthcare.txt; stage phone/website via --sheet-file\n"
            "  5. Approve in Telegram → python -m agents.clinic_ops --apply <op_id>\n"
        )
        if not any([args.sams, args.sheet, args.sheet_file]):
            # default: stage SAMS so one command does something useful
            args.sams = True

    if args.sams:
        item = stage_sams()
        print(json.dumps({"staged": "sams", "op_id": item["op_id"], "updates": item["field_updates"]}, indent=2))

    if args.sheet_file:
        path = Path(args.sheet_file)
        rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        out = stage_from_sheet_rows(rows)
        print(json.dumps({"staged": len(out), "op_ids": [o["op_id"] for o in out]}, indent=2))
    elif args.sheet:
        try:
            rows = fetch_sheet_rows(args.sheet_id, args.gid)
            out = stage_from_sheet_rows(rows)
            print(json.dumps({"staged": len(out), "op_ids": [o["op_id"] for o in out]}, indent=2))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e), "hint": "Use --sheet-file with a downloaded CSV"}, indent=2))


if __name__ == "__main__":
    main()
