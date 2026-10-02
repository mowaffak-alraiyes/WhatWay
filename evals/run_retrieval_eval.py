#!/usr/bin/env python3
"""Run grounded retrieval checks against the committed WhatWay data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pipeline import search_resources  # noqa: E402


def evaluate_case(case: Dict[str, Any], *, semantic: bool) -> Dict[str, Any]:
    result = search_resources(
        case["query"],
        category=case.get("category"),
        limit=3,
        use_llm=False,
        use_semantic=semantic,
    )
    source_ids = result["retrieval"]["source_ids"]
    expected_ids = set(case.get("expected_source_ids") or [])
    id_hit = not expected_ids or bool(expected_ids.intersection(source_ids))

    state = case.get("expected_state")
    state_ok = not state or all(item.get("state") == state for item in result["results"])

    language = str(case.get("expected_language") or "").lower()
    language_ok = not language or all(
        language in {str(value).lower() for value in (item.get("languages") or [])}
        for item in result["results"]
    )

    return {
        "name": case["name"],
        "passed": id_hit and state_ok and language_ok,
        "mode": result["retrieval"]["mode"],
        "source_ids": source_ids,
        "checks": {
            "expected_id_in_top_3": id_hit,
            "state_filter": state_ok,
            "language_filter": language_ok,
        },
    }


def run(cases: List[Dict[str, Any]], *, semantic: bool) -> Dict[str, Any]:
    results = [evaluate_case(case, semantic=semantic) for case in cases]
    passed = sum(1 for result in results if result["passed"])
    return {
        "semantic_requested": semantic,
        "passed": passed,
        "total": len(results),
        "pass_rate": passed / len(results) if results else 0.0,
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("retrieval_cases.json"),
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Use Ollama embeddings; otherwise evaluate the lexical fallback.",
    )
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    report = run(cases, semantic=args.semantic)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
