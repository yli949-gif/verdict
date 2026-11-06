"""Dispute state machine as observed in the PayPal sandbox (2026-11-06) and in the Disputes docs.

This is *descriptive*, not authoritative: at runtime the engine trusts the live `links[]`. The model
exists so tests can (a) generate realistic link sets per state, (b) check that every seller action
Verdict can take is one the state admits, and (c) document what we expect to happen after each call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SELLER_ACTIONS = {"accept_claim", "provide_evidence", "make_offer", "send_message", "escalate", "provide_supporting_info"}


@dataclass(frozen=True)
class State:
    status: str
    stage: str
    links: frozenset[str]  # seller-relevant rels observed
    note: str = ""


# observed states (status, life-cycle stage, links PayPal exposed)
STATES: dict[str, State] = {
    "OPEN_NEW": State("OPEN", "INQUIRY", frozenset(), "just filed; actions appear after ~2 min"),
    "REVIEW_INQUIRY": State("UNDER_REVIEW", "INQUIRY", frozenset(), "PayPal automation; transient"),
    "SELLER_TURN": State("WAITING_FOR_SELLER_RESPONSE", "INQUIRY",
                         frozenset({"accept_claim", "provide_evidence", "send_message", "escalate", "make_offer"}), "due date +20d"),
    "SELLER_TURN_EVIDENCE_ONLY": State("WAITING_FOR_SELLER_RESPONSE", "INQUIRY", frozenset({"accept_claim", "provide_evidence"}), "after prior responses"),
    "BUYER_TURN": State("WAITING_FOR_BUYER_RESPONSE", "INQUIRY", frozenset({"accept_claim", "escalate", "send_message", "provide_evidence"}), "after seller message"),
    "BUYER_TURN_NO_EVIDENCE": State("WAITING_FOR_BUYER_RESPONSE", "INQUIRY", frozenset({"accept_claim", "escalate", "send_message"}), "after evidence submitted"),
    "REVIEW_CHARGEBACK": State("UNDER_REVIEW", "CHARGEBACK", frozenset({"provide_supporting_info", "accept_claim"}), "tracking on order before filing"),
    "RESOLVED": State("RESOLVED", "INQUIRY", frozenset(), "closed"),
}

# (from_state, action) -> to_state, observed or documented
TRANSITIONS: dict[tuple[str, str], str] = {
    ("OPEN_NEW", "time"): "REVIEW_INQUIRY",
    ("REVIEW_INQUIRY", "time"): "SELLER_TURN",
    ("SELLER_TURN", "send_message"): "BUYER_TURN",
    ("SELLER_TURN", "provide_evidence"): "REVIEW_INQUIRY",
    ("SELLER_TURN", "escalate"): "REVIEW_INQUIRY",
    ("SELLER_TURN", "accept_claim"): "RESOLVED",
    ("SELLER_TURN", "make_offer"): "BUYER_TURN",
    ("BUYER_TURN", "provide_evidence"): "BUYER_TURN_NO_EVIDENCE",
    ("BUYER_TURN", "escalate"): "REVIEW_INQUIRY",
    ("BUYER_TURN", "accept_claim"): "RESOLVED",
    ("REVIEW_CHARGEBACK", "provide_supporting_info"): "REVIEW_CHARGEBACK",
    ("REVIEW_CHARGEBACK", "accept_claim"): "RESOLVED",
}


def admits(state_name: str, action: str) -> bool:
    return action in STATES[state_name].links


def expected_next(state_name: str, action: str) -> str | None:
    return TRANSITIONS.get((state_name, action))


def links_for(state_name: str) -> list[str]:
    return ["self", *sorted(STATES[state_name].links)]
