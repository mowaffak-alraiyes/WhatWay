"""
Fetch Health Centers the same way Find a Health Center does — no browser scrape.

Calls the public locator API behind https://findahealthcenter.hrsa.gov/ :
  GET {HDWLocatorApi}/healthcenters/find?lon=&lat=&radius=

For each state, query hub + surrounding cities (250 mi default), dedupe by site Id,
write an XLSX shaped like the HRSA bulk export, then optionally run import_hrsa_xlsx
(stage → Telegram digests / push).

Examples:
  python -m agents.fetch_hrsa_finder --states IL,CO,CA --radius 250 --out-dir data/hrsa_finder
  python -m agents.fetch_hrsa_finder --states IL --stage-ops --notify-telegram
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FINDER_API = os.environ.get(
    "HRSA_FINDER_API",
    "https://data.hrsa.gov/HDWLocatorApi/healthcenters/find",
)
UA = {
    "User-Agent": "AidrHRSAFinder/1.0 (+local; refugee resource directory)",
    "Accept": "application/json",
}


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def finder_row_to_xlsx(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Map locator JSON → columns import_hrsa_xlsx.load_xlsx_rows expects."""
    return {
        "Health Center Name": (rec.get("CtrNm") or "").strip(),
        "Operated By": (rec.get("ParentCtrNm") or "").strip(),
        "Street Address": (rec.get("CtrAddress") or "").strip(),
        "City": (rec.get("CtrCity") or "").strip(),
        "State": (rec.get("CtrStateAbbr") or "").strip().upper(),
        "ZIP Code": (rec.get("CtrZipCd") or "").strip(),
        "Telephone Number": (rec.get("CtrPhoneNum") or "").strip(),
        "Website": (rec.get("UrlTxt") or rec.get("SiteUrl") or "").strip(),
        "Latitude": rec.get("Latitude"),
        "Longitude": rec.get("Longitude"),
        "HRSA_Id": rec.get("Id"),
        "Distance": rec.get("Distance"),
        "County": (rec.get("CountyNm") or "").strip(),
    }


def fetch_around(
    lat: float,
    lon: float,
    radius_miles: float,
    *,
    session: Optional[requests.Session] = None,
    timeout: float = 90.0,
) -> List[Dict[str, Any]]:
    sess = session or requests.Session()
    # API returns nearest N (often 500) within radius — int radius matches the site UI.
    r = sess.get(
        FINDER_API,
        params={"lat": float(lat), "lon": float(lon), "radius": int(round(radius_miles))},
        headers=UA,
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "Results", "healthCenters", "HealthCenters", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def dedupe_records(records: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Prefer HRSA Id; fallback name+zip+street. Returns (unique, duplicate_count)."""
    seen = set()
    out: List[Dict[str, Any]] = []
    dups = 0
    for rec in records:
        rid = rec.get("Id")
        if rid is not None:
            key = ("id", rid)
        else:
            key = (
                "nz",
                (rec.get("CtrNm") or "").strip().lower(),
                (rec.get("CtrZipCd") or "")[:5],
                (rec.get("CtrAddress") or "").strip().lower(),
            )
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        out.append(rec)
    return out, dups


def fetch_states(
    states: Sequence[str],
    *,
    radius_miles: float = 250.0,
    pause_sec: float = 0.4,
    keep_states_only: bool = True,
) -> Dict[str, Any]:
    """Query surrounding cities per state; return merged rows + stats."""
    from agents.geo_scope import search_cities_for

    session = requests.Session()
    by_state: Dict[str, List[Dict[str, Any]]] = {}
    city_stats: List[Dict[str, Any]] = []
    all_raw: List[Dict[str, Any]] = []

    for st in states:
        st = st.upper()
        cities = search_cities_for(st)
        state_raw: List[Dict[str, Any]] = []
        for name, lat, lon in cities:
            try:
                rows = fetch_around(lat, lon, radius_miles, session=session)
            except Exception as e:
                city_stats.append(
                    {"state": st, "city": name, "ok": False, "error": str(e), "count": 0}
                )
                continue
            max_dist = None
            try:
                dists = [float(x.get("Distance")) for x in rows if x.get("Distance") is not None]
                max_dist = max(dists) if dists else None
            except Exception:
                pass
            city_stats.append(
                {
                    "state": st,
                    "city": name,
                    "ok": True,
                    "count": len(rows),
                    "capped_500": len(rows) >= 500,
                    "max_distance_mi": max_dist,
                    "note": (
                        "API returns nearest ~500 within radius; surrounding cities fill gaps"
                        if len(rows) >= 500
                        else None
                    ),
                }
            )
            for rec in rows:
                rec = dict(rec)
                rec["_query_state"] = st
                rec["_query_city"] = name
                state_raw.append(rec)
                all_raw.append(rec)
            time.sleep(pause_sec)

        unique, dups = dedupe_records(state_raw)
        if keep_states_only:
            unique = [
                r
                for r in unique
                if (r.get("CtrStateAbbr") or "").strip().upper() == st
            ]
        by_state[st] = unique
        city_stats.append(
            {
                "state": st,
                "city": "_DEDUPED_",
                "ok": True,
                "raw": len(state_raw),
                "duplicates_removed": dups,
                "kept": len(unique),
                "filtered_to_state": keep_states_only,
            }
        )

    return {
        "fetched_at": _now(),
        "radius_miles": radius_miles,
        "api": FINDER_API,
        "by_state": by_state,
        "city_stats": city_stats,
        "total_unique": sum(len(v) for v in by_state.values()),
    }


def write_xlsx(rows: List[Dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    mapped = [finder_row_to_xlsx(r) for r in rows]
    df = pd.DataFrame(mapped)
    # Drop helper cols that confuse humans but keep Lat/Lon for hub filter
    df.to_excel(path, index=False)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch Find-a-Health-Center results for hub+surrounding cities → XLSX"
    )
    ap.add_argument("--states", default="IL,CO,CA", help="Comma USPS states (default IL,CO,CA)")
    ap.add_argument("--radius", type=float, default=250.0, help="Miles (site UI default 250)")
    ap.add_argument(
        "--out-dir",
        default=str(DATA / "hrsa_finder"),
        help="Directory for per-state and combined XLSX",
    )
    ap.add_argument(
        "--allow-cross-state",
        action="store_true",
        help="Keep sites whose State ≠ query state (default: drop them)",
    )
    ap.add_argument("--stage-ops", action="store_true", help="Run import_hrsa_xlsx --stage-ops")
    ap.add_argument("--notify-telegram", action="store_true", help="Per-state digests + cards")
    ap.add_argument("--push", action="store_true", help="Also push merges to GitHub")
    ap.add_argument("--dry-run", action="store_true", help="Fetch+write only; no import side effects")
    args = ap.parse_args()

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    result = fetch_states(
        states,
        radius_miles=args.radius,
        keep_states_only=not args.allow_cross_state,
    )

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    combined: List[Dict[str, Any]] = []
    for st, rows in result["by_state"].items():
        path = out_dir / f"health_centers_{st}.xlsx"
        write_xlsx(rows, path)
        written.append({"state": st, "path": str(path), "rows": len(rows)})
        combined.extend(rows)

    combo_path = out_dir / "health_centers_combined.xlsx"
    write_xlsx(combined, combo_path)
    meta_path = out_dir / "fetch_meta.json"
    meta = {
        **{k: v for k, v in result.items() if k != "by_state"},
        "written": written,
        "combined": str(combo_path),
        "combined_rows": len(combined),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))

    if args.dry_run or not (args.stage_ops or args.push or args.notify_telegram):
        return

    # Feed each state file through existing importer
    from agents import import_hrsa_xlsx as hrsa

    for st, rows in result["by_state"].items():
        if not rows:
            continue
        xlsx = out_dir / f"health_centers_{st}.xlsx"
        # Build argv-style by calling merge path: reuse CLI via subprocess-like args
        # Direct: load rows and merge
        hc_rows = hrsa.load_xlsx_rows(xlsx, [st])
        from agents.geo_scope import filter_rows_by_hubs

        hc_rows = filter_rows_by_hubs(hc_rows, radius_miles=args.radius)
        current = hrsa.fetch_healthcare_text(st)
        merged, stats = hrsa.merge(current, hc_rows, [])
        summary = {
            "state": st,
            "file": hrsa._healthcare_rel(st),
            "finder_rows": len(rows),
            "after_hub_filter": len(hc_rows),
            **{k: v for k, v in stats.items() if k != "changes"},
            "sample_changes": stats["changes"][:12],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))

        staged = []
        if args.stage_ops:
            staged = hrsa.stage_hrsa_changes(st, stats, hc_rows)
            try:
                from agents.enrich_contacts import _load_pending, _save_pending

                pending = _load_pending()
                ids = {i.get("op_id") for i in staged}
                for it in pending.get("items") or []:
                    if it.get("op_id") in ids:
                        it["state"] = st
                        it["source"] = "hrsa_finder"
                _save_pending(pending)
            except Exception:
                pass
            print(json.dumps({"state": st, "staged": len(staged)}, indent=2))

        if args.push and not args.dry_run:
            msg = (
                f"Import Find-a-HC ({st}): +{stats['added']} add, "
                f"{stats['updated']} update"
            )
            print(json.dumps(hrsa.push_healthcare(merged, msg, state=st), indent=2))

        if args.notify_telegram and staged:
            from agents import telegram_bridge

            print(
                json.dumps(
                    telegram_bridge.notify_pending(staged, digest_by_state=True),
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()
