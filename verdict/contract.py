"""Contract checks against PayPal's own OpenAPI spec (docs/paypal-spec/customer-disputes-v1.json).

Every outbound dispute action body is validated against the component schemas PayPal publishes
*before* the request leaves the process. This turns PayPal's contract into a local, independent
oracle: if the spec says carrier_name must be one of 60 enum values, a bad carrier fails here, not
as a 400 in production.

The spec's requestBody blocks are inconsistent (they list only the file part for multipart
endpoints), so we map each action to the component schema of its JSON content explicitly.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SPEC_PATH = Path(__file__).resolve().parent.parent / "docs" / "paypal-spec" / "customer-disputes-v1.json"


class ContractError(Exception):
    def __init__(self, action: str, errors: list[str]):
        self.action, self.errors = action, errors
        super().__init__(f"{action}: payload violates PayPal's OpenAPI contract: " + "; ".join(errors[:5]))


@lru_cache(maxsize=1)
def spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


SPEC_URI = "urn:paypal:customer-disputes-v1"


@lru_cache(maxsize=1)
def registry() -> Registry:
    return Registry().with_resource(SPEC_URI, Resource.from_contents(spec(), default_specification=DRAFT202012))


def _schema(ref: str) -> dict:
    # refs like "#/components/schemas/x" resolve against the PayPal spec document itself
    return {"$ref": SPEC_URI + ref}


def _enum(name: str) -> list[str]:
    return spec()["components"]["schemas"][name]["enum"]


NOTE = {"type": "string", "minLength": 1, "maxLength": 2000}

# action -> JSON schema for the JSON body (or the multipart `input` part)
SCHEMAS: dict[str, dict[str, Any]] = {
    "make_offer": {"allOf": [_schema("#/components/schemas/make_offer"),
                             {"required": ["note", "offer_type"], "properties": {"offer_type": {"enum": _enum("offer_type")}}}]},
    "escalate": {"allOf": [_schema("#/components/schemas/escalate"), {"required": ["note"]}]},
    "send_message": {"type": "object", "required": ["message"], "properties": {"message": NOTE}, "additionalProperties": False},
    "accept_claim": {"type": "object", "required": ["note", "accept_claim_type"], "additionalProperties": False,
                     "properties": {"note": NOTE, "accept_claim_type": {"enum": _enum("accept_claim_type")},
                                    "refund_amount": _schema("#/components/schemas/money"),
                                    "return_shipping_address": _schema("#/components/schemas/address_portable"),
                                    "invoice_id": {"type": "string", "maxLength": 127}}},
    "provide_evidence": {"type": "object", "required": ["evidences"], "additionalProperties": False,
                         "properties": {"evidences": {"type": "array", "minItems": 1, "maxItems": 100,
                                                      "items": {"allOf": [_schema("#/components/schemas/evidence"), {"required": ["evidence_type"]}]}},
                                        "return_shipping_address": _schema("#/components/schemas/address_portable")}},
    "provide_supporting_info": {"type": "object", "required": ["notes"], "properties": {"notes": NOTE}, "additionalProperties": False},
}

# evidence types whose schema says evidence_info (tracking / refund ids) is expected
NEEDS_EVIDENCE_INFO = {"PROOF_OF_FULFILLMENT": "tracking_info", "PROOF_OF_REFUND": "refund_ids", "PROOF_OF_RETURN": "tracking_info"}


def validate(action: str, payload: dict) -> None:
    """Raise ContractError if payload violates PayPal's published schema for this action."""
    schema = SCHEMAS.get(action)
    if schema is None:
        return
    errors = [f"{'/'.join(str(p) for p in e.absolute_path) or '$'}: {e.message[:120]}"
              for e in sorted(Draft202012Validator(schema, registry=registry()).iter_errors(payload), key=lambda e: list(e.absolute_path))]
    if action == "provide_evidence":  # semantic rule stated in the evidence schema description
        for i, ev in enumerate(payload.get("evidences", [])):
            need = NEEDS_EVIDENCE_INFO.get(ev.get("evidence_type", ""))
            if need and not (ev.get("evidence_info") or {}).get(need):
                errors.append(f"evidences/{i}: {ev['evidence_type']} requires evidence_info.{need}")
            for t in (ev.get("evidence_info") or {}).get("tracking_info", []):
                if t.get("carrier_name") == "OTHER" and not t.get("carrier_name_other"):
                    errors.append(f"evidences/{i}: carrier_name OTHER requires carrier_name_other")
    if errors:
        raise ContractError(action, errors)


def carrier_for_paypal(carrier: str) -> dict:
    """Map a carrier string from Orders/Shipment Tracking onto the Disputes carrier_name enum."""
    allowed = set(_enum("carrier_name") if "carrier_name" in spec()["components"]["schemas"] else
                  spec()["components"]["schemas"]["tracking_info"]["properties"]["carrier_name"]["enum"])
    c = (carrier or "").upper().replace(" ", "_")
    if c in allowed:
        return {"carrier_name": c}
    return {"carrier_name": "OTHER", "carrier_name_other": carrier or "unknown carrier"}


def known_enum(name: str) -> list[str]:
    return list(_enum(name))
