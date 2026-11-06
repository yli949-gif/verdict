"""Thin, explicit PayPal REST client.

Why not only the official PayPal Agent Toolkit? The PyPI Python toolkit (1.1.0) ships no
dispute tools at all and the GitHub TypeScript one only has list/get/accept-claim. Verdict needs
provide-evidence (multipart), make-offer, send-message and escalate, so we implement them here
and expose toolkit-shaped tool definitions in `verdict.tools` for agent frameworks.

Every call that changes state is gated by `require_link()`: PayPal's HATEOAS links and
`allowed_response_options` on the dispute are the source of truth for what is allowed now.
"""
from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .config import settings


class PayPalError(Exception):
    def __init__(self, status: int, body: Any, action: str = ""):
        self.status, self.body, self.action = status, body, action
        issue = ""
        if isinstance(body, dict):
            det = body.get("details") or []
            issue = (det[0].get("issue") if det else "") or body.get("error_description") or body.get("message") or ""
        super().__init__(f"{action} -> HTTP {status} {issue}".strip())

    @property
    def issue(self) -> str:
        if isinstance(self.body, dict):
            det = self.body.get("details") or []
            if det:
                return det[0].get("issue", "")
        return ""


class ActionNotAllowed(Exception):
    """Raised before any network call when PayPal's links say the action is not available."""


@dataclass
class PayPalClient:
    client_id: str = settings.paypal_client_id
    client_secret: str = settings.paypal_client_secret
    base_url: str = settings.paypal_base_url
    timeout: float = 60.0
    _token: Optional[str] = field(default=None, repr=False)
    _token_exp: float = 0.0

    # ----- auth -----
    def token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = httpx.post(f"{self.base_url}/v1/oauth2/token", data={"grant_type": "client_credentials"},
                       headers={"Authorization": f"Basic {auth}"}, timeout=self.timeout)
        if r.status_code != 200:
            raise PayPalError(r.status_code, _safe_json(r), "oauth")
        j = r.json()
        self._token, self._token_exp = j["access_token"], time.time() + int(j.get("expires_in", 3600))
        return self._token

    def _headers(self, content_type: Optional[str] = "application/json") -> dict:
        h = {"Authorization": f"Bearer {self.token()}", "PayPal-Request-Id": str(uuid.uuid4())}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def _request(self, method: str, path: str, *, json_body: Any = None, content: bytes | None = None,
                 content_type: str | None = "application/json", action: str = "") -> Any:
        r = httpx.request(method, f"{self.base_url}{path}", headers=self._headers(content_type),
                          json=json_body, content=content, timeout=self.timeout)
        body = _safe_json(r)
        if r.status_code >= 400:
            raise PayPalError(r.status_code, body, action or f"{method} {path}")
        return body

    # ----- reads -----
    def list_disputes(self, dispute_state: str | None = None, page_size: int = 50, **params) -> list[dict]:
        q = {"page_size": page_size, **params}
        if dispute_state:
            q["dispute_state"] = dispute_state
        qs = "&".join(f"{k}={v}" for k, v in q.items())
        return self._request("GET", f"/v1/customer/disputes?{qs}", action="list_disputes").get("items", [])

    def get_dispute(self, dispute_id: str) -> dict:
        return self._request("GET", f"/v1/customer/disputes/{dispute_id}", action="get_dispute")

    def get_capture(self, capture_id: str) -> dict:
        return self._request("GET", f"/v2/payments/captures/{capture_id}", action="get_capture")

    def get_order(self, order_id: str) -> dict:
        return self._request("GET", f"/v2/checkout/orders/{order_id}", action="get_order")

    def list_transactions(self, start: str, end: str, transaction_id: str | None = None) -> dict:
        q = f"start_date={start}&end_date={end}&fields=all&page_size=50"
        if transaction_id:
            q += f"&transaction_id={transaction_id}"
        return self._request("GET", f"/v1/reporting/transactions?{q}", action="list_transactions")

    # ----- gating -----
    @staticmethod
    def links(dispute: dict) -> set[str]:
        return {l.get("rel", "") for l in dispute.get("links", [])}

    @staticmethod
    def require_link(dispute: dict, rel: str) -> None:
        if rel not in PayPalClient.links(dispute):
            raise ActionNotAllowed(
                f"PayPal does not currently allow '{rel}' on {dispute.get('dispute_id')} "
                f"(status={dispute.get('status')}, links={sorted(PayPalClient.links(dispute))})")

    # ----- seller actions (all gated) -----
    def send_message(self, dispute: dict, message: str) -> dict:
        self.require_link(dispute, "send_message")
        return self._request("POST", f"/v1/customer/disputes/{dispute['dispute_id']}/send-message",
                             json_body={"message": message}, action="send_message")

    def provide_evidence(self, dispute: dict, evidences: list[dict], return_shipping_address: dict | None = None,
                         file: tuple[str, bytes, str] | None = None) -> dict:
        """evidences: [{evidence_type, evidence_info?, notes?}], file: (filename, bytes, mime).
        Verified against sandbox 2026-11-06: multipart with an `input` JSON part (+ optional `evidence-file`)."""
        self.require_link(dispute, "provide_evidence")
        payload: dict[str, Any] = {"evidences": evidences}
        if return_shipping_address:
            payload["return_shipping_address"] = return_shipping_address
        body, ctype = encode_multipart(payload, file)
        return self._request("POST", f"/v1/customer/disputes/{dispute['dispute_id']}/provide-evidence",
                             content=body, content_type=ctype, action="provide_evidence")

    def provide_supporting_info(self, dispute: dict, notes: str, file: tuple[str, bytes, str] | None = None) -> dict:
        self.require_link(dispute, "provide_supporting_info")
        body, ctype = encode_multipart({"notes": notes}, file)
        return self._request("POST", f"/v1/customer/disputes/{dispute['dispute_id']}/provide-supporting-info",
                             content=body, content_type=ctype, action="provide_supporting_info")

    def accept_claim(self, dispute: dict, note: str, accept_claim_type: str = "REFUND",
                     refund_amount: dict | None = None, return_shipping_address: dict | None = None) -> dict:
        self.require_link(dispute, "accept_claim")
        allowed = ((dispute.get("allowed_response_options") or {}).get("accept_claim") or {}).get("accept_claim_types")
        if allowed and accept_claim_type not in allowed:
            raise ActionNotAllowed(f"accept_claim_type {accept_claim_type} not in PayPal's allowed {allowed}")
        payload: dict[str, Any] = {"note": note, "accept_claim_type": accept_claim_type}
        if refund_amount:
            payload["refund_amount"] = refund_amount
        if return_shipping_address:
            payload["return_shipping_address"] = return_shipping_address
        return self._request("POST", f"/v1/customer/disputes/{dispute['dispute_id']}/accept-claim",
                             json_body=payload, action="accept_claim")

    def make_offer(self, dispute: dict, note: str, offer_type: str, offer_amount: dict | None = None,
                   return_shipping_address: dict | None = None) -> dict:
        self.require_link(dispute, "make_offer")
        allowed = ((dispute.get("allowed_response_options") or {}).get("make_offer") or {}).get("offer_types")
        if allowed and offer_type not in allowed:
            raise ActionNotAllowed(f"offer_type {offer_type} not in PayPal's allowed {allowed}")
        payload: dict[str, Any] = {"note": note, "offer_type": offer_type}
        if offer_amount:
            payload["offer_amount"] = offer_amount
        if return_shipping_address:
            payload["return_shipping_address"] = return_shipping_address
        return self._request("POST", f"/v1/customer/disputes/{dispute['dispute_id']}/make-offer",
                             json_body=payload, action="make_offer")

    def escalate(self, dispute: dict, note: str) -> dict:
        self.require_link(dispute, "escalate")
        return self._request("POST", f"/v1/customer/disputes/{dispute['dispute_id']}/escalate",
                             json_body={"note": note}, action="escalate")


def encode_multipart(input_json: dict, file: tuple[str, bytes, str] | None = None) -> tuple[bytes, str]:
    """PayPal Disputes multipart: part `input` (application/json) + optional `evidence-file`."""
    boundary = "----verdict" + uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="input"\r\n'
             f'Content-Type: application/json\r\n\r\n{json.dumps(input_json)}\r\n'.encode()]
    if file:
        name, data, mime = file
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="evidence-file"; filename="{name}"\r\n'
                     f'Content-Type: {mime}\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json() if r.content else {}
    except ValueError:
        return {"raw": r.text[:500]}
