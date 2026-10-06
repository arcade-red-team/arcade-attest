import asyncio
import copy
import json

import pytest

from arcade_attest import mcp_server, store
from arcade_attest.engine import evaluate, sha256_hex
from arcade_attest.mcp_server import _register, explain_evidence, get_verdict
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


def test_mcp_evaluate_tool_schema_is_typed_object_not_json_string():
    pytest.importorskip("mcp")
    tools = asyncio.run(_register().list_tools())
    tool = next(t for t in tools if t.name == "evaluate_decision")
    props = tool.inputSchema["properties"]
    assert "decision_record_json" not in props
    assert "decision_record" in props
    record_schema = tool.inputSchema["$defs"]["DecisionRecordInput"]
    assert record_schema["type"] == "object"
    assert set(record_schema["required"]) == {"id", "predicates"}
    predicate_schema = tool.inputSchema["$defs"]["PredicateInput"]
    assert predicate_schema["properties"]["type"]["enum"] == [
        "no_new_smells",
        "max_responsibility_shifts",
        "component_entity_cap",
    ]
    assert predicate_schema["properties"]["severity"]["enum"] == ["fail", "warn"]


def test_mcp_evaluate_tool_accepts_structured_record_and_preserves_hash(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    monkeypatch.setattr(store, "STORE_DIR", tmp_path)
    monkeypatch.setattr(mcp_server, "analyze_pair", lambda base, head, language="python": copy.deepcopy(DATA))
    record = {**RECORD, "status": "accepted"}  # extra field must survive: it is hashed
    result = asyncio.run(
        _register().call_tool(
            "evaluate_decision",
            {"base_path": "base", "head_path": "head", "decision_record": record},
        )
    )
    content = result[0] if isinstance(result, tuple) else result
    pack = json.loads(content[0].text)
    assert pack["verdict"] == "BLOCK"
    assert pack["hashes"]["decision_record_hash"] == sha256_hex(record)
