"""On-chain anchoring (EAS on Base). D3 scope: payload shape only.

The chain stores hashes and the verdict, never the evidence itself. This
module builds the attestation payload; submitting it lands in D3-D4 work.
"""
from __future__ import annotations

# EAS schema (Base Sepolia first):
# string repo; bytes32 baseCommit; bytes32 headCommit; bytes32 decisionRecordHash;
# uint8 verdict; int32 smellsDelta; uint32 responsibilityShifts;
# bytes32 evidenceHash; uint64 evaluatedAt; uint64 expiresAt
EAS_SCHEMA = (
    "string repo,bytes32 baseCommit,bytes32 headCommit,bytes32 decisionRecordHash,"
    "uint8 verdict,int32 smellsDelta,uint32 responsibilityShifts,"
    "bytes32 evidenceHash,uint64 evaluatedAt,uint64 expiresAt"
)


def _bytes32(value: str | None) -> str:
    digest = (value or "").removeprefix("0x")
    return "0x" + digest.ljust(64, "0")[:64]


def build_attestation_payload(pack: dict, *, base_commit: str = "", head_commit: str = "") -> dict:
    summary = pack.get("summary") or {}
    smells_delta = int(summary.get("smells_new", pack["measured"]["smells_new"])) - int(
        summary.get("smells_resolved", 0)
    )
    return {
        "schema": EAS_SCHEMA,
        "network": "base-sepolia",
        "data": {
            "repo": pack.get("repo") or "",
            "baseCommit": _bytes32(base_commit),
            "headCommit": _bytes32(head_commit),
            "decisionRecordHash": _bytes32(pack["hashes"]["decision_record_hash"]),
            "verdict": pack["verdict_code"],
            "smellsDelta": smells_delta,
            "responsibilityShifts": pack["measured"]["responsibility_shifts"],
            "evidenceHash": _bytes32(pack["hashes"]["evidence_hash"]),
            "evaluatedAt": pack["evaluated_at"],
            "expiresAt": pack.get("expires_at"),
        },
        "status": "not_submitted",
        "note": "Payload builder only; EAS submission is D3-D4 scope.",
    }
