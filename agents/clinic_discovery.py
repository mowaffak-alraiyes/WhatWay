"""
Clinic discovery agent — finds / ingests new clinics from Google Forms/Sheets.

Fillable forms (linked in clinic detail UI):
  - Community report: https://docs.google.com/forms/d/e/1FAIpQLScZUiy0MirYBsbjPC50_AyZ2I6BdnjmnYKCQOcUUGximAmNVw/viewform
  - Clinic staff update: https://docs.google.com/forms/d/e/1FAIpQLSdHExiaL4A0-gbHOF2swbdlLQQIUPf0WINCaZrJsQDrliuUwA/viewform

To ingest *responses* into proposed_clinics.json:
  1. Link each form to a Google Sheet
  2. Sheet → File → Share → Publish to web → CSV
  3. Set GOOGLE_FORMS_CSV_URL to that CSV URL (or pass --url)
  4. Run: python -m agents.clinic_discovery --fetch

No scraping of private sheets — public CSV export only.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "proposed_clinics.json"

# Expected form column aliases (case-insensitive)
COLUMN_ALIASES = {
    "name": ["clinic name", "name", "organization", "org", "facility"],
    "address": ["address", "street", "location"],
    "zip": ["zip", "zip code", "zipcode", "postal"],
    "phone": ["phone", "telephone", "tel", "contact number"],
    "website": ["website", "url", "web", "link"],
    "services": ["services", "service", "what do you offer", "care types"],
    "languages": ["languages", "language", "languages spoken"],
    "hours": ["hours", "hours of operation", "schedule"],
    "notes": ["notes", "comments", "additional info", "description"],
}


def _norm_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip().lower())


def _map_row(headers: List[str], row: List[str]) -> Dict[str, str]:
    header_map = {_norm_header(h): i for i, h in enumerate(headers)}
    out: Dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            idx = header_map.get(alias)
            if idx is not None and idx < len(row) and row[idx].strip():
                out[field] = row[idx].strip()
                break
    return out


def fetch_csv(url: str) -> List[Dict[str, str]]:
    if url.startswith("file://"):
        text = Path(url.replace("file://", "")).read_text(encoding="utf-8-sig")
    elif Path(url).exists():
        text = Path(url).read_text(encoding="utf-8-sig")
    else:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    headers, data = rows[0], rows[1:]
    return [_map_row(headers, row) for row in data if any(c.strip() for c in row)]


def load_existing_names() -> set:
    path = ROOT / "data" / "healthcare.json"
    names = set()
    if path.exists():
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
            for item in items:
                n = (item.get("name") or "").strip().lower()
                if n:
                    names.add(n)
        except Exception:
            pass
    return names


def propose_new_clinics(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    existing = load_existing_names()
    proposals = []
    for row in rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        if name.lower() in existing:
            continue
        zip_code = row.get("zip") or ""
        if not zip_code and row.get("address"):
            m = re.search(r"\b(60\d{3})\b", row["address"])
            if m:
                zip_code = m.group(1)
        proposals.append(
            {
                "name": name,
                "address": row.get("address", ""),
                "zip": zip_code,
                "phone": row.get("phone", ""),
                "website": row.get("website", ""),
                "services": [s.strip() for s in re.split(r"[;,]", row.get("services", "")) if s.strip()],
                "languages": [s.strip() for s in re.split(r"[;,]", row.get("languages", "")) if s.strip()],
                "hours": row.get("hours", ""),
                "notes": row.get("notes", ""),
                "status": "proposed",
                "source": "google_forms_csv",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return proposals


def run_discovery(csv_url: Optional[str] = None) -> Dict[str, Any]:
    url = csv_url or os.environ.get("GOOGLE_FORMS_CSV_URL") or os.environ.get("GOOGLE_SHEETS_CSV_URL")
    if not url:
        return {
            "ok": False,
            "error": "Set GOOGLE_FORMS_CSV_URL (Forms/Sheets → File → Share → Publish to CSV).",
            "proposals": [],
        }

    rows = fetch_csv(url)
    proposals = propose_new_clinics(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "ok": True,
        "fetched_rows": len(rows),
        "new_proposals": len(proposals),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": url,
        "proposals": proposals,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Discover new clinics from Google Forms CSV")
    parser.add_argument("--fetch", action="store_true", help="Fetch CSV and write proposals")
    parser.add_argument("--url", default=None, help="Override GOOGLE_FORMS_CSV_URL")
    args = parser.parse_args()
    if args.fetch:
        result = run_discovery(args.url)
        print(json.dumps({k: result[k] for k in result if k != "proposals"}, indent=2))
        print(f"Wrote {result.get('new_proposals', 0)} proposals → {OUT_PATH}")
        if not result.get("ok"):
            raise SystemExit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
