# Decision Gate for GitHub Actions — local Decision API + Qxotic Jinfer

`decision-gate-local-api.yml` is a drop-in PR gate for any repo. It replaces
the "ask an LLM ALLOW/BLOCK" pattern with two local services in the CI
runner, each with one job:

- **ArcadeAttest Decision API is the judge.** It evaluates the PR's real
  base/head trees against a Decision Record and returns the deterministic
  PASS/WARN/BLOCK verdict plus the ten-criterion scorecard
  (`llm_in_verdict: false` in every pack).
- **[Qxotic](https://github.com/qxoticai/qxotic) Jinfer is the explainer.**
  Jinfer 0.3.1 (pinned jar, SHA-256 checked) serves a local GGUF model
  (`LiquidAI/LFM2.5-350M-GGUF:Q8_0`) over an OpenAI-compatible loopback
  API. After the verdict exists, `arcade-attest explain-qxotic` asks it to
  draft a short reviewer explanation of the evidence pack. The draft is
  appended to the PR comment, clearly labelled, and can never change the
  verdict — if Jinfer fails to start, the gate continues without it.

Flow:

1. Checks out the repo with full history and materializes the **real PR
   base and head trees** from their SHAs (push events use `before`/`after`).
2. Installs a **pinned** ArcadeAttest and starts `arcade-attest serve` on
   `127.0.0.1` — the Decision API never leaves the runner.
3. POSTs `{repo, base_path, head_path, language, decision_record}` to the
   local API. arcade-agent analyzes the two trees; the deterministic engine
   returns PASS/WARN/BLOCK plus the ten-criterion scorecard.
4. Starts the Qxotic Jinfer server on `127.0.0.1` (Java 25, pinned
   `jinfer-cli` 0.3.1 from Maven Central) and drafts the explanation.
5. Renders the evidence pack as a PR comment with the draft appended,
   uploads the pack as an artifact, and fails the job on BLOCK when
   `ENFORCE_BLOCK` is `"true"`.

## Use it

```bash
mkdir -p .github/workflows .arcade-attest
cp decision-gate-local-api.yml .github/workflows/decision-gate.yml
cp decision-record.example.json .arcade-attest/decision-record.json
# edit the record: id, repo, predicate thresholds, scoring profile/context
```

Set `LANGUAGE` in the workflow to the repo's primary language (`python`,
`java`, …) and bump `ATTEST_INSTALL` deliberately — it is pinned to a commit
SHA so the gate is reproducible. Set `QXOTIC_EXPLAIN` to `"false"` to skip
the Jinfer draft (the verdict path is unchanged).

Verified end to end locally (2026-10-08): Jinfer 0.3.1 served
`LFM2.5-350M-Q8_0` on loopback; the demo corpus evaluated through the
Decision API (before→after `PASS`, after→before `BLOCK 0.5`) and
`arcade-attest explain-qxotic` produced labelled drafts for both packs
with the reference model string resolved via `/v1/models`.
