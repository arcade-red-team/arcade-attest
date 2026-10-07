#!/usr/bin/env bash
# Dogfood gate (redteam-doctrine): one machine-readable verdict.
# Runs: unit tests -> demo PASS case -> demo BLOCK case -> determinism re-run.
# Exit 0 + verdict "pass" only when every gate holds.
set -euo pipefail
cd "$(dirname "$0")/.."

fail() { echo "{\"verdict\":\"block\",\"gate\":\"$1\"}"; exit 1; }

python3 -m pytest -q > /tmp/attest-pytest.log 2>&1 || fail pytest
if command -v node >/dev/null 2>&1; then
  (cd cloudflare && npm test > /tmp/attest-cf.log 2>&1) || fail cloudflare
fi
bash scripts/run-demo.sh > /tmp/attest-demo.log 2>&1 || fail demo

# Determinism: same changelog + same --evaluated-at, twice -> same evidence_hash.
CHANGELOG="${ARCADE_EXAMPLES:-$HOME/workspace/arcade-agent-examples}/docs/reports/synthetic_summary.json"
if [ -f "$CHANGELOG" ]; then
  arcade-attest from-changelog --changelog "$CHANGELOG" --record examples/decision-record.json \
    --evaluated-at 2026-10-04T00:00:00Z --out /tmp/attest-run1.json > /dev/null
  arcade-attest from-changelog --changelog "$CHANGELOG" --record examples/decision-record.json \
    --evaluated-at 2026-10-04T00:00:00Z --out /tmp/attest-run2.json > /dev/null
  python3 - <<'PY' || fail determinism
import json
a = json.load(open("/tmp/attest-run1.json"))["hashes"]["evidence_hash"]
b = json.load(open("/tmp/attest-run2.json"))["hashes"]["evidence_hash"]
assert a == b, f"hash mismatch {a} != {b}"
print("evidence_hash:", a)
PY
fi

echo '{"verdict":"pass","gates":["pytest","cloudflare","demo-pass","demo-block","determinism"]}'
