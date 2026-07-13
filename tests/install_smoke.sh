#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/agentic-project-harness-smoke.XXXXXX")
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

printf 'Smoke workspace: %s\n' "$TEMP_ROOT"

configured="$TEMP_ROOT/configured-project"
bash "$ROOT/install.sh" \
  --project-name "Configured Project" \
  --target "$configured" \
  --director-reasoning xhigh \
  --delivery-reasoning high \
  --with-specialist \
  --specialist-reasoning low \
  --worker-reasoning minimal \
  --evaluator-reasoning ultra \
  --no-git \
  --yes >"$TEMP_ROOT/configured.log"

python3 - "$configured" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
metadata = json.loads((root / ".agent-harness.json").read_text())
state = json.loads((root / "docs/project-state.json").read_text())
expected = {
    "project-director.toml": "xhigh",
    "delivery-lead.toml": "high",
    "specialist-lead.toml": "low",
    "execution-worker.toml": "minimal",
    "harness-evaluator.toml": "ultra",
}
assert metadata["provider"] == "codex"
assert metadata["harnessVersion"] == "0.2.0"
assert metadata["installed"] is True
assert metadata["sourceMode"] == "local"
assert metadata["ref"] == "local-working-tree"
assert state["project"]["name"] == "Configured Project"
assert state["project"]["agentProvider"] == "codex"
for filename, effort in expected.items():
    text = (root / ".codex/agents" / filename).read_text()
    match = re.search(r'^model_reasoning_effort = "([^"]+)"', text, re.MULTILINE)
    assert match and match.group(1) == effort, (filename, match.group(1) if match else None)
assert not (root / "adapters").exists()
assert not list(root.rglob("*.pyc"))
assert (root / "HARNESS.md").is_file()
assert (root / "README.md").is_file()
assert (root / "BOOTSTRAP_PROMPT.md").is_file()
PY

python3 "$configured/tools/harness_eval.py" >"$TEMP_ROOT/configured-eval.log"

inherited="$TEMP_ROOT/inherited-project"
bash "$ROOT/install.sh" \
  --project-name "Inherited Project" \
  --target "$inherited" \
  --director-reasoning inherit \
  --without-specialist \
  --no-git \
  --yes >"$TEMP_ROOT/inherited.log"

if grep -q '^model_reasoning_effort' "$inherited/.codex/agents/project-director.toml"; then
  fail "inherit should omit model_reasoning_effort"
fi
[ ! -e "$inherited/.codex/agents/specialist-lead.toml" ] || fail "omitted Specialist Lead config still exists"
python3 "$inherited/tools/harness_eval.py" >"$TEMP_ROOT/inherited-eval.log"

git_project="$TEMP_ROOT/git-project"
bash "$ROOT/install.sh" \
  --project-name "Git Project" \
  --target "$git_project" \
  --without-specialist \
  --yes >"$TEMP_ROOT/git.log"

[ "$(git -C "$git_project" branch --show-current)" = "main" ] || fail "Git branch is not main"
[ -z "$(git -C "$git_project" diff --cached --name-only)" ] || fail "installer staged files"

dry_target="$TEMP_ROOT/dry-project"
bash "$ROOT/install.sh" \
  --project-name "Dry Project" \
  --target "$dry_target" \
  --dry-run \
  --yes >"$TEMP_ROOT/dry.log"
[ ! -e "$dry_target" ] || fail "dry run wrote the target"

nonempty="$TEMP_ROOT/nonempty"
mkdir -p "$nonempty"
printf 'preserve me\n' >"$nonempty/user-file.txt"
if bash "$ROOT/install.sh" --project-name "Unsafe" --target "$nonempty" --yes >"$TEMP_ROOT/nonempty.log" 2>&1; then
  fail "non-empty target was accepted"
fi
[ "$(sed -n '1p' "$nonempty/user-file.txt")" = "preserve me" ] || fail "non-empty target was modified"

if bash "$ROOT/install.sh" --project-name "Invalid" --target "$TEMP_ROOT/invalid" --worker-reasoning impossible --yes >"$TEMP_ROOT/invalid.log" 2>&1; then
  fail "invalid reasoning was accepted"
fi

if bash "$ROOT/install.sh" --project-name "Missing target" --yes >"$TEMP_ROOT/missing.log" 2>&1; then
  fail "non-interactive install without a target was accepted"
fi

fake_bin="$TEMP_ROOT/fake-bin"
mkdir -p "$fake_bin"
printf '#!/bin/sh\nexit 127\n' >"$fake_bin/git"
chmod +x "$fake_bin/git"
git_failure_target="$TEMP_ROOT/git-failure"
if PATH="$fake_bin:$PATH" bash "$ROOT/install.sh" --project-name "Git Failure" --target "$git_failure_target" --yes >"$TEMP_ROOT/git-failure.log" 2>&1; then
  fail "failing Git initialization was accepted"
fi
[ ! -e "$git_failure_target" ] || fail "Git failure left a populated target"

printf 'PASS: installer smoke tests completed in isolated new folders\n'
