"""Property-based tests: invariants the engine must hold for *any* evidence bundle."""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from verdict.bundle import Address, EvidenceBundle, Item, Tracker
from verdict.contract import validate
from verdict.engine import ACTION_FOR, decide
from verdict.statemachine import STATES, links_for

NOW = datetime(2026, 11, 7, tzinfo=UTC)
ADDR = Address(address_line_1="2211 N First St", admin_area_2="San Jose", admin_area_1="CA", postal_code="95131", country_code="US")
OTHER = Address(address_line_1="9 Elm Ave", admin_area_2="Fresno", admin_area_1="CA", postal_code="93650", country_code="US")

reasons = st.sampled_from(
    ["MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED", "UNAUTHORISED", "CREDIT_NOT_PROCESSED", "OTHER"]
)
protection = st.sampled_from(["ELIGIBLE", "PARTIALLY_ELIGIBLE", "NOT_ELIGIBLE", "UNKNOWN"])
tracker = st.one_of(
    st.none(),
    st.builds(
        Tracker,
        carrier=st.sampled_from(["USPS", "UPS", "Canada Post", ""]),
        tracking_number=st.sampled_from(["", "9400100000000000000001"]),
        status=st.sampled_from(["SHIPPED", "DELIVERED", "IN_TRANSIT", "CANCELLED", "ON_HOLD", ""]),
        ship_to=st.sampled_from([ADDR, OTHER]),
    ),
)
state_names = st.sampled_from(list(STATES))


@st.composite
def bundles(draw):
    state = draw(state_names)
    t = draw(tracker)
    sp = draw(protection)
    return state, EvidenceBundle(
        dispute_id="H-1",
        reason=draw(reasons),
        status=STATES[state].status,
        life_cycle_stage=STATES[state].stage,
        amount=draw(st.floats(min_value=0, max_value=5000, allow_nan=False, allow_infinity=False)),
        links=links_for(state),
        seller_protection_status=sp,
        seller_protection_categories=["ITEM_NOT_RECEIVED", "UNAUTHORIZED_TRANSACTION"] if sp in ("ELIGIBLE", "PARTIALLY_ELIGIBLE") else [],
        items=[Item(item_id="A", name="x", item_type=draw(st.sampled_from(["PRODUCT", "DIGITAL", "SERVICE"])))],
        paypal_ship_to=draw(st.sampled_from([ADDR, None])),
        trackers=[t] if t else [],
        evidences_submitted=draw(st.sampled_from([[], ["PROOF_OF_FULFILLMENT"]])),
        supporting_info_submitted=draw(st.integers(min_value=0, max_value=2)),
        seller_has_signature_proof=draw(st.booleans()),
        seller_has_listing_evidence=draw(st.booleans()),
        seller_response_due=NOW + timedelta(hours=draw(st.integers(min_value=-48, max_value=600)))
        if "SELLER" in STATES[state].status
        else None,
        now=NOW,
    )


@hsettings(max_examples=400, deadline=None)
@given(bundles())
def test_action_always_admitted_by_links(sb):
    state, b = sb
    v = decide(b)
    assert v.action is None or v.action in b.links, (state, v.action, b.links)
    assert v.action is None or v.action in STATES[state].links


@hsettings(max_examples=400, deadline=None)
@given(bundles())
def test_verdict_vocabulary_and_action_consistency(sb):
    _, b = sb
    v = decide(b)
    assert v.verdict in ACTION_FOR
    if v.verdict == "NO_ACTION_AVAILABLE":
        assert v.action is None
    if v.verdict == "REFUND_NOW" and v.action:
        assert v.action == "accept_claim"
    assert v.rules, "every verdict must cite at least one rule"
    assert all(r.policy_basis for r in v.rules)


@hsettings(max_examples=400, deadline=None)
@given(bundles())
def test_evidence_plan_passes_paypal_contract(sb):
    _, b = sb
    v = decide(b)
    if v.action == "provide_evidence":
        assert v.evidence_plan, "provide_evidence without a plan"
        validate("provide_evidence", {"evidences": v.evidence_plan})  # raises ContractError if PayPal would reject it


@hsettings(max_examples=300, deadline=None)
@given(bundles())
def test_adding_shipment_proof_never_turns_contest_into_refund(sb):
    _, b = sb
    if b.reason != "MERCHANDISE_OR_SERVICE_NOT_RECEIVED" or not b.is_physical or "provide_evidence" not in b.links:
        return
    before = decide(b)
    b2 = b.model_copy(
        update={
            "trackers": [
                Tracker(carrier="USPS", tracking_number="9400100000000000000009", status="DELIVERED", ship_to=b.paypal_ship_to or ADDR)
            ],
            "seller_protection_status": "ELIGIBLE",
            "seller_protection_categories": ["ITEM_NOT_RECEIVED"],
        }
    )
    after = decide(b2)
    if before.verdict in ("RESPOND_WITH_EVIDENCE", "REPLY_AND_WAIT", "OFFER_PARTIAL"):
        assert after.verdict != "REFUND_NOW"
    assert after.verdict == "RESPOND_WITH_EVIDENCE"


@hsettings(max_examples=200, deadline=None)
@given(bundles(), st.floats(min_value=0, max_value=50))
def test_expected_value_bounds(sb, cost):
    _, b = sb
    v = decide(b, handling_cost=cost)
    assert -cost - 1e-6 <= v.expected_value <= b.amount + 1e-6
    assert v.ev_refund_now == 0.0
