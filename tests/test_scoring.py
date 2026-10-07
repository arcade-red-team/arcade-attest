import copy

from arcade_attest.engine import evaluate
from arcade_attest.render import render_comment
from arcade_attest.scoring import CRITERION_IDS, build_bundle, bundle_hash, quantize, score_all

AT = "2026-10-04T00:00:00Z"

RECORD = {
    "id": "ADR-SCORE",
    "repo": "example/score",
    "version": 1,
    "mode": "advisory",
    "predicates": [{"type": "no_new_smells", "severity": "fail"}],
}

FULL = {
    "smells_new": [],
    "responsibility_shifts": [{"entity": "a.B", "from": "X", "to": "Y"}],
    "components": [
        {"name": "Auth", "entities": 3},
        {"name": "Billing", "entities": 7},
        {"name": "Notifications", "entities": 3},
        {"name": "Orders", "entities": 3},
        {"name": "Utils", "entities": 4},
    ],
    "summary": {
        "components_a": 5,
        "components_b": 5,
        "entities_a": 39,
        "entities_b": 20,
        "entities_added": 6,
        "entities_deleted": 25,
        "smells_new": 0,
        "smells_resolved": 2,
    },
    "metrics": {
        "TurboMQ": {"a": 1.3914, "b": 1.7167, "delta": 0.3253},
        "IntraConnectivity": {"a": 0.14, "b": 0.1524, "delta": 0.0124},
        "InterConnectivity": {"a": 0.1185, "b": 0.2524, "delta": 0.1339},
        "TwoWayPairRatio": {"a": 0.1667, "b": 0.0, "delta": -0.1667},
        "RCI": {"a": 0.2917, "b": 0.3636, "delta": 0.0719},
    },
    "coverage": {"entities_a": 39, "entities_b": 20, "languages_b": ["python"], "component_sizes_known": True, "warnings": []},
    "refs": {"a": "base", "b": "head"},
}

BLOCKY = {
    **FULL,
    "smells_new": [
        {"smell_type": "Concern Overload", "severity": "medium", "affected_components": ["Utils"]},
        {"smell_type": "Dependency Cycle", "severity": "low", "affected_components": ["Billing", "Notifications"]},
    ],
    "components": [
        {"name": "Auth", "entities": 3},
        {"name": "Billing", "entities": 5},
        {"name": "Notifications", "entities": 5},
        {"name": "Orders", "entities": 3},
        {"name": "Utils", "entities": 23},
    ],
}


def test_ten_criteria_in_contract_order_all_scored_on_full_data():
    criteria = score_all(build_bundle(FULL))
    assert [c["id"] for c in criteria] == list(CRITERION_IDS)
    assert len(criteria) == 10
    assert all(c["status"] == "scored" for c in criteria)


def test_scores_are_quantized_to_point_one_steps():
    for criterion in score_all(build_bundle(FULL)) + score_all(build_bundle(BLOCKY)):
        score = criterion["score"]
        assert score is not None and 0.0 <= score <= 1.0
        assert abs(score * 10 - round(score * 10)) < 1e-9
    assert quantize(0.84) == 0.8
    assert quantize(0.85) == 0.9
    assert quantize(-1.0) == 0.0
    assert quantize(2.0) == 1.0


def test_clean_change_scores_high_where_blocky_scores_low():
    clean = {c["id"]: c["score"] for c in score_all(build_bundle(FULL))}
    blocky = {c["id"]: c["score"] for c in score_all(build_bundle(BLOCKY))}
    assert clean["smell_regression"] == 1.0
    assert blocky["smell_regression"] == 0.4  # weighted 2+1 -> 1 - 0.2*3
    assert blocky["god_component_risk"] < clean["god_component_risk"]
    assert clean["modularity_trend"] == 0.8  # 0.5 + 0.3253 -> 0.8
    assert clean["coupling_control"] == 0.3  # inter worsened, twoway improved


def test_missing_evidence_is_not_run_never_zero():
    bare = {"smells_new": [], "responsibility_shifts": [], "components": [], "summary": {}, "coverage": {}}
    criteria = {c["id"]: c for c in score_all(build_bundle(bare))}
    for criterion_id in (
        "responsibility_stability",
        "god_component_risk",
        "component_balance",
        "modularity_trend",
        "cohesion_trend",
        "coupling_control",
        "recovery_confidence_trend",
        "change_containment",
        "evidence_confidence",
    ):
        assert criteria[criterion_id]["status"] == "not_run"
        assert criteria[criterion_id]["score"] is None


def test_unknown_component_sizes_are_not_run():
    data = copy.deepcopy(FULL)
    data["coverage"]["component_sizes_known"] = False
    criteria = {c["id"]: c for c in score_all(build_bundle(data))}
    assert criteria["god_component_risk"]["status"] == "not_run"
    assert criteria["component_balance"]["status"] == "not_run"
    assert criteria["evidence_confidence"]["score"] == 0.7


def test_parallel_scoring_is_deterministic_and_bundle_not_mutated():
    bundle = build_bundle(FULL)
    snapshot = copy.deepcopy(bundle)
    first = score_all(bundle)
    second = score_all(bundle)
    assert first == second
    assert bundle == snapshot
    assert bundle_hash(bundle) == bundle_hash(copy.deepcopy(bundle))


def test_engine_pack_carries_criteria_and_overall_without_changing_verdict():
    pack = evaluate(RECORD, FULL, evaluated_at=AT)
    assert pack["verdict"] == "PASS"
    assert len(pack["criteria"]) == 10
    assert pack["overall_score"] is not None
    assert pack["scoring"]["version"] == "scoring@1"
    assert pack["scoring"]["parallel_scorers"] == 10
    assert pack["scoring"]["llm_in_scoring"] is False
    assert pack["scoring"]["scoring_input_hash"]
    assert pack["architecture_summary"]["largest_component"] == {"name": "Billing", "entities": 7}
    again = evaluate(RECORD, copy.deepcopy(FULL), evaluated_at=AT)
    assert pack["hashes"] == again["hashes"]


def test_supplied_changes_feed_is_hashed_with_bundle():
    supplied = copy.deepcopy(FULL)
    supplied["changes"] = {"entities_added": 6, "entities_deleted": 25, "files_changed": 4, "raw": "diff --git a/x b/x"}
    supplied["architecture_summary"] = "Billing grows; Utils stable."
    pack = evaluate(RECORD, supplied, evaluated_at=AT)
    base_pack = evaluate(RECORD, FULL, evaluated_at=AT)
    assert pack["scoring"]["changes_source"] == "supplied"
    assert pack["scoring"]["scoring_input_hash"] != base_pack["scoring"]["scoring_input_hash"]


def test_render_comment_shows_criterion_table():
    pack = evaluate(RECORD, FULL, evaluated_at=AT)
    comment = render_comment(pack)
    assert "Criterion scores" in comment
    assert "`smell_regression`" in comment
    assert "`evidence_confidence`" in comment
    assert "overall" in comment
