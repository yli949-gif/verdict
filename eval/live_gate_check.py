"""Verify Verdict's HATEOAS gate against PayPal itself.

For each real sandbox dispute and each seller action its links[] does NOT expose, send a minimal
valid request with the local gate bypassed and record PayPal's answer. Expected: PayPal rejects
every one (ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE or similar) — i.e. our gate is at least as
strict as PayPal, and no rejected call changes state. Writes eval/live_gate_check.md.

Run: python -m eval.live_gate_check
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from verdict.paypal import PayPalClient, PayPalError, encode_multipart
from verdict.statemachine import SELLER_ACTIONS
from verdict.sync import list_dispute_ids

OUT = Path(__file__).resolve().parent / "live_gate_check.md"
BODIES = {
    "send_message": ("json", "/send-message", {"message": "gate check (sandbox)"}),
    "escalate": ("json", "/escalate", {"note": "gate check (sandbox)"}),
    "accept_claim": ("json", "/accept-claim", {"note": "gate check (sandbox)", "accept_claim_type": "REFUND"}),
    "make_offer": (
        "json",
        "/make-offer",
        {"note": "gate check (sandbox)", "offer_type": "REFUND", "offer_amount": {"currency_code": "USD", "value": "1.00"}},
    ),
    "provide_evidence": ("mp", "/provide-evidence", {"evidences": [{"evidence_type": "OTHER", "notes": "gate check (sandbox)"}]}),
    "provide_supporting_info": ("mp", "/provide-supporting-info", {"notes": "gate check (sandbox)"}),
}


def main() -> None:
    c = PayPalClient()
    rows = []
    for d in list_dispute_ids(c):
        did = d["dispute_id"]
        full = c.get_dispute(did)
        links = {lk.get("rel") for lk in full.get("links", [])}
        for action in sorted(SELLER_ACTIONS - links):
            kind, path, body = BODIES[action]
            try:
                if kind == "json":
                    c._request("POST", f"/v1/customer/disputes/{did}{path}", json_body=body, action=action)
                else:
                    raw, ct = encode_multipart(body)
                    c._request("POST", f"/v1/customer/disputes/{did}{path}", content=raw, content_type=ct, action=action)
                rows.append((did, full.get("status"), action, "ACCEPTED (!)", ""))
            except PayPalError as e:
                rows.append((did, full.get("status"), action, f"HTTP {e.status}", e.issue))
        after = c.get_dispute(did)
        rows.append(
            (
                did,
                full.get("status"),
                "— state after probes —",
                after.get("status"),
                "unchanged" if after.get("status") == full.get("status") else "CHANGED",
            )
        )
    L = [
        f"# Live gate check — {datetime.now(UTC).isoformat(timespec='minutes')}",
        "",
        "For every real sandbox dispute, every seller action **not** in its `links[]` was sent to PayPal with Verdict's gate bypassed.",
        "Expected: PayPal rejects all of them and the dispute status is unchanged afterwards.",
        "",
        "| dispute | status | action not in links | PayPal answered | issue |",
        "|---|---|---|---|---|",
    ]
    L += [f"| {a} | {b} | {c_} | {d_} | {e} |" for a, b, c_, d_, e in rows]
    probes = [r for r in rows if not r[2].startswith("—")]
    rejected = sum(1 for r in probes if r[3] != "ACCEPTED (!)")
    L += ["", f"**{rejected}/{len(probes)} probes rejected by PayPal; {len(probes) - rejected} accepted.**"]
    OUT.write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
