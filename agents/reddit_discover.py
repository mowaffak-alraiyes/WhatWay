"""
Free Reddit discovery for Chicago refugee/immigrant resources.

Uses public Reddit JSON (no API key / no paid tier):
  https://www.reddit.com/r/.../search.json

Stages NEW candidates into pending_ops for Telegram ❤ / 👎 approval.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PENDING_PATH = DATA / "pending_ops.json"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass

UA = {"User-Agent": "WhatWayResourceBot/1.0 (local research; contact: local)"}
CITY_SCOPE = os.environ.get("CITY_SCOPE", "chicago").lower()

# Free public search targets (no OAuth)
SUBREDDITS = ["chicago", "Chicago", "AskChicago", "immigration", "refugees"]
QUERIES = [
    "free ESL Chicago",
    "refugee services Chicago",
    "immigration legal aid Chicago",
    "free clinic Chicago undocumented",
    "adult education GED Chicago",
    "shelter immigrant Chicago",
    "citizenship classes Chicago",
]

ORG_LINE = re.compile(
    r"(?i)\b((?:[A-Z][\w''&.-]+(?:\s+[A-Z][\w''&.-]+){1,6})"
    r"(?:\s+(?:Center|Centre|Clinic|House|Alliance|Association|Institute|Project|Ministry|Services|Coalition))?)\b"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _op_id() -> str:
    return "op_" + secrets.token_hex(3)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def _load_pending() -> Dict[str, Any]:
    if PENDING_PATH.exists():
        try:
            return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}


def _save_pending(payload: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _now()
    PENDING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def known_names() -> set:
    from agents.discover_new import load_known_names

    return load_known_names()


def guess_category(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("esl", "ged", "literacy", "school", "adult ed", "citizenship class")):
        return "education"
    if any(k in t for k in ("clinic", "health", "dental", "medical", "fqhc")):
        return "healthcare"
    return "resettlement"


def reddit_search(sub: str, query: str, limit: int = 15) -> List[Dict[str, Any]]:
    url = (
        f"https://www.reddit.com/r/{quote_plus(sub)}/search.json"
        f"?q={quote_plus(query)}&restrict_sr=1&sort=relevance&t=year&limit={limit}"
    )
    try:
        r = requests.get(url, headers=UA, timeout=25)
        if r.status_code != 200:
            return []
        children = ((r.json().get("data") or {}).get("children")) or []
        out = []
        for ch in children:
            d = ch.get("data") or {}
            title = d.get("title") or ""
            selftext = d.get("selftext") or ""
            out.append(
                {
                    "title": title,
                    "text": selftext[:1500],
                    "url": f"https://www.reddit.com{d.get('permalink') or ''}",
                    "subreddit": d.get("subreddit") or sub,
                }
            )
        return out
    except Exception:
        return []


def extract_candidates(post: Dict[str, Any]) -> List[Dict[str, str]]:
    blob = f"{post.get('title') or ''}\n{post.get('text') or ''}"
    # Prefer lines that look like org recommendations
    found = []
    seen = set()
    for m in ORG_LINE.finditer(blob):
        name = re.sub(r"\s+", " ", m.group(1)).strip(" .-")
        if len(name) < 6 or len(name) > 80:
            continue
        # Filter generic phrases
        low = name.lower()
        if any(
            x in low
            for x in (
                "chicago",
                "anyone",
                "looking",
                "please",
                "thanks",
                "reddit",
                "http",
                "www",
            )
        ) and "center" not in low and "alliance" not in low and "clinic" not in low:
            # allow if it's "X of Chicago" style with more tokens
            if not re.search(r"(?i)\b(center|clinic|house|alliance|institute|ministry|services)\b", name):
                continue
        n = _norm(name)
        if n in seen:
            continue
        seen.add(n)
        found.append(
            {
                "name": name,
                "notes": f"Mentioned on r/{post.get('subreddit')}: {post.get('title')}",
                "source_url": post.get("url") or "",
                "raw": blob[:400],
            }
        )
    return found[:5]


def ollama_verify(candidate: Dict[str, str], category: str) -> Dict[str, Any]:
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL") or "llama3"
    prompt = (
        "Verify a Chicago community org for a refugee resource directory. "
        'Reply ONLY JSON: {"ok": true|false, "confidence": "high"|"medium"|"low", "reason": "..."}\n'
        "Reject generic phrases, businesses unrelated to immigrant/refugee help, or non-Chicago orgs.\n"
        f"Category hint: {category}\n"
        f"Name: {candidate.get('name')}\n"
        f"Reddit context: {candidate.get('raw', '')[:500]}\n"
    )
    try:
        native = base.replace("/v1", "") + "/api/chat"
        body = json.dumps(
            {
                "model": model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": "Careful verifier. Prefer reject when unsure."},
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode()
        r = requests.post(native, data=body, headers={"Content-Type": "application/json"}, timeout=90)
        r.raise_for_status()
        parsed = json.loads(((r.json().get("message") or {}).get("content") or "").strip())
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
            "reason": f"Ollama unavailable ({e}); human review",
            "provider": "none",
        }


def stage_new(candidate: Dict[str, str], category: str, verification: Dict[str, Any]) -> Dict[str, Any]:
    from agents import tools as ops_tools
    from agents.geo_scope import infer_state, resources_state

    pending = _load_pending()
    name = candidate.get("name") or "Unknown"
    address = candidate.get("address") or f"Chicago, {resources_state()}"
    item = {
        "op_id": _op_id(),
        "kind": "proposed",
        "status": "proposed",
        "category": category,
        "name": name,
        "address": address,
        "zip": "",
        "phone": "",
        "website": "",
        "services": [],
        "languages": [],
        "hours": "",
        "notes": candidate.get("notes") or "",
        "source": "reddit_free_json",
        "source_url": candidate.get("source_url") or "",
        "needs_approval": True,
        "region": CITY_SCOPE,
        "state": infer_state(address),
        "verification": verification,
        "created_at": _now(),
    }
    item["github_draft"] = ops_tools.draft_github_block(
        name=name,
        address=address,
        next_id=999,
    )
    if item["notes"]:
        item["github_draft"] += f"\n📝 {item['notes'][:200]}"
    pending.setdefault("items", []).append(item)
    _save_pending(pending)
    return item


def scan(*, limit: int = 8, use_ollama: bool = True) -> Dict[str, Any]:
    known = known_names()
    staged = []
    skipped = []
    seen_names = set()

    for sub in SUBREDDITS:
        for q in QUERIES:
            if len(staged) >= limit:
                break
            posts = reddit_search(sub, q, limit=10)
            time.sleep(1.1)  # be gentle, free public endpoint
            for post in posts:
                for cand in extract_candidates(post):
                    if len(staged) >= limit:
                        break
                    n = _norm(cand["name"])
                    if n in seen_names:
                        continue
                    seen_names.add(n)
                    if n in known or any(n in k or k in n for k in known if len(n) > 8):
                        skipped.append({"name": cand["name"], "reason": "already_listed"})
                        continue
                    cat = guess_category(f"{cand.get('notes')} {cand.get('raw')}")
                    verification = (
                        ollama_verify(cand, cat)
                        if use_ollama
                        else {"ok": True, "confidence": "unchecked", "reason": "skipped", "provider": "none"}
                    )
                    if not verification.get("ok") and verification.get("confidence") != "unchecked":
                        skipped.append({"name": cand["name"], "reason": verification.get("reason")})
                        continue
                    item = stage_new(cand, cat, verification)
                    known.add(n)
                    staged.append(
                        {
                            "op_id": item["op_id"],
                            "name": cand["name"],
                            "category": cat,
                            "confidence": verification.get("confidence"),
                            "source": "reddit",
                        }
                    )
        if len(staged) >= limit:
            break

    return {
        "ok": True,
        "staged": len(staged),
        "skipped": len(skipped),
        "items": staged,
        "skipped_items": skipped[:30],
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--no-ollama", action="store_true")
    args = ap.parse_args()
    print(json.dumps(scan(limit=args.limit, use_ollama=not args.no_ollama), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
