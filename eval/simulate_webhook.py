"""Post a sample CUSTOMER.DISPUTE.UPDATED event to a local Verdict server (signature check disabled).

Run the server with VERDICT_WEBHOOK_VERIFY=false, then: python -m eval.simulate_webhook PP-R-GHY-10196892
"""

from __future__ import annotations

import json
import sys

import httpx

from verdict.webhooks import sample_event

did = sys.argv[1] if len(sys.argv) > 1 else "PP-R-GHY-10196892"
base = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8787"
ev = sample_event(did)
r = httpx.post(f"{base}/webhooks/paypal", json=ev, headers={"PayPal-Transmission-Id": "sim"}, timeout=60)
print(r.status_code, json.dumps(r.json(), indent=1))
