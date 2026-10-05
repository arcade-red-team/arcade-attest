# Dogfood reports

Real-repo evaluations of arcade-agent on itself (issue #6). Each JSON is a
verbatim evidence pack produced by `arcade-attest evaluate`.

| Date | Base -> Head | Change | Verdict | Runtime | Notes |
|---|---|---|---|---|---|
| 2026-10-04 | 3911489 -> d2bb44b | feat(parser): Rust support (#39) | PASS | ~2s | 378->407 entities (+29), 11 components, 0 new smells, 0 shifts; largest component Parsers=140 under cap 400. Coverage: python only — the new Rust files are not parsed by the python pipeline, which is exactly the blind spot honest_gaps disclose. |
