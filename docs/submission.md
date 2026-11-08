# Devpost submission — Verdict

## Tagline
An honest dispute desk for PayPal sellers: it reads what PayPal already has on file, tells you whether to refund or respond, and files the response — only after you say so.

## Inspiration
Small sellers lose twice on disputes: they refund cases they would have kept (tracking was already on file) and fight cases they cannot win (no proof, not protected). The decision — not the paperwork — is where the money is. Existing tools auto-file responses; none tells a seller "refund this one, you'll lose."

## What it does
- Pulls the dispute, the capture's `seller_protection`, the order's ship-to address and trackers, and the carrier record from the PayPal sandbox.
- Cross-checks seller protection × dispute reason × tracking × address × the actions PayPal currently allows (HATEOAS links + `allowed_response_options`).
- Returns one of five verdicts with the rules that fired, the policy text behind each rule, an expected-value comparison, and a confidence level.
- Executes the chosen PayPal action (provide-evidence with tracking + a generated evidence file, accept-claim, make-offer, send-message, escalate, provide-supporting-info) after a human confirms, and writes an audit entry with the status transition PayPal returned.
- Explains the verdict in English or 中文 with Claude; the model may rewrite the explanation and the buyer note, never the decision, and its text is checked for invented tracking numbers or contradictions.

## How we built it
Python 3.13, FastAPI, httpx, a vanilla single-page UI. `verdict/paypal.py` wraps Disputes v1, Payments v2, Orders v2, Shipment Tracking v1 and Transaction Search v1; every write calls `require_link()` first. The decision engine is deterministic and policy-cited by design — money decisions need rules you can read and test. Claude (`claude-sonnet-5-5`) sits on top as an explainer. `verdict/tools.py` exposes three toolkit-shaped tools (list disputes, get verdict, execute verdict) for agent frameworks, since the official Python Agent Toolkit ships no dispute tools.

## Evaluation
95 cases (3 captured from the sandbox, 77 synthetic bundles on the real schema, 15 messy/adversarial incl. prompt injection in buyer messages) against an independent policy decision table. Verdict: 100% agreement with the policy table, 0% unsafe actions. Refund-everything: 56% (leaves money on the table in 32% of cases). Trusting `seller_protection` alone: 36% of its recommendations are actions PayPal would refuse. Claude alone, zero-shot on the same bundles: 66%, and it contests 20% of cases policy says to refund. Independent checks: PayPal rejected 11/11 gate-bypassing probes; every generated payload validates against PayPal's OpenAPI spec (Hypothesis, 400 random bundles); a second model rating from policy text alone agrees at κ≈0.6; 90/95 verdicts are stable across a grid of the EV assumptions. Live sandbox: send-message, provide-evidence (multipart + file), provide-supporting-info, escalate and accept-claim all returned 200 and moved disputes as expected; the demo video shows a live provide-evidence and a live accept-claim (PayPal resolved it: SELLER_ISSUED_REFUND).

## Challenges
- The documented sandbox `POST /v1/customer/disputes` rejected every documented body; we file test disputes from a buyer sandbox account instead and documented the observed state machine.
- Tracking present *before* the buyer files sends the case straight to PayPal review with no seller window — the engine had to learn that "proof on file + under review" means *do nothing, do not refund*.
- The order object omits the carrier; it only exists in the Shipment Tracking API.
- In the CHARGEBACK stage the sandbox rejected the very evidence types it listed as requested (`EVIDENCE_TYPE_IS_NOT_ALLOWED`); Verdict now falls back to `OTHER` carrying the same facts, and shows what PayPal asked for.
- Dispute-level `seller_protection_eligible` populates asynchronously, so the engine reads the capture's `seller_protection` instead.

## What we learned
PayPal's HATEOAS links are the real policy engine: whatever you think the rules say, if the link isn't there the action fails. Building around the links instead of around assumptions is what gave 0% unsafe actions.

## What's next
Webhook-driven verdicts (CUSTOMER.DISPUTE.CREATED), seller-side evidence vault (listing snapshots, signature scans), calibration of `p_keep` against real outcomes with consenting sellers, and an MCP server wrapping `verdict/tools.py`.

## Built with
python, fastapi, httpx, pydantic, paypal-disputes-api, paypal-orders-api, paypal-shipment-tracking, anthropic-claude, playwright (demo)

## AI tools used
- Anthropic Claude (`claude-sonnet-5-5`) via the Anthropic SDK: explanation + buyer-note generation with a faithfulness check; also the `llm_only` baseline in the evaluation.
- Claude Code: pair-programming during the hackathon (all commits by the author; the engine, eval design and policy reading were decided by the author).

---

# Demo video (docs/demo.mp4, 2:31) — what it shows
0:00 Inbox of five live sandbox disputes, sorted by time left.
0:13 Case 1 ($74, item not received): ledger of facts from PayPal (seller protection ELIGIBLE, USPS tracking to the PayPal address, allowed actions), rule R1 with policy text, Claude explanation, EV +$58 vs $0, exact PayPal call → confirm → live provide-evidence → status waiting-for-seller → under review, audit entry.
1:05 Case 2 ($28, no tracking): verdict refund now, counterfactual "add tracking → respond", confirm → live accept-claim → PayPal later resolves it SELLER_ISSUED_REFUND.
1:45 Case 3 (proof on file, PayPal reviewing): nothing to do, do not refund. 中文 toggle.
2:10 Results and independent checks; repo link.

Voice-over is optional; the captions carry the narration. If re-recording with voice, keep the three cases and the order above.
