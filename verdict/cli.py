"""CLI: python -m verdict.cli list | show <id> | execute <id> [--yes] [--action X] [--message "..."]"""

from __future__ import annotations

import argparse
import json

from .actions import execute
from .config import settings
from .engine import decide
from .narrative import explain
from .paypal import PayPalClient
from .replay import ReplayClient
from .sync import fetch_bundle, list_dispute_ids


def main() -> None:
    ap = argparse.ArgumentParser(prog="verdict")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("show")
    s.add_argument("dispute_id")
    s.add_argument("--json", action="store_true")
    s.add_argument("--explain", action="store_true")
    e = sub.add_parser("execute")
    e.add_argument("dispute_id")
    e.add_argument("--yes", action="store_true")
    e.add_argument("--action")
    e.add_argument("--message")
    a = ap.parse_args()
    client = ReplayClient() if settings.replay else PayPalClient()
    if a.cmd == "list":
        for d in list_dispute_ids(client):
            amt = d.get("dispute_amount") or {}
            print(
                f"{d['dispute_id']}  {d.get('status'):28s} {d.get('reason'):40s} {amt.get('currency_code', '')} {amt.get('value', '')}  [{d.get('_state_bucket')}]"
            )
    elif a.cmd == "show":
        bundle, _ = fetch_bundle(client, a.dispute_id)
        v = decide(bundle)
        if a.json:
            print(json.dumps({"verdict": v.to_dict(), "bundle": json.loads(bundle.model_dump_json())}, indent=1))
            return
        print(f"{v.dispute_id}: {v.verdict}  (action: {v.action}, confidence: {v.confidence}, EV ${v.expected_value:.2f})")
        print(
            f"  allowed now: {', '.join(v.allowed_now) or 'none'}   deadline: {f'{v.deadline_hours:.0f}h' if v.deadline_hours is not None else 'n/a'}"
        )
        for r in v.rules:
            print(f"  {r.id}: {r.text}\n       policy: {r.policy_basis}")
        if v.evidence_plan:
            print("  evidence plan:", json.dumps(v.evidence_plan))
        if a.explain:
            n = explain(bundle, v)
            print("  explanation:", n and n.get("explanation"))
        print(f"  — {v.disclaimer}")
    elif a.cmd == "execute":
        bundle, _ = fetch_bundle(client, a.dispute_id)
        v = decide(bundle)
        if not a.yes:
            print(f"Would {a.action or v.action} on {a.dispute_id} ({v.verdict}). Re-run with --yes to confirm.")
            return
        print(json.dumps(execute(client, v, action=a.action, message=a.message, confirmed=True, actor="cli"), indent=1))


if __name__ == "__main__":
    main()
