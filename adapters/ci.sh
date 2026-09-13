#!/usr/bin/env bash
# Generic CI wrapper around greenwash. No host assumptions beyond python + git.
#
#   BASE=origin/main RUN_TESTS="pytest -q" HELDOUT=tests/heldout bash adapters/ci.sh
#
# Exits non-zero if greenwash flags anything, so it drops straight into any CI.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
args=(all)
[ -n "${BASE:-}" ]      && args+=(--base "$BASE")
[ -n "${RUN_TESTS:-}" ] && args+=(--run-tests "$RUN_TESTS")
[ -n "${HELDOUT:-}" ]   && args+=(--heldout "$HELDOUT")
python "$here/scripts/greenwash_check.py" "${args[@]}"
