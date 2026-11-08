import json

from verdict.actions import execute
from verdict.engine import decide
from verdict.replay import ReplayClient
from verdict.sync import fetch_bundle


def test_replay_end_to_end_simulates_state_machine(tmp_path, monkeypatch):
    import verdict.actions as actions

    monkeypatch.setattr(actions, "AUDIT", tmp_path / "audit.jsonl")
    c = ReplayClient()
    ids = [d["dispute_id"] for d in c.list_disputes()]
    assert "PP-R-GHY-10196892" in ids
    bundle, _ = fetch_bundle(c, "PP-R-GHY-10196892")
    v = decide(bundle)
    assert v.verdict == "RESPOND_WITH_EVIDENCE" and v.action == "provide_evidence"
    r = execute(c, v, confirmed=True, actor="test")
    assert r["ok"] and r["status_before"] == "WAITING_FOR_SELLER_RESPONSE" and r["status_after"] == "UNDER_REVIEW"
    after, _ = fetch_bundle(c, "PP-R-GHY-10196892")
    assert "PROOF_OF_FULFILLMENT" in after.evidences_submitted
    assert decide(after).verdict == "NO_ACTION_AVAILABLE"  # proof on file, PayPal reviewing
    entry = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])
    assert entry["replay"] is True and entry["action"] == "provide_evidence"


def test_replay_refuses_unlisted_actions():
    c = ReplayClient()
    d = c.get_dispute("PP-R-WMD-10196904")  # waiting for buyer: no provide_evidence link
    v = decide(fetch_bundle(c, "PP-R-WMD-10196904")[0])
    r = execute(c, v, action="make_offer", confirmed=True)
    assert not r["ok"] and "does not currently allow" in r["error"]
    assert c.get_dispute("PP-R-WMD-10196904")["status"] == d["status"]


def test_executor_falls_back_to_other_when_paypal_rejects_evidence_type(tmp_path, monkeypatch):
    import verdict.actions as actions
    from verdict.paypal import PayPalError

    monkeypatch.setattr(actions, "AUDIT", tmp_path / "audit.jsonl")
    c = ReplayClient()
    calls = []
    real = c.provide_evidence

    def flaky(dispute, evidences, return_shipping_address=None, file=None):
        calls.append([e["evidence_type"] for e in evidences])
        if evidences[0]["evidence_type"] != "OTHER":
            raise PayPalError(400, {"details": [{"issue": "EVIDENCE_TYPE_IS_NOT_ALLOWED"}]}, "provide_evidence")
        return real(dispute, evidences, return_shipping_address, file)

    monkeypatch.setattr(c, "provide_evidence", flaky)
    v = decide(fetch_bundle(c, "PP-R-GHY-10196892")[0])
    r = execute(c, v, confirmed=True)
    assert r["ok"] and calls == [["PROOF_OF_FULFILLMENT"], ["OTHER"]]
    assert "9400100000000000000002" in r["request"]["evidences"][0]["notes"]
    assert r["request"]["fallback_from"] == ["PROOF_OF_FULFILLMENT"]
