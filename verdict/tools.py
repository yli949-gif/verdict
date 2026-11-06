"""Toolkit-shaped tool definitions so any agent framework (OpenAI Agents SDK, LangChain, MCP, Claude
tool use) can drive Verdict. Mirrors the schema style of paypal-agent-toolkit so these could be
upstreamed: the official Python toolkit (1.1.0) has no dispute tools at all.

Each tool is {"method", "name", "description", "args_schema", "execute"}; `execute(client, params)`
returns a JSON string. State-changing tools require `confirmed: true` — an agent cannot skip the human.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .actions import execute
from .engine import decide
from .paypal import PayPalClient
from .sync import fetch_bundle, list_dispute_ids


class ListDisputes(BaseModel):
    dispute_state: str | None = Field(
        None, description="REQUIRED_ACTION | REQUIRED_OTHER_PARTY_ACTION | UNDER_PAYPAL_REVIEW | RESOLVED | OPEN_INQUIRIES"
    )


class DisputeId(BaseModel):
    dispute_id: str = Field(..., description="PayPal dispute id, e.g. PP-R-XSW-10196894")


class ExecuteVerdict(BaseModel):
    dispute_id: str
    action: str | None = Field(
        None,
        description="Override the recommended action: accept_claim | provide_evidence | send_message | make_offer | escalate | provide_supporting_info",
    )
    message: str | None = Field(None, description="Buyer-facing note / evidence notes")
    confirmed: bool = Field(False, description="Must be true. Set only after a human reviewed the verdict.")


def _list(client: PayPalClient, params: dict) -> str:
    p = ListDisputes(**params)
    items = list_dispute_ids(client)
    if p.dispute_state:
        items = [d for d in items if d.get("_state_bucket") == p.dispute_state]
    return json.dumps(
        [{k: d.get(k) for k in ("dispute_id", "reason", "status", "dispute_state", "dispute_amount", "update_time")} for d in items]
    )


def _get_verdict(client: PayPalClient, params: dict) -> str:
    p = DisputeId(**params)
    bundle, _ = fetch_bundle(client, p.dispute_id)
    v = decide(bundle)
    return json.dumps({"verdict": v.to_dict(), "evidence_bundle": json.loads(bundle.model_dump_json(exclude={"now"}))})


def _execute(client: PayPalClient, params: dict) -> str:
    p = ExecuteVerdict(**params)
    bundle, _ = fetch_bundle(client, p.dispute_id)
    v = decide(bundle)
    return json.dumps(execute(client, v, action=p.action, message=p.message, confirmed=p.confirmed, actor="agent"))


tools: list[dict[str, Any]] = [
    {
        "method": "list_disputes",
        "name": "List Disputes",
        "description": "List the merchant's PayPal disputes, actionable first.",
        "args_schema": ListDisputes,
        "execute": _list,
        "actions": {"disputes": {"read": True}},
    },
    {
        "method": "get_dispute_verdict",
        "name": "Get Dispute Verdict",
        "description": "Fetch dispute + capture + order from PayPal, cross-check seller protection, tracking, address and allowed actions, and return an evidence-based recommendation (never a prediction of PayPal's decision).",
        "args_schema": DisputeId,
        "execute": _get_verdict,
        "actions": {"disputes": {"read": True}},
    },
    {
        "method": "execute_dispute_verdict",
        "name": "Execute Dispute Verdict",
        "description": "After human confirmation, perform the recommended PayPal dispute action. Refuses anything PayPal's HATEOAS links do not currently allow.",
        "args_schema": ExecuteVerdict,
        "execute": _execute,
        "actions": {"disputes": {"write": True}},
    },
]


def as_openai_functions() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {"name": t["method"], "description": t["description"], "parameters": t["args_schema"].model_json_schema()},
        }
        for t in tools
    ]


def as_anthropic_tools() -> list[dict]:
    return [{"name": t["method"], "description": t["description"], "input_schema": t["args_schema"].model_json_schema()} for t in tools]


def run(client: PayPalClient, method: str, params: dict) -> str:
    for t in tools:
        if t["method"] == method:
            return t["execute"](client, params)
    raise ValueError(f"unknown tool {method}")
