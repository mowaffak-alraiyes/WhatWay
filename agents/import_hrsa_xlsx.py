"""
Import HRSA Health Centers + HAB (Ryan White HIV/AIDS) Excel into healthcare.txt.

Rules:
  - Never remove existing listing fields (languages, hours, services, etc.)
  - Add new clinics that aren't already listed
  - If a clinic already exists (name + ZIP match), only fill blank phone/website
    and/or add Ryan White context  -  do not wipe other lines
  - HAB rows always get clear Ryan White HIV/AIDS Program labeling

Examples:
  python -m agents.import_hrsa_xlsx \\
    --health-centers "~/Downloads/Health Centers July 31 2026.xlsx" \\
    --hab "~/Downloads/HAB July 31 2026.xlsx" \\
    --states IL --push
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import requests
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("RESOURCES_GITHUB_REPO", "mowaffak-alraiyes/refugee-resources")
HEALTHCARE_REL = "resources/healthcare.txt"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/{HEALTHCARE_REL}"

REVIEWED = "07/2026"
HC_NOTE = f"HRSA Health Center Program  -  Last reviewed {REVIEWED}"
HAB_NOTE = f"Ryan White HIV/AIDS Program (HRSA HAB) provider  -  Last reviewed {REVIEWED}"
HAB_SERVICES = (
    "Ryan White HIV/AIDS Program care and support services "
    "(HIV medical care, case management, and related HAB-funded supports)"
)
HC_SERVICES = "Primary Care"


@dataclass
class Block:
    number: int
    name: str
    lines: List[str] = field(default_factory=list)  # full block lines including title

    @property
    def address(self) -> str:
        for line in self.lines[1:]:
            s = line.strip()
            if not s or s.startswith(("📞", "🌐", "📧", "📝", "🗣", "🏥", "⏰", "#")):
                continue
            if "," in s or re.search(r"\d{5}", s):
                return s
        return ""

    @property
    def phone(self) -> str:
        for line in self.lines:
            s = line.strip()
            if s.startswith("📞") or s.lower().startswith("phone"):
                return re.sub(r"^(📞|phone)\s*:?\s*", "", s, flags=re.I).strip()
        return ""

    @property
    def website(self) -> str:
        for line in self.lines:
            s = line.strip()
            if s.startswith("🌐"):
                return re.sub(r"^🌐\s*", "", s).strip()
            if s.startswith("http"):
                return s
        return ""

    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"

    def zip5(self) -> str:
        m = re.search(r"\b(\d{5})\b", self.address)
        return m.group(1) if m else ""


def _norm_name(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _digits(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return d


def _fmt_phone(phone: str) -> str:
    d = _digits(phone)
    if len(d) == 10:
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    return (phone or "").strip()


def _fmt_website(url: str) -> str:
    u = (url or "").strip()
    if not u or u.lower() in ("nan", "none", "n/a"):
        return ""
    if not u.startswith("http"):
        u = "https://" + u
    return u


def _zip5(val) -> str:
    m = re.search(r"\b(\d{5})\b", str(val or ""))
    return m.group(1) if m else ""


def _clean_cell(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "nat"):
        return ""
    return s


def parse_blocks(text: str) -> List[Block]:
    parts = re.split(r"(?m)(?=^\s*\d+\.\s+)", text)
    blocks: List[Block] = []
    for part in parts:
        if not part.strip():
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.+)$", part.splitlines()[0] if part.splitlines() else "")
        if not m:
            continue
        lines = [ln.rstrip() for ln in part.splitlines() if ln.strip() or True]
        # keep internal blank lines lightly trimmed
        while lines and not lines[-1].strip():
            lines.pop()
        blocks.append(Block(number=int(m.group(1)), name=m.group(2).strip(), lines=lines))
    return blocks


def blocks_to_text(blocks: List[Block]) -> str:
    # Renumber sequentially
    out = []
    for i, b in enumerate(blocks, start=1):
        if b.lines:
            b.lines[0] = re.sub(r"^\s*\d+\.", f"{i}.", b.lines[0])
            b.number = i
        out.append(b.text())
    return "\n".join(out).rstrip() + "\n"


def find_match(blocks: List[Block], name: str, zip_code: str, address: str = "", raw_name: str = "") -> Optional[Block]:
    n = _norm_name(name)
    raw_n = _norm_name(raw_name) if raw_name else ""
    z = _zip5(zip_code)
    best: Optional[Tuple[float, Block]] = None
    for b in blocks:
        score = float(fuzz.token_set_ratio(n, _norm_name(b.name)))
        if raw_n:
            score = max(score, float(fuzz.token_set_ratio(raw_n, _norm_name(b.name))))
        # Street-only names: match on address ZIP + street tokens
        if address and b.address:
            score = max(score, 0.5 * fuzz.token_set_ratio(address.lower(), b.address.lower()))
        bz = b.zip5()
        if z and bz and z == bz:
            score += 12
        elif address and b.address:
            score += 0.05 * fuzz.partial_ratio(address.lower(), b.address.lower())
        if score >= 88 and (best is None or score > best[0]):
            best = (score, b)
    return best[1] if best else None


def _set_or_fill_line(lines: List[str], prefix_check, new_line: str, *, only_if_blank: bool) -> None:
    """Insert or replace a typed line without removing unrelated content."""
    idx = None
    for i, line in enumerate(lines):
        if prefix_check(line.strip()):
            idx = i
            break
    if idx is None:
        # Insert after address / notes cluster  -  before languages/services if present
        insert_at = len(lines)
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith(("🗣", "🏥", "⏰")):
                insert_at = i
                break
        lines.insert(insert_at, new_line)
        return
    existing = lines[idx].strip()
    if only_if_blank:
        # phone/website already present → keep
        return
    lines[idx] = new_line


def _ensure_note(lines: List[str], note: str) -> None:
    """Add or augment 📝 note; never delete existing note text."""
    note_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("📝"):
            note_idx = i
            break
    if note_idx is None:
        # after address
        insert_at = 1 if len(lines) > 1 else len(lines)
        for i, line in enumerate(lines[1:], start=1):
            s = line.strip()
            if s and not s.startswith(("📞", "🌐", "📧", "📝", "🗣", "🏥", "⏰")):
                insert_at = i + 1
                break
        lines.insert(insert_at, f"📝 {note}")
        return
    existing = lines[note_idx]
    body = re.sub(r"^📝\s*", "", existing).strip()
    if "ryan white" in note.lower() and "ryan white" not in body.lower():
        lines[note_idx] = f"📝 {note}; {body}" if body else f"📝 {note}"
    elif note.lower() not in body.lower() and "hrsa" in note.lower() and "hrsa" not in body.lower():
        lines[note_idx] = f"📝 {body}; {note}" if body else f"📝 {note}"


def _ensure_services_mention(lines: List[str], mention: str, *, ryan_white: bool = False) -> None:
    svc_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("🏥") or line.strip().lower().startswith("services"):
            svc_idx = i
            break
    if svc_idx is None:
        lines.append(f"🏥 Services: {mention}")
        return
    body = lines[svc_idx]
    if ryan_white and "ryan white" not in body.lower():
        # Prepend Ryan White context without removing existing services
        rest = re.sub(r"^🏥\s*", "", body).strip()
        rest = re.sub(r"^Services:\s*", "", rest, flags=re.I).strip()
        if rest:
            lines[svc_idx] = f"🏥 Services: Ryan White HIV/AIDS Program; {rest}"
        else:
            lines[svc_idx] = f"🏥 Services: {mention}"


def apply_update(
    block: Block,
    *,
    phone: str = "",
    website: str = "",
    note: str = "",
    ryan_white: bool = False,
) -> List[str]:
    """Mutate block in place; return list of change labels."""
    changes = []
    lines = block.lines
    if phone and not _digits(block.phone):
        _set_or_fill_line(
            lines,
            lambda s: s.startswith("📞") or s.lower().startswith("phone"),
            f"📞 {_fmt_phone(phone)}",
            only_if_blank=True,
        )
        changes.append("phone")
    if website and not block.website:
        _set_or_fill_line(
            lines,
            lambda s: s.startswith("🌐") or s.startswith("http"),
            f"🌐 {_fmt_website(website)}",
            only_if_blank=True,
        )
        changes.append("website")
    if note:
        before = "\n".join(lines)
        _ensure_note(lines, note)
        if "\n".join(lines) != before:
            changes.append("note")
    if ryan_white:
        before = "\n".join(lines)
        _ensure_services_mention(lines, HAB_SERVICES, ryan_white=True)
        if "\n".join(lines) != before:
            changes.append("ryan_white_services")
    return changes


def new_block(
    number: int,
    name: str,
    address: str,
    *,
    phone: str = "",
    website: str = "",
    note: str = "",
    services: str = "",
) -> Block:
    lines = [f"{number}. {name}", address]
    if note:
        lines.append(f"📝 {note}")
    if website:
        lines.append(f"🌐 {_fmt_website(website)}")
    if phone:
        lines.append(f"📞 {_fmt_phone(phone)}")
    if services:
        from core.labels import humanize_services

        lines.append(f"🏥 Services: {humanize_services(services)}")
    return Block(number=number, name=name, lines=lines)


def _looks_like_street_name(name: str) -> bool:
    """HRSA sometimes puts the street in 'Health Center Name'."""
    n = (name or "").strip()
    if not n:
        return False
    if re.match(r"^\d+\s", n):
        return True
    if re.search(r",\s*[A-Z]{2}\s+\d{5}", n):
        return True
    return False


def _title_org(operated_by: str) -> str:
    org = re.sub(r"\s+", " ", (operated_by or "").strip())
    org = re.sub(r"\bINC\.?\b", "", org, flags=re.I).strip(" ,")
    # Prefer readable title case for ALL-CAPS org names
    if org.isupper() and len(org) > 3:
        org = org.title()
    return org


def load_xlsx_rows(path: Path, states: Optional[List[str]]) -> List[Dict[str, str]]:
    df = pd.read_excel(path)
    rows = []
    for _, r in df.iterrows():
        state = _clean_cell(r.get("State")).upper()
        if states and state not in states:
            continue
        raw_name = _clean_cell(r.get("Health Center Name"))
        if not raw_name:
            continue
        street = _clean_cell(r.get("Street Address"))
        city = _clean_cell(r.get("City"))
        zip_code = _clean_cell(r.get("ZIP Code"))
        operated_by = _clean_cell(r.get("Operated By"))
        address = ", ".join(x for x in [street, city, state, zip_code] if x)

        # Prefer org name when HRSA name is just a street address
        if _looks_like_street_name(raw_name) and operated_by:
            street_short = (street or raw_name).split(",")[0].strip()
            name = f"{_title_org(operated_by)} – {street_short}"
        else:
            name = raw_name

        rows.append(
            {
                "name": name,
                "raw_name": raw_name,
                "address": address,
                "city": city,
                "state": state,
                "zip": _zip5(zip_code),
                "phone": _clean_cell(r.get("Telephone Number")),
                "website": _fmt_website(_clean_cell(r.get("Website"))),
                "operated_by": operated_by,
            }
        )
    return rows


def merge(
    text: str,
    hc_rows: List[Dict[str, str]],
    hab_rows: List[Dict[str, str]],
) -> Tuple[str, Dict]:
    blocks = parse_blocks(text)
    stats = {
        "hc_rows": len(hc_rows),
        "hab_rows": len(hab_rows),
        "updated": 0,
        "added": 0,
        "ryan_white_tagged": 0,
        "changes": [],
    }

    # Index HAB names+zips for dual membership
    hab_keys = {(_norm_name(r["name"]), r["zip"]) for r in hab_rows}

    def is_hab(row: Dict[str, str]) -> bool:
        return (_norm_name(row["name"]), row["zip"]) in hab_keys

    # Process Health Centers first (add/update contact)
    for row in hc_rows:
        match = find_match(
            blocks,
            row["name"],
            row["zip"],
            row["address"],
            raw_name=row.get("raw_name") or "",
        )
        ryan = is_hab(row)
        note = HAB_NOTE if ryan else HC_NOTE
        if match:
            # Rename street-only titles → "Org – Street"
            if _looks_like_street_name(match.name) and row["name"] != match.name:
                match.lines[0] = re.sub(r"^\s*\d+\.\s+.+", f"{match.number}. {row['name']}", match.lines[0])
                match.name = row["name"]
                stats["updated"] += 1
                stats["changes"].append({"action": "rename", "name": row["name"], "source": "health_centers"})
            ch = apply_update(
                match,
                phone=row["phone"],
                website=row["website"],
                note=note,
                ryan_white=ryan,
            )
            if ch:
                stats["updated"] += 1
                if ryan and "ryan_white_services" in ch:
                    stats["ryan_white_tagged"] += 1
                stats["changes"].append({"action": "update", "name": match.name, "fields": ch, "source": "health_centers"})
        else:
            services = HAB_SERVICES if ryan else HC_SERVICES
            blocks.append(
                new_block(
                    len(blocks) + 1,
                    row["name"],
                    row["address"],
                    phone=row["phone"],
                    website=row["website"],
                    note=note,
                    services=services,
                )
            )
            stats["added"] += 1
            if ryan:
                stats["ryan_white_tagged"] += 1
            stats["changes"].append({"action": "add", "name": row["name"], "source": "health_centers", "ryan_white": ryan})

    # HAB-only sites (not already in HC file / not matched above as new HC)
    for row in hab_rows:
        match = find_match(blocks, row["name"], row["zip"], row["address"])
        if match:
            ch = apply_update(
                match,
                phone=row["phone"],
                website=row["website"],
                note=HAB_NOTE,
                ryan_white=True,
            )
            if ch:
                stats["updated"] += 1
                if "ryan_white_services" in ch or "note" in ch:
                    stats["ryan_white_tagged"] += 1
                stats["changes"].append({"action": "update", "name": match.name, "fields": ch, "source": "hab"})
        else:
            blocks.append(
                new_block(
                    len(blocks) + 1,
                    row["name"],
                    row["address"],
                    phone=row["phone"],
                    website=row["website"],
                    note=HAB_NOTE,
                    services=HAB_SERVICES,
                )
            )
            stats["added"] += 1
            stats["ryan_white_tagged"] += 1
            stats["changes"].append({"action": "add", "name": row["name"], "source": "hab", "ryan_white": True})

    return blocks_to_text(blocks), stats


def _github_token() -> Optional[str]:
    tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if tok:
        return tok
    try:
        out = subprocess.check_output(
            ["git", "credential", "fill"],
            input=b"protocol=https\nhost=github.com\n\n",
            stderr=subprocess.DEVNULL,
        ).decode()
        for line in out.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def push_healthcare(new_text: str, commit_msg: str, dry_run: bool = False) -> Dict:
    if dry_run:
        return {"ok": True, "dry_run": True, "bytes": len(new_text), "commit_msg": commit_msg}
    token = _github_token()
    if not token:
        return {"ok": False, "error": "No GitHub token"}
    with tempfile.TemporaryDirectory(prefix="ww-hrsa-") as tmp:
        repo_dir = Path(tmp) / "repo"
        clone_url = f"https://x-access-token:{token}@github.com/{REPO}.git"
        subprocess.check_call(
            ["git", "clone", "--depth", "1", clone_url, str(repo_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        target = repo_dir / HEALTHCARE_REL
        target.write_text(new_text, encoding="utf-8")
        subprocess.check_call(["git", "add", HEALTHCARE_REL], cwd=repo_dir)
        # skip if no change
        diff = subprocess.call(["git", "diff", "--cached", "--quiet"], cwd=repo_dir)
        if diff == 0:
            return {"ok": True, "unchanged": True}
        subprocess.check_call(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_dir,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "WhatWay HRSA Import",
                "GIT_AUTHOR_EMAIL": "ww-ops@local",
                "GIT_COMMITTER_NAME": "WhatWay HRSA Import",
                "GIT_COMMITTER_EMAIL": "ww-ops@local",
            },
        )
        subprocess.check_call(["git", "push", "origin", "HEAD"], cwd=repo_dir)
    return {"ok": True, "pushed": True, "commit_msg": commit_msg, "repo": REPO}


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge HRSA/HAB Excel into healthcare.txt")
    ap.add_argument("--health-centers", required=True, help="Path to Health Centers .xlsx")
    ap.add_argument("--hab", default="", help="Path to HAB / Ryan White .xlsx")
    ap.add_argument("--states", default="IL", help="Comma states to keep (default IL). Use ALL for no filter")
    ap.add_argument("--push", action="store_true", help="Commit + push to GitHub")
    ap.add_argument("--dry-run", action="store_true", help="Preview only")
    ap.add_argument("--out", default="", help="Write merged text to local path")
    ap.add_argument("--refresh-local", action="store_true", help="Rebuild data/healthcare.json after push")
    args = ap.parse_args()

    states = None if args.states.strip().upper() == "ALL" else [s.strip().upper() for s in args.states.split(",") if s.strip()]

    hc_path = Path(args.health_centers).expanduser()
    hab_path = Path(args.hab).expanduser() if args.hab else None

    hc_rows = load_xlsx_rows(hc_path, states)
    hab_rows = load_xlsx_rows(hab_path, states) if hab_path and hab_path.exists() else []

    # Prefer Contents API (raw CDN can lag behind main)
    api = f"https://api.github.com/repos/{REPO}/contents/{HEALTHCARE_REL}?ref=main"
    ar = requests.get(api, timeout=60, headers={"Accept": "application/vnd.github+json"})
    ar.raise_for_status()
    import base64

    current = base64.b64decode(ar.json()["content"]).decode("utf-8")

    merged, stats = merge(current, hc_rows, hab_rows)
    before_n = len(parse_blocks(current))
    after_n = len(parse_blocks(merged))

    summary = {
        "before": before_n,
        "after": after_n,
        "states": states or "ALL",
        **{k: v for k, v in stats.items() if k != "changes"},
        "sample_changes": stats["changes"][:25],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.out:
        Path(args.out).expanduser().write_text(merged, encoding="utf-8")
        print(f"Wrote {args.out}")

    if args.dry_run and not args.push:
        return

    if args.push or args.dry_run:
        msg = (
            f"Import HRSA Health Centers + Ryan White HAB ({REVIEWED}): "
            f"+{stats['added']} add, {stats['updated']} update, "
            f"{stats['ryan_white_tagged']} Ryan White tagged"
        )
        result = push_healthcare(merged, msg, dry_run=args.dry_run and not args.push)
        print(json.dumps(result, indent=2))
        if result.get("ok") and args.refresh_local and not (args.dry_run and not args.push):
            from agents.github_apply import refresh_local_json

            print(json.dumps(refresh_local_json("healthcare"), indent=2))


if __name__ == "__main__":
    main()
