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
94 cases (2 captured from the sandbox, 77 synthetic bundles on the real schema, 15 messy/adversarial incl. prompt injection in buyer messages) against an independent policy decision table. Verdict: 99% agreement, 0% unsafe actions. Refund-everything: 56% (leaves money on the table in 32% of cases). Trusting `seller_protection` alone: 36% of its recommendations are actions PayPal would refuse. LLM-only baseline: see `eval/results.md`. Live sandbox replay on 2026-11-06: send-message, provide-evidence (multipart + file), provide-supporting-info and escalate all returned 200 and moved the dispute as expected.

## Challenges
- The documented sandbox `POST /v1/customer/disputes` rejected every documented body; we file test disputes from a buyer sandbox account instead and documented the observed state machine.
- Tracking present *before* the buyer files sends the case straight to PayPal review with no seller window — the engine had to learn that "proof on file + under review" means *do nothing, do not refund*.
- The order object omits the carrier; it only exists in the Shipment Tracking API.
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

# 3-minute demo script (video)

0:00 Title card: "Verdict — an honest dispute desk for PayPal sellers."
0:05 Problem (voice): "Most small sellers refund every dispute or fight every dispute. Both lose money. The hard part is the decision."
0:15 UI: three live sandbox disputes. Open case 1 ($89, item not received).
0:25 Ledger: "Every fact here comes from PayPal — seller protection on the capture, USPS tracking on the order, the address match, and the five actions PayPal allows right now."
0:45 Rules: "R1 fires, with the policy text behind it. Contesting is worth +$70 vs $0 for refunding. The percentage is an assumption we state, not a prediction of PayPal."
1:00 Action box: "The exact PayPal call is shown. I confirm." Click. "PayPal accepted it: status moved to under review, evidence is on the dispute, audit entry written."
1:25 Case 2 (under review, proof on file): "Verdict says: nothing to do — and do not refund. It never offers an action PayPal's links don't allow."
1:45 Case 3 (no tracking): "Here the honest answer is refund now. Fighting without proof is a fee and a lost case."
2:05 中文 toggle + Claude explanation: "Explanations in Chinese for sellers who don't work in English; the model explains, it never decides."
2:20 Results slide: table from eval/results.md. "99% policy agreement, 0% unsafe actions, versus 56% for refund-everything."
2:40 Limitations + close: "Verdict recommends under PayPal's published rules; PayPal decides. Code, eval and audit log are in the repo."
