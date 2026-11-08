"""Verdict decision engine — deterministic, evidence-based, policy-cited.

Design rules:
1. PayPal's HATEOAS links + allowed_response_options decide what can be done NOW (R0 gate).
2. A verdict is a recommendation about what the seller should do under PayPal's published Seller
   Protection / dispute policies. It is never a prediction of PayPal's adjudication.
3. Every fired rule carries a policy_basis so the UI, the README and the eval can show *why*.
4. p_keep values are documented assumptions used only to rank options by expected value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .bundle import EvidenceBundle
from .config import settings
from .contract import carrier_for_paypal

INR = "MERCHANDISE_OR_SERVICE_NOT_RECEIVED"
SNAD = "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED"
UNAUTH = "UNAUTHORISED"

# PayPal User Agreement / Seller Protection summary, quoted in rules (sources in docs/policy_sources.md)
POLICY = {
    "SP_INR": "Seller Protection covers 'Item Not Received' claims when the seller ships to the address on the "
    "Transaction Details page and provides proof of shipment or delivery (tracking) from the carrier.",
    "SP_UNAUTH": "Seller Protection covers 'Unauthorized Transaction' claims for eligible physical goods shipped to "
    "the address on the Transaction Details page with proof of shipment/delivery.",
    "SP_SNAD": "Seller Protection does NOT cover 'Significantly Not as Described' claims; PayPal decides them on the "
    "merits (listing, photos, return policy).",
    "SP_INELIGIBLE": "Transactions marked NOT_ELIGIBLE (e.g. direct card entry, intangible/digital goods, items picked up "
    "in person, or shipped to a different address) are not covered by Seller Protection.",
    "DEADLINE": "Sellers must respond to a dispute by the seller_response_due_date; no response is treated as conceding the case.",
    "INQUIRY": "During the inquiry stage the buyer and seller can message and resolve directly; either party can "
    "escalate to a claim, after which PayPal reviews the evidence.",
    "HATEOAS": "The dispute's links[] and allowed_response_options are the only authoritative list of actions "
    "currently permitted; anything else is rejected with ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE.",
}

AUTO_EVIDENCE_COST = 0.5  # USD: proof is already in PayPal, submitting it is one call

# documented assumptions, not predictions
P_KEEP = {"proof_full": 0.80, "proof_partial": 0.50, "snad_evidence": 0.40, "unauth_proof": 0.70, "no_proof": 0.05, "wait": 0.50}


class _PScale:
    scale = 1.0

    def __getitem__(self, k: str) -> float:
        return min(0.99, _BASE_P[k] * self.scale)


_BASE_P = dict(P_KEEP)
_P = _PScale()

VERDICTS = ("REFUND_NOW", "RESPOND_WITH_EVIDENCE", "OFFER_PARTIAL", "REPLY_AND_WAIT", "NO_ACTION_AVAILABLE")
ACTION_FOR = {
    "REFUND_NOW": "accept_claim",
    "RESPOND_WITH_EVIDENCE": "provide_evidence",
    "OFFER_PARTIAL": "make_offer",
    "REPLY_AND_WAIT": "send_message",
    "NO_ACTION_AVAILABLE": None,
}


@dataclass
class Rule:
    id: str
    text: str
    policy_basis: str


@dataclass
class Verdict:
    dispute_id: str
    verdict: str
    action: str | None  # PayPal action rel the verdict maps to (None if nothing to do)
    confidence: str  # high | medium | low
    rules: list[Rule] = field(default_factory=list)
    evidence_plan: list[dict] = field(default_factory=list)
    p_keep: float = 0.0
    expected_value: float = 0.0  # USD, of following this verdict vs. refunding now (0)
    ev_refund_now: float = 0.0
    allowed_now: list[str] = field(default_factory=list)
    deadline_hours: float | None = None
    flags: list[str] = field(default_factory=list)
    message_draft: str = ""  # deterministic draft (LLM may rewrite)
    disclaimer: str = (
        "This is a recommendation based on PayPal's published policies and the evidence PayPal has on "
        "file. PayPal makes the decision; Verdict does not predict outcomes."
    )

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["rules"] = [r.__dict__ for r in self.rules]
        return d


ACTIONABLE = {"accept_claim", "provide_evidence", "make_offer", "send_message", "escalate", "provide_supporting_info"}


def decide(b: EvidenceBundle, handling_cost: float | None = None, p_scale: float = 1.0) -> Verdict:
    """p_scale multiplies every p_keep assumption (used by robustness analysis; 1.0 = documented values)."""
    cost = settings.handling_cost_usd if handling_cost is None else handling_cost
    _P.scale = p_scale
    v = Verdict(
        dispute_id=b.dispute_id,
        verdict="NO_ACTION_AVAILABLE",
        action=None,
        confidence="high",
        allowed_now=sorted(set(b.links) & ACTIONABLE),
        deadline_hours=b.hours_to_deadline,
    )
    # EV of refunding now: lose amount, no handling cost
    v.ev_refund_now = 0.0

    # ---- R0: gate on what PayPal allows right now
    if not v.allowed_now:
        v.rules.append(
            Rule(
                "R0",
                f"PayPal currently exposes no seller actions on this dispute (status={b.status}, "
                f"stage={b.life_cycle_stage}). Wait for PayPal / the buyer.",
                POLICY["HATEOAS"],
            )
        )
        if "provide_supporting_info" in b.links:
            v.flags.append("supporting_info_allowed")
        return _finalize(v, b, cost)

    # ---- deadline flag (R7)
    if b.hours_to_deadline is not None and b.hours_to_deadline < 48:
        v.flags.append("deadline_under_48h")
        v.rules.append(
            Rule("R7", f"Only {b.hours_to_deadline:.0f}h left to respond; a missed deadline concedes the case.", POLICY["DEADLINE"])
        )

    # ---- small amount (R8) — applies to all reasons unless full proof exists
    full_proof = _has_full_proof(b)

    if b.reason == INR:
        _decide_inr(b, v, full_proof, cost)
    elif b.reason == SNAD:
        _decide_snad(b, v, cost)
    elif b.reason == UNAUTH:
        _decide_unauth(b, v, full_proof, cost)
    elif (
        b.reason == "CREDIT_NOT_PROCESSED"
        and b.seller_refund_already_issued
        and ("provide_evidence" in b.links or "provide_supporting_info" in b.links)
    ):
        v.verdict, v.confidence, v.p_keep = "RESPOND_WITH_EVIDENCE", "high", _P["proof_full"]
        v.action = "provide_evidence" if "provide_evidence" in b.links else "provide_supporting_info"
        v.flags.append("auto_evidence")
        v.evidence_plan = [
            {
                "evidence_type": "OTHER",
                "notes": "A refund for this transaction was already issued through PayPal; see the refund on the transaction.",
            }
        ]
        v.rules.append(
            Rule(
                "R12",
                "Buyer says a promised credit was not processed, but the seller already refunded: show the refund instead of paying twice.",
                POLICY["INQUIRY"],
            )
        )
    else:
        v.verdict, v.action, v.confidence, v.p_keep = "REPLY_AND_WAIT", "send_message", "low", _P["wait"]
        v.rules.append(
            Rule("R9", f"Reason {b.reason} has no specialised rule; reply to the buyer, gather facts, and re-run.", POLICY["INQUIRY"])
        )

    if b.amount < 15 and v.verdict != "NO_ACTION_AVAILABLE" and not full_proof and "accept_claim" in b.links:
        v.verdict, v.action, v.confidence, v.p_keep = "REFUND_NOW", "accept_claim", "high", 0.0
        v.rules.append(
            Rule("R8", f"Amount ${b.amount:.2f} is below the handling cost (${cost:.2f}); contesting cannot pay off.", POLICY["DEADLINE"])
        )

    return _finalize(v, b, cost)


def _has_full_proof(b: EvidenceBundle) -> bool:
    t = b.best_tracker
    return bool(
        t
        and t.tracking_number
        and t.status.upper() in ("SHIPPED", "DELIVERED", "IN_TRANSIT")
        and b.tracker_matches_paypal_address is not False
    )


def _decide_inr(b: EvidenceBundle, v: Verdict, full_proof: bool, cost: float) -> None:
    t = b.best_tracker
    covered = "ITEM_NOT_RECEIVED" in b.protection_covers
    if not b.is_physical:
        v.verdict, v.action, v.confidence, v.p_keep = "REFUND_NOW", "accept_claim", "high", _P["no_proof"]
        v.rules.append(
            Rule(
                "R2b",
                "Intangible/digital item: no shipment proof is possible and Seller Protection does not apply.",
                POLICY["SP_INELIGIBLE"],
            )
        )
        return
    if full_proof and covered:
        assert t is not None
        v.p_keep = _P["proof_full"]
        v.confidence = "high" if t.status.upper() == "DELIVERED" or b.seller_has_signature_proof else "medium"
        v.rules.append(
            Rule(
                "R1",
                f"Seller Protection ELIGIBLE for ITEM_NOT_RECEIVED and PayPal already holds tracking "
                f"{t.carrier} {t.tracking_number} ({t.status}) to the PayPal address.",
                POLICY["SP_INR"],
            )
        )
        v.evidence_plan = [
            {
                "evidence_type": "PROOF_OF_FULFILLMENT",
                "evidence_info": {"tracking_info": [{**carrier_for_paypal(t.carrier), "tracking_number": t.tracking_number}]},
                "notes": _notes_shipped(b, t),
            }
        ]
        if b.seller_has_signature_proof:
            v.evidence_plan.append({"evidence_type": "PROOF_OF_DELIVERY_SIGNATURE", "notes": "Carrier signature confirmation attached."})
        v.flags.append("auto_evidence")  # proof is already in PayPal; submitting it is one API call
        if b.requested_evidence:
            v.flags.append("paypal_requested:" + ",".join(b.requested_evidence))
        if "provide_evidence" in b.links:
            v.verdict, v.action = "RESPOND_WITH_EVIDENCE", "provide_evidence"
        elif "provide_supporting_info" in b.links and b.supporting_info_submitted:
            v.verdict, v.action = "NO_ACTION_AVAILABLE", None
            v.rules.append(
                Rule(
                    "R1d",
                    f"Tracking is on file and you already sent {b.supporting_info_submitted} supporting note(s); PayPal is reviewing. Do NOT refund.",
                    POLICY["HATEOAS"],
                )
            )
        elif "provide_supporting_info" in b.links:
            v.verdict, v.action = "RESPOND_WITH_EVIDENCE", "provide_supporting_info"
            v.rules.append(
                Rule(
                    "R1b",
                    "PayPal is reviewing and only accepts supporting information now; add the tracking as a note. Do NOT refund: proof is on file.",
                    POLICY["HATEOAS"],
                )
            )
        else:
            v.verdict, v.action, v.p_keep = "NO_ACTION_AVAILABLE", None, _P["proof_full"]
            v.rules.append(
                Rule(
                    "R1c",
                    "Proof of shipment is on file and PayPal is reviewing; no seller action is open. Do NOT refund.",
                    POLICY["HATEOAS"],
                )
            )
        return
    if t and t.tracking_number and b.tracker_matches_paypal_address is False:
        if b.seller_has_signature_proof and "provide_evidence" in b.links:
            v.verdict, v.action, v.confidence, v.p_keep = "RESPOND_WITH_EVIDENCE", "provide_evidence", "low", _P["proof_partial"]
            v.evidence_plan = [
                {"evidence_type": "PROOF_OF_DELIVERY_SIGNATURE", "notes": "Signed delivery to the buyer at the address they requested."}
            ]
        else:
            v.verdict, v.action, v.confidence, v.p_keep = "REFUND_NOW", "accept_claim", "medium", _P["no_proof"]
        v.rules.append(
            Rule(
                "R3",
                "Shipment went to an address different from the one on the PayPal transaction; Seller Protection does not apply.",
                POLICY["SP_INELIGIBLE"],
            )
        )
        return
    if t and t.tracking_number and t.status.upper() in ("SHIPPED", "IN_TRANSIT", "DELIVERED") and not covered:
        # tracking exists but protection says NOT_ELIGIBLE (e.g. direct card). PayPal still weighs delivery proof,
        # and the proof is already in PayPal's data, so submitting it is free (adjudicated with second rater, eval/README.md).
        plan = [
            {
                "evidence_type": "PROOF_OF_FULFILLMENT" if t.status.upper() == "DELIVERED" else "ONLINE_TRACKING_INFORMATION",
                "evidence_info": {"tracking_info": [{**carrier_for_paypal(t.carrier), "tracking_number": t.tracking_number}]},
                "notes": _notes_shipped(b, t),
            }
        ]
        v.flags.append("auto_evidence")
        if "provide_evidence" in b.links or "provide_supporting_info" in b.links:
            v.verdict, v.confidence = "RESPOND_WITH_EVIDENCE", "medium" if t.status.upper() == "DELIVERED" else "low"
            v.p_keep = _P["proof_partial"] if t.status.upper() == "DELIVERED" else _P["wait"]
            v.action = "provide_evidence" if "provide_evidence" in b.links else "provide_supporting_info"
            v.evidence_plan = plan
            v.rules.append(
                Rule(
                    "R4c",
                    "Tracking exists but the transaction is NOT_ELIGIBLE for Seller Protection; PayPal still reviews shipment proof on the merits, and the proof is already on file.",
                    POLICY["SP_INELIGIBLE"],
                )
            )
            return
        v.verdict, v.action, v.confidence, v.p_keep = "REPLY_AND_WAIT", "send_message", "medium", _P["proof_partial"]
        v.rules.append(
            Rule(
                "R4b",
                "Tracking exists but the transaction is NOT_ELIGIBLE for Seller Protection; share tracking and offer to reship/refund if undelivered.",
                POLICY["SP_INELIGIBLE"],
            )
        )
        v.message_draft = _msg_in_transit(b, t)
        if "send_message" not in b.links:
            v.action = None
        return
    if t and t.tracking_number and t.status.upper() in ("SHIPPED", "IN_TRANSIT") and b.expected_delivery and b.expected_delivery > b.now:
        v.verdict, v.action, v.confidence, v.p_keep = "REPLY_AND_WAIT", "send_message", "medium", _P["wait"]
        v.rules.append(
            Rule(
                "R4",
                "Package is still in transit and the expected delivery date has not passed; reply with tracking and the date.",
                POLICY["INQUIRY"],
            )
        )
        v.message_draft = _msg_in_transit(b, t)
        if "send_message" not in b.links:
            v.action = "provide_evidence" if "provide_evidence" in b.links else "accept_claim"
        return
    # no usable tracking in PayPal
    if b.evidences_submitted:
        v.verdict, v.confidence, v.p_keep = "REPLY_AND_WAIT", "medium", _P["proof_partial"]
        v.action = "send_message" if "send_message" in b.links else None
        v.rules.append(
            Rule(
                "R11",
                f"Seller already submitted {', '.join(b.evidences_submitted)}; PayPal has not added tracking to the order. Wait for the buyer/PayPal rather than refunding.",
                POLICY["INQUIRY"],
            )
        )
        v.flags.append("evidence_already_submitted")
        v.message_draft = "Hi, we've shared the shipment details with PayPal. Please let us know if the package hasn't arrived by the expected date and we'll make it right."
        return
    v.verdict, v.action, v.confidence, v.p_keep = "REFUND_NOW", "accept_claim", "high", _P["no_proof"]
    v.rules.append(
        Rule(
            "R2",
            "PayPal has no tracking for this order and the seller has no shipment proof; an INR claim without proof is lost and costs time.",
            POLICY["SP_INR"],
        )
    )
    if "accept_claim" not in b.links:
        v.action = "send_message" if "send_message" in b.links else None
        v.flags.append("accept_claim_not_offered")


def _decide_snad(b: EvidenceBundle, v: Verdict, cost: float) -> None:
    v.rules.append(
        Rule("R5", "SNAD is not covered by Seller Protection; PayPal weighs listing accuracy, photos and return policy.", POLICY["SP_SNAD"])
    )
    if b.seller_has_listing_evidence and "provide_evidence" in b.links:
        v.verdict, v.action, v.confidence, v.p_keep = "RESPOND_WITH_EVIDENCE", "provide_evidence", "medium", _P["snad_evidence"]
        v.evidence_plan = [{"evidence_type": "ITEM_DESCRIPTION", "notes": "Listing text and photos match the item shipped; see attached."}]
        if b.seller_has_return_policy:
            v.evidence_plan.append({"evidence_type": "RETURN_POLICY", "notes": "Return policy shown at checkout."})
        return
    if "make_offer" in b.links and b.amount >= 15:
        v.verdict, v.action, v.confidence, v.p_keep = "OFFER_PARTIAL", "make_offer", "medium", 0.5
        v.rules.append(
            Rule(
                "R5b", "Without listing evidence, a partial refund offer usually beats a full loss plus return shipping.", POLICY["SP_SNAD"]
            )
        )
        v.message_draft = (
            f"We're sorry the item wasn't as expected. We'd like to offer a partial refund of ${b.amount / 2:.2f} so you can keep it."
        )
        return
    v.verdict, v.action, v.confidence, v.p_keep = "REFUND_NOW", "accept_claim", "medium", _P["no_proof"]
    v.rules.append(
        Rule("R5c", "No listing evidence and no offer option: refund (with return if allowed) to close quickly.", POLICY["SP_SNAD"])
    )
    if "accept_claim" not in b.links:
        v.action = "send_message" if "send_message" in b.links else None


def _decide_unauth(b: EvidenceBundle, v: Verdict, full_proof: bool, cost: float) -> None:
    covered = "UNAUTHORIZED_TRANSACTION" in b.protection_covers
    t = b.best_tracker
    if covered and full_proof and "provide_evidence" in b.links:
        assert t is not None
        v.verdict, v.action, v.confidence, v.p_keep = "RESPOND_WITH_EVIDENCE", "provide_evidence", "high", _P["unauth_proof"]
        v.rules.append(
            Rule(
                "R6",
                "Seller Protection ELIGIBLE for UNAUTHORIZED_TRANSACTION and the item shipped to the PayPal address with tracking.",
                POLICY["SP_UNAUTH"],
            )
        )
        v.evidence_plan = [
            {
                "evidence_type": "PROOF_OF_FULFILLMENT",
                "evidence_info": {"tracking_info": [{**carrier_for_paypal(t.carrier), "tracking_number": t.tracking_number}]},
                "notes": _notes_shipped(b, t),
            }
        ]
        return
    v.verdict, v.action, v.confidence, v.p_keep = "REFUND_NOW", "accept_claim", "high", _P["no_proof"]
    v.rules.append(
        Rule(
            "R6b",
            "Unauthorized claim without Seller Protection coverage or shipment proof: the seller carries the loss either way; refund to avoid fees.",
            POLICY["SP_INELIGIBLE"],
        )
    )
    if "accept_claim" not in b.links:
        v.action = "send_message" if "send_message" in b.links else None


def _finalize(v: Verdict, b: EvidenceBundle, cost: float) -> Verdict:
    if v.verdict == "REFUND_NOW" or v.verdict == "NO_ACTION_AVAILABLE":
        v.expected_value = 0.0 if v.verdict == "REFUND_NOW" else 0.0
    elif v.verdict == "OFFER_PARTIAL":
        v.expected_value = round(0.5 * b.amount - cost, 2)
    else:
        eff_cost = AUTO_EVIDENCE_COST if "auto_evidence" in v.flags else cost
        v.expected_value = round(v.p_keep * b.amount - eff_cost, 2)
    # safety: the action must be one PayPal allows now
    if v.action and v.action not in b.links:
        v.flags.append(f"action_{v.action}_not_allowed_now")
        v.action = None
    # if the chosen path has non-positive EV, REFUND_NOW dominates
    if (
        v.verdict in ("RESPOND_WITH_EVIDENCE", "OFFER_PARTIAL", "REPLY_AND_WAIT")
        and v.expected_value <= 0
        and "accept_claim" in b.links
        and "auto_evidence" not in v.flags
    ):
        v.rules.append(
            Rule(
                "R10",
                f"Expected value of contesting (${v.expected_value:.2f}) is not positive; refunding now is cheaper.",
                POLICY["DEADLINE"],
            )
        )
        v.verdict, v.action, v.p_keep, v.expected_value = "REFUND_NOW", "accept_claim", 0.0, 0.0
    if not v.message_draft:
        v.message_draft = _default_message(b, v)
    return v


def _notes_shipped(b: EvidenceBundle, t) -> str:
    a = b.paypal_ship_to
    addr = f"{a.address_line_1}, {a.admin_area_2} {a.admin_area_1} {a.postal_code}" if a else "the address on the PayPal transaction"
    return f"Order shipped via {t.carrier or 'carrier'} tracking {t.tracking_number} (status: {t.status}) to {addr}, which matches the PayPal transaction address."


def _msg_in_transit(b: EvidenceBundle, t) -> str:
    eta = f" The expected delivery date is {b.expected_delivery.date().isoformat()}." if b.expected_delivery else ""
    return (
        f"Hi, thanks for reaching out. Your order shipped via {t.carrier or 'our carrier'} with tracking {t.tracking_number} "
        f"and is currently {t.status.lower().replace('_', ' ')}.{eta} If it doesn't arrive, reply here and we will reship or refund."
    )


def _default_message(b: EvidenceBundle, v: Verdict) -> str:
    if v.verdict == "REFUND_NOW":
        return "We're sorry about this order. We've issued a full refund through PayPal; it should appear within a few days."
    if v.verdict == "RESPOND_WITH_EVIDENCE" and v.evidence_plan:
        return v.evidence_plan[0].get("notes", "")
    return ""


# ---------------- counterfactuals & robustness ----------------


def counterfactuals(b: EvidenceBundle) -> list[dict]:
    """What seller-side change would change this verdict? Only changes the seller could actually make."""
    from .bundle import Tracker

    base = decide(b)
    out = []
    addr = b.paypal_ship_to
    cands: list[tuple[str, dict]] = []
    if not b.best_tracker or not b.best_tracker.tracking_number:
        cands.append(
            (
                "Add carrier tracking for a shipment to the PayPal address",
                {"trackers": [Tracker(carrier="USPS", tracking_number="<tracking>", status="SHIPPED", ship_to=addr)]},
            )
        )
    elif b.best_tracker.status.upper() != "DELIVERED":
        cands.append(("Tracking shows DELIVERED", {"trackers": [b.best_tracker.model_copy(update={"status": "DELIVERED"})]}))
    if not b.seller_has_signature_proof:
        cands.append(("Provide signature confirmation of delivery", {"seller_has_signature_proof": True}))
    if b.reason == SNAD and not b.seller_has_listing_evidence:
        cands.append(("Provide listing text/photos matching the item", {"seller_has_listing_evidence": True}))
    if b.reason == SNAD and not b.seller_has_return_policy:
        cands.append(("Show the return policy displayed at checkout", {"seller_has_return_policy": True}))
    for label, upd in cands:
        v = decide(b.model_copy(update=upd))
        if v.verdict != base.verdict or v.action != base.action:
            out.append(
                {
                    "change": label,
                    "verdict": v.verdict,
                    "action": v.action,
                    "expected_value": v.expected_value,
                    "ev_delta": round(v.expected_value - base.expected_value, 2),
                    "rules": [r.id for r in v.rules],
                }
            )
    return out


def robustness(b: EvidenceBundle, p_scales=(0.5, 0.75, 1.0, 1.25), costs=(0, 4, 8, 15, 25)) -> dict:
    """How stable is the verdict when the documented assumptions move? Returns fraction of the grid that agrees."""
    base = decide(b).verdict
    grid = [(ps, c) for ps in p_scales for c in costs]
    same = sum(1 for ps, c in grid if decide(b, handling_cost=c, p_scale=ps).verdict == base)
    _P.scale = 1.0
    return {"verdict": base, "agreement": round(same / len(grid), 2), "grid": len(grid), "robust": same / len(grid) >= 0.9}
