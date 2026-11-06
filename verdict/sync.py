"""Pull disputes + related capture/order from PayPal and build EvidenceBundles. Caches raw JSON in data/."""
from __future__ import annotations

import json
from pathlib import Path

from .bundle import EvidenceBundle, bundle_from_paypal
from .config import settings
from .paypal import PayPalClient, PayPalError

RAW = settings.data_dir / "raw"
RAW.mkdir(parents=True, exist_ok=True)
SELLER_FACTS = settings.data_dir / "seller_facts.json"  # optional per-dispute facts the seller supplies in the UI


def _save(name: str, obj: dict) -> None:
    (RAW / f"{name}.json").write_text(json.dumps(obj, indent=2))


def load_seller_facts() -> dict:
    return json.loads(SELLER_FACTS.read_text()) if SELLER_FACTS.exists() else {}


def save_seller_fact(dispute_id: str, facts: dict) -> None:
    all_ = load_seller_facts()
    all_.setdefault(dispute_id, {}).update(facts)
    SELLER_FACTS.write_text(json.dumps(all_, indent=2))


def fetch_bundle(client: PayPalClient, dispute_id: str) -> tuple[EvidenceBundle, dict]:
    dispute = client.get_dispute(dispute_id)
    _save(f"dispute_{dispute_id}", dispute)
    txn = (dispute.get("disputed_transactions") or [{}])[0]
    capture = order = None
    cap_id = txn.get("seller_transaction_id")
    if cap_id:
        try:
            capture = client.get_capture(cap_id)
            _save(f"capture_{cap_id}", capture)
            order_id = ((capture.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
            if order_id:
                order = client.get_order(order_id)
                for pu in order.get("purchase_units", []):
                    for t in (pu.get("shipping") or {}).get("trackers", []):
                        if not t.get("carrier") and t.get("id"):
                            try:
                                full = client.get_tracker(t["id"])
                                t["carrier"], t["tracking_number"] = full.get("carrier", ""), full.get("tracking_number", t.get("tracking_number", ""))
                                t["status"] = full.get("status", t.get("status", ""))
                            except PayPalError:
                                pass
                _save(f"order_{order_id}", order)
        except PayPalError as e:  # capture may be unreachable (e.g. not ours); engine handles UNKNOWN
            dispute.setdefault("_verdict_warnings", []).append(str(e))
    facts = load_seller_facts().get(dispute_id, {})
    return bundle_from_paypal(dispute, capture, order, facts), dispute


def list_dispute_ids(client: PayPalClient) -> list[dict]:
    """All disputes the merchant can see, newest first (actionable ones first)."""
    seen: dict[str, dict] = {}
    for state in ("REQUIRED_ACTION", "REQUIRED_OTHER_PARTY_ACTION", "UNDER_PAYPAL_REVIEW", "RESOLVED", "OPEN_INQUIRIES"):
        try:
            for d in client.list_disputes(dispute_state=state):
                seen.setdefault(d["dispute_id"], {**d, "_state_bucket": state})
        except PayPalError:
            continue
    try:
        for d in client.list_disputes():
            seen.setdefault(d["dispute_id"], {**d, "_state_bucket": "ALL"})
    except PayPalError:
        pass
    return sorted(seen.values(), key=lambda d: d.get("update_time", ""), reverse=True)
