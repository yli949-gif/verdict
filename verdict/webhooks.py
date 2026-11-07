"""PayPal webhooks → re-evaluate disputes as they change, instead of polling.

Events: CUSTOMER.DISPUTE.CREATED / UPDATED / RESOLVED. Signature verification uses PayPal's own
endpoint (`POST /v1/notifications/verify-webhook-signature`) with the webhook id from the developer
dashboard (PAYPAL_WEBHOOK_ID). Set VERDICT_WEBHOOK_VERIFY=false only for local simulation.

Register the webhook (sandbox dashboard → your app → Webhooks → Add) pointing at
https://<host>/webhooks/paypal with the three CUSTOMER.DISPUTE.* events, or simulate one with
`python -m eval.simulate_webhook`.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import settings

EVENTS = {"CUSTOMER.DISPUTE.CREATED", "CUSTOMER.DISPUTE.UPDATED", "CUSTOMER.DISPUTE.RESOLVED"}
INBOX = settings.data_dir / "events.jsonl"
WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")
VERIFY = os.environ.get("VERDICT_WEBHOOK_VERIFY", "true").lower() != "false"


def verify_signature(client, headers: dict[str, str], body: bytes) -> bool:
    """Ask PayPal whether this delivery is genuine. Returns False on any doubt."""
    if not VERIFY:
        return True
    if not WEBHOOK_ID or not hasattr(client, "_request"):
        return False
    h = {k.lower(): v for k, v in headers.items()}
    try:
        payload = {
            "auth_algo": h.get("paypal-auth-algo", ""),
            "cert_url": h.get("paypal-cert-url", ""),
            "transmission_id": h.get("paypal-transmission-id", ""),
            "transmission_sig": h.get("paypal-transmission-sig", ""),
            "transmission_time": h.get("paypal-transmission-time", ""),
            "webhook_id": WEBHOOK_ID,
            "webhook_event": json.loads(body),
        }
        r = client._request("POST", "/v1/notifications/verify-webhook-signature", json_body=payload, action="verify_webhook")
        return r.get("verification_status") == "SUCCESS"
    except Exception:
        return False


def record(event: dict[str, Any], verdict: dict | None, verified: bool) -> dict:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "event_type": event.get("event_type"),
        "event_id": event.get("id"),
        "dispute_id": (event.get("resource") or {}).get("dispute_id"),
        "status": (event.get("resource") or {}).get("status"),
        "verified": verified,
        "verdict": verdict and verdict.get("verdict"),
        "action": verdict and verdict.get("action"),
        "deadline_hours": verdict and verdict.get("deadline_hours"),
    }
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    with INBOX.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_events(limit: int = 100) -> list[dict]:
    if not INBOX.exists():
        return []
    rows = [json.loads(line) for line in INBOX.read_text().splitlines() if line.strip()]
    return rows[-limit:]


def sample_event(dispute_id: str, event_type: str = "CUSTOMER.DISPUTE.UPDATED", status: str = "WAITING_FOR_SELLER_RESPONSE") -> dict:
    """Shape of PayPal's CUSTOMER.DISPUTE.* webhook payload (resource = dispute summary)."""
    return {
        "id": "WH-" + Path(os.urandom(6).hex()).name,
        "event_version": "1.0",
        "create_time": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "resource_type": "dispute",
        "event_type": event_type,
        "summary": f"A dispute {dispute_id} was {event_type.split('.')[-1].lower()}",
        "resource": {
            "dispute_id": dispute_id,
            "status": status,
            "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
            "dispute_life_cycle_stage": "INQUIRY",
        },
    }
