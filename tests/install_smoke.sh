#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
python3 "$ROOT/tests/run_smokes.py"
