import copy
import json
from pathlib import Path

import pytest

from arcade_attest.engine import evaluate, validate_record
from arcade_attest.render import render_comment
from arcade_attest.scoring import (
    CRITERION_IDS,
    list_profiles,
    overall_score,
    resolve_weights,
    suggest_profile,
)

AT = "2026-10-04T00:00:00Z"
RECORD = {
    "id": "ADR-WEIGHTS",
    "repo": "example/weights",
    "version": 1,
    "mode": "advisory",
    "predicates": [{"type": "no_new_smells", "severity": "fail"}],
}
FULL = {
    "smells_new": [],
    "responsibility_shifts": [],
    "components": [
        {"name": "Auth", "entities": 3},
        {"name": "Billing", "entities": 7},
        {"name": "Utils", "entities": 4},
    ],
    "summary": {"entities_a": 20, "entities_b": 14, "entities_added": 2, "entities_deleted": 2},
    "metrics": {
        "TurboMQ": {"a": 1.0, "b": 1.5, "delta": 0.5},
        "IntraConnectivity": {"a": 0.1, "b": 0.1, "delta": 0.0},
        "InterConnectivity": {"a": 0.2, "b": 0.2, "delta": 0.0},
        "TwoWayPairRatio": {"a": 0.0, "b": 0.0, "delta": 0.0},
        "RCI": {"a": 0.3, "b": 0.3, "delta": 0.0},
    },
    "coverage": {"entities_a": 20, "entities_b": 14, "languages_b": ["python"], "component_sizes_known": True, "warnings": []},
    "refs": {"a": "base", "b": "head"},
}


def test_default_profile_is_balanced_equal_weights():
    pack = evaluate(RECORD, FULL, evaluated_at=AT)
    assert pack["scoring"]["profile"]["id"] == "balanced"
    assert pack["scoring"]["config_source"] == "default"
    assert all(c["weight"] == 1.0 for c in pack["criteria"])
    assert pack["overall_score"] == overall_score(pack["criteria"])


def test_preset_profile_changes_weighted_overall_but_not_verdict():
    record = {**RECORD, "scoring": {"profile": "strict_gate"}}
    pack = evaluate(record, FULL, evaluated_at=AT)
    assert pack["verdict"] == "PASS"
    assert pack["scoring"]["profile"]["id"] == "strict_gate"
    assert pack["scoring"]["config_source"] == "preset"
    weights = {c["id"]: c["weight"] for c in pack["criteria"]}
    assert weights["smell_regression"] == 3.0
    assert weights["coupling_control"] == 2.5
    assert pack["overall_score"] == overall_score(pack["criteria"], pack["scoring"]["weights"])


def test_custom_weights_override_profile_and_are_reported():
    record = {**RECORD, "scoring": {"profile": "balanced", "weights": {"smell_regression": 0.0, "coupling_control": 3.0}}}
    pack = evaluate(record, FULL, evaluated_at=AT)
    assert pack["scoring"]["config_source"] == "preset+custom_weights"
    by_id = {c["id"]: c for c in pack["criteria"]}
    assert by_id["smell_regression"]["weight"] == 0.0
    assert by_id["coupling_control"]["weight"] == 3.0
    # A 0-weight criterion is excluded from the weighted mean.
    effective = pack["scoring"]["effective_weights"]
    assert "smell_regression" not in effective


def test_auto_profile_suggests_from_context_signals_and_records_rule():
    cases = [
        ({"tags": ["ai-agent"]}, "advisory", "ai_agent_code_gate", "signal:ai-agent-code"),
        ({"change_kind": "migration"}, "advisory", "refactor_friendly", "signal:refactor-or-migration"),
        ({"tags": ["maintainer"]}, "advisory", "oss_maintainer", "signal:oss-maintainer-triage"),
        ({"tags": ["startup"]}, "advisory", "ship_fast", "signal:ship-fast"),
        ({}, "blocking", "strict_gate", "signal:blocking-or-high-risk"),
        ({}, "advisory", "balanced", "default:balanced"),
    ]
    for context, mode, profile_id, rule in cases:
        assert suggest_profile(context, mode=mode) == (profile_id, rule)
        record = {**RECORD, "mode": mode, "scoring": {"profile": "auto", "context": context}}
        pack = evaluate(record, FULL, evaluated_at=AT)
        assert pack["scoring"]["profile"]["id"] == profile_id
        assert pack["scoring"]["suggestion_rule"] == rule
        assert pack["scoring"]["config_source"].startswith("auto")


def test_weight_config_does_not_change_predicate_verdict():
    blocked = {**FULL, "smells_new": [{"smell_type": "Dependency Cycle", "severity": "high", "affected_components": ["A", "B"]}]}
    for profile in [p["id"] for p in list_profiles()]:
        pack = evaluate({**RECORD, "scoring": {"profile": profile}}, blocked, evaluated_at=AT)
        assert pack["verdict"] == "BLOCK"


def test_invalid_scoring_configs_are_rejected():
    bad_records = [
        {**RECORD, "scoring": {"profile": "nope"}},
        {**RECORD, "scoring": {"weights": {"unknown_criterion": 1.0}}},
        {**RECORD, "scoring": {"weights": {"smell_regression": -1.0}}},
        {**RECORD, "scoring": {"weights": {"smell_regression": 0.0}}},
        {**RECORD, "scoring": {"bogus": 1}},
        {**RECORD, "scoring": {"context": {"tags": "ai-agent"}}},
    ]
    for record in bad_records:
        with pytest.raises(ValueError):
            validate_record(record)


def test_resolved_weights_are_normalized_and_complete():
    resolved = resolve_weights({**RECORD, "scoring": {"profile": "ai_agent_code_gate"}})
    assert set(resolved["weights"]) == set(CRITERION_IDS)
    assert abs(sum(resolved["normalized_weights"].values()) - 1.0) < 0.01
    assert resolved["profile"]["skill"] == "skills/scoring/ai_agent_code_gate.json"


def test_scoring_skills_match_registry():
    root = Path(__file__).resolve().parents[1] / "skills" / "scoring"
    assert (root / "SKILL.md").exists()
    manifests = {}
    for path in root.glob("*.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests[manifest["id"]] = manifest
    profiles = {p["id"]: p for p in list_profiles()}
    assert set(manifests) == set(profiles)
    for profile_id, profile in profiles.items():
        assert manifests[profile_id]["weights"] == profile["weights"]
        assert manifests[profile_id]["appetite"] == profile["appetite"]
        assert manifests[profile_id]["how_to_apply"]["value"] == profile_id


def test_render_comment_shows_profile_and_weights():
    pack = evaluate({**RECORD, "scoring": {"profile": "strict_gate"}}, FULL, evaluated_at=AT)
    comment = render_comment(pack)
    assert "profile `strict_gate`" in comment
    assert "| Weight |" in comment
    assert "overall (weighted)" in comment


def test_api_lists_scoring_profiles():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from arcade_attest.api import app

    response = TestClient(app).get("/v1/scoring/profiles")
    assert response.status_code == 200
    body = response.json()
    assert body["default"] == "balanced"
    assert {p["id"] for p in body["profiles"]} >= {"balanced", "strict_gate", "ai_agent_code_gate"}


def test_mcp_lists_scoring_profiles():
    from arcade_attest.mcp_server import list_scoring_profiles

    body = list_scoring_profiles()
    assert body["version"] == "scoring@1"
    assert len(body["profiles"]) == 6


def test_cli_scoring_profiles_and_weight_overrides(tmp_path, capsys):
    import json as json_lib

    from arcade_attest import cli

    assert cli.main(["scoring-profiles"]) == 0
    payload = json_lib.loads(capsys.readouterr().out)
    assert payload["default"] == "balanced"
    assert len(payload["profiles"]) == 6

    changelog = tmp_path / "changelog.json"
    changelog.write_text(json_lib.dumps({
        "smells": {"new": []}, "responsibility_shifts": [],
        "summary": {"entities_a": 20, "entities_b": 14, "entities_added": 2, "entities_deleted": 2},
        "metrics": FULL["metrics"],
    }), encoding="utf-8")
    record = tmp_path / "record.json"
    record.write_text(json_lib.dumps(RECORD), encoding="utf-8")
    weights = tmp_path / "weights.json"
    weights.write_text(json_lib.dumps({"coupling_control": 5.0}), encoding="utf-8")
    out = tmp_path / "pack.json"
    code = cli.main([
        "from-changelog", "--changelog", str(changelog), "--record", str(record),
        "--evaluated-at", AT, "--scoring-profile", "strict_gate",
        "--weights", str(weights), "--out", str(out),
    ])
    assert code == 0
    pack = json_lib.loads(out.read_text(encoding="utf-8"))
    assert pack["scoring"]["profile"]["id"] == "strict_gate"
    assert pack["scoring"]["weights"]["coupling_control"] == 5.0
    assert "custom_weights" in pack["scoring"]["config_source"]


def test_weighted_evaluation_is_deterministic():
    record = {**RECORD, "scoring": {"profile": "auto", "context": {"tags": ["ai-agent"]}}}
    first = evaluate(record, copy.deepcopy(FULL), evaluated_at=AT)
    second = evaluate(record, copy.deepcopy(FULL), evaluated_at=AT)
    assert first["hashes"] == second["hashes"]
    assert first["overall_score"] == second["overall_score"]
