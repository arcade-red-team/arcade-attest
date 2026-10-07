"""MCP tools (SPEC D7): evaluate_decision, get_verdict, explain_evidence.

Install with: pip install "arcade-attest[mcp]" and run:
    python -m arcade_attest.mcp_server

The tool logic lives in plain functions so it is testable without a transport.
LLMs calling these tools receive verdicts; they never produce them.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import store
from .adapter import analyze_pair
from .anchor import build_attestation_payload
from .engine import evaluate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluate_decision(base_path: str, head_path: str, decision_record: dict, language: str = "python") -> dict:
    """Analyze base vs head and evaluate a Decision Record. Returns the evidence pack."""
    data = analyze_pair(base_path, head_path, language=language)
    moment = _now()
    pack = evaluate(decision_record, data, evaluated_at=_stamp(moment), expires_at=_stamp(moment + timedelta(hours=24)))
    store.write_pack(pack)
    return pack


def get_verdict(decision_uid: str) -> dict:
    """Return the stored evidence pack for a decision id, or an error object."""
    pack = store.read_pack(decision_uid)
    if pack is None:
        return {"error": "decision not found", "id": decision_uid}
    return pack


def explain_evidence(decision_uid: str) -> dict:
    """Compact, field-level explanation of a stored verdict (no generated prose)."""
    pack = store.read_pack(decision_uid)
    if pack is None:
        return {"error": "decision not found", "id": decision_uid}
    return {
        "id": pack["id"],
        "decision_id": pack["decision_id"],
        "repo": pack.get("repo"),
        "verdict": pack["verdict"],
        "verdict_code": pack["verdict_code"],
        "mode": pack["mode"],
        "enforced": pack["enforced"],
        "triggered": [
            {
                "type": result["type"],
                "severity": result["severity"],
                "measured": result["measured"],
                "threshold": result["threshold"],
                "evidence": result["evidence"],
            }
            for result in pack["predicates"]
            if result["status"] == "triggered"
        ],
        "measured": pack["measured"],
        "overall_score": pack.get("overall_score"),
        "criteria": [
            {"id": c["id"], "score": c["score"], "status": c["status"], "measured": c["measured"]}
            for c in pack.get("criteria") or []
        ],
        "scoring": pack.get("scoring"),
        "coverage_warnings": (pack.get("coverage") or {}).get("warnings", []),
        "hashes": pack["hashes"],
        "attestation_payload": build_attestation_payload(pack),
    }


def _register() -> "object":
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("arcade-attest")

    @mcp.tool(name="evaluate_decision")
    def _evaluate_tool(base_path: str, head_path: str, decision_record_json: str, language: str = "python") -> str:
        """Evaluate a Decision Record (JSON string) against base/head source trees; returns the evidence pack JSON."""
        return json.dumps(evaluate_decision(base_path, head_path, json.loads(decision_record_json), language))

    @mcp.tool(name="get_verdict")
    def _get_tool(decision_uid: str) -> str:
        """Fetch a stored evidence pack by its att_ id."""
        return json.dumps(get_verdict(decision_uid))

    @mcp.tool(name="explain_evidence")
    def _explain_tool(decision_uid: str) -> str:
        """Explain which predicates triggered, with measurements and coverage warnings."""
        return json.dumps(explain_evidence(decision_uid))

    return mcp


if __name__ == "__main__":
    _register().run()
