#!/usr/bin/env bash
# Everything CI runs, in one command: bash scripts/check.sh
# Needs: pip install -r requirements-dev.txt (and Node 18+ for the JS syntax check).
set -euo pipefail
PY="${PYTHON:-python3}"
cd "$(dirname "$0")/.."
"$PY" scripts/check_safety.py
"$PY" scripts/validate_skills.py
for f in pawse/static/*.js; do node --check "$f"; done
echo "✔ JS syntax ok"
for f in web/scripts/check-*.mjs; do node "$f" >/dev/null || { echo "✖ $f failed" >&2; exit 1; }; done
echo "✔ web app checks ok"
"$PY" scripts/export_contract.py >/dev/null
git diff --exit-code -- docs/openapi.json >/dev/null \
  || { echo "✖ docs/openapi.json is stale: run python3 scripts/export_contract.py and commit it" >&2; exit 1; }
echo "✔ OpenAPI contract in sync"
"$PY" -m pytest -q tests
