# Policy sources behind the rules

Every rule in `verdict/engine.py` cites one of the summaries below (`POLICY[...]`). The summaries are our paraphrase of PayPal's published pages; the pages themselves are authoritative and change over time. Re-check them before relying on Verdict.

| key | what it says (paraphrase) | where to read it |
|---|---|---|
| SP_INR | Seller Protection covers Item Not Received claims if the seller shipped to the address on the Transaction Details page and can show carrier proof of shipment/delivery | PayPal User Agreement → "Seller Protection" (us) |
| SP_UNAUTH | Same coverage for Unauthorized Transaction claims on eligible physical goods | PayPal User Agreement → "Seller Protection" |
| SP_SNAD | Significantly Not As Described is *not* covered; PayPal decides on the merits | PayPal User Agreement → "Seller Protection — ineligible items and transactions" |
| SP_INELIGIBLE | Not covered: direct card entry (Advanced Checkout card fields), intangible/digital goods, in-person pickup, shipping to a different address than the Transaction Details page | PayPal User Agreement → "Seller Protection — ineligible items and transactions"; Orders v2 `capture.seller_protection.status` |
| DEADLINE | Respond by `seller_response_due_date`; silence is treated as accepting the claim | Disputes API reference → dispute object; Resolution Center help |
| INQUIRY | Inquiry stage = direct buyer/seller resolution; either party may escalate to a claim | Disputes integration guide → "Dispute life cycle" |
| HATEOAS | `links[]` and `allowed_response_options` are the only authoritative list of what a seller may do now | Disputes API reference → "Provide evidence", "Accept claim", "Make offer" (each says to check the HATEOAS link first) |

Machine-readable signals Verdict reads instead of guessing:

- `GET /v2/payments/captures/{id}` → `seller_protection.status` ∈ ELIGIBLE / PARTIALLY_ELIGIBLE / NOT_ELIGIBLE and `seller_protection.dispute_categories` (ITEM_NOT_RECEIVED, UNAUTHORIZED_TRANSACTION). Verified in sandbox 2026-11-06: direct card = NOT_ELIGIBLE, wallet = ELIGIBLE, bank-funded pending = NOT_ELIGIBLE.
- `GET /v2/checkout/orders/{id}` → `purchase_units[].shipping.address` (the "Transaction Details" address) and `shipping.trackers[]`; `GET /v1/shipping/trackers/{id}` for the carrier.
- `GET /v1/customer/disputes/{id}` → `reason`, `status`, `dispute_life_cycle_stage`, `seller_response_due_date`, `disputed_transactions[].seller_protection_eligible` (populates asynchronously — do not trust it alone), `evidences[]`, `supporting_info[]`, `allowed_response_options`, `links[]`.

Sandbox state machine observed (2026-11-06), which the engine respects via links rather than hard-coding:

- Inquiry filed by buyer → OPEN → UNDER_REVIEW (≈2 min) → WAITING_FOR_SELLER_RESPONSE (links: accept_claim, provide_evidence, send_message, escalate, make_offer; due date +20 days).
- If tracking was already on the order when the buyer filed, PayPal moved the case straight to UNDER_REVIEW / CHARGEBACK stage with only `provide_supporting_info` (and sandbox-only `adjudicate`/`require_evidence`) — the seller never gets a response window.
- Seller `send_message` → UNDER_REVIEW → WAITING_FOR_BUYER_RESPONSE; `provide_evidence` succeeds once and the link disappears; `escalate` → UNDER_REVIEW.
- Adding tracking to the order *after* the buyer filed does not change the dispute state; Verdict picks it up on the next read.

- **Evidence types in CHARGEBACK stage (2026-11-07):** the dispute listed PROOF_OF_FULFILLMENT / PROOF_OF_REFUND / PROOF_OF_DELIVERY_SIGNATURE as `REQUESTED_FROM_SELLER`, yet `provide-evidence` with PROOF_OF_FULFILLMENT returned 400 `EVIDENCE_TYPE_IS_NOT_ALLOWED`; `OTHER` + notes + file was accepted. PayPal's test guide says to use `OTHER` under sandbox test conditions. Verdict shows the requested types and falls back to `OTHER` carrying the same facts when the typed submission is rejected (`verdict/actions.py`).
- **Review → seller turn (2026-11-06 ~22:00):** a case in UNDER_REVIEW / CHARGEBACK came back to WAITING_FOR_SELLER_RESPONSE with a ~70h `seller_response_due_date` and links accept_claim + provide_evidence.
