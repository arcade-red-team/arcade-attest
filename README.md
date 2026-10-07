# ArcadeAttest — Decision API for software architecture

**Attest is a receipt. Decision API is a gate.**

ArcadeAttest turns architecture decisions (ADRs) into machine-checkable policy.
You register a **Decision Record** with deterministic predicates; every change
is analyzed with [arcade-agent](https://github.com/tuannx/arcade-agent) and the
API returns a verdict — **PASS / WARN / BLOCK** — plus a signed-evidence pack
whose hash is anchored as an [EAS](https://attest.org) attestation on Base.
CI, a DAO, an agent, or a contract can then ask one question before merging or
paying: *did this change break the architecture we agreed on?*

No LLM ever participates in a verdict. LLMs may help draft Decision Records;
humans approve them; the engine is a pure function.

## Why this does not exist yet

Public neighbours verify wallets (Kyro), RWA compliance (ZKCG), agent decision
traces (Ledgerline), or smart-contract security (AuditAI). None of them
evaluate **software architecture predicates** — new architecture smells,
responsibility shifts between components, god-module growth — against a
registered decision. That is the gap ArcadeAttest fills.

## MVP (this repo, D1–D2)

Pipeline: `register → baseline → evaluate → verdict → evidence pack`

Predicates (each maps 1:1 to a `changelog_architecture` field):

| Predicate | Reads | Meaning |
|---|---|---|
| `no_new_smells` | `smells.new` | the change introduces no new architecture smells (optionally filtered by kind) |
| `max_responsibility_shifts` | `responsibility_shifts` | at most N entities change component |
| `component_entity_cap` | component entity counts | no component grows past N entities (anti god-module) |

Alongside the verdict, every pack carries a **ten-criterion scorecard**
(`scoring@1`, see [`SCORING-10-CRITERIA.md`](SCORING-10-CRITERIA.md)): ten pure
scorers run in parallel over one bundle (full changelog + changes +
architecture summary) and each returns a **0.0–1.0 score in 0.1 steps** —
smell regression, responsibility stability, god-component risk, component
balance, modularity / cohesion / coupling / RCI trends, change containment,
and evidence confidence. A criterion without evidence is `not_run`, never a
fabricated 0. Scores are advisory; the PASS/WARN/BLOCK verdict above stays
purely predicate-driven.

Every verdict ships an **evidence pack**: per-predicate measurements, the exact
offending smells/components, parser-coverage warnings, a SHA-256
`decision_record_hash` and a deterministic `evidence_hash`, and an honest list
of known gaps. `arcade-attest payload` renders the EAS attestation payload
(schema in `src/arcade_attest/anchor.py`); submitting it on Base Sepolia is
D3–D4 scope.

## Quickstart

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[api,dev]"
pytest

# Deterministic check over an existing changelog JSON:
arcade-attest from-changelog \
  --changelog path/to/summary.json \
  --record examples/decision-record.json

# Full pipeline over two source trees (uses arcade-agent):
arcade-attest evaluate \
  --base path/to/before --head path/to/after \
  --record examples/decision-record.json --out evidence.json

# HTTP API:
arcade-attest serve --port 8787
curl -X POST localhost:8787/v1/decisions:evaluate \
  -H 'content-type: application/json' \
  -d '{"base_path":"...","head_path":"...","decision_record":{...}}'
```

Exit code is `2` when the verdict is BLOCK, so the CLI drops straight into CI.

Example Decision Record: [`examples/decision-record.json`](examples/decision-record.json).

## Pre-existing code disclosure (required, and true)

- The analyzer is **arcade-agent** (MIT, PyPI `arcade-agent` 0.3.0,
  github.com/tuannx/arcade-agent), a pre-existing open-source project by the
  same author. ArcadeAttest consumes its published `changelog_architecture`
  output as a library; it does not claim that work as new.
- Everything else in this repository — the Decision Record engine, evidence
  pack format, CLI/HTTP surface, EAS payload — was written for the Crypto
  World's Fair window. Commit history starts 2026-10-04.
- Demo corpora come from `tuannx/arcade-agent-examples` (also pre-existing,
  public) and are labelled as such wherever used.

## Honest gaps (also printed inside every evidence pack)

- No edge-level diff yet → `deny_dependency` is designed but **not** in the MVP.
- Parser blind spots (e.g. files declaring no entities) can make a component
  look empty → false-PASS risk. Coverage and warnings ship with every pack.
- Thresholds are starting guesses; calibrating them needs per-repo history.
- The chain proves a verdict existed, unchanged, at a time — not that the
  verdict is objectively correct.

## Roadmap inside the window

- D3–D4: register the EAS schema on Base Sepolia, attest on evaluate, verify page. *(script ready: `scripts/eas_attest.py`, dry-run verified; on-chain execution awaits the owner's testnet wallet — issue #1. Verify page shipped: `docs/verify.html`.)*
- D5–D6: dashboard — paste repo/PR → verdict + evidence + on-chain link.
- D7: GitHub Action gate + MCP tools. *(done: `action.yml` composite gate; MCP `evaluate_decision`, `get_verdict`, `explain_evidence` via `python -m arcade_attest.mcp_server`.)*
- D8–D9: pitch + demo video (≤ 3 min).
- D10: submit early. Rules verification: [`RULES-VERIFIED.md`](RULES-VERIFIED.md).

## License

MIT (this repository). arcade-agent is MIT as well.
