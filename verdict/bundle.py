"""EvidenceBundle: everything the engine is allowed to look at, normalized from PayPal objects.

Built from (1) the dispute, (2) the capture (seller_protection), (3) the order (ship-to address,
trackers, items). The engine never sees raw PayPal JSON, so synthetic eval cases and real sandbox
cases go through the exact same code path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, computed_field


class Address(BaseModel):
    address_line_1: str = ""
    admin_area_2: str = ""  # city
    admin_area_1: str = ""  # state
    postal_code: str = ""
    country_code: str = ""

    def key(self) -> str:
        return "|".join(x.strip().lower() for x in (self.address_line_1, self.postal_code, self.country_code))


class Tracker(BaseModel):
    carrier: str = ""
    tracking_number: str = ""
    status: str = ""  # SHIPPED | ON_HOLD | DELIVERED | CANCELLED | IN_TRANSIT ...
    ship_to: Optional[Address] = None  # where the seller says it went (defaults to order address)


class Item(BaseModel):
    item_id: str = ""
    name: str = ""
    quantity: int = 1
    item_type: str = "PRODUCT"  # PRODUCT | SERVICE | DIGITAL | BOOKING


class EvidenceBundle(BaseModel):
    dispute_id: str
    reason: str  # PayPal dispute_reason enum
    status: str
    dispute_state: str = ""
    life_cycle_stage: str = ""
    amount: float
    currency: str = "USD"
    seller_response_due: Optional[datetime] = None
    links: list[str] = Field(default_factory=list)  # HATEOAS rels from PayPal
    allowed_response_options: dict[str, Any] = Field(default_factory=dict)
    # transaction
    capture_id: str = ""
    order_id: str = ""
    transaction_status: str = ""
    seller_protection_status: str = "UNKNOWN"  # ELIGIBLE | PARTIALLY_ELIGIBLE | NOT_ELIGIBLE | UNKNOWN
    seller_protection_categories: list[str] = Field(default_factory=list)
    dispute_seller_protection_eligible: Optional[bool] = None
    items: list[Item] = Field(default_factory=list)
    # fulfilment
    paypal_ship_to: Optional[Address] = None  # address PayPal has on the order
    trackers: list[Tracker] = Field(default_factory=list)
    # buyer narrative
    buyer_messages: list[str] = Field(default_factory=list)
    merchant_contacted: Optional[bool] = None
    sub_reason: str = ""  # e.g. ITEM_NOT_RECEIVED subtypes, SNAD subtypes
    # seller-side optional facts (from seller config / local store, not PayPal)
    seller_has_signature_proof: bool = False
    seller_has_listing_evidence: bool = False
    seller_has_return_policy: bool = False
    seller_refund_already_issued: bool = False
    expected_delivery: Optional[datetime] = None
    evidences_submitted: list[str] = Field(default_factory=list)
    supporting_info_submitted: int = 0  # notes the seller already sent while PayPal reviews
    now: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ----- derived helpers -----
    @computed_field  # type: ignore[misc]
    @property
    def is_physical(self) -> bool:
        return all(i.item_type in ("PRODUCT", "") for i in self.items) if self.items else True

    @property
    def best_tracker(self) -> Optional[Tracker]:
        order = {"DELIVERED": 0, "SHIPPED": 1, "IN_TRANSIT": 1, "ON_HOLD": 2, "CANCELLED": 3, "": 4}
        return min(self.trackers, key=lambda t: order.get(t.status.upper(), 4)) if self.trackers else None

    @computed_field  # type: ignore[misc]
    @property
    def tracker_matches_paypal_address(self) -> Optional[bool]:
        t = self.best_tracker
        if not t or not self.paypal_ship_to:
            return None
        ship = t.ship_to or self.paypal_ship_to
        return ship.key() == self.paypal_ship_to.key()

    @computed_field  # type: ignore[misc]
    @property
    def hours_to_deadline(self) -> Optional[float]:
        if not self.seller_response_due:
            return None
        return (self.seller_response_due - self.now).total_seconds() / 3600

    @property
    def protection_covers(self) -> set[str]:
        return set(self.seller_protection_categories) if self.seller_protection_status in ("ELIGIBLE", "PARTIALLY_ELIGIBLE") else set()


# ---------- builders from raw PayPal JSON ----------

def _addr(a: dict | None) -> Optional[Address]:
    return Address(**{k: a.get(k, "") for k in Address.model_fields}) if a else None


def _dt(s: str | None) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def bundle_from_paypal(dispute: dict, capture: dict | None, order: dict | None, seller_facts: dict | None = None) -> EvidenceBundle:
    txn = (dispute.get("disputed_transactions") or [{}])[0]
    amt = dispute.get("dispute_amount") or txn.get("gross_amount") or {}
    pu = (order or {}).get("purchase_units", [{}])[0] if order else {}
    shipping = pu.get("shipping") or {}
    ship_to = _addr(shipping.get("address"))
    trackers = []
    for t in shipping.get("trackers", []):
        # Orders v2 returns tracker ids as "<capture_id>-<tracking_number>" and no tracking_number field
        num = t.get("tracking_number") or (t.get("id", "").split("-", 1)[1] if "-" in t.get("id", "") else "")
        trackers.append(Tracker(carrier=t.get("carrier", ""), tracking_number=num, status=t.get("status", ""), ship_to=ship_to))
    items = [Item(item_id=i.get("item_id") or i.get("sku", ""), name=i.get("item_name") or i.get("name", ""),
                  quantity=int(i.get("item_quantity") or i.get("quantity") or 1), item_type=i.get("item_type", "PRODUCT"))
             for i in (txn.get("items") or pu.get("items") or [])]
    sp = (capture or {}).get("seller_protection") or {}
    ext = dispute.get("extensions") or {}
    mdp = ext.get("merchandize_dispute_properties") or {}
    sub = mdp.get("issue_type", "")
    pd = mdp.get("product_details") or {}
    if pd.get("sub_reasons"):
        sub = ",".join(pd["sub_reasons"])
    facts = seller_facts or {}
    return EvidenceBundle(
        dispute_id=dispute["dispute_id"], reason=dispute.get("reason", "OTHER"), status=dispute.get("status", ""),
        dispute_state=dispute.get("dispute_state", ""), life_cycle_stage=dispute.get("dispute_life_cycle_stage", ""),
        amount=float(amt.get("value", 0) or 0), currency=amt.get("currency_code", "USD"),
        seller_response_due=_dt(dispute.get("seller_response_due_date")),
        links=[l.get("rel", "") for l in dispute.get("links", [])],
        allowed_response_options=dispute.get("allowed_response_options") or {},
        capture_id=txn.get("seller_transaction_id", ""),
        order_id=((capture or {}).get("supplementary_data") or {}).get("related_ids", {}).get("order_id", "") or (order or {}).get("id", ""),
        transaction_status=txn.get("transaction_status", ""),
        seller_protection_status=sp.get("status", "UNKNOWN"), seller_protection_categories=sp.get("dispute_categories", []),
        dispute_seller_protection_eligible=txn.get("seller_protection_eligible"),
        items=items, paypal_ship_to=ship_to, trackers=trackers,
        buyer_messages=[m.get("content", "") for m in dispute.get("messages", []) if m.get("posted_by") == "BUYER"],
        merchant_contacted=ext.get("merchant_contacted"), sub_reason=sub,
        evidences_submitted=[e.get("evidence_type", "") for e in dispute.get("evidences", []) if e.get("source") == "SUBMITTED_BY_SELLER"],
        expected_delivery=_dt(pd.get("expected_delivery_date")),
        supporting_info_submitted=sum(1 for x in dispute.get("supporting_info", []) if x.get("source") == "SUBMITTED_BY_SELLER"),
        **{k: v for k, v in facts.items() if k in EvidenceBundle.model_fields},
    )
