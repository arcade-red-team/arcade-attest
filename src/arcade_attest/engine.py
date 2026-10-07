"""Decision engine: pure, deterministic predicate evaluation.

Input is a normalized evaluation payload (see adapter.normalize_changelog for
how arcade-agent output maps into it) plus a Decision Record. Output is an
evidence pack whose hashes are stable for identical inputs.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import HONEST_GAPS, VERDICT_CODES, __version__
from .scoring import (
    SCORING_VERSION,
    build_bundle,
    bundle_hash,
    overall_score,
    resolve_weights,
    score_all,
    validate_scoring_config,
)

SUPPORTED_PREDICATES = ("no_new_smells", "max_responsibility_shifts", "component_entity_cap")
SEVERITIES = ("fail", "warn")


def canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(payload: Any) -> str:
    if isinstance(payload, (bytes, bytearray)):
        return hashlib.sha256(bytes(payload)).hexdigest()
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def validate_record(record: dict) -> None:
    if not isinstance(record, dict):
        raise ValueError("Decision Record must be a JSON object")
    if not record.get("id"):
        raise ValueError("Decision Record requires an 'id'")
    predicates = record.get("predicates")
    if not isinstance(predicates, list) or not predicates:
        raise ValueError("Decision Record requires a non-empty 'predicates' list")
    for pred in predicates:
        ptype = pred.get("type")
        if ptype not in SUPPORTED_PREDICATES:
            raise ValueError(f"Unsupported predicate type: {ptype!r} (supported: {', '.join(SUPPORTED_PREDICATES)})")
        if pred.get("severity", "fail") not in SEVERITIES:
            raise ValueError(f"Predicate {ptype}: severity must be one of {SEVERITIES}")
        params = pred.get("params") or {}
        if ptype in ("max_responsibility_shifts", "component_entity_cap"):
            limit = params.get("max")
            if not isinstance(limit, (int, float)) or isinstance(limit, bool) or limit < 0:
                raise ValueError(f"Predicate {ptype}: params.max must be a non-negative number")
    validate_scoring_config(record.get("scoring"))


def _smell_kind(smell: dict) -> str:
    return str(smell.get("smell_type") or smell.get("type") or smell.get("kind") or "unknown")


def evaluate_predicate(pred: dict, data: dict) -> dict:
    ptype = pred["type"]
    params = pred.get("params") or {}
    severity = pred.get("severity", "fail")
    if ptype == "no_new_smells":
        kinds = params.get("kinds")
        new_smells = data.get("smells_new") or []
        measured_items = [s for s in new_smells if not kinds or _smell_kind(s) in kinds]
        measured = len(measured_items)
        triggered = measured > 0
        evidence = [
            {"kind": _smell_kind(s), "components": s.get("affected_components") or s.get("components") or []}
            for s in measured_items
        ]
        threshold = {"kinds": kinds or "any", "allowed": 0}
    elif ptype == "max_responsibility_shifts":
        shifts = data.get("responsibility_shifts") or []
        measured = len(shifts)
        triggered = measured > int(params["max"])
        evidence = shifts
        threshold = {"max": params["max"]}
    else:  # component_entity_cap
        components = data.get("components") or []
        only = params.get("component")
        scoped = [c for c in components if not only or c.get("name") == only]
        offenders = [c for c in scoped if int(c.get("entities", 0)) > int(params["max"])]
        measured = max((int(c.get("entities", 0)) for c in scoped), default=0)
        triggered = bool(offenders)
        evidence = [{"component": c.get("name"), "entities": int(c.get("entities", 0))} for c in offenders]
        threshold = {"max": params["max"], "component": only or "any"}
    return {
        "type": ptype,
        "severity": severity,
        "status": "triggered" if triggered else "pass",
        "measured": measured,
        "threshold": threshold,
        "evidence": evidence,
    }


def evaluate(record: dict, data: dict, *, evaluated_at: str, expires_at: str | None = None) -> dict:
    """Evaluate a Decision Record against normalized changelog data.

    Returns the evidence pack (without on-chain fields). `evaluated_at` is an
    ISO-8601 string supplied by the caller so results stay reproducible.
    """
    validate_record(record)
    results = [evaluate_predicate(pred, data) for pred in record["predicates"]]
    verdict = "PASS"
    for result in results:
        if result["status"] == "triggered":
            candidate = "BLOCK" if result["severity"] == "fail" else "WARN"
            if VERDICT_CODES[candidate] > VERDICT_CODES[verdict]:
                verdict = candidate
    components = data.get("components") or []
    largest = max(components, key=lambda c: int(c.get("entities", 0)), default=None)
    coverage = dict(data.get("coverage") or {})
    warnings = list(coverage.get("warnings") or [])
    if coverage.get("entities_b") == 0:
        warnings.append("Head analysis produced 0 entities: possible parser blind spot, verdict may be a false PASS.")
    if coverage.get("component_sizes_known") is False:
        warnings.append("Component entity counts are unknown (changelog-only input): component_entity_cap cannot trigger on this input.")
    mode = record.get("mode", "advisory")
    # Ten-criterion advisory scoring (scoring@1): all scorers run in parallel
    # over one bundle holding the full changelog + changes + architecture
    # summary. Scores never change the predicate verdict above.
    bundle = build_bundle(data)
    resolved = resolve_weights(record)
    criteria = score_all(bundle, weights=resolved["weights"])
    scored = [c for c in criteria if c["status"] == "scored"]
    scored_positive = [c for c in scored if resolved["weights"][c["id"]] > 0]
    scored_weight = sum(resolved["weights"][c["id"]] for c in scored_positive)
    effective_weights = {
        c["id"]: round(resolved["weights"][c["id"]] / scored_weight, 4)
        for c in scored_positive
    } if scored_weight > 0 else {}
    pack = {
        "schema": "arcade-attest/evidence@1",
        "decision_id": record["id"],
        "record_version": record.get("version", 1),
        "repo": record.get("repo"),
        "mode": mode,
        "enforced": mode == "blocking",
        "refs": data.get("refs") or {},
        "evaluated_at": evaluated_at,
        "expires_at": expires_at,
        "verdict": verdict,
        "verdict_code": VERDICT_CODES[verdict],
        "predicates": results,
        "measured": {
            "smells_new": len(data.get("smells_new") or []),
            "responsibility_shifts": len(data.get("responsibility_shifts") or []),
            "largest_component": (
                {"name": largest.get("name"), "entities": int(largest.get("entities", 0))} if largest else None
            ),
        },
        "summary": data.get("summary") or {},
        "architecture_summary": bundle["architecture_summary"]["derived"],
        "criteria": criteria,
        "overall_score": overall_score(criteria, resolved["weights"]),
        "scoring": {
            "version": SCORING_VERSION,
            "scale": "0.0-1.0 step 0.1",
            "parallel_scorers": len(criteria),
            "scored_count": len(scored),
            "not_run": [c["id"] for c in criteria if c["status"] != "scored"],
            "scoring_input_hash": bundle_hash(bundle),
            "changes_source": bundle["changes"]["source"],
            "profile": resolved["profile"],
            "config_source": resolved["source"],
            "suggestion_rule": resolved["suggestion_rule"],
            "weights": resolved["weights"],
            "normalized_weights": resolved["normalized_weights"],
            "effective_weights": effective_weights,
            "llm_in_scoring": False,
        },
        "coverage": {**coverage, "warnings": warnings},
        "engine": {
            "name": "arcade-attest",
            "version": __version__,
            "analyzer": "arcade-agent changelog_architecture (PKG recovery)",
            "llm_in_verdict": False,
        },
        "honest_gaps": HONEST_GAPS,
        "hashes": {"decision_record_hash": sha256_hex(record)},
    }
    pack["hashes"]["evidence_hash"] = sha256_hex(pack)
    pack["id"] = f"att_{pack['hashes']['evidence_hash'][:16]}"
    return pack
