# Submission checklist — Crypto World's Fair

Rules state: see RULES-VERIFIED.md (checked 2026-10-04; exact closing hour NOT
printed on the official page). Internal deadline: **submit by Oct 12, 12:00
America/Chicago** (before both candidate cut-offs found in third-party sources).

- [ ] Register on colosseum.com/worldsfair; read the full in-arena rules (exact hour, fields, eligibility) and update RULES-VERIFIED.md.
- [ ] Public GitHub repo with MIT license (this repo, once pushed to the arcade-red-team org).
- [ ] README carries the pre-existing-code disclosure (arcade-agent) — done, keep it accurate.
- [ ] Demo video ≤ 3 minutes (per Colosseum guidance cited by the solanabr course): problem → live evaluate → BLOCK case → evidence pack → attestation.
- [ ] Pitch: why (architecture decisions are unenforced prose today) + how (deterministic predicates, evidence hashes, on-chain receipts).
- [ ] Choose track: Base ecosystem (EAS on Base) unless track list changes; confirm in arena.
- [ ] One product submission per individual — do not enter a second project on the side.
- [ ] Team leader (owner) completes the submission before the deadline.
- [ ] Owner-only gates: Deere IP/moonlighting self-check before public push; nothing is submitted without the owner's explicit go.

---

## Pitch (DRAFT — owner edits before submission)

*Draft written 2026-10-08. Beats follow the demo-video shot list in the film
kit (0:00–2:30 filmed + 2:30–2:50 EAS slate). Every number below cites the
artifact it came from; re-verify each against the artifact before filming.*

**0:00–0:20 — Why.** Architecture decisions today are unenforced prose. An ADR
says "no new god modules, no responsibility drift," and then nothing checks
it — reviewers eyeball diffs, agents ignore it entirely, and the decision
silently rots. ArcadeAttest turns a Decision Record into a machine-checkable
gate: **Attest is a receipt. Decision API is a gate.** No LLM ever
participates in a verdict; LLMs may draft records, humans approve them, and
the engine is a pure function (README.md, SPEC.md).

**0:20–0:40 — How.** A Decision Record carries three deterministic
predicates — `no_new_smells`, `max_responsibility_shifts`,
`component_entity_cap` (`examples/decision-record.json`, README predicate
table). Every evaluation returns PASS / WARN / BLOCK plus an **evidence
pack**: per-predicate measurements, the exact offending components, parser
coverage, a SHA-256 `decision_record_hash` and a deterministic
`evidence_hash` (same input + same `--evaluated-at` → same hash, per
AGENTS.md determinism law). The pack's hash is what gets anchored as an
EAS attestation on Base (`src/arcade_attest/anchor.py`).

**0:40–1:20 — Live PASS case.** `scripts/run-demo.sh` on the
synthetic-smells corpus: before → after returns **PASS**, 39 → 20 entities,
2 smells resolved, advisory overall score 0.7
(`data/demo-evidence.json`, re-run and verified 2026-10-08). Real-repo
proof, same command, no cherry-picking: arcade-agent on itself,
3911489 → d2bb44b, **PASS** — 378 → 407 entities (+29), 11 components,
0 new smells, largest component 140 under the 400 cap, ~2s
(`docs/dogfood/arcade-agent-3911489-to-d2bb44b.json`).

**1:20–1:50 — Live BLOCK case.** Reverse direction (smells reintroduced):
**BLOCK**, 2 new smells, CLI exits with code **2** so CI can gate on it
(`data/demo-block-evidence.json`, verified 2026-10-08). This gate has
already caught a silent false-PASS in its own engine during development —
a component-size fallback that fabricated 0 so the cap could never fire —
fixed with a `component_sizes_known` flag plus a regression test
(`test_unknown_component_sizes_warn_cap_cannot_trigger`,
`tests/test_engine.py`); the flag still ships in every pack's coverage
block.

**1:50–2:15 — Scorecard (advisory, never the verdict).** Alongside the
verdict, ten pure scorers (`scoring@1`, SCORING-10-CRITERIA.md) grade the
change 0.0–1.0 in 0.1 steps — smell regression, responsibility stability,
god-component risk, modularity/cohesion/coupling trends, change
containment, evidence confidence. A criterion without evidence is
`not_run`, never a fabricated 0. Six admin weight profiles ship as skills
(`skills/scoring/`); weights move the advisory overall only — **the
PASS/WARN/BLOCK verdict never moves with weights**. Live evidence across
four third-party repos, one record shape, same thresholds
(`docs/dogfood/README.md`, 2026-10-08): psf/requests v2.33.1 → v2.34.0
**PASS** (277 → 285 entities, 3 shifts); pallets/click 8.4.2 → 8.5.0
**WARN** (29 shifts over the 25 warn threshold, 557 → 576 entities);
encode/httpx 0.27.2 → 0.28.0 **WARN** (33 shifts, 524 → 510);
Textualize/rich v14.3.4 → v15.0.0 **WARN** (largest component 1089
entities over the 400 cap, 1135 → 1136). Four real verdicts, three of
them WARN — the gate fires on real code, and every pack is reproducible
from its cited tags.

**2:15–2:30 — Verify, don't trust.** `docs/verify.html` recomputes the
`evidence_hash` client-side from the pack: paste a pack, see MATCHES, and
recompute anywhere else. The test suite behind all of this: **34 pytest
tests** on main `5efbfda` (`tests/`, re-run 2026-10-08). Consumers
already wired: HTTP API (`/v1/decisions:evaluate`), MCP tools
`evaluate_decision` / `get_verdict` / `explain_evidence`, and a composite
GitHub Action gate (`action.yml`).

**2:30–2:50 — EAS slate (filmed after D3).** The evidence hash becomes an
EAS attestation on Base Sepolia: schema registration + attest-on-evaluate
via `scripts/eas_attest.py`, dry-run verified (README roadmap). On-chain
execution awaits the owner's testnet wallet — until then this beat is a
slate, and the pitch claims a *ready script*, not a live attestation.

**Honest gaps (stated on camera, printed in every pack).** No edge-level
diff yet, so `deny_dependency` is designed but not evaluated. Parser
blind spots (files declaring no entities) can make a component look
empty → false-PASS risk; the click dogfood above shows the flat end of
that — 557 components for 557 entities, so component-level signals there
are weak and the pack says so via coverage. Predicate thresholds are
starting guesses awaiting per-repo calibration. Scoring thresholds are
likewise uncalibrated, and scores are advisory by design. The chain
proves a verdict existed, unchanged, at a time — not that the verdict is
objectively correct. (Source: README "Honest gaps" + each pack's
`honest_gaps` field.)

**Disclosure (mandatory, and true).** The analyzer is **arcade-agent**
(MIT, PyPI `arcade-agent` 0.3.0, github.com/tuannx/arcade-agent), a
pre-existing open-source project by the same author, consumed as a
pinned published dependency — not claimed as new work. Everything else
here — Decision Record engine, evidence pack format, scoring, CLI/HTTP/
MCP surfaces, EAS payload — was written for the Crypto World's Fair
window; commit history starts 2026-10-04 (README "Pre-existing code
disclosure").
