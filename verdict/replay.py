"""Replay client: the same interface as PayPalClient, backed by a snapshot of real sandbox objects.

Purpose: let anyone (judges included) run Verdict end-to-end without PayPal credentials. Reads are
served from `replay/*.json` (captured from the sandbox and scrubbed); writes are simulated with the
observed state machine (`verdict/statemachine.py`) and clearly labelled as replay in the audit log.

Enable with VERDICT_MODE=replay (or automatically when no PayPal credentials are set).
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contract import validate as validate_contract
from .paypal import ActionNotAllowed, PayPalError

REPLAY_DIR = Path(__file__).resolve().parent.parent / "replay"

# what links PayPal exposed after each action, as observed in the sandbox
AFTER = {
    "send_message": (
        "WAITING_FOR_BUYER_RESPONSE",
        "REQUIRED_OTHER_PARTY_ACTION",
        ["accept_claim", "escalate", "send_message", "provide_evidence"],
    ),
    "provide_evidence": ("UNDER_REVIEW", "UNDER_PAYPAL_REVIEW", []),
    "provide_supporting_info": (None, None, None),  # unchanged
    "escalate": ("UNDER_REVIEW", "UNDER_PAYPAL_REVIEW", []),
    "accept_claim": ("RESOLVED", "RESOLVED", []),
    "make_offer": ("WAITING_FOR_BUYER_RESPONSE", "REQUIRED_OTHER_PARTY_ACTION", ["accept_claim", "escalate", "send_message"]),
}


class ReplayClient:
    is_replay = True

    def __init__(self, snapshot: Path | None = None):
        files = sorted(REPLAY_DIR.glob("*.json"))
        if not files:
            raise RuntimeError(f"no replay snapshot in {REPLAY_DIR}")
        self.snapshot_name = (snapshot or files[-1]).name
        self.s: dict[str, Any] = copy.deepcopy(json.loads((snapshot or files[-1]).read_text()))

    # ----- reads -----
    def list_disputes(self, dispute_state: str | None = None, page_size: int = 50, **params) -> list[dict]:
        out = []
        for d in self.s["disputes"].values():
            if dispute_state and d.get("dispute_state") != dispute_state:
                continue
            out.append(
                {
                    k: d.get(k)
                    for k in (
                        "dispute_id",
                        "reason",
                        "status",
                        "dispute_state",
                        "dispute_life_cycle_stage",
                        "dispute_amount",
                        "create_time",
                        "update_time",
                    )
                }
            )
        return out

    def get_dispute(self, dispute_id: str) -> dict:
        try:
            return copy.deepcopy(self.s["disputes"][dispute_id])
        except KeyError as e:
            raise PayPalError(404, {"name": "RESOURCE_NOT_FOUND"}, "get_dispute") from e

    def get_capture(self, capture_id: str) -> dict:
        try:
            return copy.deepcopy(self.s["captures"][capture_id])
        except KeyError as e:
            raise PayPalError(404, {"name": "RESOURCE_NOT_FOUND"}, "get_capture") from e

    def get_order(self, order_id: str) -> dict:
        try:
            return copy.deepcopy(self.s["orders"][order_id])
        except KeyError as e:
            raise PayPalError(404, {"name": "RESOURCE_NOT_FOUND"}, "get_order") from e

    def get_tracker(self, tracker_id: str) -> dict:
        try:
            return copy.deepcopy(self.s["trackers"][tracker_id])
        except KeyError as e:
            raise PayPalError(404, {"name": "RESOURCE_NOT_FOUND"}, "get_tracker") from e

    # ----- gating (identical to the live client) -----
    @staticmethod
    def links(dispute: dict) -> set[str]:
        return {lk.get("rel", "") for lk in dispute.get("links", [])}

    @staticmethod
    def require_link(dispute: dict, rel: str) -> None:
        if rel not in ReplayClient.links(dispute):
            raise ActionNotAllowed(
                f"PayPal does not currently allow '{rel}' on {dispute.get('dispute_id')} (status={dispute.get('status')}, links={sorted(ReplayClient.links(dispute))})"
            )

    # ----- simulated writes -----
    def _apply(self, dispute: dict, action: str, mutate) -> dict:
        self.require_link(dispute, action)
        live = self.s["disputes"][dispute["dispute_id"]]
        mutate(live)
        status, state, links = AFTER[action]
        if status and links is not None:
            live["status"], live["dispute_state"] = status, state
            live["links"] = [{"rel": "self"}] + [{"rel": r} for r in links]
        live["update_time"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        return {"replay": True, "links": [{"rel": "detail", "href": f"replay://{dispute['dispute_id']}"}]}

    def send_message(self, dispute: dict, message: str) -> dict:
        self.require_link(dispute, "send_message")
        validate_contract("send_message", {"message": message})
        return self._apply(
            dispute,
            "send_message",
            lambda d: d.setdefault("messages", []).append({"posted_by": "SELLER", "time_posted": _now(), "content": message}),
        )

    def provide_evidence(self, dispute: dict, evidences: list[dict], return_shipping_address: dict | None = None, file=None) -> dict:
        self.require_link(dispute, "provide_evidence")
        payload: dict[str, Any] = {"evidences": evidences}
        if return_shipping_address:
            payload["return_shipping_address"] = return_shipping_address
        validate_contract("provide_evidence", payload)

        def mut(d):
            for e in evidences:
                d.setdefault("evidences", []).append(
                    {**e, "source": "SUBMITTED_BY_SELLER", "date": _now(), "documents": [{"name": file[0]}] if file else []}
                )

        return self._apply(dispute, "provide_evidence", mut)

    def provide_supporting_info(self, dispute: dict, notes: str, file=None) -> dict:
        self.require_link(dispute, "provide_supporting_info")
        validate_contract("provide_supporting_info", {"notes": notes})
        return self._apply(
            dispute,
            "provide_supporting_info",
            lambda d: d.setdefault("supporting_info", []).append(
                {"notes": notes, "source": "SUBMITTED_BY_SELLER", "provided_time": _now()}
            ),
        )

    def accept_claim(
        self, dispute: dict, note: str, accept_claim_type: str = "REFUND", refund_amount=None, return_shipping_address=None
    ) -> dict:
        allowed = ((dispute.get("allowed_response_options") or {}).get("accept_claim") or {}).get("accept_claim_types")
        if allowed and accept_claim_type not in allowed:
            raise ActionNotAllowed(f"accept_claim_type {accept_claim_type} not in PayPal's allowed {allowed}")
        validate_contract("accept_claim", {"note": note, "accept_claim_type": accept_claim_type})

        def mut(d):
            d["dispute_outcome"] = {"outcome_code": "ACCEPTED", "amount_refunded": d.get("dispute_amount")}

        return self._apply(dispute, "accept_claim", mut)

    def make_offer(self, dispute: dict, note: str, offer_type: str, offer_amount=None, return_shipping_address=None) -> dict:
        self.require_link(dispute, "make_offer")
        validate_contract(
            "make_offer", {"note": note, "offer_type": offer_type, **({"offer_amount": offer_amount} if offer_amount else {})}
        )
        return self._apply(
            dispute,
            "make_offer",
            lambda d: d.update(
                {
                    "offer": {
                        "offer_type": offer_type,
                        "seller_offered_amount": offer_amount,
                        "history": [{"offer_time": _now(), "actor": "SELLER", "notes": note}],
                    }
                }
            ),
        )

    def escalate(self, dispute: dict, note: str) -> dict:
        self.require_link(dispute, "escalate")
        validate_contract("escalate", {"note": note})
        return self._apply(
            dispute,
            "escalate",
            lambda d: d.setdefault("messages", []).append({"posted_by": "SELLER", "time_posted": _now(), "content": f"[escalated] {note}"}),
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
