"""
Controlled tools for clinic ops (David local-ai-agents pattern).

Side effects are NEVER automatic  -  tools only stage or report.
Push/apply happens only after explicit Telegram (or CLI) approval.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

# OpenAI-style tool schemas (for local LLM tool-calling later)
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_pending",
            "description": "List staged clinic proposals awaiting human approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["proposed", "proposed_update", "approved", "rejected", "all"],
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_proposal",
            "description": "Summarize one pending proposal by op_id for Telegram.",
            "parameters": {
                "type": "object",
                "properties": {"op_id": {"type": "string"}},
                "required": ["op_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_github_block",
            "description": "Format a clinic record as a refugee-resources .txt block (no map-pin emoji).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "phone": {"type": "string"},
                    "website": {"type": "string"},
                    "services": {"type": "string"},
                    "languages": {"type": "string"},
                    "hours": {"type": "string"},
                    "next_id": {"type": "integer"},
                },
                "required": ["name"],
            },
        },
    },
]


def draft_github_block(
    name: str,
    address: str = "",
    phone: str = "",
    website: str = "",
    services: str = "",
    languages: str = "",
    hours: str = "",
    next_id: int = 999,
) -> str:
    """Match healthcare.txt style  -  plain address (no 📍)."""
    lines = [f"{next_id}. {name}"]
    if address:
        lines.append(address)
    if website:
        lines.append(f"🌐 {website if website.startswith('http') else 'https://' + website}")
    if languages:
        lines.append(f"🗣 Languages: {languages}")
    if services:
        from core.labels import humanize_services

        lines.append(f"🏥 Services: {humanize_services(services)}")
    if hours:
        lines.append(f"⏰ Hours: {hours}")
    if phone:
        lines.append(f"📞 {phone}")
    return "\n".join(lines)


def format_telegram_card(item: Dict[str, Any]) -> str:
    op = item.get("op_id", "?")
    kind = "UPDATE" if item.get("status") == "proposed_update" else "NEW"
    name = item.get("name") or "Unknown"
    lines = [
        f"{'✏️' if kind == 'UPDATE' else '🆕'} [{kind}] {op}",
        f"*{name}*",
    ]
    if item.get("address"):
        lines.append(f"Address: {item['address']}")
    if item.get("zip"):
        lines.append(f"ZIP: {item['zip']}")
    if item.get("phone"):
        lines.append(f"Phone: {item['phone']}")
    if item.get("website"):
        lines.append(f"Web: {item['website']}")
    if item.get("region"):
        lines.append(f"Scope: {item['region']}")
    if item.get("field_updates"):
        lines.append("Changes: " + ", ".join(f"{k}→{v}" for k, v in item["field_updates"].items()))
    lines.append("")
    lines.append(f"Reply: `approve {op}`  or  `reject {op}`")
    return "\n".join(lines)


def dispatch(name: str, args: Dict[str, Any], ctx: Dict[str, Callable]) -> Any:
    """Run an allowlisted tool only."""
    allowed = {s["function"]["name"] for s in TOOL_SCHEMAS}
    if name not in allowed:
        return {"ok": False, "error": f"Tool not allowed: {name}"}
    fn = ctx.get(name)
    if not fn:
        return {"ok": False, "error": f"Tool not bound: {name}"}
    return fn(**args)
