import json

import pytest

from verdict.paypal import ActionNotAllowed, PayPalClient, encode_multipart


def test_multipart_has_input_json_part_and_file():
    body, ctype = encode_multipart({"evidences": [{"evidence_type": "OTHER", "notes": "hi"}]}, ("proof.txt", b"abc", "text/plain"))
    assert ctype.startswith("multipart/form-data; boundary=")
    boundary = ctype.split("boundary=")[1]
    assert body.count(f"--{boundary}".encode()) == 3  # 2 parts + closing
    assert b'name="input"' in body and b"Content-Type: application/json" in body
    assert b'name="evidence-file"; filename="proof.txt"' in body and b"abc" in body
    assert json.loads(body.split(b"\r\n\r\n")[1].split(b"\r\n--")[0]) == {"evidences": [{"evidence_type": "OTHER", "notes": "hi"}]}


def test_require_link_blocks_before_network():
    d = {"dispute_id": "X", "status": "UNDER_REVIEW", "links": [{"rel": "self"}]}
    c = PayPalClient(client_id="x", client_secret="y")
    with pytest.raises(ActionNotAllowed):
        c.send_message(d, "hello")
    with pytest.raises(ActionNotAllowed):
        c.provide_evidence(d, [{"evidence_type": "OTHER"}])
    with pytest.raises(ActionNotAllowed):
        c.accept_claim(d, "note")


def test_accept_claim_type_must_be_allowed():
    d = {"dispute_id": "X", "links": [{"rel": "accept_claim"}], "allowed_response_options": {"accept_claim": {"accept_claim_types": ["REFUND"]}}}
    c = PayPalClient(client_id="x", client_secret="y")
    with pytest.raises(ActionNotAllowed):
        c.accept_claim(d, "note", accept_claim_type="PARTIAL_REFUND")
