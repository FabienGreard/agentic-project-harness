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
  --project-type research \
  --reasoning-preset custom \
  --director-reasoning xhigh \
  --delivery-reasoning high \
  --specialist-reasoning low \
  --worker-reasoning minimal \
  --evaluator-reasoning ultra \
  --no-git \
  --yes >"$TEMP_ROOT/configured.log"

grep -Fq 'First project prompt:' "$TEMP_ROOT/configured.log" || fail "installer did not point to the inline first-project prompt"
grep -Fq 'Copy the `First project prompt` block from README.md into the task.' "$TEMP_ROOT/configured.log" || fail "installer did not print the README handoff"

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
assert metadata["projectType"] == "research"
assert metadata["reasoningPreset"] == "custom"
assert metadata["harnessVersion"] == "0.3.0"
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
assert not (root / "BOOTSTRAP_PROMPT.md").exists()
readme = (root / "README.md").read_text()
assert "## First project prompt" in readme
assert "Bootstrap Configured Project using the repository harness." in readme
PY

python3 "$configured/tools/harness_eval.py" >"$TEMP_ROOT/configured-eval.log"

inherited="$TEMP_ROOT/inherited-project"
bash "$ROOT/install.sh" \
  --project-name "Inherited Project" \
  --target "$inherited" \
  --director-reasoning inherit \
  --no-git \
  --yes >"$TEMP_ROOT/inherited.log"

if grep -q '^model_reasoning_effort' "$inherited/.codex/agents/project-director.toml"; then
  fail "inherit should omit model_reasoning_effort"
fi
grep -q '^model_reasoning_effort = "xhigh"$' "$inherited/.codex/agents/harness-evaluator.toml" || fail "default evaluator reasoning is not xhigh"
grep -q '| Harness Evaluator | `xhigh` |' "$inherited/README.md" || fail "generated README does not report the xhigh evaluator default"
python3 - "$inherited/.agent-harness.json" <<'PY'
import json
import sys
metadata = json.load(open(sys.argv[1], encoding="utf-8"))
assert metadata["projectType"] == "software-product"
assert metadata["reasoningPreset"] == "balanced"
PY
grep -q '^model_reasoning_effort = "high"$' "$inherited/.codex/agents/specialist-lead.toml" || fail "standard Specialist Lead config is missing or incorrect"
python3 "$inherited/tools/harness_eval.py" >"$TEMP_ROOT/inherited-eval.log"
mv "$inherited/.codex/agents/specialist-lead.toml" "$inherited/.codex/agents/specialist-lead.toml.missing"
if python3 "$inherited/tools/harness_eval.py" >"$TEMP_ROOT/missing-specialist-eval.log" 2>&1; then
  fail "harness evaluator accepted a missing Specialist Lead config"
fi
mv "$inherited/.codex/agents/specialist-lead.toml.missing" "$inherited/.codex/agents/specialist-lead.toml"

git_project="$TEMP_ROOT/git-project"
bash "$ROOT/install.sh" \
  --project-name "Git Project" \
  --target "$git_project" \
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

if bash "$ROOT/install.sh" --project-name "Invalid type" --target "$TEMP_ROOT/invalid-type" --project-type impossible --yes >"$TEMP_ROOT/invalid-type.log" 2>&1; then
  fail "invalid project type was accepted"
fi

if bash "$ROOT/install.sh" --project-name "Invalid preset" --target "$TEMP_ROOT/invalid-preset" --reasoning-preset impossible --yes >"$TEMP_ROOT/invalid-preset.log" 2>&1; then
  fail "invalid reasoning preset was accepted"
fi

if bash "$ROOT/install.sh" --project-name "No optional roles" --target "$TEMP_ROOT/no-optional" --without-specialist --dry-run --yes >"$TEMP_ROOT/no-optional.log" 2>&1; then
  fail "removed --without-specialist option was accepted"
fi
grep -q 'unknown option: --without-specialist' "$TEMP_ROOT/no-optional.log" || fail "removed Specialist option did not return a clear error"

if bash "$ROOT/install.sh" --project-name "Missing target" --yes >"$TEMP_ROOT/missing.log" 2>&1; then
  fail "non-interactive install without a target was accepted"
fi

inspection_target="$TEMP_ROOT/inspection-target"
mkdir -p "$inspection_target"
printf 'preserve me\n' >"$inspection_target/user-file.txt"
fake_find_bin="$TEMP_ROOT/fake-find-bin"
mkdir -p "$fake_find_bin"
printf '#!/bin/sh\nexit 1\n' >"$fake_find_bin/find"
chmod +x "$fake_find_bin/find"
if PATH="$fake_find_bin:$PATH" bash "$ROOT/install.sh" --project-name "Inspection Failure" --target "$inspection_target" --dry-run --yes >"$TEMP_ROOT/inspection.log" 2>&1; then
  fail "target inspection failure was treated as an empty directory"
fi
[ "$(sed -n '1p' "$inspection_target/user-file.txt")" = "preserve me" ] || fail "inspection failure modified the target"
grep -q 'target cannot be safely inspected' "$TEMP_ROOT/inspection.log" || fail "inspection failure did not explain the safety stop"

fake_bin="$TEMP_ROOT/fake-bin"
mkdir -p "$fake_bin"
printf '#!/bin/sh\nexit 127\n' >"$fake_bin/git"
chmod +x "$fake_bin/git"
git_failure_target="$TEMP_ROOT/git-failure"
if PATH="$fake_bin:$PATH" bash "$ROOT/install.sh" --project-name "Git Failure" --target "$git_failure_target" --yes >"$TEMP_ROOT/git-failure.log" 2>&1; then
  fail "failing Git initialization was accepted"
fi
[ ! -e "$git_failure_target" ] || fail "Git failure left a populated target"

python3 "$ROOT/tests/install_interactive_smoke.py" "$ROOT"
printf 'PASS: installer smoke tests completed in isolated new folders\n'
