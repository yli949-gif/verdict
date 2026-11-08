# verdict

Decision support for PayPal sellers handling disputes. Reads what PayPal already has on file about a dispute (seller protection on the capture, tracking on the order, the buyer's claim, the actions PayPal currently allows), decides whether the seller should refund or respond and with what evidence, and after the seller confirms, sends the response through the Disputes API.

Built for the PayPal AI Hackathon, Nov 2026. Runs against the PayPal sandbox. MIT.

![demo](docs/demo.gif)

## Why

A small seller gets an "item not received" dispute. Two common reactions, both wrong a lot of the time:

- refund everything: in our test set, 31% of the time the tracking that wins the case was already sitting in PayPal's own data.
- fight everything: 33% of the time there is no proof and the seller just burned a fee and 20 days.

The hard part is the decision, not the paperwork. Existing tools automate the paperwork.

## What it does

```
PayPal sandbox ──GET dispute / capture / order / tracker──▶ EvidenceBundle
                                                                │
                              rules (R0–R12, each cites PayPal policy text)
                                                                │
                            verdict + evidence plan + EV + counterfactuals
                                                                │
                      seller confirms ──▶ POST provide-evidence / accept-claim / ...
                                                                │
                                         audit.jsonl (request, response, status before → after)
```

Verdicts: `REFUND_NOW`, `RESPOND_WITH_EVIDENCE`, `OFFER_PARTIAL`, `REPLY_AND_WAIT`, `NO_ACTION_AVAILABLE`.

Three things it does deliberately:

1. The decision is a rule engine, not a model. Money decisions should be readable and testable. Every rule carries the policy sentence it rests on (`verdict/engine.py`, `docs/policy_sources.md`).
2. PayPal's `links[]` and `allowed_response_options` on the dispute are treated as the only truth about what can be done right now. The engine never recommends an action that isn't in the links, and the client re-reads them at execution time. Outbound bodies are validated against PayPal's published OpenAPI spec before they leave the process.
3. Claude is used only to explain the verdict (English / 中文) and draft the buyer note. It cannot change the verdict, and its text is checked for tracking numbers or amounts that are not in the evidence.

A verdict is what PayPal's published policy says a seller should do with the evidence on file. It is not a prediction of PayPal's decision.

## How it decides

```
no seller action in links                                  → NO_ACTION_AVAILABLE (and: do not refund while PayPal holds your proof)
INR, protection covers INR, tracking to the PayPal address → RESPOND_WITH_EVIDENCE (PROOF_OF_FULFILLMENT + tracking)
INR, tracking to a different address                       → REFUND_NOW (unless signature proof)
INR, tracking on file but NOT_ELIGIBLE                     → RESPOND_WITH_EVIDENCE if a submit link exists (it's free), else REPLY_AND_WAIT
INR, no tracking anywhere                                  → REFUND_NOW
INR, in transit, before promised date                      → REPLY_AND_WAIT
SNAD, listing/photos on hand                               → RESPOND_WITH_EVIDENCE; else OFFER_PARTIAL; below handling cost → REFUND_NOW
UNAUTH, protection covers it, shipped with tracking        → RESPOND_WITH_EVIDENCE; else REFUND_NOW
EV(contest) = p_keep × amount − handling_cost ≤ 0          → REFUND_NOW (not applied when the proof is already in PayPal's data)
```

`p_keep` values are stated assumptions (0.8 with full proof, 0.05 with none, ...), not calibrated probabilities. For each verdict the UI shows how much of a 20-point grid over `p_keep × handling_cost` keeps the same verdict, and what seller-side change would flip it ("add tracking → RESPOND_WITH_EVIDENCE, EV +$49").

## Results

95 cases: 3 captured from the sandbox, 77 synthetic bundles on the same schema over a factor grid, 15 messy/adversarial (cancelled trackers, unknown protection, missed deadline, prompt injection in buyer messages). Ground truth is `eval/oracle.py`, a flat decision table written from PayPal's policy pages. Details and every judgment call: `eval/README.md`.

| system | agreement with policy | unsafe actions | over-refund | under-refund |
|---|---|---|---|---|
| refund everything | 56% | 0% | 31% | 0% |
| fight everything the links allow | 45% | 0% | 0% | 33% |
| trust `seller_protection` alone | 33% | 37% | 8% | 26% |
| Claude zero-shot on the same bundle (`claude-sonnet-5-5`) | 66% | 3% | 2% | 20% |
| verdict (rules) | 100% | 0% | 0% | 0% |

unsafe = recommends a call PayPal would reject (`ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE`). over-refund = refunds when policy says contest. under-refund = contests when policy says refund.

100% against our own table is expected; the engine implements it. The checks that are not us grading us:

- PayPal: 11/11 calls that bypassed the gate (actions not in `links[]`) were rejected by the sandbox and left the dispute unchanged. `eval/live_gate_check.md`.
- PayPal's OpenAPI spec: every evidence plan the engine can produce validates against it, on 400 random bundles (Hypothesis). `verdict/contract.py`, `tests/test_properties.py`.
- A second rater: a different model, given only the policy text and the bundle, agrees with the table at κ = 0.57–0.62. The disagreements were adjudicated by hand; two changed the engine. `eval/second_rater.md`.
- Robustness: 90/95 verdicts unchanged on ≥90% of the assumption grid; the other 5 are flagged in the UI.
- Live: `send-message`, `provide-evidence` (multipart + file), `provide-supporting-info`, `escalate` returned 200 against the sandbox and moved the dispute as `verdict/statemachine.py` predicts.

The zero-shot LLM is the interesting baseline: fine on clean cases, but it contests 20% of the cases policy says to refund, and it was moved once by an injected buyer message. The rules were not.

## Run

Without PayPal credentials (replay of real sandbox cases, writes simulated with the observed state machine, labelled as replay in the UI):

```bash
pip install -e .
VERDICT_MODE=replay uvicorn verdict.app:app --port 8787    # http://localhost:8787
```

With a sandbox app (enable Disputes and Transaction Search on the app):

```bash
cp .env.example .env        # PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET; ANTHROPIC_API_KEY optional
uvicorn verdict.app:app --port 8787
python -m verdict.cli list | show <dispute_id> | execute <dispute_id> --yes
```

To get a dispute to look at: pay a sandbox order from a sandbox personal account, then "Report a problem → I haven't received the item" from that account's Activity page. It reaches `WAITING_FOR_SELLER_RESPONSE` in 2–3 minutes. The documented `POST /v1/customer/disputes` sandbox endpoint rejected every documented body we tried; notes in `docs/policy_sources.md`.

Other entry points: `POST /webhooks/paypal` (CUSTOMER.DISPUTE.*, verified through PayPal's verify endpoint), `GET /api/inbox` (actionable disputes sorted by time left), `verdict/tools.py` (three tool definitions for OpenAI / Anthropic / LangChain agents), `docs/postman/`, `render.yaml`.

```bash
pytest                                   # 23 tests incl. Hypothesis invariants
ruff check . && mypy verdict
python -m eval.generate_cases && python -m eval.run   # writes eval/results.md
python -m eval.live_gate_check           # needs sandbox credentials
```

## PayPal surface used

Disputes v1 (list, get, provide-evidence, accept-claim, make-offer, send-message, escalate, provide-supporting-info), Payments v2 captures (`seller_protection`), Orders v2 (ship-to address, trackers), Shipment Tracking v1 (carrier), Transaction Search v1, webhook signature verification. The Python Agent Toolkit on PyPI (1.1.0) has no dispute tools; `verdict/tools.py` is shaped so they could be upstreamed.

Things learned the hard way, recorded in `docs/policy_sources.md`: tracking added before the buyer files sends the case straight to PayPal review with no seller window; the dispute-level `seller_protection_eligible` field populates late (read the capture instead); the order object omits the carrier; `provide-evidence` consumes its link after one call.

## Limitations

- Policy agreement is not a win rate. PayPal adjudicates with signals no API exposes.
- The sandbox state machine is simplified and cannot produce adjudication outcomes on demand.
- Synthetic cases are a grid; real data is messier and INR-heavy.
- Seller-side facts PayPal does not hold (signature proof, listing screenshots) are checkboxes; nothing verifies them.
- One merchant, one currency, PayPal disputes only (no card-network chargeback logic).

## Layout

```
verdict/paypal.py        REST client; every write gated by require_link() and schema-validated
verdict/bundle.py        EvidenceBundle + builder from raw PayPal JSON
verdict/engine.py        rules, EV, counterfactuals, robustness
verdict/actions.py       executor + audit log
verdict/contract.py      validation against docs/paypal-spec/customer-disputes-v1.json
verdict/statemachine.py  observed states and transitions
verdict/replay.py        credential-less replay client
verdict/webhooks.py      CUSTOMER.DISPUTE.* verification + event log
verdict/narrative.py     Claude explanation with faithfulness check
verdict/tools.py         agent tool definitions
verdict/app.py           FastAPI + static/index.html
eval/                    oracle, case generator, runner, live gate check, second rater, reports
tests/                   unit, property, replay, webhook tests; fixtures from real sandbox JSON
```
