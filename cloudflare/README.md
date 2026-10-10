# ArcadeAttest Decision API — Cloudflare Workers

Cloudflare surface for the Decision API. It mirrors the FastAPI contract
(`src/arcade_attest/api.py`) where the edge can, and keeps the same
deterministic engine semantics: one machine-readable verdict
(`PASS | WARN | BLOCK`), every claim mapped to evidence, no LLM in the
verdict or the scores.

Docs cross-checked 2026-10-07 against developers.cloudflare.com (Workers
configuration, Workers KV bindings, Python Workers package support).

## Why changelog-in, not source-trees-in

The Python API evaluates two source trees with arcade-agent
(`ingest → parse (tree-sitter) → recover → detect_smells → metrics`).
arcade-agent depends on native packages (`tree-sitter`, `numpy`, `scipy`),
and Python Workers only run pure-Python or PyEmscripten wheels in an
isolate with no functioning threading and an ephemeral filesystem — so
source analysis cannot run on the edge today. The Worker therefore
evaluates the **changelog** arcade-agent produces in CI, locally, or in
the GitHub Action, and rejects `base_path`/`head_path` with that boundary
explained (HTTP 422).

## Endpoints

| Method | Path | Body / result |
|---|---|---|
| GET | `/health` | `{ok, service, runtime: "cloudflare-workers", llm_in_verdict: false}` |
| GET | `/v1/scoring/profiles` | the 6 appetite profiles (same registry as `skills/scoring/*.json`) |
| POST | `/v1/decisions:evaluate` | `{decision_record, changelog}` or `{decision_record, data}` (+ optional `evaluated_at`) → evidence pack, stored in KV |
| GET | `/v1/decisions/{id}` | stored evidence pack |
| GET | `/v1/decisions/{id}/comment` | rendered PR comment (Markdown) |
| GET | `/v1/decisions/{id}/attestation-payload` | EAS payload shape (status `not_submitted`) |
| GET | `/v1/repos/{owner}/{repo}/latest-verdict` | latest stored pack for the repo |

`data` is normalized engine input (`smells_new`, `responsibility_shifts`,
`components`, `summary`, `metrics`, `coverage`); `changelog` is raw
`changelog_architecture` output and is normalized the same way the Python
adapter does (component sizes unknown → `component_entity_cap` cannot
trigger and the pack says so).

Scoring config works exactly like the Decision API: the Decision Record
may carry `scoring: {profile, weights, context}`; `"profile": "auto"`
suggests a profile deterministically from context signals and records the
`suggestion_rule`. Weights move the advisory `overall_score` only — never
the predicate verdict, never a threshold.

## Parity and determinism

- `src/scoring.js` / `src/engine.js` are ports of the Python engine.
- `test/golden.json` is generated from the Python engine; the Node tests
  assert identical verdicts, predicate results, criterion scores/weights,
  overall scores, and profile selection for every golden case.
- Same record + data + `evaluated_at` → same `evidence_hash` on every
  Workers run (JS-canonical JSON + SHA-256). Cross-runtime hash equality
  with the Python engine is **not** claimed: JSON number formatting
  differs between runtimes, so a pack's hash is authoritative within the
  surface that produced it.

## Run locally

```bash
cd cloudflare
npm test                       # Node tests incl. Python-parity golden cases
npx wrangler deploy --dry-run  # bundle check (37 KiB at time of writing)
npx wrangler dev               # http://localhost:8787 (KV is local-simulated)
```

## Deploy (owner step)

The agent holds no Cloudflare credentials; deploy is the owner's tap,
following the same pattern as Tony's other Workers repos:

```bash
cd cloudflare
npx wrangler kv namespace create arcade-attest-decisions
npx wrangler kv namespace create arcade-attest-decisions --preview
# put the returned ids into wrangler.jsonc (replace the PLACEHOLDER ids)
npx wrangler secret put API_TOKEN   # optional but recommended: bearer auth on POST
npx wrangler deploy
```

Or wire the repo's GitHub Actions to deploy with `CLOUDFLARE_API_TOKEN` +
`CLOUDFLARE_ACCOUNT_ID` secrets, as in tube2notes/OmniCal.

Until KV ids are provisioned, `wrangler.jsonc` keeps explicit
`PLACEHOLDER_KV_NAMESPACE_ID` / `PLACEHOLDER_KV_PREVIEW_ID` values; the
Worker falls back to in-memory storage only when the binding is absent
(local tests).

## Known gaps (honest)

- No source-tree analysis on the edge (above); the analyzer runs where
  arcade-agent runs and posts the changelog here.
- KV is eventually consistent; `latest-verdict` can lag a fresh write by
  up to ~60s globally.
- Scores remain advisory and uncalibrated against real PR history, same
  as the Python surface.
