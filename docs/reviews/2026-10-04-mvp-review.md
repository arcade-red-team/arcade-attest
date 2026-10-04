# MVP red-team review — 2026-10-04

Verdict: **pass** (with warnings tracked as issues). Method per DOCTRINE.md:
every claim below maps to evidence; unmapped claims are marked unverified.

| # | Claim under attack | Evidence | Result |
|---|---|---|---|
| 1 | Verdict is deterministic | `scripts/dogfood.sh` re-runs `from-changelog` twice with fixed `--evaluated-at`; hashes equal (`da92bbde…` at review time) | pass |
| 2 | BLOCK actually blocks | demo case 2 (smells reintroduced) exits 2, verdict BLOCK, evidence lists Dependency Cycle + Concern Overload | pass |
| 3 | PASS case is a real analysis, not a stub | `data/demo-evidence.json`: arcade-agent ran on the synthetic corpus (39→20 entities, 2 smells resolved) | pass |
| 4 | No silent unknowns | Issue #3: from-changelog fallback invented component sizes (0) so `component_entity_cap` could never fire | **was fail → fixed**: `coverage.component_sizes_known` + warning in every affected pack; regression test `test_unknown_component_sizes_warn_cap_cannot_trigger` |
| 5 | SPEC API complete | SPEC vs `api.py`: `latest-verdict` missing, MCP tools missing | warn → latest-verdict added this round; MCP tracked in issue #4 (D7) |
| 6 | No LLM in verdict path | engine imports only hashlib/json/typing; `llm_in_verdict: false` stamped in every pack | pass |
| 7 | Deadline/rules claims sourced | RULES-VERIFIED.md: official page confirms Oct 12 2026 + Base track; exact hour unverified (stated, not hidden) | warn → issue #7 |
| 8 | Pre-existing code disclosed | README disclosure + LICENSE files; arcade-agent is a pinned PyPI dependency, not vendored | pass |
| 9 | Secrets handling | no keys in repo; D3 wallet is an owner gate (issue #1), agents never hold secrets | pass |
| 10 | On-chain anchor exists | anchor.py is a payload builder, `status: not_submitted` | unverified → issue #1 (D3) |

## Fixes landed with this review

- `--evaluated-at` on CLI (issue #2), `scripts/dogfood.sh` one-verdict gate, CI workflow `.github/workflows/dogfood.yml`.
- `component_sizes_known` flag + explicit warning (issue #3).
- `GET /v1/repos/{owner}/{repo}/latest-verdict` (issue #4, partial — MCP remains).

Tests at review time: 9 passed. Demo + determinism gates green.
