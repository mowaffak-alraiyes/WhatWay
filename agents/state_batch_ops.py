"""
State-by-state Aidr batch:
  1) Find-a-HC fetch (250mi hubs+surrounding) → stage healthcare ops
  2) Ollama-backed enrich of missing phone/web/languages on that state's GitHub files
  3) Discover education + resettlement seeds for that state (Ollama verify)
  4) Telegram digest + limited cards; remind `approve all ST`

  python -m agents.state_batch_ops --states IL,IN,CO,CA
  python -m agents.state_batch_ops --states CO --skip-fetch   # enrich+discover only
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except Exception:
    pass


def _notify(msg: str) -> None:
    from agents.telegram_bridge import send_message, _allowed_chats

    for c in _allowed_chats():
        send_message(c, msg[:3900])
        time.sleep(0.25)


def _notify_batch(items: List[Dict[str, Any]], state: str, *, card_limit: int = 20) -> Dict[str, Any]:
    from agents import telegram_bridge
    from agents.tools import format_telegram_digest
    from agents.telegram_bridge import send_message, _allowed_chats

    open_items = [i for i in items if i.get("status") in ("proposed", "proposed_update")]
    if not open_items:
        return {"ok": True, "items": 0}
    digest = format_telegram_digest(state, open_items)
    extra = (
        f"\n\nBatch ready for {state}.\n"
        f"Showing {min(card_limit, len(open_items))} of {len(open_items)} cards.\n"
        f"When done reviewing: `approve all {state}`"
    )
    for chat in _allowed_chats():
        send_message(chat, digest + extra)
    notified = telegram_bridge.notify_pending(open_items[:card_limit], digest_by_state=False)
    return {"digest": True, "notify": notified, "total": len(open_items)}


def run_state(
    state: str,
    *,
    skip_fetch: bool = False,
    skip_discover: bool = False,
    enrich_limit: int = 10,
    discover_limit: int = 8,
    card_limit: int = 20,
    use_ollama: bool = True,
    notify: bool = True,
) -> Dict[str, Any]:
    st = state.upper()
    summary: Dict[str, Any] = {"state": st, "steps": {}}
    staged_ops: List[Dict[str, Any]] = []

    # 1) Healthcare Find-a-HC
    if not skip_fetch:
        try:
            from agents.fetch_hrsa_finder import fetch_states, write_xlsx
            from agents import import_hrsa_xlsx as hrsa
            from agents.geo_scope import filter_rows_by_hubs
            from agents.enrich_contacts import _load_pending, _save_pending

            print(f"=== [{st}] Find-a-HC fetch ===", flush=True)
            result = fetch_states([st], radius_miles=250.0, keep_states_only=True)
            rows = result["by_state"].get(st) or []
            out_dir = ROOT / "data" / "hrsa_finder"
            xlsx = out_dir / f"health_centers_{st}.xlsx"
            write_xlsx(rows, xlsx)
            hc_rows = hrsa.load_xlsx_rows(xlsx, [st])
            hc_rows = filter_rows_by_hubs(hc_rows, radius_miles=250.0)
            current = hrsa.fetch_healthcare_text(st)
            merged, stats = hrsa.merge(current, hc_rows, [])
            staged = hrsa.stage_hrsa_changes(st, stats, hc_rows)
            pending = _load_pending()
            ids = {i.get("op_id") for i in staged}
            for it in pending.get("items") or []:
                if it.get("op_id") in ids:
                    it["state"] = st
                    it["source"] = it.get("source") or "hrsa_finder"
            _save_pending(pending)
            staged_ops.extend(staged)
            summary["steps"]["finder"] = {
                "unique": len(rows),
                "added": stats.get("added"),
                "updated": stats.get("updated"),
                "staged": len(staged),
            }
            print(json.dumps(summary["steps"]["finder"], indent=2), flush=True)
        except Exception as e:
            summary["steps"]["finder"] = {"error": str(e)}
            print(f"[{st}] finder error: {e}", flush=True)
    else:
        summary["steps"]["finder"] = {"skipped": True}

    # 2) Ollama enrich missing fields on that state's listings
    try:
        from agents import enrich_contacts

        print(f"=== [{st}] Ollama enrich gaps ===", flush=True)
        enrich = enrich_contacts.scan(
            categories=["healthcare", "education", "resettlement"],
            limit=enrich_limit,
            discover_sites=True,
            use_ollama=use_ollama,
            fetch_sites=True,
            state=st,
        )
        summary["steps"]["enrich"] = {
            "listings": enrich.get("listings"),
            "gaps": enrich.get("gaps"),
            "staged": enrich.get("staged"),
            "skipped_by_ollama": enrich.get("skipped_by_ollama"),
            "items": enrich.get("items"),
        }
        # pull full ops for notify
        from agents.enrich_contacts import _load_pending

        pending = _load_pending()
        enrich_ids = {i.get("op_id") for i in (enrich.get("items") or [])}
        for it in pending.get("items") or []:
            if it.get("op_id") in enrich_ids:
                staged_ops.append(it)
        print(json.dumps({k: v for k, v in summary["steps"]["enrich"].items() if k != "items"}, indent=2), flush=True)
    except Exception as e:
        summary["steps"]["enrich"] = {"error": str(e)}
        print(f"[{st}] enrich error: {e}", flush=True)

    # 3) Education + resettlement discover (Ollama)
    if skip_discover or discover_limit <= 0:
        summary["steps"]["discover"] = {"skipped": True}
    else:
        try:
            from agents import discover_new

            print(f"=== [{st}] Discover edu/resettle (Ollama) ===", flush=True)
            disc = discover_new.scan(
                ["education", "resettlement"],
                limit=discover_limit,
                use_ollama=use_ollama,
                discover_sites=True,
                state=st,
            )
            summary["steps"]["discover"] = {
                "staged": disc.get("staged"),
                "skipped": disc.get("skipped"),
                "items": disc.get("items"),
            }
            from agents.enrich_contacts import _load_pending

            pending = _load_pending()
            disc_ids = {i.get("op_id") for i in (disc.get("items") or [])}
            for it in pending.get("items") or []:
                if it.get("op_id") in disc_ids:
                    staged_ops.append(it)
            print(
                json.dumps(
                    {k: v for k, v in summary["steps"]["discover"].items() if k != "items"},
                    indent=2,
                ),
                flush=True,
            )
        except Exception as e:
            summary["steps"]["discover"] = {"error": str(e)}
            print(f"[{st}] discover error: {e}", flush=True)

    # Dedupe staged_ops by op_id for notify
    by_id = {}
    for it in staged_ops:
        oid = it.get("op_id")
        if oid:
            by_id[oid] = it
    unique_ops = list(by_id.values())

    # High+known → apply immediately; only ask-tier goes to Telegram
    try:
        from agents.confidence import drain_auto_apply, tier_action

        auto = drain_auto_apply(unique_ops)
        summary["steps"]["auto_apply_high"] = auto
        print(json.dumps({"auto_apply_high": auto}, indent=2), flush=True)
        ask_ops = [i for i in unique_ops if tier_action(i) == "ask"]
        # refresh statuses — auto-applied ones are no longer proposed
        from agents.enrich_contacts import _load_pending

        pending = _load_pending()
        open_ids = {
            i.get("op_id")
            for i in pending.get("items") or []
            if i.get("status") in ("proposed", "proposed_update")
        }
        ask_ops = [i for i in ask_ops if i.get("op_id") in open_ids]
    except Exception as e:
        summary["steps"]["auto_apply_high"] = {"error": str(e)}
        ask_ops = unique_ops

    if notify and ask_ops:
        try:
            summary["steps"]["telegram"] = _notify_batch(ask_ops, st, card_limit=card_limit)
        except Exception as e:
            summary["steps"]["telegram"] = {"error": str(e)}
    else:
        summary["steps"]["telegram"] = {
            "skipped": not ask_ops,
            "ops": len(ask_ops),
            "auto_applied": (summary.get("steps") or {}).get("auto_apply_high", {}).get("auto_apply"),
        }

    summary["staged_ops"] = len(unique_ops)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="State-by-state HRSA + Ollama enrich + edu/resettle discover")
    ap.add_argument("--states", default="IL,IN,CO,CA", help="Comma USPS states")
    ap.add_argument("--skip-fetch", action="store_true", help="Skip Find-a-HC (enrich+discover only)")
    ap.add_argument("--skip-discover", action="store_true", help="Skip edu/resettle discover")
    ap.add_argument("--skip-states", default="", help="Comma states to skip entirely")
    ap.add_argument("--enrich-limit", type=int, default=10)
    ap.add_argument("--discover-limit", type=int, default=8)
    ap.add_argument("--card-limit", type=int, default=20)
    ap.add_argument("--no-ollama", action="store_true")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    skip = {s.strip().upper() for s in args.skip_states.split(",") if s.strip()}
    results = []
    _notify(
        "🏙 Starting state-by-state batches\n"
        f"States: {', '.join(states)}\n"
        "Each state: Find-a-HC → Ollama enrich gaps → edu/resettle discover\n"
        "Finish a state with: `approve all ST`"
    )

    for st in states:
        if st in skip:
            print(f"Skipping {st}", flush=True)
            continue
        # IN healthcare already fetched earlier — still allow enrich/discover; fetch optional
        skip_fetch = args.skip_fetch or st == "IN"
        summary = run_state(
            st,
            skip_fetch=skip_fetch,
            skip_discover=args.skip_discover,
            enrich_limit=args.enrich_limit,
            discover_limit=0 if args.skip_discover else args.discover_limit,
            card_limit=args.card_limit,
            use_ollama=not args.no_ollama,
            notify=not args.no_notify,
        )
        results.append(summary)
        print(json.dumps({"state": st, "staged_ops": summary.get("staged_ops"), "steps": list((summary.get("steps") or {}).keys())}, indent=2), flush=True)
        time.sleep(1)

    print(json.dumps({"ok": True, "states": results}, indent=2, ensure_ascii=False, default=str)[:8000])
    _notify(
        "✅ State batches finished\n"
        + "\n".join(
            f"• {r.get('state')}: {r.get('staged_ops', 0)} ops — `approve all {r.get('state')}`"
            for r in results
        )
    )


if __name__ == "__main__":
    main()
