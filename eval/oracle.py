"""Ground-truth oracle for the evaluation — deliberately written as a flat decision table, separate
from the engine, so the engine is checked against an independent reading of PayPal's policy.

What a label means: "the response PayPal's published Seller Protection / dispute rules say a seller
should give, given only what PayPal has on file". It is NOT PayPal's adjudication outcome.
Labels were reviewed by hand (see eval/README.md); edit this table, not the cases, to change them.
"""
from __future__ import annotations

from verdict.bundle import EvidenceBundle

INR = "MERCHANDISE_OR_SERVICE_NOT_RECEIVED"
SNAD = "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED"
UNAUTH = "UNAUTHORISED"
HANDLING_COST = 15.0  # USD, reviewed assumption: manual evidence gathering is not worth it below this


def label(b: EvidenceBundle) -> tuple[str, str]:
    """Returns (verdict, reason)."""
    links = set(b.links)
    seller_actions = links & {"accept_claim", "provide_evidence", "make_offer", "send_message", "escalate", "provide_supporting_info"}
    t = b.best_tracker
    has_tracking = bool(t and t.tracking_number and t.status.upper() in ("SHIPPED", "DELIVERED", "IN_TRANSIT"))
    addr_ok = b.tracker_matches_paypal_address is not False
    eligible = b.seller_protection_status in ("ELIGIBLE", "PARTIALLY_ELIGIBLE")

    if not seller_actions:
        return "NO_ACTION_AVAILABLE", "PayPal exposes no seller action"

    if b.reason == INR:
        if not b.is_physical:
            return "REFUND_NOW", "intangible item: no shipping proof possible"
        if has_tracking and addr_ok and eligible and "ITEM_NOT_RECEIVED" in b.seller_protection_categories:
            if "provide_evidence" in links:
                return "RESPOND_WITH_EVIDENCE", "covered INR with tracking to PayPal address"
            if "provide_supporting_info" in links and not b.supporting_info_submitted:
                return "RESPOND_WITH_EVIDENCE", "covered INR with tracking; PayPal reviewing, add supporting note"
            return "NO_ACTION_AVAILABLE", "proof on file, PayPal reviewing, no submit link"
        if has_tracking and not addr_ok:
            return ("RESPOND_WITH_EVIDENCE" if b.seller_has_signature_proof and "provide_evidence" in links else "REFUND_NOW"), "shipped to a different address"
        if has_tracking and not eligible:
            if t.status.upper() == "DELIVERED" and ("provide_evidence" in links or "provide_supporting_info" in links):
                return "RESPOND_WITH_EVIDENCE", "delivered proof, not protected: PayPal reviews on merits"
            return "REPLY_AND_WAIT", "tracking but not protected: inform buyer"
        if has_tracking and b.expected_delivery and b.expected_delivery > b.now:
            return "REPLY_AND_WAIT", "in transit before expected date"
        if b.evidences_submitted:
            return "REPLY_AND_WAIT", "already responded; await"
        if b.amount < 15 and "accept_claim" not in links:
            return "REPLY_AND_WAIT", "tiny amount, cannot accept yet"
        return "REFUND_NOW", "no proof of shipment"

    if b.reason == SNAD:
        if b.amount < HANDLING_COST and "accept_claim" in links:
            return "REFUND_NOW", "SNAD below handling cost: gathering listing evidence costs more than the item"
        if b.seller_has_listing_evidence and "provide_evidence" in links:
            return "RESPOND_WITH_EVIDENCE", "listing evidence available"
        if "make_offer" in links and b.amount >= 15:
            return "OFFER_PARTIAL", "no listing evidence; offer beats loss + return"
        return "REFUND_NOW", "SNAD without evidence"

    if b.reason == UNAUTH:
        if eligible and "UNAUTHORIZED_TRANSACTION" in b.seller_protection_categories and has_tracking and addr_ok and "provide_evidence" in links:
            return "RESPOND_WITH_EVIDENCE", "covered unauthorized claim with shipment proof"
        return "REFUND_NOW", "unauthorized without coverage/proof"

    return "REPLY_AND_WAIT", "uncommon reason: gather facts"
