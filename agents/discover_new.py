"""
Discover NEW Chicago education / resettlement (and related) orgs for Telegram approval.

Uses curated seed candidates + DuckDuckGo (optional site fill) + local Ollama verify.
Never auto-pushes: stages to data/pending_ops.json like clinic_ops.

  CITY_SCOPE=chicago python -m agents.discover_new --category education --category resettlement
  python -m agents.clinic_ops --notify
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote_plus, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PENDING_PATH = DATA / "pending_ops.json"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass

CITY_SCOPE = os.environ.get("CITY_SCOPE", "chicago").lower()
UA = {
    "User-Agent": "WhatWayResourceBot/1.0 (+local; research directory enrichment)",
}

# Curated Chicago seeds (public community orgs). Filtered against GitHub before staging.
SEED_CANDIDATES: Dict[str, List[Dict[str, Any]]] = {
    "education": [
        {
            "name": "Literacy Chicago",
            "address": "17 N State St #1070, Chicago, IL 60602",
            "zip": "60602",
            "website": "https://www.literacychicago.org",
            "phone": "(312) 750-4000",
            "services": ["ESL", "GED", "adult literacy", "workforce"],
            "notes": "Free adult literacy & workforce classes (ESL, GED, digital skills).",
        },
        {
            "name": "Trellus",
            "address": "Chicago, IL",
            "zip": "60600",
            "website": "https://mytrellus.org",
            "services": ["ESL", "GED", "computer classes", "adult education"],
            "notes": "Immigrant & underserved families, adult ESL/GED/computer classes.",
        },
        {
            "name": "Pui Tak Center",
            "address": "2216 S Wentworth Ave, Chicago, IL 60616",
            "zip": "60616",
            "website": "https://www.puitak.org",
            "phone": "(312) 328-1188",
            "services": ["Adult ESL", "citizenship", "job readiness"],
            "notes": "Chinatown community center, free Adult ESL (6 levels).",
        },
        {
            "name": "Instituto del Progreso Latino",
            "address": "2570 S Blue Island Ave, Chicago, IL 60608",
            "zip": "60608",
            "website": "https://www.idpl.org",
            "services": ["ESL", "GED", "career pathways", "adult education"],
            "notes": "Latino-focused adult education and career pathways.",
        },
        {
            "name": "Albany Park Community Center",
            "address": "3401 W Ainslie St, Chicago, IL 60625",
            "zip": "60625",
            "website": "https://www.apcc-chgo.org",
            "services": ["ESL", "youth programs", "family literacy"],
            "notes": "Community center with ESL and family education programs.",
        },
        {
            "name": "Association House of Chicago",
            "address": "1116 N Kedzie Ave, Chicago, IL 60651",
            "zip": "60651",
            "website": "https://www.associationhouse.org",
            "services": ["ESL", "adult education", "youth", "workforce"],
            "notes": "Settlement house, education and family support.",
        },
        {
            "name": "Howard Area Community Center",
            "address": "7648 N Paulina St, Chicago, IL 60626",
            "zip": "60626",
            "website": "https://howardarea.org",
            "services": ["ESL", "adult education", "family services"],
            "notes": "Rogers Park community education and family programs.",
        },
    ],
    "resettlement": [
        {
            "name": "Legal Aid Chicago",
            "address": "120 S LaSalle St #900, Chicago, IL 60603",
            "zip": "60603",
            "website": "https://www.legalaidchicago.org",
            "phone": "(312) 341-0300",
            "services": ["civil legal aid", "immigration", "housing", "family law"],
            "notes": "Free civil legal services for low-income Cook County residents.",
        },
        {
            "name": "National Immigrant Justice Center (NIJC)",
            "address": "224 S Michigan Ave #600, Chicago, IL 60604",
            "zip": "60604",
            "website": "https://immigrantjustice.org",
            "services": ["immigration legal services", "asylum", "detention"],
            "notes": "Heartland Alliance NIJC, immigrant legal defense.",
        },
        {
            "name": "Illinois Coalition for Immigrant and Refugee Rights (ICIRR)",
            "address": "228 S Wabash Ave #800, Chicago, IL 60604",
            "zip": "60604",
            "website": "https://www.icirr.org",
            "services": ["immigrant rights", "citizenship", "policy advocacy", "referrals"],
            "notes": "Statewide immigrant & refugee rights coalition and referrals.",
        },
        {
            "name": "Centro Romero",
            "address": "6216 N Clark St, Chicago, IL 60660",
            "zip": "60660",
            "website": "https://centroromero.org",
            "services": ["legal services", "ESL", "youth", "immigrant support"],
            "notes": "Immigrant community organization, legal and education support.",
        },
        {
            "name": "The Resurrection Project",
            "address": "1818 S Paulina St, Chicago, IL 60608",
            "zip": "60608",
            "website": "https://resurrectionproject.org",
            "services": ["housing", "community development", "immigrant services"],
            "notes": "Pilsen-based housing and community development for immigrant families.",
        },
        {
            "name": "HANA Center",
            "address": "4300 N California Ave, Chicago, IL 60618",
            "zip": "60618",
            "website": "https://www.hanacenter.org",
            "services": ["immigrant services", "youth", "family support", "ESL"],
            "notes": "Korean American / immigrant community services.",
        },
        {
            "name": "Apna Ghar",
            "address": "Chicago, IL",
            "zip": "60600",
            "website": "https://www.apnaghar.org",
            "services": ["domestic violence", "shelter", "immigrant survivors"],
            "notes": "Support for survivors of gender-based violence in immigrant communities.",
        },
        {
            "name": "The Night Ministry",
            "address": "1735 N Ashland Ave, Chicago, IL 60622",
            "zip": "60622",
            "website": "https://thenightministry.org",
            "services": ["shelter", "outreach", "health", "youth housing"],
            "notes": "Homeless outreach, health, and housing support.",
        },
    ],
}

# Extra multi-state education / resettlement seeds (IN, CO, CA)
MULTI_STATE_SEEDS: Dict[str, List[Dict[str, Any]]] = {
    "education": [
        {
            "name": "Exodus Refugee Immigration — Education Supports",
            "address": "2457 E Washington St, Indianapolis, IN 46201",
            "zip": "46201",
            "state": "IN",
            "website": "https://www.exodusrefugee.org",
            "services": ["ESL", "orientation", "employment", "refugee education"],
            "notes": "Indiana refugee resettlement, ESL and orientation supports.",
        },
        {
            "name": "Immigrant Welcome Center",
            "address": "901 Shelby St, Indianapolis, IN 46203",
            "zip": "46203",
            "state": "IN",
            "website": "https://www.immigrantwelcomecenter.org",
            "services": ["ESL", "citizenship", "workforce", "immigrant navigation"],
            "notes": "Central Indiana immigrant education and welcome services.",
        },
        {
            "name": "Spring Institute for Intercultural Learning",
            "address": "1373 Grant St, Denver, CO 80203",
            "zip": "80203",
            "state": "CO",
            "website": "https://www.springinstitute.org",
            "services": ["ESL", "workforce", "interpreter training", "adult education"],
            "notes": "Denver adult ESL and intercultural learning programs.",
        },
        {
            "name": "Emily Griffith Technical College",
            "address": "1860 Lincoln St, Denver, CO 80203",
            "zip": "80203",
            "state": "CO",
            "website": "https://www.emilygriffith.edu",
            "services": ["ESL", "GED", "career training", "adult education"],
            "notes": "Denver adult ESL and career/technical education.",
        },
        {
            "name": "International Institute of the Bay Area",
            "address": "1111 Market St, San Francisco, CA 94103",
            "zip": "94103",
            "state": "CA",
            "website": "https://iibayarea.org",
            "services": ["ESL", "citizenship", "immigrant education", "legal referrals"],
            "notes": "Bay Area immigrant education and integration services.",
        },
        {
            "name": "Jewish Vocational Service (JVS SoCal)",
            "address": "6505 Wilshire Blvd, Los Angeles, CA 90048",
            "zip": "90048",
            "state": "CA",
            "website": "https://www.jvs-socal.org",
            "services": ["ESL", "workforce", "job readiness", "refugee employment"],
            "notes": "Southern California workforce and ESL supports for newcomers.",
        },
    ],
    "resettlement": [
        {
            "name": "Exodus Refugee Immigration",
            "address": "2457 E Washington St, Indianapolis, IN 46201",
            "zip": "46201",
            "state": "IN",
            "website": "https://www.exodusrefugee.org",
            "services": ["refugee resettlement", "case management", "employment"],
            "notes": "Primary Indiana refugee resettlement agency.",
        },
        {
            "name": "Catholic Charities Indianapolis — Refugee & Immigrant Services",
            "address": "1400 N Meridian St, Indianapolis, IN 46202",
            "zip": "46202",
            "state": "IN",
            "website": "https://www.archindy.org/cc",
            "services": ["refugee resettlement", "immigration", "basic needs"],
            "notes": "Archdiocese of Indianapolis refugee and immigrant services.",
        },
        {
            "name": "Colorado Refugee Services Program (CDHS)",
            "address": "1575 Sherman St, Denver, CO 80203",
            "zip": "80203",
            "state": "CO",
            "website": "https://cdhs.colorado.gov/crsp",
            "services": ["refugee resettlement", "benefits", "case management"],
            "notes": "State refugee office, Colorado Department of Human Services.",
        },
        {
            "name": "Lutheran Family Services Rocky Mountains",
            "address": "363 S Harlan St, Denver, CO 80226",
            "zip": "80226",
            "state": "CO",
            "website": "https://www.lfsrm.org",
            "services": ["refugee resettlement", "immigration", "family support"],
            "notes": "Denver-area refugee resettlement and immigrant services.",
        },
        {
            "name": "African Community Center of Denver",
            "address": "925 S Niagara St, Denver, CO 80224",
            "zip": "80224",
            "state": "CO",
            "website": "https://www.acc-den.org",
            "services": ["refugee resettlement", "employment", "youth"],
            "notes": "Denver refugee resettlement focused on African newcomers.",
        },
        {
            "name": "International Rescue Committee — Sacramento",
            "address": "Sacramento, CA 95814",
            "zip": "95814",
            "state": "CA",
            "website": "https://www.rescue.org/united-states/sacramento-ca",
            "services": ["refugee resettlement", "employment", "education"],
            "notes": "IRC Sacramento resettlement and integration programs.",
        },
        {
            "name": "International Rescue Committee — Los Angeles",
            "address": "Los Angeles, CA 90015",
            "zip": "90015",
            "state": "CA",
            "website": "https://www.rescue.org/united-states/los-angeles-ca",
            "services": ["refugee resettlement", "legal", "employment"],
            "notes": "IRC Los Angeles resettlement and immigrant services.",
        },
        {
            "name": "Jewish Family and Children's Services — San Francisco",
            "address": "2150 Post St, San Francisco, CA 94115",
            "zip": "94115",
            "state": "CA",
            "website": "https://www.jfcs.org",
            "services": ["refugee resettlement", "immigration", "family support"],
            "notes": "Bay Area refugee and immigrant family services.",
        },
    ],
}


def _all_seeds() -> Dict[str, List[Dict[str, Any]]]:
    """Merge Chicago seeds (default state IL) with multi-state seeds."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for cat, rows in SEED_CANDIDATES.items():
        merged = []
        for r in rows:
            row = dict(r)
            row.setdefault("state", "IL")
            merged.append(row)
        out[cat] = merged
    for cat, rows in MULTI_STATE_SEEDS.items():
        out.setdefault(cat, []).extend(rows)
    return out


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


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def load_known_names() -> set:
    """Union of GitHub-synced local JSON + pending open proposals."""
    names = set()
    for fname in ("healthcare.json", "education.json", "resettlement_legal_shelter.json"):
        path = DATA / fname
        if not path.exists():
            continue
        try:
            for item in json.loads(path.read_text(encoding="utf-8")):
                n = _norm_name(item.get("name") or "")
                if n:
                    names.add(n)
        except Exception:
            continue
    pending = _load_pending()
    for it in pending.get("items") or []:
        if it.get("status") in ("proposed", "proposed_update", "approved"):
            n = _norm_name(it.get("name") or "")
            if n:
                names.add(n)
    return names


def already_listed(name: str, known: set) -> bool:
    n = _norm_name(name)
    if n in known:
        return True
    # soft match: first 3 tokens
    tokens = n.split()
    if len(tokens) >= 2:
        prefix = " ".join(tokens[:3])
        for k in known:
            if k.startswith(prefix) or prefix in k:
                return True
    return False


def discover_website_ddg(name: str, address: str = "") -> Optional[str]:
    q = f"{name} Chicago official site".strip()
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(q)
    try:
        r = requests.get(url, timeout=25, headers=UA)
        if r.status_code != 200:
            return None
        hrefs = re.findall(r'uddg=([^&"]+)', r.text)
        from urllib.parse import unquote

        skip = (
            "facebook.com",
            "yelp.com",
            "google.com",
            "maps.google",
            "bing.com",
            "yellowpages",
            "duckduckgo",
            "wikipedia.org",
        )
        for enc in hrefs[:12]:
            link = unquote(enc)
            host = urlparse(link).netloc.lower()
            if any(s in host for s in skip):
                continue
            if link.startswith("http"):
                return link.split("&")[0]
    except Exception:
        return None
    return None


def ollama_verify_new(candidate: Dict[str, Any], category: str) -> Dict[str, Any]:
    """Ask local Ollama if this is a real Chicago org for the category."""
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL") or "llama3"
    prompt = (
        "You verify a community resource for a Chicago refugee/immigrant directory. "
        'Reply ONLY JSON: {"ok": true|false, "confidence": "high"|"medium"|"low", "reason": "..."}\n'
        "Reject if not Chicago-area, not real, or wrong category.\n"
        f"Category: {category}\n"
        f"Name: {candidate.get('name')}\n"
        f"Address: {candidate.get('address')}\n"
        f"Website: {candidate.get('website')}\n"
        f"Services: {candidate.get('services')}\n"
        f"Notes: {candidate.get('notes')}\n"
    )
    try:
        native = base.replace("/v1", "") + "/api/chat"
        body = json.dumps(
            {
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [
                    {
                        "role": "system",
                        "content": "Careful verifier. Never invent orgs. Prefer reject when unsure.",
                    },
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode()
        req = requests.post(native, data=body, headers={"Content-Type": "application/json"}, timeout=90)
        req.raise_for_status()
        content = ((req.json().get("message") or {}).get("content") or "").strip()
        parsed = json.loads(content)
        return {
            "ok": bool(parsed.get("ok")),
            "confidence": parsed.get("confidence") or "low",
            "reason": parsed.get("reason") or "",
            "provider": "ollama",
        }
    except Exception as e:
        return {
            "ok": True,
            "confidence": "unchecked",
            "reason": f"Ollama unavailable ({e}); left for human approve",
            "provider": "none",
        }


def stage_new(candidate: Dict[str, Any], category: str, verification: Dict[str, Any]) -> Dict[str, Any]:
    from agents import tools as ops_tools
    from agents.geo_scope import infer_state

    pending = _load_pending()
    name = candidate.get("name") or "Unknown"
    services = candidate.get("services") or []
    services_s = ", ".join(services) if isinstance(services, list) else str(services)
    address = candidate.get("address") or ""
    item = {
        "op_id": _op_id(),
        "kind": "proposed",
        "status": "proposed",
        "category": category,
        "name": name,
        "address": address,
        "zip": candidate.get("zip") or "",
        "phone": candidate.get("phone") or "",
        "website": candidate.get("website") or "",
        "services": services if isinstance(services, list) else [services_s],
        "languages": candidate.get("languages") or [],
        "hours": candidate.get("hours") or "",
        "notes": candidate.get("notes") or "",
        "source": "discover_new_seeds",
        "needs_approval": True,
        "region": CITY_SCOPE,
        "city_scope": CITY_SCOPE,
        "state": infer_state(address, zip_code=str(candidate.get("zip") or "")),
        "verification": verification,
        "created_at": _now(),
    }
    item["github_draft"] = ops_tools.draft_github_block(
        name=name,
        address=item["address"],
        phone=item["phone"],
        website=item["website"],
        services=services_s,
        languages="",
        hours=str(item["hours"] or ""),
        next_id=999,
    )
    pending.setdefault("items", []).append(item)
    _save_pending(pending)
    return item


def scan(
    categories: Optional[Sequence[str]] = None,
    *,
    limit: int = 20,
    use_ollama: bool = True,
    discover_sites: bool = True,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    cats = list(categories) if categories else ["education", "resettlement"]
    st_filter = (state or "").strip().upper() or None
    known = load_known_names()
    staged: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    seeds = _all_seeds()

    for cat in cats:
        for cand in seeds.get(cat, []):
            if len(staged) >= limit:
                break
            cand_state = (cand.get("state") or "IL").upper()
            if st_filter and cand_state != st_filter:
                continue
            name = cand.get("name") or ""
            if already_listed(name, known):
                skipped.append({"name": name, "category": cat, "reason": "already_listed"})
                continue

            row = dict(cand)
            if discover_sites and not (row.get("website") or "").strip():
                found = discover_website_ddg(name, row.get("address") or "")
                if found:
                    row["website"] = found

            if use_ollama:
                verification = ollama_verify_new(row, cat)
            else:
                verification = {
                    "ok": True,
                    "confidence": "unchecked",
                    "reason": "Ollama skipped",
                    "provider": "none",
                }

            # Curated seeds: if Ollama rejects, still stage for human ❤ (mark low)
            if not verification.get("ok") and verification.get("confidence") != "unchecked":
                verification = {
                    "ok": True,
                    "confidence": "low",
                    "reason": f"Ollama unsure ({verification.get('reason')}); staged for human review",
                    "provider": verification.get("provider") or "ollama",
                }

            item = stage_new(row, cat, verification)
            # ensure state stamped
            try:
                pending = _load_pending()
                for it in pending.get("items") or []:
                    if it.get("op_id") == item.get("op_id"):
                        it["state"] = cand_state
                _save_pending(pending)
            except Exception:
                pass
            known.add(_norm_name(name))
            staged.append(
                {
                    "op_id": item["op_id"],
                    "name": name,
                    "category": cat,
                    "state": cand_state,
                    "confidence": verification.get("confidence"),
                }
            )

    auto_info = {"auto_apply": 0}
    if staged:
        try:
            from agents.confidence import drain_auto_apply

            auto_info = drain_auto_apply(staged)
        except Exception as e:
            auto_info = {"error": str(e)}

    return {
        "ok": True,
        "scope": CITY_SCOPE,
        "state": st_filter,
        "categories": cats,
        "staged": len(staged),
        "skipped": len(skipped),
        "auto_apply_high": auto_info,
        "items": staged,
        "skipped_items": skipped[:40],
        "pending_path": str(PENDING_PATH),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Discover NEW education/resettlement orgs for Telegram approve")
    ap.add_argument(
        "--category",
        action="append",
        choices=["education", "resettlement", "healthcare"],
        help="Repeatable. Default: education + resettlement",
    )
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--no-ollama", action="store_true")
    ap.add_argument("--no-discover-sites", action="store_true")
    args = ap.parse_args()
    result = scan(
        args.category,
        limit=args.limit,
        use_ollama=not args.no_ollama,
        discover_sites=not args.no_discover_sites,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
