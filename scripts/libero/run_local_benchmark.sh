#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
# Use the activated environment on either device; allow an explicit interpreter.
exec "${TURBOVLA_PYTHON:-python}" scripts/libero/benchmark_local.py "$@"
