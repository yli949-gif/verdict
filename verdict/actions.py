"""Execute a verdict against PayPal — only after a human confirms, only if PayPal still allows it.

Flow: re-fetch the dispute (links may have changed) → require_link → call → audit → re-fetch.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import settings
from .engine import Verdict
from .paypal import ActionNotAllowed, PayPalClient, PayPalError

AUDIT = settings.data_dir / "audit.jsonl"


def audit(entry: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
    with AUDIT.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def read_audit(dispute_id: str | None = None, limit: int = 200) -> list[dict]:
    if not AUDIT.exists():
        return []
    rows = [json.loads(l) for l in AUDIT.read_text().splitlines() if l.strip()]
    if dispute_id:
        rows = [r for r in rows if r.get("dispute_id") == dispute_id]
    return rows[-limit:]


def execute(client: PayPalClient, verdict: Verdict, *, action: str | None = None, message: str | None = None,
            evidence_plan: list[dict] | None = None, accept_claim_type: str | None = None,
            offer_amount: float | None = None, confirmed: bool = False, actor: str = "ui") -> dict:
    """Returns {ok, action, request, response, dispute_after}. Raises nothing; errors are in the result + audit."""
    action = action or verdict.action
    if not confirmed:
        return {"ok": False, "error": "not_confirmed", "action": action}
    if not action:
        return {"ok": False, "error": "no_action", "action": None}
    dispute = client.get_dispute(verdict.dispute_id)  # fresh links = source of truth
    req: dict[str, Any] = {}
    try:
        if action == "send_message":
            req = {"message": message or verdict.message_draft}
            resp = client.send_message(dispute, req["message"])
        elif action == "provide_evidence":
            plan = evidence_plan or verdict.evidence_plan
            if not plan:
                raise ActionNotAllowed("no evidence plan to submit")
            summary = _evidence_summary(verdict, plan, message)
            req = {"evidences": plan, "file": "verdict_evidence_summary.txt"}
            resp = client.provide_evidence(dispute, plan, file=("verdict_evidence_summary.txt", summary.encode(), "text/plain"))
        elif action == "provide_supporting_info":
            notes = message or (evidence_plan or verdict.evidence_plan or [{}])[0].get("notes") or verdict.message_draft
            req = {"notes": notes}
            resp = client.provide_supporting_info(dispute, notes)
        elif action == "accept_claim":
            allowed = ((dispute.get("allowed_response_options") or {}).get("accept_claim") or {}).get("accept_claim_types") or ["REFUND"]
            ctype = accept_claim_type or ("REFUND" if "REFUND" in allowed else allowed[0])
            req = {"note": message or verdict.message_draft, "accept_claim_type": ctype}
            resp = client.accept_claim(dispute, req["note"], ctype)
        elif action == "make_offer":
            allowed = ((dispute.get("allowed_response_options") or {}).get("make_offer") or {}).get("offer_types") or ["REFUND"]
            otype = "REFUND" if "REFUND" in allowed else allowed[0]
            amt = offer_amount if offer_amount is not None else round(float((dispute.get("dispute_amount") or {}).get("value", 0)) / 2, 2)
            req = {"note": message or verdict.message_draft, "offer_type": otype, "offer_amount": {"currency_code": (dispute.get("dispute_amount") or {}).get("currency_code", "USD"), "value": f"{amt:.2f}"}}
            resp = client.make_offer(dispute, req["note"], otype, req["offer_amount"])
        elif action == "escalate":
            req = {"note": message or "Escalating to PayPal for review."}
            resp = client.escalate(dispute, req["note"])
        else:
            raise ActionNotAllowed(f"unknown action {action}")
        after = client.get_dispute(verdict.dispute_id)
        result = {"ok": True, "action": action, "request": req, "response": resp,
                  "status_before": dispute.get("status"), "status_after": after.get("status"), "links_after": [l["rel"] for l in after.get("links", [])]}
    except (ActionNotAllowed, PayPalError) as e:
        result = {"ok": False, "action": action, "request": req, "error": str(e),
                  "issue": getattr(e, "issue", ""), "status_before": dispute.get("status")}
    audit({"dispute_id": verdict.dispute_id, "actor": actor, "verdict": verdict.verdict, **result})
    return result


def _evidence_summary(verdict: Verdict, plan: list[dict], extra: str | None) -> str:
    lines = [f"Verdict evidence summary for dispute {verdict.dispute_id}", "=" * 60, ""]
    for e in plan:
        lines.append(f"- {e.get('evidence_type')}: {e.get('notes', '')}")
        for t in (e.get("evidence_info") or {}).get("tracking_info", []):
            lines.append(f"    carrier={t.get('carrier_name')} tracking={t.get('tracking_number')}")
    if extra:
        lines += ["", "Seller note:", extra]
    lines += ["", "Rules applied:"] + [f"  {r.id}: {r.text}" for r in verdict.rules]
    return "\n".join(lines)
