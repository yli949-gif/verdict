# Second-rater check — claude-haiku-5-5

An independent model labelled every case from the policy summaries and the evidence bundle only (no engine, no oracle code). This measures whether our reading of the policy is reproducible by a reader who is not us.

**Agreement with oracle: 66/95 (69%); Cohen's κ = 0.57.**

| case | oracle | second rater | rater's reason | case note |
|---|---|---|---|---|
| case-001 | NO_ACTION_AVAILABLE | RESPOND_WITH_EVIDENCE | The claim is Seller Protection-eligible and PayPal's own data already shows a USPS tracker shipped to the matc | captured from PayPal sandbox 2026-11-06 |
| case-002 | NO_ACTION_AVAILABLE | REPLY_AND_WAIT | The seller is protected: the USPS tracker on the order already matches PayPal's ship-to address, and no eviden | captured from PayPal sandbox 2026-11-06 |
| case-003 | REPLY_AND_WAIT | REFUND_NOW | PayPal shows no tracker on the order and the seller has no signature or carrier proof of delivery, so contesti | captured from PayPal sandbox 2026-11-06 |
| case-006 | REFUND_NOW | REPLY_AND_WAIT | The seller has no tracking, signature, or other shipment proof (trackers are empty and no evidence has been su |  |
| case-014 | REFUND_NOW | REPLY_AND_WAIT | The only permitted link is provide_supporting_info, which would not help because the tracker shows delivery to |  |
| case-021 | REFUND_NOW | ? |  |  |
| case-022 | REFUND_NOW | RESPOND_WITH_EVIDENCE | The only seller action in links is provide_supporting_info, and the USPS tracker showing DELIVERED is already  |  |
| case-023 | NO_ACTION_AVAILABLE | REFUND_NOW | The only permitted action is accept_claim (REFUND or PARTIAL_REFUND), and the tracker shows delivery to Fresno |  |
| case-026 | REFUND_NOW | NO_ACTION_AVAILABLE | The seller has no tracking, signature, or other shipment proof, the transaction is NOT_ELIGIBLE for Seller Pro |  |
| case-034 | REFUND_NOW | NO_ACTION_AVAILABLE | The transaction is NOT_ELIGIBLE for Seller Protection because the tracker shows delivery to Fresno while PayPa |  |
| case-042 | REFUND_NOW | RESPOND_WITH_EVIDENCE | The only seller action exposed in links[] is provide_supporting_info, so the seller should submit the USPS tra |  |
| case-043 | NO_ACTION_AVAILABLE | REFUND_NOW | Seller Protection is NOT_ELIGIBLE, the only allowed response is accept_claim (REFUND), and the tracker shows d |  |
| case-047 | REPLY_AND_WAIT | REFUND_NOW | The claim is Item Not Received, there are no carrier trackers in PayPal's data, and the seller has no signatur |  |
| case-048 | RESPOND_WITH_EVIDENCE | REFUND_NOW | The tracker shows delivery to Fresno, not the San Jose address on the Transaction Details page, so the shipmen |  |
| case-049 | REFUND_NOW | RESPOND_WITH_EVIDENCE | This is a Significantly Not as Described claim, which Seller Protection does not cover, so PayPal will decide  |  |
| case-051 | REFUND_NOW | RESPOND_WITH_EVIDENCE | This is a Significantly Not as Described claim, which Seller Protection does not cover and PayPal decides on t |  |
| case-055 | REFUND_NOW | RESPOND_WITH_EVIDENCE | This is a Significantly Not as Described claim, which Seller Protection does not cover, so PayPal will decide  |  |
| case-057 | REFUND_NOW | RESPOND_WITH_EVIDENCE | This is a Significantly Not as Described claim, which Seller Protection does not cover, so PayPal will decide  |  |
| case-059 | NO_ACTION_AVAILABLE | REFUND_NOW | The only permitted action in the current state is accept_claim (REFUND or PARTIAL_REFUND), the claim is Signif |  |
| case-061 | REFUND_NOW | RESPOND_WITH_EVIDENCE | This is a Significantly Not as Described claim, which Seller Protection does not cover, so PayPal will decide  |  |
| case-062 | OFFER_PARTIAL | REPLY_AND_WAIT | This is a Significantly Not as Described claim, which Seller Protection does not cover, so the delivered USPS  |  |
| case-063 | REFUND_NOW | REPLY_AND_WAIT | This is a Significantly Not as Described claim, which Seller Protection does not cover and PayPal decides on t |  |
| case-067 | REFUND_NOW | REPLY_AND_WAIT | This is a Significantly Not as Described claim, which Seller Protection does not cover, and the seller has no  |  |
| case-068 | OFFER_PARTIAL | REFUND_NOW | This is a Significantly Not as Described claim, which Seller Protection does not cover and PayPal decides on l |  |
| case-070 | REFUND_NOW | REPLY_AND_WAIT | This is a Significantly Not as Described claim that Seller Protection does not cover, the buyer's only stateme |  |
| case-074 | NO_ACTION_AVAILABLE | REFUND_NOW | The only permitted response is accept_claim (REFUND or PARTIAL_REFUND) per allowed_response_options, and the s |  |
| case-079 | REFUND_NOW | RESPOND_WITH_EVIDENCE | The provide_evidence link is available, and the USPS tracker showing DELIVERED to the PayPal ship-to address i |  |
| case-090 | REFUND_NOW | REPLY_AND_WAIT | The tracker shows delivery to Fresno rather than the PayPal ship-to address in San Jose, so the shipment likel | unauthorized, shipped to a different address |
| case-094 | NO_ACTION_AVAILABLE | REPLY_AND_WAIT | The only evidence-submission path is absent from the links, the USPS tracker already shows delivery to the Pay | buyer's turn: evidence link gone, accept still offered |

Disagreements are adjudicated by hand in eval/README.md; κ above 0.6 is conventionally 'substantial' agreement.