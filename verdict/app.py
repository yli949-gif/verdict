"""FastAPI app: JSON API + a single-page UI (static/index.html)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .actions import execute, read_audit
from .bundle import EvidenceBundle
from .config import settings
from .engine import Verdict, counterfactuals, decide, robustness
from .narrative import explain
from .paypal import PayPalClient, PayPalError
from .replay import ReplayClient
from .sync import fetch_bundle, list_dispute_ids, save_seller_fact
from .webhooks import EVENTS, read_events, record, verify_signature

app = FastAPI(title="Verdict", version="0.1.0")
STATIC = Path(__file__).resolve().parent.parent / "static"
_client: PayPalClient | None = None
_cache: dict[str, tuple[EvidenceBundle, Verdict, dict]] = {}


def client():
    global _client
    if _client is None:
        _client = ReplayClient() if settings.replay else PayPalClient()
    return _client


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "environment": "replay" if settings.replay else settings.paypal_environment,
        "llm": settings.llm_enabled,
        "replay_snapshot": getattr(client(), "snapshot_name", None),
    }


@app.get("/api/disputes")
def disputes():
    try:
        items = list_dispute_ids(client())
    except PayPalError as e:
        raise HTTPException(502, str(e)) from e
    return [
        {
            "dispute_id": d["dispute_id"],
            "reason": d.get("reason"),
            "status": d.get("status"),
            "dispute_state": d.get("dispute_state"),
            "amount": d.get("dispute_amount"),
            "update_time": d.get("update_time"),
            "bucket": d.get("_state_bucket"),
        }
        for d in items
    ]


def _analyze(dispute_id: str, with_llm: bool) -> dict:
    try:
        bundle, raw = fetch_bundle(client(), dispute_id)
    except PayPalError as e:
        raise HTTPException(502, str(e)) from e
    verdict = decide(bundle)
    _cache[dispute_id] = (bundle, verdict, raw)
    out: dict[str, Any] = {
        "bundle": bundle.model_dump(mode="json"),
        "verdict": verdict.to_dict(),
        "counterfactuals": counterfactuals(bundle),
        "robustness": robustness(bundle),
        "raw_links": [lk.get("rel") for lk in raw.get("links", [])],
        "warnings": raw.get("_verdict_warnings", []),
    }
    if with_llm and settings.llm_enabled:
        try:
            out["narrative"] = explain(bundle, verdict)
        except Exception as e:  # LLM is optional; never block the verdict
            out["narrative_error"] = str(e)
    return out


@app.get("/api/disputes/{dispute_id}")
def dispute(dispute_id: str, llm: bool = True):
    return _analyze(dispute_id, llm)


class Facts(BaseModel):
    seller_has_signature_proof: bool | None = None
    seller_has_listing_evidence: bool | None = None
    seller_has_return_policy: bool | None = None
    seller_refund_already_issued: bool | None = None


@app.post("/api/disputes/{dispute_id}/facts")
def facts(dispute_id: str, f: Facts):
    save_seller_fact(dispute_id, {k: v for k, v in f.model_dump().items() if v is not None})
    return _analyze(dispute_id, False)


class ExecuteReq(BaseModel):
    action: str | None = None
    message: str | None = None
    accept_claim_type: str | None = None
    offer_amount: float | None = None
    confirmed: bool = False


@app.post("/api/disputes/{dispute_id}/execute")
def do_execute(dispute_id: str, req: ExecuteReq):
    if dispute_id not in _cache:
        _analyze(dispute_id, False)
    bundle, verdict, _ = _cache[dispute_id]
    result = execute(
        client(),
        verdict,
        action=req.action,
        message=req.message,
        accept_claim_type=req.accept_claim_type,
        offer_amount=req.offer_amount,
        confirmed=req.confirmed,
    )
    _cache.pop(dispute_id, None)
    return {"result": result, "refreshed": _analyze(dispute_id, False) if result.get("ok") else None}


@app.get("/api/audit")
def audit(dispute_id: str | None = None):
    return read_audit(dispute_id)


@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    """CUSTOMER.DISPUTE.* → verify with PayPal, re-evaluate the dispute, record the event."""
    body = await request.body()
    verified = verify_signature(client(), dict(request.headers), body)
    if not verified:
        raise HTTPException(401, "webhook signature not verified")
    event = json.loads(body)
    if event.get("event_type") not in EVENTS:
        return {"ignored": event.get("event_type")}
    dispute_id = (event.get("resource") or {}).get("dispute_id")
    verdict = None
    if dispute_id:
        _cache.pop(dispute_id, None)
        try:
            verdict = _analyze(dispute_id, False)["verdict"]
        except HTTPException:
            verdict = None
    return record(event, verdict, verified)


@app.get("/api/inbox")
def inbox():
    """Actionable disputes sorted by time left, with the verdict each one needs. The daily triage view."""
    rows = []
    for d in list_dispute_ids(client()):
        if d.get("_state_bucket") != "REQUIRED_ACTION":
            continue
        a = _analyze(d["dispute_id"], False)
        v = a["verdict"]
        rows.append(
            {
                "dispute_id": d["dispute_id"],
                "amount": d.get("dispute_amount"),
                "reason": d.get("reason"),
                "deadline_hours": v["deadline_hours"],
                "verdict": v["verdict"],
                "action": v["action"],
                "urgent": v["deadline_hours"] is not None and v["deadline_hours"] < 48,
            }
        )
    rows.sort(key=lambda r: (r["deadline_hours"] is None, r["deadline_hours"] or 0))
    return rows


@app.get("/api/events")
def events():
    return read_events()
