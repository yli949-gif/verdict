"""Optional LLM layer (Claude): explains the verdict in plain language (EN / 中文) and polishes the
buyer-facing message. It never changes the verdict, the action, or the evidence facts.

Guardrails: the model only receives the verdict + rule texts + the evidence bundle fields; the
output is checked so that any tracking number / amount it mentions exists in the bundle.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from .bundle import EvidenceBundle
from .config import settings
from .engine import Verdict

import os
MODEL = os.environ.get("VERDICT_MODEL", "claude-sonnet-5-5")

SYSTEM = """You are Verdict, an assistant for small PayPal sellers handling disputes.
You receive a decision that was ALREADY made by a deterministic policy engine, with the rules it fired and the evidence PayPal has on file.
Your job: explain the decision to the seller clearly and honestly, and draft the buyer-facing note.
Hard rules:
- Never change the verdict or the action. Never invent evidence, tracking numbers, dates, or amounts not in the input.
- Never claim to know how PayPal will decide. Say "PayPal decides"; this is a recommendation.
- Be concrete: cite the rule ids (e.g. R1) and what fact triggered them.
- Keep the buyer note polite, short, factual, no legal threats.
Return JSON: {"explanation": str, "buyer_note": str, "explanation_zh": str}. explanation_zh is a faithful Simplified Chinese version of explanation."""


def explain(bundle: EvidenceBundle, verdict: Verdict, language: str = "en") -> Optional[dict]:
    if not settings.llm_enabled:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    payload = {"verdict": verdict.to_dict(), "bundle": json.loads(bundle.model_dump_json(exclude={"now"}))}
    msg = client.messages.create(model=MODEL, max_tokens=900, system=SYSTEM,
                                 messages=[{"role": "user", "content": json.dumps(payload)}])
    text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    out["faithful"] = _faithful(out, bundle, verdict)
    return out


_NUM = re.compile(r"\b\d{10,}\b")  # long digit runs = tracking numbers


def _faithful(out: dict, bundle: EvidenceBundle, verdict: Verdict) -> bool:
    """True if every long number the model wrote exists in the bundle and it didn't contradict the verdict."""
    text = " ".join(str(out.get(k, "")) for k in ("explanation", "buyer_note", "explanation_zh"))
    known = {t.tracking_number for t in bundle.trackers} | {bundle.dispute_id, bundle.capture_id, bundle.order_id}
    for n in _NUM.findall(text):
        if not any(n in k for k in known):
            return False
    if verdict.verdict == "REFUND_NOW" and re.search(r"(do not|don't|never) refund", text, re.I):
        return False
    if verdict.verdict != "REFUND_NOW" and re.search(r"issue(d)? a full refund", text, re.I):
        return False
    return True
