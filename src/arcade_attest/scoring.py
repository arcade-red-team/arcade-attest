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


def score_all(bundle: dict, *, max_workers: int = 10) -> list[dict]:
    """Score all ten criteria in parallel over the same bundle.

    Results are reassembled in CRITERION_IDS order, so parallel execution
    never changes the output. Each scorer gets its own deep copy: scorers
    are pure, and the copy keeps that true even if one misbehaves.
    """
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(CRITERIA)))) as pool:
        results = list(pool.map(lambda scorer: scorer(copy.deepcopy(bundle)), CRITERIA))
    by_id = {result["id"]: result for result in results}
    return [by_id[criterion_id] for criterion_id in CRITERION_IDS]


def overall_score(criteria: list[dict]) -> float | None:
    scored = [c["score"] for c in criteria if c["status"] == "scored" and c["score"] is not None]
    if not scored:
        return None
    return quantize(sum(scored) / len(scored))
