#!/usr/bin/env bash
# ArcadeAttest demo: the synthetic-smells corpus from arcade-agent-examples.
# Refactored direction must PASS; reintroducing the smells must BLOCK (exit 2).
set -euo pipefail
cd "$(dirname "$0")/.."

EXAMPLES="${ARCADE_EXAMPLES:-$HOME/workspace/arcade-agent-examples}"
SYN="$EXAMPLES/scenarios/synthetic-smells/synthetic"
RECORD="examples/decision-record.json"
mkdir -p data

if [ ! -d "$SYN" ]; then
  echo "Demo corpus not found at $SYN" >&2
  echo "Clone https://github.com/tuannx/arcade-agent-examples or set ARCADE_EXAMPLES." >&2
  exit 1
fi

echo "== Case 1: before -> after (smells removed) =="
arcade-attest evaluate --base "$SYN/before" --head "$SYN/after" \
  --record "$RECORD" --out data/demo-evidence.json > /dev/null
python3 -c "import json; p=json.load(open('data/demo-evidence.json')); print('verdict:', p['verdict'], '| id:', p['id'])"

echo "== Case 2: after -> before (smells reintroduced) =="
set +e
arcade-attest evaluate --base "$SYN/after" --head "$SYN/before" \
  --record "$RECORD" --out data/demo-block-evidence.json > /dev/null
code=$?
set -e
python3 -c "import json; p=json.load(open('data/demo-block-evidence.json')); print('verdict:', p['verdict'], '| new smells:', p['measured']['smells_new'])"
echo "CLI exit code: $code (2 = BLOCK, by design)"
