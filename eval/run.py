"""Run every system over eval/cases and write eval/results.md.

Systems:
  refund_all       accept every claim (what many small sellers actually do)
  fight_all        submit evidence whenever PayPal allows it, else accept
  protection_only  respond iff seller_protection == ELIGIBLE (ignores tracking/address/links)
  verdict          the deterministic engine (verdict.engine)
  llm_only         Claude zero-shot on the same bundle, no rules (only when ANTHROPIC_API_KEY is set)

Metrics (vs oracle label):
  accuracy, unsafe-action rate (recommends a PayPal action the links don't allow),
  over-refund rate (REFUND_NOW when oracle says contest/respond), under-refund rate (contest when oracle says refund),
  per-reason accuracy, latency.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from verdict.bundle import EvidenceBundle
from verdict.config import settings
from verdict.engine import ACTION_FOR, VERDICTS, decide

CASES = Path(__file__).resolve().parent / "cases"
OUT = Path(__file__).resolve().parent / "results.md"
CONTEST = {"RESPOND_WITH_EVIDENCE", "OFFER_PARTIAL", "REPLY_AND_WAIT"}


def load() -> list[dict]:
    rows = []
    for p in sorted(CASES.glob("*.json")):
        c = json.loads(p.read_text())
        c["bundle_obj"] = EvidenceBundle(**c["bundle"])
        rows.append(c)
    return rows


# ---------- systems ----------
def sys_refund_all(b: EvidenceBundle):
    return ("REFUND_NOW", "accept_claim") if "accept_claim" in b.links else ("NO_ACTION_AVAILABLE", None)


def sys_fight_all(b: EvidenceBundle):
    if "provide_evidence" in b.links:
        return "RESPOND_WITH_EVIDENCE", "provide_evidence"
    if "accept_claim" in b.links:
        return "REFUND_NOW", "accept_claim"
    return "NO_ACTION_AVAILABLE", None


def sys_protection_only(b: EvidenceBundle):
    if b.seller_protection_status == "ELIGIBLE":
        return "RESPOND_WITH_EVIDENCE", "provide_evidence"  # ignores links on purpose: measures unsafe actions
    return "REFUND_NOW", "accept_claim"


def sys_verdict(b: EvidenceBundle):
    v = decide(b)
    return v.verdict, v.action


LLM_PROMPT = """You advise a PayPal seller on a dispute. Given the evidence bundle (JSON), answer with one of:
REFUND_NOW, RESPOND_WITH_EVIDENCE, OFFER_PARTIAL, REPLY_AND_WAIT, NO_ACTION_AVAILABLE
and the PayPal action rel you would call (accept_claim, provide_evidence, make_offer, send_message, provide_supporting_info, or null).
Respond ONLY as JSON: {"verdict": ..., "action": ...}"""


def sys_llm_only(b: EvidenceBundle):
    import anthropic, os, re
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(model=os.environ.get("VERDICT_MODEL", "claude-sonnet-5-5"), max_tokens=1500, system=LLM_PROMPT,
                                 messages=[{"role": "user", "content": b.model_dump_json(exclude={"now"})}])
    text = "".join(x.text for x in msg.content if getattr(x, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        j = json.loads(m.group(0))
        return j.get("verdict", "?"), j.get("action")
    except Exception:
        return "?", None


SYSTEMS = {"refund_all": sys_refund_all, "fight_all": sys_fight_all, "protection_only": sys_protection_only, "verdict": sys_verdict}


def evaluate(rows: list[dict], systems: dict) -> dict:
    res = {}
    for name, fn in systems.items():
        n = len(rows); correct = unsafe = over = under = 0; per_reason = defaultdict(lambda: [0, 0]); t0 = time.time(); confusion = Counter(); errors = []
        for c in rows:
            b, gold = c["bundle_obj"], c["label"]
            pred, action = fn(b)
            if pred == gold:
                correct += 1
            else:
                errors.append((c["id"], gold, pred, c["label_reason"]))
            if action and action not in b.links:
                unsafe += 1
            if pred == "REFUND_NOW" and gold in CONTEST:
                over += 1
            if pred in CONTEST and gold == "REFUND_NOW":
                under += 1
            per_reason[b.reason][0] += pred == gold; per_reason[b.reason][1] += 1
            confusion[(gold, pred)] += 1
        res[name] = {"n": n, "accuracy": correct / n, "unsafe_rate": unsafe / n, "over_refund": over / n, "under_refund": under / n,
                     "per_reason": {k: v[0] / v[1] for k, v in per_reason.items()}, "ms_per_case": (time.time() - t0) * 1000 / n,
                     "confusion": confusion, "errors": errors}
    return res


def write_md(rows: list[dict], res: dict) -> str:
    gold = Counter(c["label"] for c in rows); src = Counter(c["source"] for c in rows)
    L = ["# Evaluation results", "", f"{len(rows)} cases ({src['sandbox']} captured from the PayPal sandbox, {src['synthetic']} synthetic bundles on the same schema). "
         "Ground truth = `eval/oracle.py`, an independent decision table written from PayPal's published Seller Protection / dispute rules and hand-reviewed. "
         "**A label is what policy says the seller should do, not what PayPal will decide.**", "",
         "Label distribution: " + ", ".join(f"{k} {v}" for k, v in gold.most_common()), "",
         "| system | accuracy | unsafe-action rate | over-refund | under-refund | INR acc | SNAD acc | UNAUTH acc | ms/case |", "|---|---|---|---|---|---|---|---|---|"]
    for name, r in res.items():
        pr = r["per_reason"]
        L.append(f"| {name} | **{r['accuracy']:.0%}** | {r['unsafe_rate']:.0%} | {r['over_refund']:.0%} | {r['under_refund']:.0%} | "
                 f"{pr.get('MERCHANDISE_OR_SERVICE_NOT_RECEIVED', 0):.0%} | {pr.get('MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED', 0):.0%} | {pr.get('UNAUTHORISED', 0):.0%} | {r['ms_per_case']:.1f} |")
    L += ["", "- unsafe-action rate: the system recommends calling a PayPal action that the dispute's HATEOAS links do not currently allow (PayPal would return ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE).",
          "- over-refund: refunds when the policy says respond/offer/wait (money left on the table). under-refund: contests when the policy says refund (time and fees wasted).", ""]
    for name, r in res.items():
        if r["errors"]:
            L += [f"## {name}: disagreements with the oracle ({len(r['errors'])})", "", "| case | oracle | system | oracle reason |", "|---|---|---|---|"]
            L += [f"| {cid} | {g} | {p} | {why} |" for cid, g, p, why in r["errors"][:40]]
            L.append("")
    L += ["## Limitations", "",
          "- The oracle is our reading of PayPal's policy pages (docs/policy_sources.md); PayPal's internal adjudication uses more signals (buyer history, carrier scans, fraud models) that no API exposes.",
          "- Synthetic cases vary 6 factors on a grid; real dispute mixes are skewed (INR ≈ 70%) and contain messier data (partial addresses, multiple trackers).",
          "- The sandbox cannot produce adjudication outcomes on demand, so we do not report win rates and make no claim about them.",
          "- `p_keep` values in the EV model are documented assumptions used to rank options, not calibrated probabilities."]
    md = "\n".join(L)
    OUT.write_text(md)
    return md


def main() -> None:
    rows = load()
    systems = dict(SYSTEMS)
    if settings.llm_enabled and "--no-llm" not in sys.argv:
        systems["llm_only"] = sys_llm_only
    res = evaluate(rows, systems)
    print(write_md(rows, res))


if __name__ == "__main__":
    main()
