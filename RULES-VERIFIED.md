# Colosseum rules — verification log

Competition: **Crypto World's Fair** (Colosseum), online.
Checked: 2026-10-04 (America/Chicago). Sources: official pages below.

## Verified on official pages

- "Submissions due **October 12, 2026**." — colosseum.com/worldsfair
- Total described on the official page: **$840,000 in prizes** and **$2.5 million in seed funding**.
- "Colosseum hackathons are open to builders across **all blockchain ecosystems**, and every submission is eligible for prizes regardless of the crypto infrastructure used." + dedicated ecosystem tracks — colosseum.com/hackathon (FAQ) and track tiles on /worldsfair (Solana, Ethereum, Hyperliquid, **Base**, Tempo, Arbitrum, Zcash, Robinhood Chain). Base track judge listed (David Tso, Ecosystem & Ventures, Base).

## NOT verified officially (treat as unknown)

- **Exact closing hour/timezone.** The official page prints only the date. Third-party sources conflict:
  - A submission-plan repo (researched 2026-09-23) states a hard deadline of Oct 13 2026 06:59 UTC (= Oct 12 11:59pm PT).
  - Superteam Brasil's participant wiki states Oct 12 23:59 Brasília time (= Oct 13 02:59 UTC).
  - **Internal safety rule: submit by Oct 12, 12:00 America/Chicago at the latest.** That is before both candidate cut-offs.
- Detailed rulebook (pre-existing code handling, team size, submission fields) lives behind the arena/join flow and was not read in this pass.

## Second-hand quotes of the official rules page (solanabr academy course, read 2026-09-06)

- "one product submission per team, and so one per individual"
- "the team leader completes the submission before the deadline"
- "**misrepresenting the development history, or failing to disclose pre-existing code: disqualifies, bans, revokes a prize**"

Implication for ArcadeAttest: the submission MUST disclose that the evaluator wraps **arcade-agent** (pre-existing, MIT, github.com/tuannx/arcade-agent, PyPI 0.3.0) and that this repository's commit history starts when it starts. See README "Pre-existing code disclosure".

## Open checks before submitting

1. Read the full rules inside the arena after registering (exact hour, eligibility, fields).
2. Confirm Base track specifics (any dedicated Base prize pool; press reported $25,000 announced for Base).
3. Deere IP/moonlighting self-check by the owner before using any related code/story publicly.
