"""
Overnight Aidr ops worker — free sources only.

Cycles:
  1) enrich missing phone/website/languages/services/hours (org sites + DDG)
  2) discover NEW education/resettlement seeds (Ollama verify)
  3) Reddit free JSON search for more candidates
  4) Telegram notify open proposals (❤ / 👎)
  5) Optional: auto-apply already-approved ops

Does NOT replace Telegram poll — run poll separately.

  python -m agents.overnight_ops --interval-min 60
  python -m agents.overnight_ops --once
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notify(msg: str) -> None:
    try:
        from agents.telegram_bridge import send_message, _allowed_chats

        for c in _allowed_chats():
            send_message(c, msg[:3900])
            time.sleep(0.3)
    except Exception as e:
        print(f"notify error: {e}")


def run_cycle(
    *,
    enrich_limit: int = 12,
    discover_limit: int = 6,
    reddit_limit: int = 5,
    auto_apply: bool = False,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"at": _now(), "steps": {}}

    # 1) Enrich gaps across all categories
    try:
        from agents import enrich_contacts

        enrich = enrich_contacts.scan(
            categories=["healthcare", "education", "resettlement"],
            limit=enrich_limit,
            discover_sites=True,
            use_ollama=True,
            fetch_sites=True,
        )
        summary["steps"]["enrich"] = {
            "staged": enrich.get("staged"),
            "gaps": enrich.get("gaps"),
            "skipped": enrich.get("skipped_by_ollama"),
        }
    except Exception as e:
        summary["steps"]["enrich"] = {"error": str(e)}

    # 2) Seed discover (education + resettlement)
    try:
        from agents import discover_new

        disc = discover_new.scan(
            ["education", "resettlement"],
            limit=discover_limit,
            use_ollama=True,
            discover_sites=True,
        )
        summary["steps"]["discover_new"] = {
            "staged": disc.get("staged"),
            "skipped": disc.get("skipped"),
            "items": disc.get("items"),
        }
    except Exception as e:
        summary["steps"]["discover_new"] = {"error": str(e)}

    # 3) Reddit free JSON
    try:
        from agents import reddit_discover

        red = reddit_discover.scan(limit=reddit_limit, use_ollama=True)
        summary["steps"]["reddit"] = {
            "staged": red.get("staged"),
            "skipped": red.get("skipped"),
            "items": red.get("items"),
        }
    except Exception as e:
        summary["steps"]["reddit"] = {"error": str(e)}

    # 4) Confidence tiers: auto-apply high+known; ask medium/low via Telegram
    try:
        from agents import clinic_ops
        from agents import telegram_bridge
        from agents.confidence import drain_auto_apply, tier_action, confidence_of

        open_items = clinic_ops.list_pending("open")
        auto = drain_auto_apply(open_items)
        summary["steps"]["auto_apply_high"] = auto
        ask_items = [it for it in clinic_ops.list_pending("open") if tier_action(it) == "ask"]
        skipped = [
            {"op_id": it.get("op_id"), "name": it.get("name"), "conf": confidence_of(it)}
            for it in clinic_ops.list_pending("open")
            if tier_action(it) == "skip"
        ]
        summary["steps"]["skipped_low"] = skipped
        summary["open_count"] = len(ask_items)
        n_auto = int(auto.get("auto_apply") or 0)

        if ask_items:
            notified = telegram_bridge.notify_pending(ask_items, digest_by_state=True)
            summary["steps"]["notify"] = notified
            from agents.geo_scope import group_by_state

            by_st = group_by_state(ask_items)
            state_lines = "\n".join(f"  {st}: {len(g)}" for st, g in sorted(by_st.items()))
            _notify(
                f"🌙 Aidr overnight @ {_now()[:16]}Z\n"
                f"Auto-applied (high+known): {n_auto}\n"
                f"Needs ❤ by state:\n{state_lines}\n"
                f"Skipped low: {len(skipped)}\n"
                f"❤ = approve+apply · 👎 = reject"
            )
        else:
            summary["steps"]["notify"] = {"messages_sent": 0}
            if n_auto:
                _notify(
                    f"🌙 Aidr overnight @ {_now()[:16]}Z\n"
                    f"Auto-applied {n_auto} high+known updates. No cards needing ❤."
                )
    except Exception as e:
        summary["steps"]["notify"] = {"error": str(e)}

    # 5) Optional drain any leftover approved → GitHub
    if auto_apply:
        try:
            from agents import github_apply

            summary["steps"]["apply_all"] = github_apply.apply_all_approved(dry_run=False)
        except Exception as e:
            summary["steps"]["apply_all"] = {"error": str(e)}

    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Overnight free discover/enrich + Telegram ask")
    ap.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    ap.add_argument("--interval-min", type=int, default=60, help="Minutes between cycles (default 60)")
    ap.add_argument("--enrich-limit", type=int, default=12)
    ap.add_argument("--discover-limit", type=int, default=6)
    ap.add_argument("--reddit-limit", type=int, default=5)
    ap.add_argument(
        "--auto-apply",
        action="store_true",
        help="Also push already-approved ops each cycle (default: you apply manually)",
    )
    args = ap.parse_args()

    print(
        f"Overnight ops starting (interval={args.interval_min}m). "
        "Telegram poll should run separately for ❤/👎."
    )
    while True:
        try:
            run_cycle(
                enrich_limit=args.enrich_limit,
                discover_limit=args.discover_limit,
                reddit_limit=args.reddit_limit,
                auto_apply=args.auto_apply,
            )
        except Exception as e:
            print(f"cycle error: {e}")
            _notify(f"⚠️ Overnight cycle error: {e}")
        if args.once:
            break
        time.sleep(max(5, args.interval_min) * 60)


if __name__ == "__main__":
    main()
