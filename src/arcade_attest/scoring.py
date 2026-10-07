"""Ten-criterion PR scoring (scoring@1): pure, deterministic, parallel.

Every scorer receives the SAME immutable bundle (full changelog + changes +
architecture summary) and returns a score on a 0.0-1.0 scale quantized to
0.1 steps, or ``not_run`` with ``score=None`` when its evidence is missing.
No scorer performs I/O, reads the clock, or mutates the bundle. The overall
verdict (PASS/WARN/BLOCK) stays with the predicate engine; these scores are
an advisory layer and never replace it. See SCORING-10-CRITERIA.md.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

SCORING_VERSION = "scoring@1"
SCORE_STEP = 0.1

_SEVERITY_WEIGHT = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _canon(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def bundle_hash(bundle: dict) -> str:
    return hashlib.sha256(_canon(bundle)).hexdigest()


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def quantize(raw: float) -> float:
    """Clamp to [0.0, 1.0] and quantize to the nearest 0.1 step."""
    return math.floor(_clamp(raw) * 10 + 0.5) / 10.0


def _result(criterion_id: str, formula: str, measured: dict, evidence: list, raw: float | None) -> dict:
    if raw is None:
        return {
            "id": criterion_id,
            "score": None,
            "status": "not_run",
            "measured": measured,
            "evidence": evidence,
            "formula": formula,
        }
    return {
        "id": criterion_id,
        "score": quantize(raw),
        "status": "scored",
        "measured": measured,
        "evidence": evidence,
        "formula": formula,
    }


def build_bundle(data: dict) -> dict:
    """Assemble the single scoring bundle fed to every scorer.

    ``data`` is the normalized changelog (adapter.normalize_changelog). The
    caller may additionally supply ``changes`` (full PR change feed) and
    ``architecture_summary``; supplied raw text is hashed with the bundle but
    never copied into the evidence pack by the engine.
    """
    data = copy.deepcopy(data) if isinstance(data, dict) else {}
    summary = data.get("summary") or {}
    metrics = data.get("metrics") or {}
    components = data.get("components") or []
    total_entities = sum(int(c.get("entities", 0)) for c in components if isinstance(c, dict))
    largest = max(
        (c for c in components if isinstance(c, dict)),
        key=lambda c: int(c.get("entities", 0)),
        default=None,
    )
    supplied_arch = data.get("architecture_summary")
    derived_arch = {
        "components_b": summary.get("components_b", len(components)),
        "entities_a": summary.get("entities_a"),
        "entities_b": summary.get("entities_b"),
        "total_component_entities": total_entities,
        "largest_component": (
            {"name": largest.get("name"), "entities": int(largest.get("entities", 0))} if largest else None
        ),
        "metrics_b": {name: (vals or {}).get("b") for name, vals in metrics.items() if isinstance(vals, dict)},
        "languages_b": (data.get("coverage") or {}).get("languages_b") or [],
    }
    supplied_changes = data.get("changes") if isinstance(data.get("changes"), dict) else None
    changes = {
        "source": "supplied" if supplied_changes else "derived_from_summary",
        "entities_added": (supplied_changes or {}).get("entities_added", summary.get("entities_added")),
        "entities_deleted": (supplied_changes or {}).get("entities_deleted", summary.get("entities_deleted")),
        "files_changed": (supplied_changes or {}).get("files_changed"),
        "lines_added": (supplied_changes or {}).get("lines_added"),
        "lines_deleted": (supplied_changes or {}).get("lines_deleted"),
    }
    if supplied_changes and "raw" in supplied_changes:
        changes["raw"] = supplied_changes["raw"]
    bundle = {
        "changes": changes,
        "architecture_summary": {
            "source": "supplied" if supplied_arch is not None else "derived",
            "derived": derived_arch,
            "supplied": supplied_arch,
        },
        "changelog": {
            "smells_new": data.get("smells_new") or [],
            "responsibility_shifts": data.get("responsibility_shifts") or [],
            "components": components,
            "summary": summary,
            "metrics": metrics,
            "coverage": data.get("coverage") or {},
        },
    }
    return bundle


# --- The ten scorers -------------------------------------------------------
# Each takes the bundle and returns one criterion result. Order in CRITERIA
# is the output order, regardless of parallel completion order.

def _score_smell_regression(bundle: dict) -> dict:
    smells = bundle["changelog"]["smells_new"]
    weighted = 0
    evidence = []
    for smell in smells:
        if not isinstance(smell, dict):
            continue
        weight = _SEVERITY_WEIGHT.get(str(smell.get("severity") or "").lower(), 1)
        weighted += weight
        evidence.append(
            {
                "kind": smell.get("smell_type") or smell.get("type") or smell.get("kind") or "unknown",
                "severity": smell.get("severity"),
                "weight": weight,
                "components": smell.get("affected_components") or smell.get("components") or [],
            }
        )
    raw = 1.0 - 0.2 * weighted
    return _result(
        "smell_regression",
        "scoring@1:smell_regression:raw=clamp(1-0.2*weighted_smells)",
        {"new_smells": len(evidence), "weighted_smells": weighted},
        evidence,
        raw,
    )


def _score_responsibility_stability(bundle: dict) -> dict:
    changelog = bundle["changelog"]
    shifts = changelog["responsibility_shifts"]
    entities_b = _num(changelog["summary"].get("entities_b"))
    if entities_b is None:
        entities_b = _num(changelog["coverage"].get("entities_b"))
    if entities_b is None:
        return _result(
            "responsibility_stability",
            "scoring@1:responsibility_stability:raw=clamp(1-5*(shifts/max(1,entities_b)))",
            {"responsibility_shifts": len(shifts), "entities_b": None},
            [{"reason": "entities_b missing: shift rate cannot be computed"}],
            None,
        )
    shift_rate = len(shifts) / max(1.0, entities_b)
    return _result(
        "responsibility_stability",
        "scoring@1:responsibility_stability:raw=clamp(1-5*(shifts/max(1,entities_b)))",
        {"responsibility_shifts": len(shifts), "entities_b": int(entities_b), "shift_rate": round(shift_rate, 4)},
        list(shifts)[:10],
        1.0 - 5.0 * shift_rate,
    )


def _component_shares(bundle: dict) -> tuple[list[dict], float] | None:
    changelog = bundle["changelog"]
    if changelog["coverage"].get("component_sizes_known") is False:
        return None
    components = [c for c in changelog["components"] if isinstance(c, dict)]
    total = sum(int(c.get("entities", 0)) for c in components)
    if not components or total <= 0:
        return None
    return components, float(total)


def _score_god_component_risk(bundle: dict) -> dict:
    formula = "scoring@1:god_component_risk:raw=clamp(1-largest_share)"
    shares = _component_shares(bundle)
    if shares is None:
        return _result("god_component_risk", formula, {}, [{"reason": "component sizes unknown or empty"}], None)
    components, total = shares
    largest = max(components, key=lambda c: int(c.get("entities", 0)))
    share = int(largest.get("entities", 0)) / total
    return _result(
        "god_component_risk",
        formula,
        {"largest_component": largest.get("name"), "largest_entities": int(largest.get("entities", 0)),
         "largest_share": round(share, 4)},
        [{"component": largest.get("name"), "entities": int(largest.get("entities", 0))}],
        1.0 - share,
    )


def _score_component_balance(bundle: dict) -> dict:
    formula = "scoring@1:component_balance:raw=clamp(1-(HHI-1/n)/(1-1/n))"
    shares = _component_shares(bundle)
    if shares is None:
        return _result("component_balance", formula, {}, [{"reason": "component sizes unknown or empty"}], None)
    components, total = shares
    n = len(components)
    if n < 2:
        return _result(
            "component_balance", formula, {"components": n},
            [{"reason": "fewer than 2 components: balance is undefined"}], None,
        )
    hhi = sum((int(c.get("entities", 0)) / total) ** 2 for c in components)
    raw = 1.0 - (hhi - 1.0 / n) / (1.0 - 1.0 / n)
    return _result(
        "component_balance",
        formula,
        {"components": n, "hhi": round(hhi, 4)},
        [{"component": c.get("name"), "entities": int(c.get("entities", 0))} for c in components],
        raw,
    )


def _metric_delta(bundle: dict, name: str) -> float | None:
    metric = (bundle["changelog"]["metrics"] or {}).get(name)
    if not isinstance(metric, dict):
        return None
    return _num(metric.get("delta"))


def _trend(criterion_id: str, metric: str, factor: float, sign: float, bundle: dict) -> dict:
    formula = f"scoring@1:{criterion_id}:raw=clamp(0.5{'+' if sign > 0 else '-'}{factor}*{metric}.delta)"
    delta = _metric_delta(bundle, metric)
    if delta is None:
        return _result(
            criterion_id, formula, {"metric": metric, "delta": None},
            [{"reason": f"metric {metric} missing from changelog"}], None,
        )
    metric_values = (bundle["changelog"]["metrics"] or {}).get(metric) or {}
    return _result(
        criterion_id,
        formula,
        {"metric": metric, "a": metric_values.get("a"), "b": metric_values.get("b"), "delta": delta},
        [{"metric": metric, "a": metric_values.get("a"), "b": metric_values.get("b"), "delta": delta}],
        0.5 + sign * factor * delta,
    )


def _score_modularity_trend(bundle: dict) -> dict:
    formula = "scoring@1:modularity_trend:raw=clamp(0.5+clamp(TurboMQ.delta,-0.5,0.5))"
    delta = _metric_delta(bundle, "TurboMQ")
    if delta is None:
        return _result(
            "modularity_trend", formula, {"metric": "TurboMQ", "delta": None},
            [{"reason": "metric TurboMQ missing from changelog"}], None,
        )
    metric_values = (bundle["changelog"]["metrics"] or {}).get("TurboMQ") or {}
    return _result(
        "modularity_trend",
        formula,
        {"metric": "TurboMQ", "a": metric_values.get("a"), "b": metric_values.get("b"), "delta": delta},
        [{"metric": "TurboMQ", "a": metric_values.get("a"), "b": metric_values.get("b"), "delta": delta}],
        0.5 + max(-0.5, min(0.5, delta)),
    )


def _score_coupling_control(bundle: dict) -> dict:
    formula = "scoring@1:coupling_control:raw=clamp(0.5-2.5*InterConnectivity.delta-1.0*TwoWayPairRatio.delta)"
    inter = _metric_delta(bundle, "InterConnectivity")
    if inter is None:
        return _result(
            "coupling_control", formula, {"metric": "InterConnectivity", "delta": None},
            [{"reason": "metric InterConnectivity missing from changelog"}], None,
        )
    twoway = _metric_delta(bundle, "TwoWayPairRatio") or 0.0
    return _result(
        "coupling_control",
        formula,
        {"inter_delta": inter, "twoway_delta": twoway},
        [{"metric": "InterConnectivity", "delta": inter}, {"metric": "TwoWayPairRatio", "delta": twoway}],
        0.5 - 2.5 * inter - 1.0 * twoway,
    )


def _score_change_containment(bundle: dict) -> dict:
    formula = "scoring@1:change_containment:raw=clamp(1-0.5*((added+deleted)/max(1,entities_a)))"
    summary = bundle["changelog"]["summary"]
    changes = bundle["changes"]
    added = _num(changes.get("entities_added"))
    deleted = _num(changes.get("entities_deleted"))
    entities_a = _num(summary.get("entities_a"))
    if added is None or deleted is None or entities_a is None:
        return _result(
            "change_containment", formula,
            {"entities_added": added, "entities_deleted": deleted, "entities_a": entities_a},
            [{"reason": "entities_added/entities_deleted/entities_a missing: churn cannot be computed"}], None,
        )
    churn = (added + deleted) / max(1.0, entities_a)
    return _result(
        "change_containment",
        formula,
        {"entities_added": int(added), "entities_deleted": int(deleted),
         "entities_a": int(entities_a), "churn_rate": round(churn, 4)},
        [{"entities_added": int(added), "entities_deleted": int(deleted), "entities_a": int(entities_a)}],
        1.0 - 0.5 * churn,
    )


def _score_evidence_confidence(bundle: dict) -> dict:
    formula = "scoring@1:evidence_confidence:raw=clamp(1-penalties)"
    coverage = bundle["changelog"]["coverage"]
    entities_b = _num(coverage.get("entities_b"))
    if entities_b is None:
        entities_b = _num(bundle["changelog"]["summary"].get("entities_b"))
    if entities_b is None:
        return _result(
            "evidence_confidence", formula, {"entities_b": None},
            [{"reason": "coverage entities_b missing: measurement confidence cannot be scored"}], None,
        )
    penalties = []
    raw = 1.0
    if entities_b == 0:
        raw = 0.0
        penalties.append({"penalty": "entities_b_zero", "value": -1.0})
    if coverage.get("component_sizes_known") is False:
        raw -= 0.3
        penalties.append({"penalty": "component_sizes_unknown", "value": -0.3})
    warnings = coverage.get("warnings") or []
    if warnings:
        deduction = min(0.3, 0.1 * len(warnings))
        raw -= deduction
        penalties.append({"penalty": "coverage_warnings", "count": len(warnings), "value": -deduction})
    if not coverage.get("languages_b"):
        raw -= 0.2
        penalties.append({"penalty": "languages_b_empty", "value": -0.2})
    return _result(
        "evidence_confidence",
        formula,
        {"entities_b": int(entities_b), "warnings": len(warnings)},
        penalties,
        raw,
    )


CRITERIA: tuple[Callable[[dict], dict], ...] = (
    _score_smell_regression,
    _score_responsibility_stability,
    _score_god_component_risk,
    _score_component_balance,
    _score_modularity_trend,
    lambda bundle: _trend("cohesion_trend", "IntraConnectivity", 2.5, 1.0, bundle),
    _score_coupling_control,
    lambda bundle: _trend("recovery_confidence_trend", "RCI", 2.5, 1.0, bundle),
    _score_change_containment,
    _score_evidence_confidence,
)

CRITERION_IDS: tuple[str, ...] = (
    "smell_regression",
    "responsibility_stability",
    "god_component_risk",
    "component_balance",
    "modularity_trend",
    "cohesion_trend",
    "coupling_control",
    "recovery_confidence_trend",
    "change_containment",
    "evidence_confidence",
)


# --- Admin weight configuration: template/appetite profiles ("skills") -----
# Each profile is a selection skill for agents applying the Decision API: the
# manifest under skills/scoring/<id>.json mirrors this registry 1:1 (a test
# enforces that), an agent picks a profile id from the `apply_when` signals,
# and the deterministic engine resolves and validates the weights. An admin
# may also override individual weights; verdict thresholds never move.


def _weights(**overrides: float) -> dict[str, float]:
    weights = {criterion_id: 1.0 for criterion_id in CRITERION_IDS}
    weights.update(overrides)
    return weights


SCORING_PROFILES: tuple[dict, ...] = (
    {
        "id": "balanced",
        "name": "Balanced (default)",
        "appetite": "balanced",
        "description": "Every criterion counts equally. Default when an admin configures nothing.",
        "apply_when": {"signals": ["no special signal", "first rollout", "baseline reporting"]},
        "weights": _weights(),
    },
    {
        "id": "strict_gate",
        "name": "Strict Gate",
        "appetite": "risk_averse",
        "description": "Blocking/architecture-board gates: smells, god components, coupling and evidence confidence dominate.",
        "apply_when": {"mode": ["blocking"], "signals": ["architecture board", "regulated", "high risk"]},
        "weights": _weights(
            smell_regression=3.0, responsibility_stability=2.0, god_component_risk=3.0,
            component_balance=1.5, modularity_trend=1.5, coupling_control=2.5,
            change_containment=1.5, evidence_confidence=2.0,
        ),
    },
    {
        "id": "ship_fast",
        "name": "Ship Fast",
        "appetite": "speed",
        "description": "Small-team/startup flow: containment and responsibility stability dominate; trend criteria still report but weigh less.",
        "apply_when": {"signals": ["ship-fast", "startup", "mvp", "small team"]},
        "weights": _weights(
            smell_regression=1.5, responsibility_stability=2.0, god_component_risk=1.0,
            component_balance=0.5, modularity_trend=1.0, cohesion_trend=0.5,
            coupling_control=1.0, recovery_confidence_trend=0.5,
            change_containment=3.0, evidence_confidence=1.5,
        ),
    },
    {
        "id": "refactor_friendly",
        "name": "Refactor Friendly",
        "appetite": "refactor_tolerant",
        "description": "Migrations and refactors: modularity/cohesion/RCI/balance dominate; shifts and churn are expected, so they weigh less.",
        "apply_when": {"signals": ["refactor", "migration", "modernization"]},
        "weights": _weights(
            smell_regression=1.5, responsibility_stability=0.5, god_component_risk=2.0,
            component_balance=2.0, modularity_trend=3.0, cohesion_trend=2.5,
            coupling_control=2.0, recovery_confidence_trend=2.5,
            change_containment=0.5, evidence_confidence=1.5,
        ),
    },
    {
        "id": "ai_agent_code_gate",
        "name": "AI Agent Code Gate",
        "appetite": "agent_risk_averse",
        "description": "Code produced by AI agents: smells, god components, coupling, containment and evidence confidence dominate.",
        "apply_when": {"signals": ["ai-agent", "agent-code", "ai-generated"]},
        "weights": _weights(
            smell_regression=3.0, responsibility_stability=2.0, god_component_risk=3.0,
            component_balance=1.5, modularity_trend=1.5, coupling_control=3.0,
            change_containment=2.5, evidence_confidence=2.5,
        ),
    },
    {
        "id": "oss_maintainer",
        "name": "OSS Maintainer Triage",
        "appetite": "maintainer_triage",
        "description": "High-volume PR triage: evidence confidence, smells, stability and containment decide what needs a human first.",
        "apply_when": {"signals": ["oss", "maintainer", "review-triage", "high-volume pr"]},
        "weights": _weights(
            smell_regression=2.5, responsibility_stability=2.0, god_component_risk=1.5,
            cohesion_trend=0.75, recovery_confidence_trend=0.75,
            change_containment=2.5, evidence_confidence=3.0,
        ),
    },
)

_PROFILE_BY_ID = {profile["id"]: profile for profile in SCORING_PROFILES}


def list_profiles() -> list[dict]:
    """All admin weight profiles (templates), in registry order."""
    return copy.deepcopy(list(SCORING_PROFILES))


def validate_scoring_config(config: Any) -> None:
    """Validate the optional ``scoring`` object of a Decision Record."""
    if config is None:
        return
    if not isinstance(config, dict):
        raise ValueError("Decision Record 'scoring' must be a JSON object")
    unknown_keys = set(config) - {"profile", "weights", "context"}
    if unknown_keys:
        raise ValueError(f"Decision Record 'scoring' has unsupported keys: {sorted(unknown_keys)}")
    profile = config.get("profile")
    if profile is not None and profile != "auto" and profile not in _PROFILE_BY_ID:
        raise ValueError(
            f"Unsupported scoring profile: {profile!r} (supported: {', '.join(_PROFILE_BY_ID)}, auto)"
        )
    weights = config.get("weights")
    if weights is not None:
        if not isinstance(weights, dict) or not weights:
            raise ValueError("Decision Record 'scoring.weights' must be a non-empty JSON object")
        unknown = set(weights) - set(CRITERION_IDS)
        if unknown:
            raise ValueError(f"Unknown criterion in scoring.weights: {sorted(unknown)}")
        for criterion_id, value in weights.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValueError(f"scoring.weights.{criterion_id} must be a non-negative number")
        if all(float(value) == 0.0 for value in weights.values()):
            raise ValueError("scoring.weights must not set every criterion weight to 0")
    context = config.get("context")
    if context is not None:
        if not isinstance(context, dict):
            raise ValueError("Decision Record 'scoring.context' must be a JSON object")
        tags = context.get("tags")
        if tags is not None and (not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags)):
            raise ValueError("Decision Record 'scoring.context.tags' must be a list of strings")


def suggest_profile(context: dict | None = None, *, mode: str | None = None) -> tuple[str, str]:
    """Deterministically suggest a profile from admin/agent-supplied signals.

    Returns (profile_id, rule_id). This is the machine form of the selection
    skill in skills/scoring/SKILL.md: an agent may propose the context, but
    the suggestion rule is fixed and reported in the evidence pack.
    """
    context = context or {}
    tags = {str(tag).lower() for tag in context.get("tags") or []}
    signals = tags | {str(context.get("purpose") or "").lower(), str(context.get("change_kind") or "").lower()}
    if signals & {"ai-agent", "agent-code", "ai-generated"}:
        return "ai_agent_code_gate", "signal:ai-agent-code"
    if signals & {"refactor", "migration", "modernization"}:
        return "refactor_friendly", "signal:refactor-or-migration"
    if signals & {"oss", "maintainer", "review-triage", "high-volume pr"}:
        return "oss_maintainer", "signal:oss-maintainer-triage"
    if signals & {"ship-fast", "startup", "mvp", "small team"}:
        return "ship_fast", "signal:ship-fast"
    if mode == "blocking" or signals & {"regulated", "architecture board", "high risk"}:
        return "strict_gate", "signal:blocking-or-high-risk"
    return "balanced", "default:balanced"


def resolve_weights(record: dict) -> dict:
    """Resolve a Decision Record's scoring config into effective weights."""
    config = record.get("scoring") or {}
    validate_scoring_config(config)
    suggestion_rule = None
    profile_id = config.get("profile")
    if profile_id == "auto":
        profile_id, suggestion_rule = suggest_profile(config.get("context"), mode=record.get("mode"))
        source = "auto_suggested"
    elif profile_id:
        source = "preset"
    else:
        profile_id = "balanced"
        source = "default"
    profile = _PROFILE_BY_ID[profile_id]
    weights = {criterion_id: float(value) for criterion_id, value in profile["weights"].items()}
    overrides = config.get("weights") or {}
    for criterion_id, value in overrides.items():
        weights[criterion_id] = float(value)
    if overrides:
        source = f"{source}+custom_weights"
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Resolved scoring weights sum to 0: at least one criterion needs a positive weight")
    return {
        "profile": {
            "id": profile["id"],
            "name": profile["name"],
            "appetite": profile["appetite"],
            "skill": f"skills/scoring/{profile['id']}.json",
        },
        "source": source,
        "suggestion_rule": suggestion_rule,
        "weights": weights,
        "normalized_weights": {criterion_id: round(value / total, 4) for criterion_id, value in weights.items()},
    }


def score_all(bundle: dict, *, weights: dict | None = None, max_workers: int = 10) -> list[dict]:
    """Score all ten criteria in parallel over the same bundle.

    Results are reassembled in CRITERION_IDS order, so parallel execution
    never changes the output. Each scorer gets its own deep copy: scorers
    are pure, and the copy keeps that true even if one misbehaves. Resolved
    admin weights are attached to each result; scoring itself is unweighted.
    """
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(CRITERIA)))) as pool:
        results = list(pool.map(lambda scorer: scorer(copy.deepcopy(bundle)), CRITERIA))
    by_id = {result["id"]: result for result in results}
    ordered = [by_id[criterion_id] for criterion_id in CRITERION_IDS]
    resolved = weights or {}
    for result in ordered:
        weight = float(resolved.get(result["id"], 1.0))
        result["weight"] = weight
        result["weighted_score"] = round(result["score"] * weight, 4) if result["score"] is not None else None
    return ordered


def overall_score(criteria: list[dict], weights: dict | None = None) -> float | None:
    """Weighted mean of scored criteria (not_run and 0-weight excluded)."""
    total_weight = 0.0
    weighted_sum = 0.0
    for criterion in criteria:
        if criterion["status"] != "scored" or criterion["score"] is None:
            continue
        weight = float((weights or {}).get(criterion["id"], criterion.get("weight", 1.0)))
        if weight <= 0:
            continue
        weighted_sum += criterion["score"] * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    return quantize(weighted_sum / total_weight)
