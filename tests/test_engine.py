import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from verdict.bundle import Address, EvidenceBundle, Item, Tracker, bundle_from_paypal
from verdict.engine import decide

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)
ADDR = Address(address_line_1="2211 N First St", admin_area_2="San Jose", admin_area_1="CA", postal_code="95131", country_code="US")


def bundle(**kw) -> EvidenceBundle:
    base = dict(dispute_id="T-1", reason="MERCHANDISE_OR_SERVICE_NOT_RECEIVED", status="WAITING_FOR_SELLER_RESPONSE", amount=62.0,
                links=["self", "accept_claim", "provide_evidence", "send_message", "escalate", "make_offer"],
                seller_protection_status="ELIGIBLE", seller_protection_categories=["ITEM_NOT_RECEIVED", "UNAUTHORIZED_TRANSACTION"],
                items=[Item(item_id="A", name="thing")], paypal_ship_to=ADDR, now=NOW,
                seller_response_due=NOW + timedelta(days=10))
    base.update(kw)
    return EvidenceBundle(**base)


def test_inr_with_tracking_responds_with_evidence():
    v = decide(bundle(trackers=[Tracker(carrier="USPS", tracking_number="9400111", status="DELIVERED", ship_to=ADDR)]))
    assert v.verdict == "RESPOND_WITH_EVIDENCE" and v.action == "provide_evidence"
    assert v.evidence_plan[0]["evidence_type"] == "PROOF_OF_FULFILLMENT"
    assert v.evidence_plan[0]["evidence_info"]["tracking_info"][0]["tracking_number"] == "9400111"
    assert v.expected_value > 0 and "R1" in [r.id for r in v.rules]


def test_inr_without_tracking_refunds():
    v = decide(bundle())
    assert v.verdict == "REFUND_NOW" and v.action == "accept_claim" and v.expected_value == 0


def test_tracking_to_wrong_address_refunds():
    other = Address(address_line_1="9 Elm Ave", admin_area_2="Fresno", admin_area_1="CA", postal_code="93650", country_code="US")
    v = decide(bundle(trackers=[Tracker(carrier="USPS", tracking_number="9400222", status="DELIVERED", ship_to=other)]))
    assert v.verdict == "REFUND_NOW" and "R3" in [r.id for r in v.rules]


def test_no_links_means_no_action_and_never_refund():
    v = decide(bundle(links=["self"], trackers=[Tracker(carrier="USPS", tracking_number="9400111", status="DELIVERED", ship_to=ADDR)]))
    assert v.verdict == "NO_ACTION_AVAILABLE" and v.action is None


def test_action_is_always_an_allowed_link():
    for links in (["self", "accept_claim"], ["self", "provide_evidence"], ["self", "send_message"], ["self", "provide_supporting_info"], ["self"]):
        for trk in ([], [Tracker(carrier="USPS", tracking_number="9400111", status="DELIVERED", ship_to=ADDR)]):
            for reason in ("MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED", "UNAUTHORISED"):
                v = decide(bundle(links=links, trackers=trk, reason=reason))
                assert v.action is None or v.action in links, (links, trk, reason, v.action)


def test_proof_on_file_under_review_uses_supporting_info():
    v = decide(bundle(status="UNDER_REVIEW", links=["self", "accept_claim", "provide_supporting_info"],
                      trackers=[Tracker(carrier="USPS", tracking_number="9400111", status="SHIPPED", ship_to=ADDR)]))
    assert v.verdict == "RESPOND_WITH_EVIDENCE" and v.action == "provide_supporting_info"


def test_small_amount_without_proof_refunds_and_small_with_proof_still_responds():
    assert decide(bundle(amount=9.5)).verdict == "REFUND_NOW"
    v = decide(bundle(amount=9.5, trackers=[Tracker(carrier="USPS", tracking_number="9400111", status="DELIVERED", ship_to=ADDR)]))
    assert v.verdict == "RESPOND_WITH_EVIDENCE"  # proof already in PayPal: submitting is ~free


def test_snad_with_listing_evidence_vs_without():
    assert decide(bundle(reason="MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED", amount=120, seller_has_listing_evidence=True)).verdict == "RESPOND_WITH_EVIDENCE"
    assert decide(bundle(reason="MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED", amount=120)).verdict == "OFFER_PARTIAL"


def test_unauthorised_not_eligible_refunds():
    v = decide(bundle(reason="UNAUTHORISED", seller_protection_status="NOT_ELIGIBLE", seller_protection_categories=[],
                      trackers=[Tracker(carrier="USPS", tracking_number="9400111", status="DELIVERED", ship_to=ADDR)]))
    assert v.verdict == "REFUND_NOW"


def test_deadline_flag():
    v = decide(bundle(seller_response_due=NOW + timedelta(hours=10)))
    assert "deadline_under_48h" in v.flags


def test_bundle_from_real_sandbox_json():
    raw = Path(__file__).parent / "fixtures"
    d = json.loads((raw / "dispute.json").read_text()); c = json.loads((raw / "capture.json").read_text()); o = json.loads((raw / "order.json").read_text())
    b = bundle_from_paypal(d, c, o)
    assert b.capture_id == c["id"] and b.seller_protection_status == "ELIGIBLE"
    assert b.trackers and b.trackers[0].tracking_number == "9400100000000000000002"
    assert b.paypal_ship_to.postal_code == "95131"
