import json

from arcade_attest import store
from arcade_attest.engine import evaluate
from arcade_attest.mcp_server import explain_evidence, get_verdict
from arcade_attest.render import render_comment

RECORD = {
    "id": "ADR-MCP",
    "repo": "example/mcp",
    "version": 1,
    "mode": "blocking",
    "predicates": [{"type": "no_new_smells", "severity": "fail"}],
}
DATA = {
    "smells_new": [{"smell_type": "cycle", "affected_components": ["a", "b"]}],
    "responsibility_shifts": [],
    "components": [{"name": "a", "entities": 3}],
    "summary": {"entities_a": 3, "entities_b": 4},
    "coverage": {"entities_a": 3, "entities_b": 4, "warnings": []},
    "refs": {"a": "x", "b": "y"},
}


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_DIR", tmp_path)
    pack = evaluate(RECORD, DATA, evaluated_at="2026-10-04T00:00:00Z")
    store.write_pack(pack)
    return pack


def test_store_roundtrip_and_explain(tmp_path, monkeypatch):
    pack = _seed(tmp_path, monkeypatch)
    fetched = get_verdict(pack["id"])
    assert fetched["verdict"] == "BLOCK"
    explanation = explain_evidence(pack["id"])
    assert explanation["triggered"][0]["type"] == "no_new_smells"
    assert explanation["attestation_payload"]["data"]["verdict"] == 2


def test_missing_verdict_is_error_object(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_DIR", tmp_path)
    assert get_verdict("att_missing")["error"] == "decision not found"


def test_render_comment_is_template_from_pack(tmp_path, monkeypatch):
    pack = _seed(tmp_path, monkeypatch)
    comment = render_comment(pack)
    assert "BLOCK" in comment
    assert pack["id"] in comment
    assert "no_new_smells" in comment
    json.dumps(pack)  # pack stays JSON-serializable
