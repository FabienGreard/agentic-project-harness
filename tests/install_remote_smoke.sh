#!/usr/bin/env bash
set -eu

REPO=${HARNESS_REPO:-FabienGreard/agentic-project-harness}
TAG=${1:-}
EXPECTED_SHA=${2:-}
[ -n "$TAG" ] && [ -n "$EXPECTED_SHA" ] || {
  printf 'Usage: bash tests/install_remote_smoke.sh STABLE_TAG EXPECTED_COMMIT_SHA\n' >&2
  exit 2
}

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/agentic-project-harness-remote-smoke.XXXXXX")
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

bundle="$TEMP_ROOT/bundle"
target="$TEMP_ROOT/remote-project"
mkdir -p "$bundle" "$target"
for asset in install.sh agentic-project-harness-template.tar.gz harness-manifest.json SHA256SUMS; do
  curl -fsSL "https://github.com/$REPO/releases/download/$TAG/$asset" -o "$bundle/$asset"
done

(
  cd "$target"
  APH_RELEASE_DIR="$bundle" bash "$bundle/install.sh" --yes --json >"$TEMP_ROOT/install.json"
)

python3 - "$target" "$REPO" "$TAG" "$EXPECTED_SHA" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
repository, tag, expected_sha = sys.argv[2:]
metadata = json.loads((root / ".agent-harness.json").read_text(encoding="utf-8"))
assert metadata["schemaVersion"] == 2
assert metadata["installationStatus"] == "Installed"
assert metadata["source"]["repository"] == repository
assert metadata["source"]["channel"] == "stable"
assert metadata["source"]["tag"] == tag
assert metadata["source"]["commit"] == expected_sha
assert metadata["source"]["manifestSha256"]
assert (root / ".codex/skills").is_symlink()
assert (root / ".codex/skills").resolve() == (root / ".agents/skills").resolve()
assert (root / "docs/index.html").is_file()
team = json.loads((root / "docs/state/team.json").read_text(encoding="utf-8"))
assert team["preset"] == "software-product"
assert [item["id"] for item in team["consultants"] if item["status"] == "active"] == ["product-designer"]
assert {path.name for path in (root / ".codex/agents").glob("*.toml")} == {
    "management.toml", "operations.toml", "contractor.toml",
    "internal-audit.toml", "consultant-product-designer.toml",
}
assert not (root / "hire").exists() and not (root / "fire").exists()
assert (root / ".agents/skills/hire-consultant/SKILL.md").is_file()
assert (root / ".agents/skills/fire-consultant/SKILL.md").is_file()
PY

python3 "$target/tools/harness_team.py" check --json >"$TEMP_ROOT/team.json"
python3 "$target/tools/harness_state.py" check --json >"$TEMP_ROOT/state.json"
python3 "$target/tools/harness_eval.py" --json >"$TEMP_ROOT/eval.json"
printf 'PASS: immutable stable release-asset smoke at %s@%s (%s)\n' "$REPO" "$TAG" "$EXPECTED_SHA"
