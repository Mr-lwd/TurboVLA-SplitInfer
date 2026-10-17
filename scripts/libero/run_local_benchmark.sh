#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
# Use the activated environment on either device; allow an explicit interpreter.
# The Python runner records control-step timestamps and exports p95 + *_steps.csv.
exec "${TURBOVLA_PYTHON:-python}" scripts/libero/benchmark_local.py "$@"
