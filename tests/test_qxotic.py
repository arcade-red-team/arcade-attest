import json
import urllib.error

import pytest

from arcade_attest.qxotic import (
    DEFAULT_MODEL,
    QxoticError,
    build_explanation_prompt,
    explain_pack,
    render_explanation_section,
)

PACK = {
    "decision_id": "ADR-TEST-001",
    "repo": "owner/repo",
    "verdict": "BLOCK",
    "overall_score": 0.5,
    "measured": {"smells_new": 2, "responsibility_shifts": 3, "largest_component": {"name": "Core", "entities": 42}},
    "predicates": [
        {"type": "no_new_smells", "status": "triggered", "severity": "fail", "measured": 2},
        {"type": "component_entity_cap", "status": "ok", "severity": "warn", "measured": 42},
    ],
    "criteria": [
        {"id": "smell_regression", "status": "scored", "score": 0.4},
        {"id": "modularity_trend", "status": "not_run", "score": None},
    ],
    "scoring": {"not_run": ["modularity_trend"]},
    "coverage": {"warnings": ["example warning"]},
}


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return json.dumps(self._body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_prompt_carries_only_measured_facts():
    prompt = build_explanation_prompt(PACK)
    assert "Verdict (final, deterministic): BLOCK" in prompt
    assert "new smells=2" in prompt
    assert "smell_regression=0.4" in prompt
    assert "modularity_trend" in prompt
    assert "example warning" in prompt


def test_explain_pack_posts_openai_shape_and_returns_text():
    captured = {}

    def opener(request, timeout=None):
        if request.full_url.endswith("/v1/models"):
            return FakeResponse({"data": [{"id": DEFAULT_MODEL}]})
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        return FakeResponse({"choices": [{"message": {"content": "  Blocked: two new smells.  "}}]})

    text = explain_pack(PACK, opener=opener)
    assert text == "Blocked: two new smells."
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["payload"]["model"] == DEFAULT_MODEL
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["seed"] == 42


def test_explain_pack_unreachable_raises_qxotic_error():
    def opener(request, timeout=None):
        raise urllib.error.URLError("refused")

    with pytest.raises(QxoticError):
        explain_pack(PACK, opener=opener)


def test_explain_pack_bad_shape_raises_qxotic_error():
    def opener(request, timeout=None):
        return FakeResponse({"unexpected": True})

    with pytest.raises(QxoticError):
        explain_pack(PACK, opener=opener)


def test_rendered_section_labels_draft_and_verdict_boundary():
    section = render_explanation_section(PACK, "Some explanation.", model="m")
    assert "Local AI explanation (draft)" in section
    assert "llm_in_verdict: false" in section
    assert "**BLOCK**" in section
    assert "qxoticai/qxotic" in section
