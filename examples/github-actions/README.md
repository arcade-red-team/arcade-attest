# Decision Gate for GitHub Actions — local Decision API

`decision-gate-local-api.yml` is a drop-in PR gate for any repo. It replaces
the "ask an LLM ALLOW/BLOCK" pattern with the ArcadeAttest Decision API
running locally in the CI runner:

1. Checks out the repo with full history and materializes the **real PR
   base and head trees** from their SHAs (push events use `before`/`after`).
2. Installs a **pinned** ArcadeAttest and starts `arcade-attest serve` on
   `127.0.0.1` — the Decision API never leaves the runner.
3. POSTs `{repo, base_path, head_path, language, decision_record}` to the
   local API. arcade-agent analyzes the two trees; the deterministic engine
   returns PASS/WARN/BLOCK plus the ten-criterion scorecard.
4. Renders the evidence pack as a PR comment, uploads the pack as an
   artifact, and fails the job on BLOCK when `ENFORCE_BLOCK` is `"true"`.

No direct LLM participates in the verdict (`llm_in_verdict: false` in every
pack). A local model such as Jinfer may be added later as a *drafting* step
that explains the pack to reviewers; it must never gate.

## Use it

```bash
mkdir -p .github/workflows .arcade-attest
cp decision-gate-local-api.yml .github/workflows/decision-gate.yml
cp decision-record.example.json .arcade-attest/decision-record.json
# edit the record: id, repo, predicate thresholds, scoring profile/context
```

Set `LANGUAGE` in the workflow to the repo's primary language (`python`,
`java`, …) and bump `ATTEST_INSTALL` deliberately — it is pinned to a commit
SHA so the gate is reproducible.

Verified locally against the demo corpus through the real HTTP API:
before→after `PASS 0.7`, after→before `BLOCK 0.5`, both with
`llm_in_verdict: false`.
