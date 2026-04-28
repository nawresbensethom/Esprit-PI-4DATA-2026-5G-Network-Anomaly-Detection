#!/usr/bin/env bash
# Thin wrapper around init_env.py for muscle-memory bash users.
# Forwards every argument straight through.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python scripts/init_env.py "$@"
