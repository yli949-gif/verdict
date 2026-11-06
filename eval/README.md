# Evaluation — how the numbers are produced and what they mean

## Pieces
- `oracle.py` — the ground-truth decision table. Written from PayPal's policy pages (`docs/policy_sources.md`), deliberately flat and separate from the engine. A label is *what policy says the seller should do with what PayPal has on file*, never PayPal's adjudication.
- `generate_cases.py` — 3 bundles captured from the sandbox + 77 synthetic bundles over a factor grid (protection × tracking × address × links × amount, plus reason-specific facts) + 15 messy/adversarial bundles (cancelled trackers, unknown protection, missed deadline, prompt injection in buyer messages, zero amount). All on the real `EvidenceBundle` schema.
- `run.py` — five systems vs the oracle; writes `results.md` (accuracy, unsafe-action rate, over/under-refund, per-reason, robustness).
- `live_gate_check.py` — PayPal as the oracle for the gate: sends every action the links do **not** offer, with the gate bypassed, and records PayPal's refusal (`live_gate_check.md`).
- `second_rater.py` — an independent model labels every case from the policy text only; reports Cohen's κ and disagreements (`second_rater.md`).
- Contract checks (`verdict/contract.py`) validate every outbound body against PayPal's OpenAPI spec; property tests (`tests/test_properties.py`) prove invariants over random bundles.

## Independent evidence (things that are not "us grading us")
1. PayPal rejected 11/11 gate-bypassing probes (`live_gate_check.md`), states unchanged.
2. PayPal's OpenAPI schema validates every evidence plan the engine can produce (Hypothesis, 400 random bundles).
3. Second rater (different model, policy text only): κ = see `second_rater.md`.
4. Claude zero-shot on the same bundles is a real competitor baseline, not a straw man (61–62%).

## Adjudication log (second-rater disagreements, 2026-11-06)
Changed after review (rater was right):
- **Tracking on file but protection NOT_ELIGIBLE, submit link available** → was REPLY_AND_WAIT, now RESPOND_WITH_EVIDENCE. Reason: the proof is already in PayPal's data; submitting it costs nothing and PayPal reviews shipment proof on the merits even without Seller Protection. Engine rule R4c, oracle updated.
- **CREDIT_NOT_PROCESSED when the seller already refunded** → was REPLY_AND_WAIT, now RESPOND_WITH_EVIDENCE (show the refund). Engine rule R12.

Kept the oracle (judgment calls, documented):
- **SNAD under the handling cost (~$15) with listing evidence** → REFUND_NOW. Gathering listing screenshots for a $12 item is not worth it; these cases are flagged "sensitive to assumptions" in the UI because the handling-cost assumption decides them.
- **Only `accept_claim` offered while PayPal holds the seller's proof / is reviewing** → NO_ACTION_AVAILABLE, not REFUND_NOW. Refunding while PayPal already has the evidence concedes a case the policy says is covered.
- **DUPLICATE_TRANSACTION / other uncommon reasons with no facts** → REPLY_AND_WAIT (gather facts) rather than refund.
- Rater returned no label (`?`) on 3 cases; counted as disagreements.

## Limitations (repeated from results.md on purpose)
Policy-agreement ≠ win rate. Sandbox ≠ production. Synthetic grid ≠ real mix. `p_keep` are stated assumptions; the robustness section shows which verdicts depend on them.
