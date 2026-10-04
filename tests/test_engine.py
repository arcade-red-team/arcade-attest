import json

import pytest

from arcade_attest.engine import evaluate, sha256_hex, validate_record

AT = "2026-10-04T00:00:00Z"

RECORD = {
    "id": "ADR-TEST",
    "repo": "example/test",
    "version": 1,
    "mode": "advisory",
    "predicates": [
        {"type": "no_new_smells", "severity": "fail"},
        {"type": "max_responsibility_shifts", "params": {"max": 2}, "severity": "warn"},
        {"type": "component_entity_cap", "params": {"max": 20}, "severity": "warn"},
    ],
}

CLEAN = {
    "smells_new": [],
    "responsibility_shifts": [],
    "components": [{"name": "core", "entities": 12}],
    "summary": {"entities_a": 30, "entities_b": 32},
    "coverage": {"entities_a": 30, "entities_b": 32, "warnings": []},
    "refs": {"a": "base", "b": "head"},
}


def test_clean_change_passes():
    pack = evaluate(RECORD, CLEAN, evaluated_at=AT)
    assert pack["verdict"] == "PASS"
    assert pack["verdict_code"] == 0
    assert all(p["status"] == "pass" for p in pack["predicates"])


def test_new_smell_blocks():
    data = {**CLEAN, "smells_new": [{"smell_type": "cycle", "affected_components": ["a", "b"]}]}
    pack = evaluate(RECORD, data, evaluated_at=AT)
    assert pack["verdict"] == "BLOCK"
    assert pack["verdict_code"] == 2


def test_warn_only_escalates_to_warn():
    data = {**CLEAN, "responsibility_shifts": [{"entity": "x"}, {"entity": "y"}, {"entity": "z"}]}
    pack = evaluate(RECORD, data, evaluated_at=AT)
    assert pack["verdict"] == "WARN"


def test_component_cap_reports_offender():
    data = {**CLEAN, "components": [{"name": "god", "entities": 307}]}
    pack = evaluate(RECORD, data, evaluated_at=AT)
    cap = next(p for p in pack["predicates"] if p["type"] == "component_entity_cap")
    assert cap["status"] == "triggered"
    assert cap["evidence"] == [{"component": "god", "entities": 307}]


def test_hashes_are_deterministic_for_same_inputs():
    first = evaluate(RECORD, CLEAN, evaluated_at=AT)
    second = evaluate(RECORD, CLEAN, evaluated_at=AT)
    assert first["hashes"] == second["hashes"]
    assert first["id"] == second["id"]
    assert sha256_hex(RECORD) == first["hashes"]["decision_record_hash"]


def test_zero_entity_head_adds_false_pass_warning():
    data = {**CLEAN, "coverage": {"entities_a": 30, "entities_b": 0, "warnings": []}}
    pack = evaluate(RECORD, data, evaluated_at=AT)
    assert any("false PASS" in w for w in pack["coverage"]["warnings"])


def test_invalid_records_rejected():
    with pytest.raises(ValueError):
        validate_record({"id": "X", "predicates": [{"type": "deny_dependency", "severity": "fail"}]})
    with pytest.raises(ValueError):
        validate_record({"id": "X", "predicates": [{"type": "max_responsibility_shifts", "severity": "warn"}]})
    with pytest.raises(ValueError):
        validate_record({"predicates": [{"type": "no_new_smells"}]})


def test_evidence_pack_is_json_serializable():
    pack = evaluate(RECORD, CLEAN, evaluated_at=AT)
    json.dumps(pack)


def test_unknown_component_sizes_warn_cap_cannot_trigger():
    from arcade_attest.adapter import normalize_changelog

    data = normalize_changelog({"smells": {"new": []}, "summary": {"entities_a": 5, "entities_b": 6}})
    assert data["coverage"]["component_sizes_known"] is False
    pack = evaluate(RECORD, {**data, "coverage": {**data["coverage"], "entities_b": 6}}, evaluated_at=AT)
    assert any("component_entity_cap cannot trigger" in w for w in pack["coverage"]["warnings"])
