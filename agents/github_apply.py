"""
Apply Telegram-approved clinic drafts to refugee-resources GitHub.

Only runs for status=approved. Never called automatically by the LLM.
"""

from __future__ import annotations

import json
import os
import core.env  # noqa: F401 — maps legacy AIDR_* vars onto WHATWAY_*
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PENDING_PATH = DATA / "pending_ops.json"

REPO = os.environ.get("RESOURCES_GITHUB_REPO", "mowaffak-alraiyes/refugee-resources")


def _category_files(state: Optional[str] = None) -> Dict[str, str]:
    from agents.geo_scope import category_files_for_state

    return category_files_for_state(state)


# Lazy snapshot for callers that still import CATEGORY_FILES
def __getattr__(name: str):
    if name == "CATEGORY_FILES":
        return _category_files()
    raise AttributeError(name)


def _pending() -> Dict[str, Any]:
    if PENDING_PATH.exists():
        return json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    return {"items": []}


def _save(payload: Dict[str, Any]) -> None:
    PENDING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def redact_secrets(text: str) -> str:
    """Strip PATs / embedded clone credentials from error strings (never send to Telegram)."""
    s = str(text or "")
    s = re.sub(r"https://x-access-token:[^@\s]+@", "https://x-access-token:***@", s)
    s = re.sub(r"\bgho_[A-Za-z0-9]{20,}\b", "gho_***", s)
    s = re.sub(r"\bghp_[A-Za-z0-9]{20,}\b", "ghp_***", s)
    s = re.sub(r"\bgithub_pat_[A-Za-z0-9_]+\b", "github_pat_***", s)
    s = re.sub(r"\bghr_[A-Za-z0-9]{20,}\b", "ghr_***", s)
    return s


def _git_clone_repo(dest: Path, token: str) -> None:
    """
    Shallow-clone RESOURCES repo without embedding the token in argv.
    (Embedding leaks into CalledProcessError → Telegram.)
    Auth via GIT_ASKPASS + username x-access-token.
    """
    askpass = tempfile.NamedTemporaryFile("w", prefix="ww-askpass-", suffix=".sh", delete=False)
    try:
        askpass.write('#!/bin/sh\ncase "$1" in *Username*) echo x-access-token;; *) echo "$WHATWAY_GIT_PASSWORD";; esac\n')
        askpass.close()
        os.chmod(askpass.name, 0o700)
        env = {
            **os.environ,
            "GIT_ASKPASS": askpass.name,
            "SSH_ASKPASS": askpass.name,
            "GIT_TERMINAL_PROMPT": "0",
            "WHATWAY_GIT_PASSWORD": token,
        }
        # No token in URL / argv
        url = f"https://github.com/{REPO}.git"
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError(
                f"git clone failed (exit {proc.returncode})"
                + (f": {redact_secrets(err[:400])}" if err else "")
            )
    finally:
        try:
            os.unlink(askpass.name)
        except Exception:
            pass


def _git_push(repo_dir: Path, token: str) -> None:
    askpass = tempfile.NamedTemporaryFile("w", prefix="ww-askpass-", suffix=".sh", delete=False)
    try:
        askpass.write('#!/bin/sh\ncase "$1" in *Username*) echo x-access-token;; *) echo "$WHATWAY_GIT_PASSWORD";; esac\n')
        askpass.close()
        os.chmod(askpass.name, 0o700)
        env = {
            **os.environ,
            "GIT_ASKPASS": askpass.name,
            "SSH_ASKPASS": askpass.name,
            "GIT_TERMINAL_PROMPT": "0",
            "WHATWAY_GIT_PASSWORD": token,
        }
        proc = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=repo_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError(
                f"git push failed (exit {proc.returncode})"
                + (f": {redact_secrets(err[:400])}" if err else "")
            )
    finally:
        try:
            os.unlink(askpass.name)
        except Exception:
            pass


def _category_file(item: Dict[str, Any]) -> str:
    from agents.geo_scope import category_rel, state_of

    return category_rel(item.get("category") or "healthcare", state_of(item))


def _next_id(text: str) -> int:
    ids = [int(m.group(1)) for m in re.finditer(r"(?m)^\s*(\d+)\.\s+", text)]
    return (max(ids) + 1) if ids else 1


def _street_key(text: str) -> str:
    """Normalize for address overlap (street number + first street token)."""
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    m = re.search(r"\b(\d+\w*)\s+(\w+)", t)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return t[:24]


def _block_address_line(part: str) -> str:
    for line in part.splitlines()[1:6]:
        s = line.strip()
        if not s:
            continue
        if s.startswith(("📞", "🌐", "📧", "📝", "🗣", "🏥", "⏰", "#")):
            continue
        low = s.lower()
        if low.startswith(("phone", "website", "http", "hours", "services", "languages")):
            continue
        return s
    return ""


def _apply_update_block(text: str, name: str, updates: Dict[str, str], address_hint: str = "") -> str:
    """Replace phone/website/hours lines inside a named clinic block.

    If address_hint is set and multiple entries share a name, update only the
    block whose address best matches the hint (street number + name).
    """
    parts = re.split(r"(?m)(?=^\s*\d+\.\s+)", text)
    name_l = name.lower().strip()
    hint_l = (address_hint or "").lower().strip()
    hint_key = _street_key(hint_l) if hint_l else ""

    # Collect candidate indices that match the clinic name
    candidates: List[int] = []
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        first = part.splitlines()[0] if part.splitlines() else ""
        m = re.match(r"^\s*\d+\.\s+(.+)$", first)
        entry_name = (m.group(1).strip() if m else "").lower()
        if entry_name == name_l:
            candidates.append(i)

    target_i: Optional[int] = None
    if candidates:
        if hint_key:
            # Prefer exact street-key match, then substring overlap
            scored = []
            for i in candidates:
                addr = _block_address_line(parts[i]).lower()
                key = _street_key(addr)
                score = 0
                if key and key == hint_key:
                    score = 100
                elif hint_key and hint_key in addr:
                    score = 80
                elif key and key in hint_l:
                    score = 70
                elif addr and (addr[:18] in hint_l or hint_l[:18] in addr):
                    score = 40
                scored.append((score, i))
            scored.sort(key=lambda x: (-x[0], x[1]))
            if scored and scored[0][0] > 0:
                target_i = scored[0][1]
            else:
                target_i = candidates[0]
        else:
            target_i = candidates[0]

    out = []
    for i, part in enumerate(parts):
        if not part.strip() or i != target_i:
            out.append(part)
            continue

        lines = part.splitlines()
        new_lines = []
        replaced = set()
        address_done = False
        for j, line in enumerate(lines):
            low = line.lower()
            stripped = line.strip()
            if (
                j > 0
                and "address" in updates
                and not address_done
                and stripped
                and not stripped.startswith(("📞", "🌐", "📧", "📝", "🗣", "🏥", "⏰", "#"))
                and not low.startswith(("phone", "website", "http", "hours", "services", "languages"))
                and ("il" in low or re.search(r"\b\d{5}\b", stripped) or "," in stripped)
            ):
                new_lines.append(updates["address"])
                replaced.add("address")
                address_done = True
                continue
            if "phone" in updates and (stripped.startswith("📞") or low.startswith("phone")):
                new_lines.append(f"📞 {updates['phone']}")
                replaced.add("phone")
            elif "website" in updates and (
                stripped.startswith("🌐") or "http" in low or low.startswith("website")
            ):
                web = updates["website"]
                if not web.startswith("http"):
                    web = "https://" + web
                new_lines.append(f"🌐 {web}")
                replaced.add("website")
            elif "email" in updates and (stripped.startswith("📧") or low.startswith("email")):
                new_lines.append(f"📧 {updates['email']}")
                replaced.add("email")
            elif "hours" in updates and (stripped.startswith("⏰") or low.startswith("hours")):
                new_lines.append(f"⏰ Hours: {updates['hours']}")
                replaced.add("hours")
            elif "services" in updates and (stripped.startswith("🏥") or low.startswith("services")):
                from core.labels import humanize_services

                svc = humanize_services(updates["services"])
                new_lines.append(f"🏥 Services: {svc}")
                replaced.add("services")
            elif "languages" in updates and (stripped.startswith("🗣") or low.startswith("language")):
                lang = updates["languages"]
                if not lang.lower().startswith("language"):
                    lang = f"Languages: {lang}"
                new_lines.append(f"🗣 {lang}" if not lang.startswith("🗣") else lang)
                replaced.add("languages")
            else:
                new_lines.append(line)
        for k, v in updates.items():
            if k in replaced:
                continue
            if k == "phone":
                # Insert phone after address / notes, before website if present
                insert_at = len(new_lines)
                for idx, ln in enumerate(new_lines):
                    if ln.strip().startswith("🌐") or "http" in ln.lower():
                        insert_at = idx
                        break
                new_lines.insert(insert_at, f"📞 {v}")
            elif k == "website":
                web = v if v.startswith("http") else f"https://{v}"
                new_lines.append(f"🌐 {web}")
            elif k == "email":
                new_lines.append(f"📧 {v}")
            elif k == "hours":
                new_lines.append(f"⏰ Hours: {v}")
            elif k == "address" and len(new_lines) >= 1:
                new_lines.insert(1, v)
            elif k == "services":
                from core.labels import humanize_services

                svc = humanize_services(v)
                new_lines.append(f"🏥 Services: {svc}")
            elif k == "languages":
                lang = v if v.lower().startswith("language") else f"Languages: {v}"
                new_lines.append(f"🗣 {lang}" if not lang.startswith("🗣") else lang)
        out.append("\n".join(new_lines))
        if not part.endswith("\n"):
            out[-1] = out[-1]
    return "".join(
        p if p.endswith("\n") or not p else p + "\n" for p in out
    )


def apply_approved(op_id: str, dry_run: bool = False) -> Dict[str, Any]:
    pending = _pending()
    item = next((i for i in pending.get("items", []) if i.get("op_id") == op_id), None)
    if not item:
        return {"ok": False, "error": f"Unknown op_id {op_id}"}
    if item.get("status") != "approved":
        return {"ok": False, "error": f"{op_id} is not approved (status={item.get('status')})"}

    token = _github_token()
    if not token and not dry_run:
        return {"ok": False, "error": "No GitHub token (set GITHUB_TOKEN or use git credential)"}

    rel = _category_file(item)

    def _build(text: str) -> Tuple[str, str]:
        if item.get("field_updates"):
            new_text = _apply_update_block(
                text,
                item.get("name") or "",
                item.get("field_updates") or {},
                address_hint=item.get("address") or "",
            )
            commit_msg = f"Update {item.get('name')}: {', '.join(item.get('field_updates', {}))}"
            return new_text, commit_msg
        draft = item.get("github_draft") or ""
        if not draft.strip():
            raise ValueError("No github_draft on item")
        nid = _next_id(text)
        draft_lines = draft.splitlines()
        if draft_lines:
            draft_lines[0] = re.sub(r"^\s*\d+\.", f"{nid}.", draft_lines[0])
        block = "\n".join(draft_lines).strip() + "\n\n"
        new_text = text.rstrip() + "\n\n" + block
        return new_text, f"Add clinic: {item.get('name')}"

    if dry_run:
        # Prefer Contents API (no raw CDN lag); fall back to raw
        text = _fetch_file_text(rel, token)
        try:
            new_text, commit_msg = _build(text)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {
            "ok": True,
            "dry_run": True,
            "file": rel,
            "commit_msg": commit_msg,
            "changed": new_text != text,
            "preview_tail": new_text[-500:],
        }

    # Clone = source of truth (avoids stale raw.githubusercontent.com)
    try:
        with tempfile.TemporaryDirectory(prefix="ww-resources-") as tmp:
            repo_dir = Path(tmp) / "repo"
            _git_clone_repo(repo_dir, token or "")
            target = repo_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text(
                    f"# {(item.get('state') or 'IL')} — placeholder\n\n",
                    encoding="utf-8",
                )
            text = target.read_text(encoding="utf-8")
            try:
                new_text, commit_msg = _build(text)
            except ValueError as e:
                return {"ok": False, "error": str(e)}

            if new_text == text:
                item["status"] = "applied"
                item["applied_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
                item["applied_file"] = rel
                item["apply_note"] = "no_github_diff"
                _save(pending)
                refresh_info: Dict[str, Any] = {"refreshed": False}
                try:
                    refresh_info = refresh_local_json(item.get("category") or rel)
                except Exception as e:
                    refresh_info = {"refreshed": False, "error": redact_secrets(str(e))}
                return {
                    "ok": True,
                    "op_id": op_id,
                    "file": rel,
                    "commit_msg": commit_msg,
                    "skipped_commit": True,
                    "reason": "GitHub already had this content (or no matching block change)",
                    "repo": REPO,
                    "local_json": refresh_info,
                }

            target.write_text(new_text, encoding="utf-8")
            subprocess.check_call(["git", "add", rel], cwd=repo_dir)
            subprocess.check_call(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_dir,
                env={
                    **os.environ,
                    "GIT_AUTHOR_NAME": "WhatWay Clinic Ops",
                    "GIT_AUTHOR_EMAIL": "ww-ops@local",
                    "GIT_COMMITTER_NAME": "WhatWay Clinic Ops",
                    "GIT_COMMITTER_EMAIL": "ww-ops@local",
                },
            )
            _git_push(repo_dir, token or "")
    except Exception as e:
        return {"ok": False, "error": redact_secrets(str(e)), "op_id": op_id}

    item["status"] = "applied"
    item["applied_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    item["applied_file"] = rel
    _save(pending)

    refresh_info = {"refreshed": False}
    try:
        refresh_info = refresh_local_json(item.get("category") or rel)
    except Exception as e:
        refresh_info = {"refreshed": False, "error": redact_secrets(str(e))}

    return {
        "ok": True,
        "op_id": op_id,
        "file": rel,
        "commit_msg": commit_msg,
        "repo": REPO,
        "local_json": refresh_info,
    }


def _fetch_file_text(rel: str, token: Optional[str] = None) -> str:
    """Fetch file via GitHub Contents API (fresher than raw CDN)."""
    tok = token or _github_token()
    headers = {"Accept": "application/vnd.github.raw"}
    if tok:
        headers["Authorization"] = f"token {tok}"
    url = f"https://api.github.com/repos/{REPO}/contents/{rel}"
    r = requests.get(url, headers=headers, timeout=45)
    if r.status_code == 200 and r.text:
        return r.text
    raw = f"https://raw.githubusercontent.com/{REPO}/main/{rel}"
    r2 = requests.get(raw, timeout=30)
    r2.raise_for_status()
    return r2.text


def _mutate_text_for_item(text: str, item: Dict[str, Any]) -> Tuple[str, str]:
    """Apply one approved item to in-memory file text. Returns (new_text, short_msg)."""
    if item.get("field_updates"):
        new_text = _apply_update_block(
            text,
            item.get("name") or "",
            item.get("field_updates") or {},
            address_hint=item.get("address") or "",
        )
        msg = f"{item.get('name')}: {', '.join(item.get('field_updates', {}))}"
        return new_text, msg
    draft = item.get("github_draft") or ""
    if not draft.strip():
        raise ValueError(f"{item.get('op_id')}: No github_draft")
    nid = _next_id(text)
    draft_lines = draft.splitlines()
    if draft_lines:
        draft_lines[0] = re.sub(r"^\s*\d+\.", f"{nid}.", draft_lines[0])
    block = "\n".join(draft_lines).strip() + "\n\n"
    new_text = text.rstrip() + "\n\n" + block
    return new_text, f"Add {item.get('name')}"


def apply_all_approved(dry_run: bool = False) -> Dict[str, Any]:
    """Apply every status=approved item in one clone/push per file (no CDN races)."""
    pending = _pending()
    approved = [i for i in pending.get("items", []) if i.get("status") == "approved" and i.get("op_id")]
    if not approved:
        return {"ok": True, "total": 0, "succeeded": 0, "failed": 0, "results": []}

    token = _github_token()
    if not token and not dry_run:
        return {"ok": False, "error": "No GitHub token (set GITHUB_TOKEN or use git credential)", "total": len(approved)}

    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for item in approved:
        by_file.setdefault(_category_file(item), []).append(item)

    results: List[Dict[str, Any]] = []

    if dry_run:
        for rel, items in by_file.items():
            text = _fetch_file_text(rel, token)
            for item in items:
                try:
                    new_text, msg = _mutate_text_for_item(text, item)
                    results.append(
                        {
                            "ok": True,
                            "dry_run": True,
                            "op_id": item.get("op_id"),
                            "file": rel,
                            "commit_msg": msg,
                            "changed": new_text != text,
                        }
                    )
                    text = new_text  # chain so later ops see earlier edits
                except Exception as e:
                    results.append({"ok": False, "op_id": item.get("op_id"), "error": str(e)})
        ok_n = sum(1 for r in results if r.get("ok"))
        return {
            "ok": ok_n == len(results),
            "total": len(results),
            "succeeded": ok_n,
            "failed": len(results) - ok_n,
            "results": results,
        }

    try:
        with tempfile.TemporaryDirectory(prefix="ww-resources-") as tmp:
            repo_dir = Path(tmp) / "repo"
            _git_clone_repo(repo_dir, token or "")

            for rel, items in by_file.items():
                target = repo_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_text("# placeholder\n\n", encoding="utf-8")
                text = target.read_text(encoding="utf-8")
                original = text
                msgs: List[str] = []
                for item in items:
                    try:
                        text, msg = _mutate_text_for_item(text, item)
                        msgs.append(msg)
                        results.append({"ok": True, "op_id": item.get("op_id"), "file": rel, "msg": msg})
                    except Exception as e:
                        results.append(
                            {"ok": False, "op_id": item.get("op_id"), "error": redact_secrets(str(e))}
                        )

                if text == original:
                    for item in items:
                        if any(r.get("op_id") == item.get("op_id") and r.get("ok") for r in results):
                            item["status"] = "applied"
                            item["applied_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
                            item["applied_file"] = rel
                            item["apply_note"] = "no_github_diff"
                    continue

                target.write_text(text, encoding="utf-8")
                subprocess.check_call(["git", "add", rel], cwd=repo_dir)
                commit_msg = "Apply approved clinic ops (" + "; ".join(msgs[:8]) + ")"
                if len(msgs) > 8:
                    commit_msg += f"; +{len(msgs) - 8} more"
                subprocess.check_call(
                    ["git", "commit", "-m", commit_msg[:200]],
                    cwd=repo_dir,
                    env={
                        **os.environ,
                        "GIT_AUTHOR_NAME": "WhatWay Clinic Ops",
                        "GIT_AUTHOR_EMAIL": "ww-ops@local",
                        "GIT_COMMITTER_NAME": "WhatWay Clinic Ops",
                        "GIT_COMMITTER_EMAIL": "ww-ops@local",
                    },
                )
                for item in items:
                    if any(r.get("op_id") == item.get("op_id") and r.get("ok") for r in results):
                        item["status"] = "applied"
                        item["applied_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
                        item["applied_file"] = rel

            _git_push(repo_dir, token or "")
    except Exception as e:
        return {
            "ok": False,
            "error": redact_secrets(str(e)),
            "total": len(approved),
            "succeeded": sum(1 for r in results if r.get("ok")),
            "failed": len(approved) - sum(1 for r in results if r.get("ok")),
            "results": results,
        }

    _save(pending)

    # Refresh local JSON once per touched category
    cats = {i.get("category") or "healthcare" for i in approved}
    refresh: Dict[str, Any] = {}
    for cat in cats:
        try:
            refresh[str(cat)] = refresh_local_json(str(cat))
        except Exception as e:
            refresh[str(cat)] = {"refreshed": False, "error": str(e)}

    ok_n = sum(1 for r in results if r.get("ok"))
    return {
        "ok": ok_n == len(results),
        "total": len(results),
        "succeeded": ok_n,
        "failed": len(results) - ok_n,
        "results": results,
        "local_json": refresh,
        "batched": True,
    }


def refresh_local_json(category_or_file: str) -> Dict[str, Any]:
    """
    Rebuild data/*.json from GitHub .txt so WhatWay search sees applied edits.
    Works from CLI (no Streamlit cache required).
    """
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Avoid Streamlit runtime errors when importing data_loader from CLI
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

    import data_loader

    tok = _github_token()
    if tok:
        os.environ.setdefault("GITHUB_TOKEN", tok)

    key = (category_or_file or "").lower()
    if "educ" in key:
        cat = "Education"
    elif "legal" in key or "shelter" in key or "resettle" in key:
        cat = "Resettlement / Legal / Shelter"
    else:
        cat = "Healthcare"

    items = data_loader.load_category_data(cat, force_refresh=True)
    return {"refreshed": True, "category": cat, "count": len(items)}
