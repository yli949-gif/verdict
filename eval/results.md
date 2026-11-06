# Evaluation results

95 cases (3 captured from the PayPal sandbox, 77 synthetic bundles on the same schema). Ground truth = `eval/oracle.py`, an independent decision table written from PayPal's published Seller Protection / dispute rules and hand-reviewed. **A label is what policy says the seller should do, not what PayPal will decide.**

Label distribution: REFUND_NOW 37, RESPOND_WITH_EVIDENCE 28, NO_ACTION_AVAILABLE 25, REPLY_AND_WAIT 3, OFFER_PARTIAL 2

| system | accuracy | unsafe-action rate | over-refund | under-refund | INR acc | SNAD acc | UNAUTH acc | ms/case |
|---|---|---|---|---|---|---|---|---|
| refund_all | **56%** | 0% | 31% | 0% | 46% | 72% | 89% | 0.0 |
| fight_all | **48%** | 0% | 0% | 33% | 46% | 52% | 56% | 0.0 |
| protection_only | **34%** | 37% | 8% | 26% | 39% | 20% | 33% | 0.0 |
| verdict | **100%** | 0% | 0% | 0% | 100% | 100% | 100% | 0.0 |
| llm_only | **66%** | 3% | 2% | 20% | 73% | 40% | 89% | 3224.6 |

- unsafe-action rate: the system recommends calling a PayPal action that the dispute's HATEOAS links do not currently allow (PayPal would return ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE).
- over-refund: refunds when the policy says respond/offer/wait (money left on the table). under-refund: contests when the policy says refund (time and fees wasted).

## refund_all: disagreements with the oracle (42)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-001 | NO_ACTION_AVAILABLE | REFUND_NOW | proof on file, PayPal reviewing, no submit link |
| case-002 | NO_ACTION_AVAILABLE | REFUND_NOW | proof on file, PayPal reviewing, no submit link |
| case-003 | REPLY_AND_WAIT | REFUND_NOW | already responded; await |
| case-006 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-008 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-009 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-010 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking; PayPal reviewing, add supporting note |
| case-014 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-016 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-017 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-018 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking; PayPal reviewing, add supporting note |
| case-022 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-026 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-028 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-029 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-030 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-034 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-036 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-037 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-038 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-042 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-045 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-047 | REPLY_AND_WAIT | REFUND_NOW | already responded; await |
| case-048 | RESPOND_WITH_EVIDENCE | REFUND_NOW | shipped to a different address |
| case-050 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-052 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-056 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-058 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-062 | OFFER_PARTIAL | REFUND_NOW | no listing evidence; offer beats loss + return |
| case-068 | OFFER_PARTIAL | REFUND_NOW | no listing evidence; offer beats loss + return |
| case-075 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered unauthorized claim with shipment proof |
| case-081 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-083 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-084 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-085 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-088 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-089 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-091 | RESPOND_WITH_EVIDENCE | REFUND_NOW | refund already issued: show proof of refund |
| case-092 | REPLY_AND_WAIT | REFUND_NOW | uncommon reason: gather facts |
| case-093 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |

## fight_all: disagreements with the oracle (49)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-001 | NO_ACTION_AVAILABLE | REFUND_NOW | proof on file, PayPal reviewing, no submit link |
| case-002 | NO_ACTION_AVAILABLE | REFUND_NOW | proof on file, PayPal reviewing, no submit link |
| case-003 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-004 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-005 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-006 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-010 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking; PayPal reviewing, add supporting note |
| case-012 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-013 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-014 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-018 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking; PayPal reviewing, add supporting note |
| case-020 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-021 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-022 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-024 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-025 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-026 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-030 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-032 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-033 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-034 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-038 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-040 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-041 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-042 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-044 | REFUND_NOW | RESPOND_WITH_EVIDENCE | intangible item: no shipping proof possible |
| case-046 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-047 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-049 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-051 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-055 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-057 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-061 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-062 | OFFER_PARTIAL | RESPOND_WITH_EVIDENCE | no listing evidence; offer beats loss + return |
| case-063 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-064 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD without evidence |
| case-067 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-068 | OFFER_PARTIAL | RESPOND_WITH_EVIDENCE | no listing evidence; offer beats loss + return |
| case-069 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-070 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD without evidence |

## protection_only: disagreements with the oracle (63)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-001 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | proof on file, PayPal reviewing, no submit link |
| case-002 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | proof on file, PayPal reviewing, no submit link |
| case-003 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-004 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-005 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-006 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-007 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-011 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-012 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-013 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-014 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-015 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-019 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-020 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-021 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-022 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-023 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-027 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-028 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-029 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-030 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-031 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-035 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-036 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-037 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-038 | RESPOND_WITH_EVIDENCE | REFUND_NOW | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-039 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-043 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-044 | REFUND_NOW | RESPOND_WITH_EVIDENCE | intangible item: no shipping proof possible |
| case-046 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-047 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-049 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-051 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-053 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-054 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-055 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-057 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-059 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-060 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-061 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |

## llm_only: disagreements with the oracle (32)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-002 | NO_ACTION_AVAILABLE | REPLY_AND_WAIT | proof on file, PayPal reviewing, no submit link |
| case-003 | REPLY_AND_WAIT | REFUND_NOW | already responded; await |
| case-006 | REFUND_NOW | REPLY_AND_WAIT | no proof of shipment |
| case-007 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-010 | RESPOND_WITH_EVIDENCE | REPLY_AND_WAIT | covered INR with tracking; PayPal reviewing, add supporting note |
| case-014 | REFUND_NOW | REPLY_AND_WAIT | shipped to a different address |
| case-022 | REFUND_NOW | REPLY_AND_WAIT | shipped to a different address |
| case-026 | REFUND_NOW | REPLY_AND_WAIT | no proof of shipment |
| case-028 | RESPOND_WITH_EVIDENCE | REPLY_AND_WAIT | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-030 | RESPOND_WITH_EVIDENCE | REPLY_AND_WAIT | tracking on file, not protected: submit it anyway (free), PayPal reviews on merits |
| case-034 | REFUND_NOW | REPLY_AND_WAIT | shipped to a different address |
| case-042 | REFUND_NOW | REPLY_AND_WAIT | shipped to a different address |
| case-044 | REFUND_NOW | REPLY_AND_WAIT | intangible item: no shipping proof possible |
| case-048 | RESPOND_WITH_EVIDENCE | REFUND_NOW | shipped to a different address |
| case-049 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-051 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-055 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-056 | RESPOND_WITH_EVIDENCE | REPLY_AND_WAIT | listing evidence available |
| case-057 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-061 | REFUND_NOW | REPLY_AND_WAIT | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-062 | OFFER_PARTIAL | REPLY_AND_WAIT | no listing evidence; offer beats loss + return |
| case-063 | REFUND_NOW | REPLY_AND_WAIT | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-064 | REFUND_NOW | REPLY_AND_WAIT | SNAD without evidence |
| case-066 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-067 | REFUND_NOW | REPLY_AND_WAIT | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-068 | OFFER_PARTIAL | REPLY_AND_WAIT | no listing evidence; offer beats loss + return |
| case-069 | REFUND_NOW | REPLY_AND_WAIT | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-070 | REFUND_NOW | REPLY_AND_WAIT | SNAD without evidence |
| case-071 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-073 | REFUND_NOW | REPLY_AND_WAIT | unauthorized without coverage/proof |
| case-086 | REFUND_NOW | REPLY_AND_WAIT | no proof of shipment |
| case-094 | NO_ACTION_AVAILABLE | REPLY_AND_WAIT | proof on file, PayPal reviewing, no submit link |

## Robustness to assumptions

Each verdict is re-computed on a 20-point grid (p_keep × 0.5–1.25, handling cost $0–$25). **90/95 verdicts are unchanged on ≥90% of the grid.** The 5 assumption-sensitive cases are flagged in the UI:

- case-003: REPLY_AND_WAIT (agreement 70%)
- case-049: REFUND_NOW (agreement 70%)
- case-051: REFUND_NOW (agreement 70%)
- case-055: REFUND_NOW (agreement 70%)
- case-057: REFUND_NOW (agreement 70%)

Verdict accuracy vs oracle as p_keep is scaled: ×0.5: 100%, ×0.75: 100%, ×1.0: 100%, ×1.25: 100%

## Limitations

- The oracle is our reading of PayPal's policy pages (docs/policy_sources.md); PayPal's internal adjudication uses more signals (buyer history, carrier scans, fraud models) that no API exposes.
- Synthetic cases vary 6 factors on a grid; real dispute mixes are skewed (INR ≈ 70%) and contain messier data (partial addresses, multiple trackers).
- The sandbox cannot produce adjudication outcomes on demand, so we do not report win rates and make no claim about them.
- `p_keep` values in the EV model are documented assumptions used to rank options, not calibrated probabilities.