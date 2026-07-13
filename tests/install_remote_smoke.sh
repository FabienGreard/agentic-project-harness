#!/usr/bin/env bash
set -eu

REPO=${HARNESS_REPO:-FabienGreard/agentic-project-harness}
REF=${1:-}
[ -n "$REF" ] || {
  printf 'Usage: bash tests/install_remote_smoke.sh COMMIT_OR_REF\n' >&2
  exit 2
}

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/agentic-project-harness-remote-smoke.XXXXXX")
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

installer="$TEMP_ROOT/install.sh"
target="$TEMP_ROOT/remote-project"
neutral="$TEMP_ROOT/neutral"
mkdir -p "$neutral"

curl -fsSL "https://raw.githubusercontent.com/$REPO/$REF/install.sh" -o "$installer"

(
  cd "$neutral"
  bash "$installer" \
    --repo "$REPO" \
    --ref "$REF" \
    --project-name "Remote Smoke Project" \
    --target "$target" \
    --director-reasoning xhigh \
    --delivery-reasoning high \
    --without-specialist \
    --worker-reasoning medium \
    --evaluator-reasoning high \
    --no-git \
    --yes >"$TEMP_ROOT/install.log"
)

python3 - "$target" "$REPO" "$REF" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
metadata = json.loads((root / ".agent-harness.json").read_text())
assert metadata["provider"] == "codex"
assert metadata["source"] == sys.argv[2]
assert metadata["ref"] == sys.argv[3]
assert metadata["sourceMode"] == "remote"
assert metadata["sourceDirty"] is None
assert metadata["installed"] is True
assert not (root / ".codex/agents/specialist-lead.toml").exists()
assert (root / "HARNESS.md").is_file()
PY

python3 "$target/tools/harness_eval.py" >"$TEMP_ROOT/eval.log"
printf 'PASS: standalone remote installer smoke at %s@%s\n' "$REPO" "$REF"
