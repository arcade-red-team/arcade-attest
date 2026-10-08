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
purely predicate-driven. Admins weight the criteria through the Decision API
(`scoring.profile` / `scoring.weights` in the Decision Record, CLI
`--scoring-profile/--weights`, `GET /v1/scoring/profiles`, MCP
`list_scoring_profiles`): six template/appetite profiles (balanced, strict
gate, ship-fast, refactor-friendly, AI-agent gate, OSS maintainer) ship as
selection skills under [`skills/scoring/`](skills/scoring/), and
`"profile": "auto"` lets the engine suggest one deterministically from
context signals. Weighted overall only — verdicts never move with weights.

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

## GitHub Actions — Decision Gate without any direct LLM

ArcadeAttest can gate pull requests in GitHub Actions in two ways. Both run
the same deterministic engine, produce the same evidence pack, and post the
same PR comment. No LLM decides a verdict: `llm_in_verdict: false` in every
pack. A local model such as Jinfer may draft an explanation for reviewers,
but it must never turn into the gate.

### Option A (recommended): local Decision API workflow

This option starts the Decision API inside the GitHub Actions runner and
evaluates the actual PR base/head trees locally.

1. **Add a Decision Record to the consumer repo** at
   `.arcade-attest/decision-record.json`. Start from
   [`examples/github-actions/decision-record.example.json`](examples/github-actions/decision-record.example.json)
   and set `id`, `repo`, predicate thresholds, and scoring policy:

   - `no_new_smells` with `severity: "fail"` blocks a PR that introduces a
     new architecture smell.
   - `max_responsibility_shifts` with `params.max` warns or fails when too
     many entities move between components.
   - `component_entity_cap` with `params.max` warns or fails when a
     component grows into a god component.
   - `scoring.profile` chooses an appetite skill from
     [`skills/scoring/`](skills/scoring/), or `"auto"` plus
     `scoring.context.tags` lets the engine suggest one deterministically.
     Custom `scoring.weights` only change the advisory overall score; they
     never change PASS/WARN/BLOCK or a threshold.

2. **Copy the workflow** into the consumer repo:

   ```bash
   mkdir -p .github/workflows .arcade-attest
   cp examples/github-actions/decision-gate-local-api.yml \
     /path/to/consumer/.github/workflows/decision-gate.yml
   cp examples/github-actions/decision-record.example.json \
     /path/to/consumer/.arcade-attest/decision-record.json
   ```

   In the copied workflow's `env` block, set:

   - `DECISION_RECORD`: path to the record, normally
     `.arcade-attest/decision-record.json`.
   - `LANGUAGE`: the analyzed tree's primary language, for example
     `python` or `java`.
   - `ENFORCE_BLOCK`: `"true"` makes a BLOCK verdict fail the job;
     `"false"` keeps the gate advisory (comments and artifacts only).
   - `ATTEST_INSTALL`: the pinned ArcadeAttest install spec. Keep the commit
     SHA pinned and upgrade it deliberately. For a pinned Git install, pip
     extras must come before the `@`:

     ```bash
     pip install "arcade-attest[api] @ git+https://github.com/arcade-red-team/arcade-attest@<PINNED_SHA>"
     ```

     Writing `pip install "git+...@<SHA>[api]"` is a common typo: pip treats
     `[api]` as part of the Git revision and checkout fails.

   If the code to analyze is a subdirectory — for example
   `app/src/main/java` in a Java repo — change the *Evaluate* step so
   `base_path` and `head_path` point at that subdirectory in both trees.

3. **Give the workflow only the permissions it needs**:

   ```yaml
   permissions:
     contents: read
     pull-requests: write
   ```

   No secret is required. The API listens on `127.0.0.1` inside the runner;
   source code and evidence do not leave the job for the verdict.

4. **Open a pull request.** The workflow:

   - checks out full history (`fetch-depth: 0`) and materializes base/head
     trees from the real PR `base.sha` and `head.sha` (for `push`, it uses
     `before` and `after`), not `HEAD~1` from a shallow checkout;
   - installs the pinned ArcadeAttest and waits for `GET /health` from the
     local Decision API;
   - sends `POST /v1/decisions:evaluate` with the two trees, language, and
     Decision Record;
   - posts the rendered verdict and ten-criterion scorecard as a PR comment;
   - uploads `evidence-pack.json` as the `arcade-attest-evidence-pack`
     artifact; and
   - fails the job on BLOCK when `ENFORCE_BLOCK` is `"true"`.

5. **Read the verdict**:

   - `PASS`: no predicate triggered. Trend criteria at `0.5` mean no measured
     change, not failure.
   - `WARN`: a warning predicate triggered. The comment names the measured
     value, threshold, and evidence.
   - `BLOCK`: a fail predicate triggered. Follow the offending smells or
     components in the comment, or download the evidence-pack artifact for
     the full measurements, coverage warnings, hashes, and honest gaps.

   A criterion marked `not_run` means the evidence needed for that score was
   missing. It is never converted into a fake `0.0`.

6. **Change policy deliberately.** Thresholds, profiles, and weights live
   in the Decision Record, not in workflow prose. Change them in a separate
   PR with measured evidence from previous packs. Never lower a threshold
   on the same PR merely to make that PR pass.

### Option B: composite Action

If another workflow already creates before/after trees, use the composite
Action in [`action.yml`](action.yml):

```yaml
- uses: arcade-red-team/arcade-attest@<PINNED_SHA>
  with:
    record: .arcade-attest/decision-record.json
    base-path: ./before
    head-path: ./after
    language: python
    comment: "true"
```

Inputs are `record`, `base-path`, `head-path`, optional `language`, and
optional `comment`. Outputs are `verdict` and `pack`. The Action step exits
with code `2` on BLOCK, so the job fails without extra shell logic.

### Worked example and deeper reference

`tuannx/spring-boot-multi-region-ha` runs Option A on every PR with
`ADR-HA-001`, Java analysis over `app/src/main/java`, and blocking mode.
Calibration recorded before enabling it: main evaluated `PASS` with
overall score `0.8`; an injected god class evaluated `BLOCK`.

For the extended guide — Decision Record anatomy, scoring configuration,
result reproduction, and troubleshooting — see
[`docs/GITHUB-ACTIONS.md`](docs/GITHUB-ACTIONS.md). Example record:
[`examples/decision-record.json`](examples/decision-record.json).

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
