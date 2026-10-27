# GitHub Actions guide — ArcadeAttest Decision Gate

Two ways to gate a pull request with ArcadeAttest in GitHub Actions. Both
produce the same deterministic verdict (`PASS | WARN | BLOCK`), the same
evidence pack, and the same PR comment. **No LLM participates in either
verdict** (`llm_in_verdict: false` in every pack); a local model may draft
an explanation of the pack, but it never decides.

| | A. Local Decision API workflow (recommended) | B. Composite Action |
|---|---|---|---|
| File | [`examples/github-actions/decision-gate-local-api.yml`](../examples/github-actions/decision-gate-local-api.yml) copied into your repo | [`action.yml`](../action.yml) in this repo, referenced with `uses:` |
| How it evaluates | Starts `arcade-attest serve` inside the runner and POSTs the PR's base/head source trees to `127.0.0.1` | Runs the `arcade-attest evaluate` CLI directly |
| Base/head trees | Materialized from the real PR `base.sha` / `head.sha` (push: `before` / `after`) | You check out or build the two trees yourself |
| Best for | Drop-in gate for any repo, API-shaped integration | Workflows that already produce before/after trees |

## Option A — Local Decision API workflow

### 1. Add the Decision Record

Create `.arcade-attest/decision-record.json` in your repo (starter:
[`examples/github-actions/decision-record.example.json`](../examples/github-actions/decision-record.example.json)):

```json
{
  "id": "ADR-YOUR-REPO-001",
  "repo": "owner/repo",
  "version": 1,
  "status": "accepted",
  "mode": "blocking",
  "predicates": [
    {"type": "no_new_smells", "severity": "fail"},
    {"type": "max_responsibility_shifts", "params": {"max": 25}, "severity": "warn"},
    {"type": "component_entity_cap", "params": {"max": 400}, "severity": "warn"}
  ],
  "scoring": {"profile": "auto", "context": {"tags": []}}
}
```

Predicate reference:

- `no_new_smells` (`severity: fail` by default) — BLOCK when the change
  introduces a new architecture smell. Optional `params.kinds` filters by
  smell kind.
- `max_responsibility_shifts` (`params.max`) — WARN/FAIL when more than
  `max` entities move between components.
- `component_entity_cap` (`params.max`, optional `params.component`) —
  WARN/FAIL when a component grows past `max` entities (anti god-module).

`severity: fail` produces BLOCK; `severity: warn` produces WARN. Threshold
changes are policy changes: make them in their own PR with measured
evidence, never silently tuned to make a red gate green.

The `scoring` block configures the advisory ten-criterion scorecard
(`scoring@1`): `profile` is one of the appetite skills in
[`skills/scoring/`](../skills/scoring/) (`balanced`, `strict_gate`,
`ship_fast`, `refactor_friendly`, `ai_agent_code_gate`, `oss_maintainer`),
`"auto"` to let the engine suggest one deterministically from
`context.tags`, or omit it for `balanced`. Custom `weights` override the
profile per criterion. Weights move `overall_score` only — never the
verdict, never a threshold. A criterion without evidence is reported
`not_run`, never scored 0.

### 2. Add the workflow

Copy `examples/github-actions/decision-gate-local-api.yml` to
`.github/workflows/decision-gate.yml`, then adjust the `env` block:

- `DECISION_RECORD` — path to the record from step 1.
- `LANGUAGE` — primary language of the analyzed source tree (`python`,
  `java`, …).
- `ENFORCE_BLOCK` — `"true"` fails the job on BLOCK; `"false"` reports
  advisory comments only.
- `ATTEST_INSTALL` — pinned ArcadeAttest install spec. Keep it pinned to a
  commit SHA and bump it deliberately. For VCS installs, pip extras go
  **before** the `@`:

  ```bash
  pip install "arcade-attest[api] @ git+https://github.com/arcade-red-team/arcade-attest@<SHA>"
  ```

  (`pip install "git+...@<SHA>[api]"` is a common typo: pip parses `[api]`
  as part of the revision and the checkout fails.)

If the source tree to analyze is a subdirectory (for example a Java repo
whose code lives in `app/src/main/java`), point `base_path` / `head_path`
in the *Evaluate* step at that subdirectory of both trees.

### 3. Permissions

The workflow needs:

```yaml
permissions:
  contents: read
  pull-requests: write   # to post the verdict comment
```

No secrets are required. The Decision API runs on `127.0.0.1` inside the
runner; nothing is sent to a third-party service.

### 4. What runs on each PR

1. Checkout with `fetch-depth: 0` and materialize the base/head trees from
   the actual PR SHAs (not `HEAD~1` on a shallow checkout).
2. Install the pinned ArcadeAttest and start the local Decision API;
   the job waits for `GET /health`.
3. `POST /v1/decisions:evaluate` with `{repo, base_path, head_path,
   language, decision_record}`. arcade-agent analyzes both trees; the
   deterministic engine returns the evidence pack.
4. The pack is rendered as a PR comment (verdict, predicate table,
   ten-criterion scorecard with weights) and uploaded as the
   `arcade-attest-evidence-pack` artifact.
5. `BLOCK` + `ENFORCE_BLOCK: "true"` fails the job.

### 5. Reading the result

- **PASS** — no predicate triggered. The scorecard still shows trends
  (a trend criterion at `0.5` means “no measured change”).
- **WARN** — a `warn`-severity predicate triggered. Review the evidence;
  the job does not fail unless you map WARN to failure yourself.
- **BLOCK** — a `fail`-severity predicate triggered. The comment lists the
  exact smells/components that tripped it; the artifact carries the full
  pack with `hashes.evidence_hash` for reproduction:
  `arcade-attest from-changelog` / `evaluate` with the same record and
  trees reproduces the same hash.

## Option B — Composite Action

When your workflow already produces before/after trees, call the Action
directly:

```yaml
jobs:
  gate:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      # ... produce ./before and ./after trees for the change ...
      - uses: arcade-red-team/arcade-attest@<PINNED_SHA>
        with:
          record: .arcade-attest/decision-record.json
          base-path: ./before
          head-path: ./after
          language: python        # optional, default python
          comment: "true"         # optional, default true
```

Outputs: `verdict` (`PASS`/`WARN`/`BLOCK`) and `pack` (path to the evidence
pack JSON). The step exits non-zero on BLOCK (CLI exit code 2), so the job
fails without extra wiring.

## Worked example

`tuannx/spring-boot-multi-region-ha` runs Option A in production
(`.github/workflows/decision-gate.yml`, record `ADR-HA-001`, language
`java`, tree `app/src/main/java`, mode `blocking`, profile `auto` →
`strict_gate`). Calibration before enabling: main evaluated `PASS 0.8`
(319 entities); a negative control (an injected 60-field/60-method god
class) evaluated `BLOCK` with `smell_regression` 0.4.

## Troubleshooting

- **Install step fails at `git checkout '<SHA>[api]'`** — pip extras typo;
  use `"arcade-attest[api] @ git+...@<SHA>"` (see step 2).
- **`component_entity_cap` never triggers** — the input was changelog-only
  without component sizes; the pack says `component_sizes_known: false`
  and warns. Evaluate source trees (both options above do) for sizes.
- **Verdict PASS but `entities_b: 0`** — parser blind spot on the head
  tree; the pack warns this may be a false PASS. Check `coverage` before
  trusting the gate on a new language/layout.
- **Scorecard criteria `not_run`** — the changelog lacks the metric or
  coverage that criterion needs. That is reported, not zero-filled; feed
  full source trees to score all ten.
- **Gate too strict/lenient** — thresholds are starting guesses. Change
  them in the Decision Record with evidence from past packs, in a separate
  PR; never lower a threshold to silence a finding on the PR that tripped it.
