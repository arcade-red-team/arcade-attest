# ArcadeAttest + Decision API - Colosseum Spec (draft 2026-10-02)

## Thesis: Attest is a receipt. Decision API is a gate.
Existing public cousins:
- Kyro: Decision API for wallet counterparty (allow/caution/block + USDC limit + immutable decision receipt) - not code/architecture
- ZKCG: proof-backed compliance decision API for RWA, API signs on-chain attestation, contract consumes it - not code
- Ledgerline/trace-ai: AI agent decision trace, hash+Mercle anchored via EAS on Base Sepolia - trace, not verdict API for repo
- AuditAI: smart-contract security auditor + EAS Sepolia attestation + MCP - security audit, not architecture ADR predicates
- ERC-8004 Validation Registry: code hash / audit attestation for agents - registry layer, no architecture Decision API
Gap found 2026-10-02 search: No public Decision API for software architecture (ADR-as-code predicates) anchored on blockchain.

## Product
POST repo/PR + Decision Record (policy-as-code) -> arcade-agent evaluates -> verdict PASS/WARN/BLOCK + evidence pack -> evidence hash anchored as EAS attestation on Base -> anyone (CI, DAO, agent, contract) can query verdict before merge/pay.

Decision Record predicates MVP (from 2026-09-30 design doc):
1. no_new_smells
2. max_responsibility_shifts (e.g. <=2)
3. component_entity_cap (e.g. <=20)

Pipeline: register -> baseline -> evaluate -> verdict -> evidence pack -> decision health

## API (public)
POST /v1/decisions:evaluate { repo, baseCommit, headCommit, decisionRecord }
GET /v1/decisions/{id}
GET /v1/repos/{owner}/{repo}/latest-verdict
MCP tools: evaluate_decision, get_verdict, explain_evidence
On-chain read: EAS GraphQL (base.easscan.org/graphql) by attestation UID, or contract reads UID

## EAS Schema (Base Sepolia first)
string repo; bytes32 baseCommit; bytes32 headCommit; bytes32 decisionRecordHash; uint8 verdict (0 PASS 1 WARN 2 BLOCK); int32 smellsDelta; uint32 responsibilityShifts; bytes32 evidenceHash; uint64 evaluatedAt; uint64 expiresAt

Only hashes on-chain. Evidence pack (JSON+HTML report) off-chain IPFS/content hash.

## Consumers
- GitHub Action: block PR merge if BLOCK (like existing arch-drift)
- AgentPay Firewall: agent only pays/releases if repo/agent code verdict = PASS
- DAO/investor: query latest verdict before funding

## Honest gaps (must disclose to judges, from design doc)
- No edge-level diff yet -> deny_dependency predicate not in MVP
- Parser blind spots (e.g. Go var-only files = 0 entities) -> false PASS risk, must show coverage/warnings in evidence
- Thresholds are starting guesses, need history to calibrate
- Chain proves integrity+timestamp of verdict, not that verdict is objectively correct

## Colosseum build (10 days)
D1-2: Decision API MVP wrapping arcade-agent changelog_architecture (3 predicates)
D3-4: EAS schema on Base Sepolia + attest on evaluate + verify page
D5-6: Next.js dashboard: paste repo/PR -> verdict + evidence + on-chain link
D7: GitHub Action gate demo + MCP endpoint
D8-9: Pitch (WHY) + Demo (HOW) videos
D10: Submit early (deadline Oct 12)
