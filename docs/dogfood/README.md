# Dogfood reports

Real-repo evaluations produced by `arcade-attest evaluate`. The first row is
arcade-agent evaluated on itself (issue #6); its JSON is a verbatim evidence
pack. The 2026-10-08 rows are third-party OSS repos: each directory holds the
Decision Record used (`decision-record.json`), the verbatim evidence pack
(`evidence.json`), and a compact summary (`verdict.json`), so every row can be
reproduced from the cited tags.

| Date | Repo | Base -> Head | Verdict | Runtime | Notes |
|---|---|---|---|---|---|
| 2026-10-04 | tuannx/arcade-agent | 3911489 -> d2bb44b | PASS | ~2s | feat(parser): Rust support (#39). 378->407 entities (+29), 11 components, 0 new smells, 0 shifts; largest component Parsers=140 under cap 400. Coverage: python only — the new Rust files are not parsed by the python pipeline, which is exactly the blind spot honest_gaps disclose. Pack: `arcade-agent-3911489-to-d2bb44b.json`. |
| 2026-10-08 | pallets/click | 8.4.2 (b2e30a1) -> 8.5.0 (8b19813), 96 commits | WARN | ~1.4s | 557->576 entities, 0 new smells; `max_responsibility_shifts` triggered: 29 shifts > warn threshold 25. Component recovery is near-flat here (557 components at base), so the entity cap measured only 1 — component-level signals on this layout are weak, as disclosed in honest_gaps. Pack: `pallets-click/`. |
| 2026-10-08 | psf/requests | v2.33.1 (111d2b7) -> v2.34.0 (0b401c7), 34 commits | PASS | ~0.7s | 277->285 entities (+8), 0 new smells, 3 shifts, largest component 2 entities. All three predicates pass at the same starting-guess thresholds used for every row here. Pack: `psf-requests/`. |
| 2026-10-08 | encode/httpx | 0.27.2 (609df7e) -> 0.28.0 (80960fa), 34 commits | WARN | ~0.8s | 524->510 entities (−14), 0 new smells; `max_responsibility_shifts` triggered: 33 shifts > warn threshold 25. Largest component Transports=40, well under cap 400. Pack: `encode-httpx/`. |
| 2026-10-08 | Textualize/rich | v14.3.4 (ee8378c) -> v15.0.0 (6ac483c), 28 commits | WARN | ~2.3s | 1135->1136 entities, 0 new smells, 0 shifts; `component_entity_cap` triggered: largest component Rich=1089 entities > cap 400. A monolith-shaped package trips the anti-god-module cap at these starting-guess thresholds — the WARN is the gate working as designed, not an analysis failure. Pack: `textualize-rich/`. |
