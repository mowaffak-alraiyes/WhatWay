"""
Enrich missing 📞 / 🌐 on GitHub listings — free sources only, human approve.

Flow:
  1. Read each listing from refugee-resources (name + address + existing phone/web)
  2. For gaps only, try:
       - org’s own site (existing URL, or optional DuckDuckGo HTML discover)
       - local HRSA CSV / contacts sheet CSV
     NOT Google Places / Yelp bulk scrape
  3. Optional Ollama check: “does this phone/site match this clinic?”
  4. Stage proposed_update → data/pending_ops.json (never auto-push)
  5. You approve (Telegram or CLI) → apply → GitHub .txt
  6. Apply also refreshes local data/*.json so Aidr search sees it

Cost: $0 on Ollama + public pages + existing GitHub token.

Examples:
  python -m agents.enrich_contacts --scan --limit 20
  python -m agents.enrich_contacts --scan --category healthcare --hrsa data/hrsa_il.csv
  python -m agents.enrich_contacts --scan --discover-sites --limit 5
  python -m agents.enrich_contacts --list-gaps
  # then same approve/apply as clinic_ops:
  python -m agents.clinic_ops --list
  python -m agents.clinic_ops --approve op_ab12
  python -m agents.clinic_ops --apply op_ab12
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass

PENDING_PATH = DATA / "pending_ops.json"


def _github_files(state: Optional[str] = None) -> Dict[str, str]:
    from agents.geo_scope import category_files_for_state, raw_github_url

    return {k: raw_github_url(v) for k, v in category_files_for_state(state).items()}


GITHUB_FILES = _github_files()

CITY_SCOPE = os.environ.get("CITY_SCOPE", "chicago").lower()
# Optional USPS filter for enrich (e.g. IN) — set via scan(state=...) or --state
ENRICH_STATE = (os.environ.get("RESOURCES_STATE") or "").strip().upper() or None
CHICAGO_ZIP = re.compile(r"\b60\d{3}\b")
PHONE_RE = re.compile(
    r"(?:\+?1[\s\-.]*)?(?:\(?\d{3}\)?[\s\-.]*)\d{3}[\s\-.]*\d{4}"
)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
UA = {
    "User-Agent": "AidrContactEnrich/1.0 (+local; free-clinic directory; respectful fetch)"
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
    return {"updated_at": None, "items": [], "scope": CITY_SCOPE}


def _save_pending(payload: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _now()
    payload["scope"] = CITY_SCOPE
    PENDING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def _in_scope(address: str, zip_code: str = "", *, state: Optional[str] = None) -> bool:
    text = f"{zip_code} {address}"
    st = (state or ENRICH_STATE or "").upper()
    if st:
        from agents.geo_scope import infer_state

        return infer_state(address, zip_code=zip_code) == st or f" {st} " in f" {text.upper()} "
    if CITY_SCOPE == "national":
        return True
    return bool(CHICAGO_ZIP.search(text)) or "chicago" in text.lower() or "il" in text.lower()


def parse_github_listings(
    categories: Optional[List[str]] = None,
    *,
    state: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Parse name, address, phone, website from GitHub .txt files."""
    files = _github_files(state)
    cats = categories or list(files.keys())
    out: List[Dict[str, str]] = []
    for key in cats:
        url = files.get(key)
        if not url:
            continue
        try:
            r = requests.get(url, timeout=45, headers=UA)
            r.raise_for_status()
            text = r.text
        except Exception as e:
            print(f"GitHub fetch warning ({key}): {e}")
            continue

        current: Optional[Dict[str, str]] = None
        for line in text.splitlines():
            m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
            if m:
                if current and current.get("name"):
                    out.append(current)
                current = {
                    "id": m.group(1),
                    "name": m.group(2).strip(),
                    "address": "",
                    "phone": "",
                    "website": "",
                    "languages": "",
                    "services": "",
                    "hours": "",
                    "category": key,
                    "zip": "",
                    "state": (state or "").upper(),
                }
                continue
            if not current:
                continue
            s = line.strip()
            if not s:
                continue
            if s.startswith("📞") or s.lower().startswith("phone"):
                current["phone"] = re.sub(r"^(📞|phone)\s*:?\s*", "", s, flags=re.I).strip()
            elif s.startswith("🌐") or s.startswith("http"):
                current["website"] = re.sub(r"^🌐\s*", "", s).strip()
            elif s.startswith("🗣") or s.lower().startswith("language"):
                current["languages"] = re.sub(r"^(🗣|languages?)\s*:?\s*", "", s, flags=re.I).strip()
            elif s.startswith("🏥") or s.lower().startswith("service"):
                current["services"] = re.sub(r"^(🏥|services?)\s*:?\s*", "", s, flags=re.I).strip()
            elif s.startswith("⏰") or s.lower().startswith("hours"):
                current["hours"] = re.sub(r"^(⏰|hours?)\s*:?\s*", "", s, flags=re.I).strip()
            elif s.startswith(("📝", "📧", "#")):
                continue
            elif not current["address"] and (
                "," in s or re.search(r"\b[A-Z]{2}\b", s) or re.search(r"\b\d{5}\b", s)
            ):
                current["address"] = s
                zm = re.search(r"\b(\d{5})\b", s)
                if zm:
                    current["zip"] = zm.group(1)
        if current and current.get("name"):
            out.append(current)
    return out


def list_gaps(
    listings: List[Dict[str, str]],
    *,
    websites_only: bool = False,
    phones_only: bool = False,
    fields_only: bool = False,
    state: Optional[str] = None,
) -> List[Dict[str, str]]:
    gaps = []
    for it in listings:
        if not _in_scope(it.get("address") or "", it.get("zip") or "", state=state):
            continue
        missing_phone = not _digits(it.get("phone") or "")
        missing_web = not (it.get("website") or "").strip()
        missing_lang = not (it.get("languages") or "").strip()
        missing_svc = not (it.get("services") or "").strip()
        missing_hours = not (it.get("hours") or "").strip()
        if websites_only and not missing_web:
            continue
        if phones_only and not missing_phone:
            continue
        if fields_only and not (missing_lang or missing_svc or missing_hours):
            continue
        if missing_phone or missing_web or missing_lang or missing_svc or missing_hours:
            gaps.append(
                {
                    **it,
                    "missing_phone": missing_phone,
                    "missing_web": missing_web,
                    "missing_lang": missing_lang,
                    "missing_svc": missing_svc,
                    "missing_hours": missing_hours,
                }
            )
    return gaps


_LANG_HINTS = (
    "spanish",
    "arabic",
    "mandarin",
    "cantonese",
    "polish",
    "urdu",
    "hindi",
    "french",
    "ukrainian",
    "swahili",
    "korean",
    "vietnamese",
    "tagalog",
    "portuguese",
    "russian",
    "bosnian",
    "somali",
    "burmese",
    "english",
    "amharic",
    "tigrinya",
    "farsi",
    "persian",
    "pashto",
    "dari",
    "hmong",
    "lao",
    "thai",
    "khmer",
    "nepali",
    "bengali",
    "punjabi",
    "gujarati",
    "haitian creole",
    "creole",
    "asl",
    "sign language",
)
_SVC_HINTS = (
    "esl",
    "ged",
    "citizenship",
    "primary care",
    "dental",
    "mental health",
    "behavioral health",
    "immigration",
    "legal aid",
    "housing",
    "shelter",
    "workforce",
    "job training",
    "youth",
    "food pantry",
    "case management",
    "interpretation",
    "interpreter",
    "translation",
    "asylum",
    "pediatrics",
    "prenatal",
    "obgyn",
    "ob/gyn",
    "women's health",
    "pharmacy",
    "vision",
    "optometry",
    "substance use",
    "hiv",
    "std",
    "sti",
    "family planning",
    "sliding fee",
    "sliding scale",
    "medicaid",
    "uninsured",
)
_LANG_PHRASE_RE = re.compile(
    r"(?i)(?:languages?\s*(?:spoken|offered|available)?|we\s+speak|interpretation\s+(?:available|services?)"
    r"|bilingual\s+(?:staff|services?)|interpreters?\s+(?:available|on\s+site))"
    r"\s*[:\-–]?\s*([A-Za-z][A-Za-z\s,/;&()]{2,120})"
)
_HOURS_RE = re.compile(
    r"(?i)((?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?(?:\s*[-–]\s*(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?)?"
    r"\s*[:\-]?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))?)"
)


def extract_fields_from_text(text: str) -> Dict[str, str]:
    """Best-effort languages / services / hours from free org-site text."""
    low = (text or "").lower()
    out: Dict[str, str] = {}
    langs = []
    phrase = _LANG_PHRASE_RE.search(text or "")
    if phrase:
        chunk = phrase.group(1)
        # stop at sentence break / boilerplate
        chunk = re.split(r"[.!?]|click |learn more|read more", chunk, maxsplit=1, flags=re.I)[0]
        for part in re.split(r"[,;/&]| and ", chunk):
            p = part.strip(" .:-–()").strip()
            if 2 <= len(p) <= 40 and re.search(r"[A-Za-z]", p):
                langs.append(p.title() if p.lower() != "asl" else "ASL")
    for h in _LANG_HINTS:
        if re.search(rf"\b{re.escape(h)}\b", low):
            label = "ASL" if h in ("asl", "sign language") else ("Haitian Creole" if h == "haitian creole" else h.title())
            langs.append(label)
    # ESL/GED are services, not languages
    langs = [x for x in langs if x.lower() not in ("esl", "ged")]
    if langs:
        out["languages"] = ", ".join(list(dict.fromkeys(langs))[:10])
    svcs = []
    for h in _SVC_HINTS:
        if re.search(rf"\b{re.escape(h)}\b", low):
            if h in ("esl", "ged", "hiv", "std", "sti", "obgyn", "ob/gyn"):
                svcs.append(h.upper().replace("OB/GYN", "OB/GYN"))
            else:
                svcs.append(h.title())
    if svcs:
        out["services"] = ", ".join(list(dict.fromkeys(svcs))[:12])
    hm = _HOURS_RE.search(text or "")
    if hm:
        out["hours"] = re.sub(r"\s+", " ", hm.group(1)).strip()[:120]
    return out


def fields_from_site(website: str) -> Tuple[Dict[str, str], str]:
    if not website:
        return {}, ""
    base = website if website.startswith("http") else f"https://{website}"
    merged: Dict[str, str] = {}
    for path in ("", "/about", "/services", "/programs", "/contact", "/languages", "/patients"):
        url = urljoin(base.rstrip("/") + "/", path.lstrip("/")) if path else base
        try:
            text = fetch_page_text(url)
            got = extract_fields_from_text(text)
            for k, v in got.items():
                if v and k not in merged:
                    merged[k] = v
        except Exception:
            continue
        if len(merged) >= 3:
            break
        time.sleep(0.35)
    return merged, base

def _directory_row_from_keys(
    lower: Dict[str, str],
    *,
    source: str,
    allow_state: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    def pick(*keys: str) -> str:
        for key in keys:
            for k, v in lower.items():
                if key in k and v:
                    return v
        return ""

    name = pick("site name", "site_name", "health center name", "organization", "name", "facility")
    phone = pick("phone", "telephone", "site telephone", "site phone", "telephone number")
    website = pick("website", "web site", "url", "site url")
    address = pick("address", "site address", "street", "street address", "location")
    city = pick("city", "site city")
    state = pick("state", "site state")
    zip_code = pick("zip", "postal", "zip code", "site zip")
    st = (state or "").upper().strip()
    allow = (allow_state or "").upper().strip() or None
    if allow:
        if st and st != allow and allow not in f"{city} {address} {zip_code}".upper():
            return None
    elif CITY_SCOPE != "national":
        if st and st not in ("IL", "ILLINOIS", ""):
            return None
        if zip_code and not CHICAGO_ZIP.search(zip_code):
            if "chicago" not in f"{city} {address}".lower():
                return None
    if not name:
        return None
    return {
        "name": name,
        "phone": phone,
        "website": website,
        "address": ", ".join(x for x in [address, city, state, zip_code] if x),
        "zip": zip_code,
        "source": source,
    }


def load_hrsa_index(path: Path, *, state: Optional[str] = None) -> List[Dict[str, str]]:
    """Load HRSA CSV or Find-a-HC XLSX; flexible column names."""
    if not path.exists():
        raise FileNotFoundError(path)
    rows: List[Dict[str, str]] = []
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        try:
            hdr = next(it)
        except StopIteration:
            wb.close()
            return []
        keys = [re.sub(r"\s+", " ", str(h or "").strip().lower()) for h in hdr]
        for raw in it:
            lower = {
                keys[i]: str(raw[i]).strip() if raw[i] is not None else ""
                for i in range(min(len(keys), len(raw)))
            }
            row = _directory_row_from_keys(lower, source=f"hrsa_xlsx:{path.name}", allow_state=state)
            if row:
                rows.append(row)
        wb.close()
        return rows

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lower = {re.sub(r"\s+", " ", (k or "").strip().lower()): (v or "").strip() for k, v in row.items()}
            got = _directory_row_from_keys(lower, source=f"hrsa_csv:{path.name}", allow_state=state)
            if got:
                rows.append(got)
    return rows


def default_hrsa_sheet_for_state(state: Optional[str]) -> Optional[Path]:
    st = (state or "").upper().strip()
    if not st:
        return None
    p = DATA / "hrsa_finder" / f"health_centers_{st}.xlsx"
    return p if p.exists() else None


def match_directory(
    listing: Dict[str, str],
    directory: List[Dict[str, str]],
    *,
    min_score: int = 82,
) -> Optional[Dict[str, str]]:
    name = (listing.get("name") or "").lower()
    zip_code = listing.get("zip") or ""
    best: Optional[Tuple[int, Dict[str, str]]] = None
    for row in directory:
        score = fuzz.token_set_ratio(name, (row.get("name") or "").lower())
        if zip_code and row.get("zip") and zip_code == row["zip"]:
            score += 8
        if score >= min_score and (best is None or score > best[0]):
            best = (score, row)
    if not best:
        return None
    return {**best[1], "match_score": str(best[0])}


def fetch_page_text(url: str, timeout: int = 20) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    r = requests.get(url, timeout=timeout, headers=UA, allow_redirects=True)
    r.raise_for_status()
    # Strip scripts/styles roughly
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", r.text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text[:80000]


def extract_phones(text: str) -> List[str]:
    found = []
    seen = set()
    for m in PHONE_RE.finditer(text or ""):
        raw = m.group(0)
        d = _digits(raw)
        if len(d) != 10 or d in seen:
            continue
        # Skip obvious junk / toll-free placeholders sometimes
        seen.add(d)
        found.append(_fmt_phone(raw))
    return found


def phones_from_site(website: str) -> Tuple[List[str], str]:
    """Fetch homepage (+ /contact if linked) and extract phones."""
    if not website:
        return [], ""
    base = website if website.startswith("http") else f"https://{website}"
    phones: List[str] = []
    tried = []
    for path in ("", "/contact", "/contact-us", "/about", "/appointment"):
        url = urljoin(base.rstrip("/") + "/", path.lstrip("/")) if path else base
        if url in tried:
            continue
        tried.append(url)
        try:
            text = fetch_page_text(url)
            phones.extend(extract_phones(text))
            # also tel: from raw html quickly
            raw = requests.get(url, timeout=15, headers=UA).text
            for m in re.finditer(r"tel:([+\d\-\(\)\s\.]+)", raw, re.I):
                phones.extend(extract_phones(m.group(1)))
        except Exception:
            continue
        if phones:
            break
        time.sleep(0.4)
    # dedupe
    uniq = []
    seen = set()
    for p in phones:
        d = _digits(p)
        if d not in seen:
            seen.add(d)
            uniq.append(p)
    return uniq, base


def discover_website_ddg(name: str, address: str = "") -> Optional[str]:
    """
    Optional free discovery via DuckDuckGo HTML (not Google/Yelp).
    Often blocked (HTTP 202); returns None when empty — callers should
    fall back to sibling / parent-org inference.
    """
    q = f"{name} {address} official site".strip()
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(q)
    try:
        r = requests.get(url, timeout=25, headers=UA)
        if r.status_code != 200:
            return None
        hrefs = re.findall(r'uddg=([^&"]+)', r.text)
        from urllib.parse import unquote

        skip = ("facebook.com", "yelp.com", "google.com", "maps.google", "bing.com", "yellowpages", "duckduckgo")
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


# Common Chicago FQHC / free-clinic parent sites (free, curated — not Places API)
_PARENT_SITE_RULES = [
    (re.compile(r"\blchc\b|lawndale christian", re.I), "https://www.lawndale.org"),
    (re.compile(r"\berie\b", re.I), "https://www.eriefamilyhealth.org"),
    (re.compile(r"\bpcc\b", re.I), "https://www.pcccommunitywellness.org"),
    (re.compile(r"\baccess\b", re.I), "https://www.achn.net"),
    (re.compile(r"chicago family health|cfhc\b", re.I), "https://chicagofamilyhealth.org"),
    (re.compile(r"\balivio\b", re.I), "https://alivio.org"),
    (re.compile(r"\bahs\b|asian human services", re.I), "https://ahsfhc.org"),
    (re.compile(r"friend family|ffhc\b", re.I), "https://www.friendfamilyhealth.org"),
    (re.compile(r"christian community health|cchc\b", re.I), "https://cchc-online.org"),
    (re.compile(r"haymarket", re.I), "https://www.haymarketcenter.org"),
    (re.compile(r"heartland health|heartland alliance", re.I), "https://www.heartlandalliance.org"),
    (re.compile(r"tapestry\b|heartland.*health.*centers", re.I), "https://www.tapestry360.org"),
    (re.compile(r"near north health|nnhc\b", re.I), "https://www.nearnorthhealth.org"),
    (re.compile(r"prime\s*care|primecare", re.I), "https://www.primecarechicago.com"),
    (re.compile(r"sams\b|syrian american medical", re.I), "https://samscommunityclinic.org/"),
]


def infer_parent_website(name: str) -> Optional[str]:
    for pat, url in _PARENT_SITE_RULES:
        if pat.search(name or ""):
            return url
    return None


def infer_sibling_website(listing: Dict[str, str], all_listings: List[Dict[str, str]]) -> Optional[str]:
    """Reuse a website from another site with the same org-like name prefix."""
    name = listing.get("name") or ""
    # Prefix before " at " / " - " / " – "
    prefix = re.split(r"\s+at\s+|\s+[-–—]\s+", name, maxsplit=1, flags=re.I)[0].strip()
    if len(prefix) < 3:
        return None

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

    prefix_n = norm(prefix)
    for other in all_listings:
        if other is listing:
            continue
        web = (other.get("website") or "").strip()
        if not web:
            continue
        on = norm(other.get("name") or "")
        if on.startswith(prefix_n) or prefix_n.split()[0] in on.split()[:2]:
            return web if web.startswith("http") else f"https://{web}"
    return None


def ollama_verify_match(
    listing: Dict[str, str],
    candidate_phone: str = "",
    candidate_website: str = "",
    evidence: str = "",
    candidate_updates: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Local Ollama: does this contact likely belong to this clinic?
    Returns {ok, confidence, reason}. If Ollama is down, ok=True with confidence='unchecked'.
    """
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL") or "llama3"
    extras = candidate_updates or {}
    prompt = (
        "You verify clinic contact enrichment. Reply with ONLY JSON: "
        '{"match": true|false, "confidence": "high"|"medium"|"low", "reason": "..."}\n'
        "Accept language/service/hours fills scraped from the clinic's own site if plausible.\n"
        "Reject if the phone/website clearly belongs to a different org.\n"
        f"Clinic name: {listing.get('name')}\n"
        f"Address: {listing.get('address')}\n"
        f"Existing website: {(listing.get('website') or '')[:120]}\n"
        f"Candidate phone: {candidate_phone}\n"
        f"Candidate website: {candidate_website}\n"
        f"Other proposed fields: {json.dumps({k: extras.get(k) for k in ('languages','services','hours') if extras.get(k)}, ensure_ascii=False)}\n"
        f"Evidence snippet: {evidence[:500]}\n"
    )
    try:
        native = base.replace("/v1", "") + "/api/chat"
        body = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a careful data verifier for a free clinic directory. Never invent contacts.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        r = requests.post(native, json=body, timeout=45)
        r.raise_for_status()
        data = r.json()
        content = (data.get("message") or {}).get("content") or "{}"
        parsed = json.loads(content) if isinstance(content, str) else content
        return {
            "ok": bool(parsed.get("match")),
            "confidence": parsed.get("confidence") or "low",
            "reason": parsed.get("reason") or "",
            "provider": "ollama",
        }
    except Exception as e:
        # Fail open to human review — still stage, mark unchecked
        return {
            "ok": True,
            "confidence": "unchecked",
            "reason": f"Ollama unavailable ({e}); left for human approve",
            "provider": "none",
        }


def stage_update(
    name: str,
    field_updates: Dict[str, str],
    *,
    category: str,
    source: str,
    notes: str = "",
    verification: Optional[Dict[str, Any]] = None,
    address: str = "",
) -> Dict[str, Any]:
    pending = _load_pending()
    name_l = name.lower().strip()
    for it in pending.get("items") or []:
        if (
            (it.get("name") or "").lower().strip() == name_l
            and it.get("status") in ("proposed_update", "pending", "approved")
            and it.get("field_updates")
        ):
            it["field_updates"] = {**(it.get("field_updates") or {}), **field_updates}
            it["source"] = source
            it["notes"] = notes or it.get("notes")
            it["verification"] = verification or it.get("verification")
            it["updated_at"] = _now()
            _save_pending(pending)
            return it

    item = {
        "op_id": _op_id(),
        "kind": "proposed_update",
        "status": "proposed_update",
        "category": category,
        "name": name,
        "address": address,
        "field_updates": field_updates,
        "source": source,
        "notes": notes,
        "verification": verification,
        "city_scope": CITY_SCOPE,
        "state": __import__("agents.geo_scope", fromlist=["infer_state"]).infer_state(address),
        "created_at": _now(),
    }
    pending.setdefault("items", []).append(item)
    _save_pending(pending)
    return item


def enrich_one(
    listing: Dict[str, str],
    *,
    hrsa: Optional[List[Dict[str, str]]] = None,
    sheet: Optional[List[Dict[str, str]]] = None,
    discover_sites: bool = False,
    use_ollama: bool = True,
    fetch_sites: bool = True,
    all_listings: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Propose phone/website fills for one listing. Returns staged op or None."""
    updates: Dict[str, str] = {}
    sources: List[str] = []
    evidence_bits: List[str] = []

    need_phone = not _digits(listing.get("phone") or "")
    need_web = not (listing.get("website") or "").strip()
    website = (listing.get("website") or "").strip()

    # 1) Directory matches (HRSA / sheet)
    for label, directory in (("hrsa", hrsa or []), ("sheet", sheet or [])):
        if not directory:
            continue
        hit = match_directory(listing, directory)
        if not hit:
            continue
        if need_phone and hit.get("phone") and not updates.get("phone"):
            updates["phone"] = _fmt_phone(hit["phone"])
            sources.append(hit.get("source") or label)
            evidence_bits.append(f"{label} match score={hit.get('match_score')}")
        if need_web and hit.get("website") and not updates.get("website"):
            w = hit["website"]
            updates["website"] = w if w.startswith("http") else f"https://{w}"
            sources.append(hit.get("source") or label)
            website = updates["website"]
            need_web = False

    # 2) Parent-org / sibling site inference (free, no scraping)
    if need_web:
        parent = infer_parent_website(listing.get("name") or "")
        if parent:
            updates["website"] = parent
            sources.append("parent_org_map")
            website = parent
            need_web = False
            evidence_bits.append(f"parent org site {parent}")
        elif all_listings:
            sib = infer_sibling_website(listing, all_listings)
            if sib:
                updates["website"] = sib
                sources.append("sibling_listing")
                website = sib
                need_web = False
                evidence_bits.append(f"sibling site {sib}")

    # 3) Discover website (optional; DDG often blocked — best-effort)
    if need_web and discover_sites:
        found = discover_website_ddg(listing.get("name") or "", listing.get("address") or "")
        if found:
            updates["website"] = found
            sources.append("duckduckgo_html")
            website = found
            need_web = False
            evidence_bits.append(f"discovered site {found}")
            time.sleep(1.2)

    # 4) Org site scrape for phone
    if need_phone and fetch_sites and website:
        phones, used = phones_from_site(website)
        if phones:
            updates["phone"] = phones[0]
            sources.append(used)
            evidence_bits.append(f"phones on site: {phones[:3]}")

    # 5) Org site scrape for languages / services / hours when blank
    need_meta = (
        not (listing.get("languages") or "").strip()
        or not (listing.get("services") or "").strip()
        or not (listing.get("hours") or "").strip()
    )
    if need_meta and fetch_sites and website:
        fields, used = fields_from_site(website)
        if fields.get("languages") and not (listing.get("languages") or "").strip():
            updates["languages"] = fields["languages"]
            sources.append(used + "#lang")
            evidence_bits.append(f"languages≈{fields['languages']}")
        if fields.get("services") and not (listing.get("services") or "").strip():
            updates["services"] = fields["services"]
            sources.append(used + "#svc")
            evidence_bits.append(f"services≈{fields['services']}")
        if fields.get("hours") and not (listing.get("hours") or "").strip():
            updates["hours"] = fields["hours"]
            sources.append(used + "#hours")
            evidence_bits.append(f"hours≈{fields['hours']}")

    if not updates:
        return None

    verification = None
    if use_ollama:
        verification = ollama_verify_match(
            listing,
            candidate_phone=updates.get("phone", ""),
            candidate_website=updates.get("website", ""),
            evidence="; ".join(evidence_bits),
            candidate_updates=updates,
        )
        if verification.get("confidence") != "unchecked" and not verification.get("ok"):
            return {
                "skipped": True,
                "name": listing.get("name"),
                "reason": verification.get("reason"),
                "candidate": updates,
            }

    item = stage_update(
        listing["name"],
        updates,
        category=listing.get("category") or "healthcare",
        source="; ".join(dict.fromkeys(sources)) or "enrich_contacts",
        notes="; ".join(evidence_bits),
        verification=verification,
        address=listing.get("address") or "",
    )
    return item


def _gap_priority(g: Dict[str, str]) -> Tuple[int, int, str]:
    """Prefer directory-fillable web/phone, then lang/svc scrape when a site exists."""
    has_web = 1 if (g.get("website") or "").strip() else 0
    # lower tuple sorts first
    if g.get("missing_web") or g.get("missing_phone"):
        return (0, 0 if has_web else 1, g.get("name") or "")
    if g.get("missing_lang") or g.get("missing_svc") or g.get("missing_hours"):
        return (1, 0 if has_web else 1, g.get("name") or "")
    return (2, 1, g.get("name") or "")


def scan(
    *,
    categories: Optional[List[str]] = None,
    limit: int = 25,
    hrsa_path: Optional[Path] = None,
    sheet_path: Optional[Path] = None,
    discover_sites: bool = False,
    use_ollama: bool = True,
    fetch_sites: bool = True,
    websites_only: bool = False,
    phones_only: bool = False,
    fields_only: bool = False,
    state: Optional[str] = None,
) -> Dict[str, Any]:
    st = (state or ENRICH_STATE or "").upper() or None
    listings = parse_github_listings(categories, state=st)
    gaps = list_gaps(
        listings,
        websites_only=websites_only,
        phones_only=phones_only,
        fields_only=fields_only,
        state=st,
    )
    gaps = sorted(gaps, key=_gap_priority)
    if sheet_path is None and not hrsa_path:
        sheet_path = default_hrsa_sheet_for_state(st)
    hrsa = load_hrsa_index(hrsa_path, state=st) if hrsa_path else []
    sheet = load_hrsa_index(sheet_path, state=st) if sheet_path else []

    staged = []
    skipped = []
    for gap in gaps[: max(0, limit)]:
        result = enrich_one(
            gap,
            hrsa=hrsa,
            sheet=sheet,
            discover_sites=discover_sites,
            use_ollama=use_ollama,
            fetch_sites=fetch_sites,
            all_listings=listings,
        )
        if not result:
            continue
        if result.get("skipped"):
            skipped.append(result)
        else:
            if st and not result.get("state"):
                result["state"] = st
                # persist state on pending item
                try:
                    pending = _load_pending()
                    for it in pending.get("items") or []:
                        if it.get("op_id") == result.get("op_id"):
                            it["state"] = st
                    _save_pending(pending)
                except Exception:
                    pass
            staged.append(
                {
                    "op_id": result.get("op_id"),
                    "name": result.get("name"),
                    "state": st,
                    "field_updates": result.get("field_updates"),
                    "source": result.get("source"),
                    "verification": result.get("verification"),
                }
            )
        time.sleep(0.35)

    # High+known enrich fills → push immediately
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
        "state": st,
        "listings": len(listings),
        "gaps": len(gaps),
        "staged": len(staged),
        "skipped_by_ollama": len(skipped),
        "auto_apply_high": auto_info,
        "items": staged,
        "skipped": skipped,
        "hint": "Review with: python -m agents.clinic_ops --list  then --approve / --apply",
    }


def main() -> None:
    global CITY_SCOPE
    ap = argparse.ArgumentParser(description="Enrich missing clinic phone/website (stage only)")
    ap.add_argument("--scan", action="store_true", help="Scan GitHub gaps and stage proposals")
    ap.add_argument("--list-gaps", action="store_true", help="Show listings missing phone/website")
    ap.add_argument(
        "--category",
        action="append",
        choices=list(GITHUB_FILES.keys()),
        help="Limit to category (repeatable). Default: all",
    )
    ap.add_argument("--limit", type=int, default=25, help="Max gaps to attempt this run")
    ap.add_argument("--hrsa", type=str, help="Path to HRSA (or similar) CSV for IL/Chicago")
    ap.add_argument("--sheet-file", type=str, help="Local contacts CSV (name/phone/website columns)")
    ap.add_argument(
        "--discover-sites",
        action="store_true",
        help="Opt-in: DuckDuckGo HTML to find official sites when missing (not Google/Yelp)",
    )
    ap.add_argument("--websites-only", action="store_true", help="Only fill missing websites")
    ap.add_argument("--phones-only", action="store_true", help="Only fill missing phones")
    ap.add_argument(
        "--fields-only",
        action="store_true",
        help="Only fill missing languages / services / hours",
    )
    ap.add_argument("--no-fetch-sites", action="store_true", help="Do not fetch org pages for phones")
    ap.add_argument("--no-ollama", action="store_true", help="Skip Ollama verify (still stage for human)")
    ap.add_argument("--scope", default=None, help="chicago | national")
    ap.add_argument("--state", default=None, help="USPS state filter + resources/{ST}/ paths (e.g. IN)")
    args = ap.parse_args()

    if args.scope:
        CITY_SCOPE = args.scope.lower()

    cats = args.category or None

    if args.list_gaps:
        gaps = list_gaps(
            parse_github_listings(cats, state=args.state),
            websites_only=args.websites_only,
            phones_only=args.phones_only,
            fields_only=args.fields_only,
            state=args.state,
        )
        slim = [
            {
                "name": g["name"],
                "address": g.get("address"),
                "missing_phone": g.get("missing_phone"),
                "missing_web": g.get("missing_web"),
                "category": g.get("category"),
            }
            for g in gaps
        ]
        print(json.dumps({"count": len(slim), "gaps": slim[:200]}, indent=2, ensure_ascii=False))
        return

    if args.scan:
        result = scan(
            categories=cats,
            limit=args.limit,
            hrsa_path=Path(args.hrsa) if args.hrsa else None,
            sheet_path=Path(args.sheet_file) if args.sheet_file else None,
            discover_sites=args.discover_sites,
            use_ollama=not args.no_ollama,
            fetch_sites=not args.no_fetch_sites,
            websites_only=args.websites_only,
            phones_only=args.phones_only,
            fields_only=args.fields_only,
            state=args.state,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    ap.print_help()
    print(
        "\nTypical path:\n"
        "  1. ollama serve && ollama pull llama3\n"
        "  2. Download HRSA Health Center Sites CSV → filter IL → data/hrsa_il.csv\n"
        "     https://data.hrsa.gov/data/download?hmpgtitle=hmpg-hrsa-data\n"
        "  3. python -m agents.enrich_contacts --list-gaps\n"
        "  4. python -m agents.enrich_contacts --scan --hrsa data/hrsa_il.csv --limit 20\n"
        "  5. python -m agents.clinic_ops --notify   # or --list\n"
        "  6. approve / apply via Telegram or CLI\n"
        "  7. Local JSON refreshes automatically on apply\n"
    )


if __name__ == "__main__":
    main()
