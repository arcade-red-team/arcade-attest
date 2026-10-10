# Changelog

All notable changes are recorded here. Every claim maps to evidence:
a test name, an artifact field, or a commit SHA (red-team doctrine).

## 0.2.0 — 2026-10-10

Upgrade release. Verdict engine unchanged: still a pure function,
`llm_in_verdict: false` in every pack, one machine-readable
`PASS | WARN | BLOCK` per gate.

- **Dependency:** `arcade-agent` 0.3.0 → `>=0.4.1,<0.5` (PyPI 0.4.1,
  verified 2026-10-10). `requires-python` `>=3.11` → `>=3.12` to match
  arcade-agent 0.4.1. Evidence: full pipeline on the synthetic-smells
  corpus — Case 1 PASS (`att_bbb0acf688e08bf1`), Case 2 BLOCK with
  2 new smells, CLI exit 2; `scripts/dogfood.sh` verdict `pass`
  (pytest + demo-pass + demo-block + determinism, evidence_hash
  `61b71a5a3ce40ee4d328be40e17e07c951e6789a19dce9784fbabd38f136342a`).
- **MCP:** `evaluate_decision` now takes a typed Decision Record
  object (Pydantic `DecisionRecordInput` / `PredicateInput`), not a
  JSON string; `get_verdict` / `explain_evidence` return objects, not
  JSON text. Hash parity with CLI/API is preserved
  (`model_dump(exclude_unset=True)`, `extra="allow"`).
  Evidence: `test_mcp_evaluate_tool_schema_is_typed_object_not_json_string`,
  `test_mcp_evaluate_tool_accepts_structured_record_and_preserves_hash`.
- **API:** `GET /health` now reports `version`; the FastAPI app version
  reads `arcade_attest.__version__` instead of a second hardcoded copy.
- **Gate template:** `examples/github-actions/decision-gate-local-api.yml`
  pin bumped `351a972` → `a3595bc` (current main, Qxotic #16) with the
  corrected VCS extras syntax (`arcade-attest[api] @ git+...@SHA`).
  Supersedes the conflicting PR #14.
- **Disclosure:** pre-existing-code disclosure updated to arcade-agent
  0.4.1 at github.com/arcade-agent/arcade-agent (README,
  RULES-VERIFIED.md, adapter docstring).

Tests: 39 → 41 passed (`pytest -q`), dogfood verdict `pass`.

## 0.1.0 — 2026-10-04

Initial Decision API MVP for the Crypto World's Fair window:
3-predicate engine, `scoring@1` ten-criterion scorecard with admin
weight profiles, CLI / FastAPI / MCP surfaces, GitHub Action gate,
EAS attestation payload (D3 submission awaits the owner's testnet
wallet), Qxotic Jinfer draft-only explanations.
