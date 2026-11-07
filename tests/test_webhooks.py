from fastapi.testclient import TestClient

import verdict.webhooks as wh
from verdict.webhooks import sample_event


def test_webhook_unverified_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("VERDICT_MODE", "replay")
    monkeypatch.setattr(wh, "VERIFY", True)
    monkeypatch.setattr(wh, "WEBHOOK_ID", "")
    from verdict import app as appmod

    appmod._client = None
    c = TestClient(appmod.app)
    r = c.post("/webhooks/paypal", json=sample_event("PP-R-GHY-10196892"))
    assert r.status_code == 401


def test_webhook_reevaluates_dispute_in_replay(monkeypatch, tmp_path):
    monkeypatch.setenv("VERDICT_MODE", "replay")
    monkeypatch.setattr(wh, "VERIFY", False)
    monkeypatch.setattr(wh, "INBOX", tmp_path / "events.jsonl")
    from verdict import app as appmod
    from verdict.config import Settings

    monkeypatch.setattr(appmod, "settings", Settings())
    appmod._client = None
    c = TestClient(appmod.app)
    r = c.post("/webhooks/paypal", json=sample_event("PP-R-GHY-10196892"))
    assert r.status_code == 200
    j = r.json()
    assert j["dispute_id"] == "PP-R-GHY-10196892" and j["verdict"] == "RESPOND_WITH_EVIDENCE" and j["verified"] is True
    inbox = c.get("/api/inbox").json()
    assert inbox and inbox[0]["dispute_id"] in {"PP-R-GHY-10196892", "PP-R-XSW-10196894"}
    assert all(k in inbox[0] for k in ("deadline_hours", "verdict", "urgent"))
