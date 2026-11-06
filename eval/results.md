# Evaluation results

94 cases (2 captured from the PayPal sandbox, 77 synthetic bundles on the same schema). Ground truth = `eval/oracle.py`, an independent decision table written from PayPal's published Seller Protection / dispute rules and hand-reviewed. **A label is what policy says the seller should do, not what PayPal will decide.**

Label distribution: REFUND_NOW 37, RESPOND_WITH_EVIDENCE 25, NO_ACTION_AVAILABLE 23, REPLY_AND_WAIT 7, OFFER_PARTIAL 2

| system | accuracy | unsafe-action rate | over-refund | under-refund | INR acc | SNAD acc | UNAUTH acc | ms/case |
|---|---|---|---|---|---|---|---|---|
| refund_all | **56%** | 0% | 32% | 0% | 47% | 72% | 89% | 0.0 |
| fight_all | **46%** | 0% | 1% | 33% | 43% | 52% | 56% | 0.0 |
| protection_only | **34%** | 36% | 9% | 27% | 41% | 20% | 33% | 0.0 |
| verdict | **99%** | 0% | 1% | 0% | 98% | 100% | 100% | 0.0 |

- unsafe-action rate: the system recommends calling a PayPal action that the dispute's HATEOAS links do not currently allow (PayPal would return ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE).
- over-refund: refunds when the policy says respond/offer/wait (money left on the table). under-refund: contests when the policy says refund (time and fees wasted).

## refund_all: disagreements with the oracle (41)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-001 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-002 | REPLY_AND_WAIT | REFUND_NOW | already responded; await |
| case-005 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-007 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-008 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-009 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking to PayPal address |
| case-013 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-015 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-016 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-017 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking to PayPal address |
| case-021 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-025 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-027 | REPLY_AND_WAIT | REFUND_NOW | tracking but not protected: inform buyer |
| case-028 | REPLY_AND_WAIT | REFUND_NOW | tracking but not protected: inform buyer |
| case-029 | REPLY_AND_WAIT | NO_ACTION_AVAILABLE | tracking but not protected: inform buyer |
| case-033 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-035 | RESPOND_WITH_EVIDENCE | REFUND_NOW | delivered proof, not protected: PayPal reviews on merits |
| case-036 | RESPOND_WITH_EVIDENCE | REFUND_NOW | delivered proof, not protected: PayPal reviews on merits |
| case-037 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | delivered proof, not protected: PayPal reviews on merits |
| case-041 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-044 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-046 | REPLY_AND_WAIT | REFUND_NOW | already responded; await |
| case-047 | RESPOND_WITH_EVIDENCE | REFUND_NOW | shipped to a different address |
| case-049 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-051 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-055 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-057 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-061 | OFFER_PARTIAL | REFUND_NOW | no listing evidence; offer beats loss + return |
| case-067 | OFFER_PARTIAL | REFUND_NOW | no listing evidence; offer beats loss + return |
| case-074 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered unauthorized claim with shipment proof |
| case-080 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-082 | RESPOND_WITH_EVIDENCE | REFUND_NOW | delivered proof, not protected: PayPal reviews on merits |
| case-083 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-084 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-087 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-088 | RESPOND_WITH_EVIDENCE | REFUND_NOW | listing evidence available |
| case-090 | REPLY_AND_WAIT | REFUND_NOW | uncommon reason: gather facts |
| case-091 | REPLY_AND_WAIT | REFUND_NOW | uncommon reason: gather facts |
| case-092 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-093 | NO_ACTION_AVAILABLE | REFUND_NOW | proof on file, PayPal reviewing, no submit link |

## fight_all: disagreements with the oracle (51)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-001 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |
| case-002 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-003 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-004 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-005 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-009 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking to PayPal address |
| case-011 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-012 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-013 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-017 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | covered INR with tracking to PayPal address |
| case-019 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-020 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-021 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-023 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-024 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-025 | REFUND_NOW | NO_ACTION_AVAILABLE | no proof of shipment |
| case-027 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | tracking but not protected: inform buyer |
| case-028 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | tracking but not protected: inform buyer |
| case-029 | REPLY_AND_WAIT | NO_ACTION_AVAILABLE | tracking but not protected: inform buyer |
| case-031 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-032 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-033 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-037 | RESPOND_WITH_EVIDENCE | NO_ACTION_AVAILABLE | delivered proof, not protected: PayPal reviews on merits |
| case-039 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-040 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-041 | REFUND_NOW | NO_ACTION_AVAILABLE | shipped to a different address |
| case-043 | REFUND_NOW | RESPOND_WITH_EVIDENCE | intangible item: no shipping proof possible |
| case-045 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-046 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-048 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-050 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-054 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-056 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-060 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-061 | OFFER_PARTIAL | RESPOND_WITH_EVIDENCE | no listing evidence; offer beats loss + return |
| case-062 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-063 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD without evidence |
| case-066 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-067 | OFFER_PARTIAL | RESPOND_WITH_EVIDENCE | no listing evidence; offer beats loss + return |
| case-068 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |

## protection_only: disagreements with the oracle (62)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-002 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-003 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-004 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-005 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-006 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-010 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-011 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-012 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-013 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-014 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-018 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-019 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-020 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-021 | REFUND_NOW | RESPOND_WITH_EVIDENCE | shipped to a different address |
| case-022 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-026 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-027 | REPLY_AND_WAIT | REFUND_NOW | tracking but not protected: inform buyer |
| case-028 | REPLY_AND_WAIT | REFUND_NOW | tracking but not protected: inform buyer |
| case-029 | REPLY_AND_WAIT | REFUND_NOW | tracking but not protected: inform buyer |
| case-030 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-034 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-035 | RESPOND_WITH_EVIDENCE | REFUND_NOW | delivered proof, not protected: PayPal reviews on merits |
| case-036 | RESPOND_WITH_EVIDENCE | REFUND_NOW | delivered proof, not protected: PayPal reviews on merits |
| case-037 | RESPOND_WITH_EVIDENCE | REFUND_NOW | delivered proof, not protected: PayPal reviews on merits |
| case-038 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-042 | NO_ACTION_AVAILABLE | REFUND_NOW | PayPal exposes no seller action |
| case-043 | REFUND_NOW | RESPOND_WITH_EVIDENCE | intangible item: no shipping proof possible |
| case-045 | REFUND_NOW | RESPOND_WITH_EVIDENCE | no proof of shipment |
| case-046 | REPLY_AND_WAIT | RESPOND_WITH_EVIDENCE | already responded; await |
| case-048 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-050 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-052 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-053 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-054 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-056 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-058 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-059 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | PayPal exposes no seller action |
| case-060 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |
| case-061 | OFFER_PARTIAL | RESPOND_WITH_EVIDENCE | no listing evidence; offer beats loss + return |
| case-062 | REFUND_NOW | RESPOND_WITH_EVIDENCE | SNAD below handling cost: gathering listing evidence costs more than the item |

## verdict: disagreements with the oracle (1)

| case | oracle | system | oracle reason |
|---|---|---|---|
| case-094 | RESPOND_WITH_EVIDENCE | REFUND_NOW | covered INR with tracking to PayPal address |

## Limitations

- The oracle is our reading of PayPal's policy pages (docs/policy_sources.md); PayPal's internal adjudication uses more signals (buyer history, carrier scans, fraud models) that no API exposes.
- Synthetic cases vary 6 factors on a grid; real dispute mixes are skewed (INR ≈ 70%) and contain messier data (partial addresses, multiple trackers).
- The sandbox cannot produce adjudication outcomes on demand, so we do not report win rates and make no claim about them.
- `p_keep` values in the EV model are documented assumptions used to rank options, not calibrated probabilities.