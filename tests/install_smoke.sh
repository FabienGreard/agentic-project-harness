#!/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/agentic-project-harness-smoke.XXXXXX")
TEMP_ROOT=$(CDPATH= cd -- "$TEMP_ROOT" && pwd -P)
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
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / "tools"))
from codex_config_contract import assert_codex_config

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
assert metadata["harnessVersion"] == (root / "VERSION").read_text(encoding="utf-8").strip()
assert metadata["installed"] is True
assert metadata["sourceMode"] == "local"
assert metadata["ref"] == "local-working-tree"
assert state["project"]["name"] == "Configured Project"
assert state["project"]["agentProvider"] == "codex"
assert_codex_config(root / ".codex/config.toml")
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
assert (root / "AGENTS.md").is_file()
assert (root / ".agents/rules").is_dir()
assert (root / ".codex/skills").is_symlink()
assert (root / ".codex/skills").resolve() == (root / ".agents/skills").resolve()
for skill in ("brainstorm", "improve-codebase-architecture", "code-review"):
    assert (root / ".agents/skills" / skill / "SKILL.md").is_file(), skill
assert list((root / ".agents/skills").glob("*.json")), "skill metadata missing"
assert any((root / ".agents/skills" / name).is_file() for name in ("README.md", "ATTRIBUTION.md", "NOTICE.md"))
PY

python3 "$configured/tools/harness_eval.py" >"$TEMP_ROOT/configured-eval.log"

custom_rules="$TEMP_ROOT/custom-rules-project"
mkdir -p "$custom_rules"
tar -C "$configured" -cf - . | tar -C "$custom_rules" -xf -
cp "$custom_rules/.agents/rules/repository-safety.md" "$custom_rules/.agents/rules/security-policy.md"
python3 - "$custom_rules/AGENTS.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
anchor = "| Rule authoring template | [.agents/rules/_template.md](.agents/rules/_template.md) |\n"
row = "| Project security policy | [.agents/rules/security-policy.md](.agents/rules/security-policy.md) |\n"
assert anchor in text
path.write_text(text.replace(anchor, anchor + row), encoding="utf-8")
PY
python3 "$custom_rules/tools/harness_eval.py" >"$TEMP_ROOT/custom-rules-eval.log"

unmapped_rules="$TEMP_ROOT/unmapped-rules-project"
mkdir -p "$unmapped_rules"
tar -C "$configured" -cf - . | tar -C "$unmapped_rules" -xf -
cp "$unmapped_rules/.agents/rules/repository-safety.md" "$unmapped_rules/.agents/rules/unmapped-policy.md"
if python3 "$unmapped_rules/tools/harness_eval.py" >"$TEMP_ROOT/unmapped-rules-eval.log" 2>&1; then
  fail "harness evaluator accepted an unmapped project-specific rule"
fi
grep -q 'AGENTS.md missing map targets: .agents/rules/unmapped-policy.md' "$TEMP_ROOT/unmapped-rules-eval.log" || fail "unmapped rule failure did not identify the missing AGENTS map target"

missing_review_contract="$TEMP_ROOT/missing-review-contract-project"
mkdir -p "$missing_review_contract"
tar -C "$configured" -cf - . | tar -C "$missing_review_contract" -xf -
python3 - "$missing_review_contract/docs/roles/project-director.md" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
prefix, _ = text.split("## Final audit", 1)
path.write_text(prefix + "## Final audit\n", encoding="utf-8")
PY
if python3 "$missing_review_contract/tools/harness_eval.py" >"$TEMP_ROOT/missing-review-contract-eval.log" 2>&1; then
  fail "ST-042 accepted an empty Director final-audit contract"
fi
grep -q 'director role missing required contract' "$TEMP_ROOT/missing-review-contract-eval.log" || fail "ST-042 did not identify the missing Director contract"

piped_archive="$TEMP_ROOT/piped-source.tar.gz"
repo_parent=$(dirname "$ROOT")
repo_name=$(basename "$ROOT")
tar -C "$repo_parent" \
  --exclude="$repo_name/.git" \
  --exclude="$repo_name/.artifacts" \
  --exclude="$repo_name/__pycache__" \
  -czf "$piped_archive" "$repo_name"
piped_curl_bin="$TEMP_ROOT/piped-curl-bin"
mkdir -p "$piped_curl_bin"
printf '%s\n' \
  '#!/bin/sh' \
  'output=' \
  'while [ "$#" -gt 0 ]; do' \
  '  case "$1" in' \
  '    -o) output=$2; shift 2 ;;' \
  '    *) shift ;;' \
  '  esac' \
  'done' \
  '[ -n "$output" ] || exit 2' \
  'cp "$HARNESS_PIPE_ARCHIVE" "$output"' >"$piped_curl_bin/curl"
chmod +x "$piped_curl_bin/curl"
piped_target="$TEMP_ROOT/piped-project"
PATH="$piped_curl_bin:$PATH" HARNESS_PIPE_ARCHIVE="$piped_archive" \
  bash -s -- \
    --repo example/agentic-project-harness \
    --ref candidate \
    --project-name "Piped Candidate" \
    --target "$piped_target" \
    --project-type software-product \
    --reasoning-preset balanced \
    --no-git \
    --yes <"$ROOT/install.sh" >"$TEMP_ROOT/piped.log"

python3 - "$piped_target" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / "tools"))
from codex_config_contract import assert_codex_config

metadata = json.loads((root / ".agent-harness.json").read_text(encoding="utf-8"))
assert metadata["sourceMode"] == "remote"
assert metadata["ref"] == "candidate"
assert metadata["harnessVersion"] == "0.4.0"
assert_codex_config(root / ".codex/config.toml")
assert (root / ".codex/skills").is_symlink()
assert (root / ".codex/skills").resolve() == (root / ".agents/skills").resolve()
PY
python3 "$piped_target/tools/harness_eval.py" >"$TEMP_ROOT/piped-eval.log"

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
python3 - "$inherited" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / "tools"))
from codex_config_contract import assert_codex_config

assert_codex_config(root / ".codex/config.toml")
PY
test -L "$inherited/.codex/skills" || fail "Codex skills discovery link missing"
test "$(readlink "$inherited/.codex/skills")" = "../.agents/skills" || fail "Codex skills discovery link is not relative"
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

symlink_real="$TEMP_ROOT/symlink-real"
symlink_target="$TEMP_ROOT/symlink-target"
mkdir -p "$symlink_real"
ln -s "$symlink_real" "$symlink_target"
if bash "$ROOT/install.sh" --project-name "Unsafe symlink" --target "$symlink_target" --no-git --yes >"$TEMP_ROOT/symlink-target.log" 2>&1; then
  fail "symbolic-link target was accepted"
fi
[ -z "$(find "$symlink_real" -mindepth 1 -maxdepth 1 -print -quit)" ] || fail "symbolic-link target destination was modified"
grep -q 'target path must not be or pass through a symbolic link' "$TEMP_ROOT/symlink-target.log" || fail "symbolic-link refusal was not explained"

symlink_parent_real="$TEMP_ROOT/symlink-parent-real"
symlink_parent="$TEMP_ROOT/symlink-parent"
mkdir -p "$symlink_parent_real"
ln -s "$symlink_parent_real" "$symlink_parent"
if bash "$ROOT/install.sh" --project-name "Unsafe symlink parent" --target "$symlink_parent/nested" --no-git --yes >"$TEMP_ROOT/symlink-parent.log" 2>&1; then
  fail "target below a symbolic-link parent was accepted"
fi
[ ! -e "$symlink_parent_real/nested" ] || fail "symbolic-link parent destination was modified"

mkdir -p "$symlink_parent_real/existing"
if bash "$ROOT/install.sh" --project-name "Unsafe existing target below symlink parent" --target "$symlink_parent/existing" --no-git --yes >"$TEMP_ROOT/symlink-existing-parent.log" 2>&1; then
  fail "existing target below a symbolic-link parent was accepted"
fi
[ -z "$(find "$symlink_parent_real/existing" -mindepth 1 -maxdepth 1 -print -quit)" ] || fail "existing target below a symbolic-link parent was modified"
grep -q 'target path must not be or pass through a symbolic link' "$TEMP_ROOT/symlink-existing-parent.log" || fail "existing target below a symbolic-link parent did not return the symlink refusal"

mkdir -p "$symlink_parent_real/level/existing"
if bash "$ROOT/install.sh" --project-name "Unsafe deep existing target below symlink parent" --target "$symlink_parent/level/existing" --no-git --yes >"$TEMP_ROOT/symlink-deep-existing-parent.log" 2>&1; then
  fail "deep existing target below a symbolic-link parent was accepted"
fi
[ -z "$(find "$symlink_parent_real/level/existing" -mindepth 1 -maxdepth 1 -print -quit)" ] || fail "deep existing target below a symbolic-link parent was modified"
grep -q 'target path must not be or pass through a symbolic link' "$TEMP_ROOT/symlink-deep-existing-parent.log" || fail "deep existing target below a symbolic-link parent did not return the symlink refusal"

dotdot_real="$TEMP_ROOT/dotdot-real"
dotdot_link="$TEMP_ROOT/dotdot-link"
mkdir -p "$dotdot_real/level"
ln -s "$dotdot_real/level" "$dotdot_link"
if bash "$ROOT/install.sh" --project-name "Unsafe dotdot target" --target "$dotdot_link/../escaped-project" --no-git --yes >"$TEMP_ROOT/dotdot-target.log" 2>&1; then
  fail "target with a symlink-hidden .. segment was accepted"
fi
[ ! -e "$dotdot_real/escaped-project" ] || fail "target with a symlink-hidden .. segment wrote through the redirected path"
grep -q 'target cannot contain .. path segments' "$TEMP_ROOT/dotdot-target.log" || fail "dotdot target refusal was not explained"

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

real_tar=$(command -v tar)
rollback_tar_bin="$TEMP_ROOT/rollback-tar-bin"
rollback_count="$TEMP_ROOT/rollback-tar-count"
mkdir -p "$rollback_tar_bin"
printf '%s\n' \
  '#!/bin/sh' \
  'count=0' \
  '[ ! -f "$HARNESS_TAR_COUNT" ] || count=$(cat "$HARNESS_TAR_COUNT")' \
  'count=$((count + 1))' \
  'printf "%s\n" "$count" >"$HARNESS_TAR_COUNT"' \
  '[ "$count" -ne 4 ] || exit 99' \
  'exec "$HARNESS_REAL_TAR" "$@"' >"$rollback_tar_bin/tar"
chmod +x "$rollback_tar_bin/tar"

rollback_created="$TEMP_ROOT/rollback-created"
if PATH="$rollback_tar_bin:$PATH" HARNESS_REAL_TAR="$real_tar" HARNESS_TAR_COUNT="$rollback_count" \
  bash "$ROOT/install.sh" --project-name "Rollback Created" --target "$rollback_created" --no-git --yes >"$TEMP_ROOT/rollback-created.log" 2>&1; then
  fail "post-population archive failure was accepted"
fi
[ ! -e "$rollback_created" ] || fail "post-population failure left a newly created target"

rm -f "$rollback_count"
rollback_existing="$TEMP_ROOT/rollback-existing"
mkdir -p "$rollback_existing"
if PATH="$rollback_tar_bin:$PATH" HARNESS_REAL_TAR="$real_tar" HARNESS_TAR_COUNT="$rollback_count" \
  bash "$ROOT/install.sh" --project-name "Rollback Existing" --target "$rollback_existing" --no-git --yes >"$TEMP_ROOT/rollback-existing.log" 2>&1; then
  fail "post-population archive failure in an existing empty target was accepted"
fi
[ -d "$rollback_existing" ] || fail "rollback removed a target directory that existed before installation"
[ -z "$(find "$rollback_existing" -mindepth 1 -maxdepth 1 -print -quit)" ] || fail "rollback left files in a pre-existing empty target"

python3 "$ROOT/tests/install_interactive_smoke.py" "$ROOT"
printf 'PASS: installer smoke tests completed in isolated new folders\n'
