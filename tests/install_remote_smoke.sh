#!/usr/bin/env bash
set -eu

REPO=${BATON_REPO:-${HARNESS_REPO:-FabienGreard/baton}}
TAG=${1:-}
EXPECTED_SHA=${2:-}
[ -n "$TAG" ] && [ -n "$EXPECTED_SHA" ] || {
  printf 'Usage: bash tests/install_remote_smoke.sh STABLE_TAG EXPECTED_COMMIT_SHA\n' >&2
  exit 2
}

case "$EXPECTED_SHA" in
  *[!0-9a-f]*|'')
    printf 'EXPECTED_COMMIT_SHA must be a lowercase hexadecimal SHA.\n' >&2
    exit 2
    ;;
esac
[ "${#EXPECTED_SHA}" -eq 40 ] || {
  printf 'EXPECTED_COMMIT_SHA must contain exactly 40 hexadecimal characters.\n' >&2
  exit 2
}

TEMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/baton-remote-smoke.XXXXXX")
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT HUP INT TERM

bundle="$TEMP_ROOT/bundle"
target="$TEMP_ROOT/remote-project"
state_home="$TEMP_ROOT/external-state"
mkdir -p "$bundle" "$target" "$state_home"
for asset in install.sh baton-new-project.tar.gz baton-adoption.tar.gz baton-manifest.json SHA256SUMS; do
  curl -fsSL "https://github.com/$REPO/releases/download/$TAG/$asset" -o "$bundle/$asset"
done

(
  cd "$target"
  BATON_RELEASE_DIR="$bundle" \
  HOME="$TEMP_ROOT/home" \
  PYTHONDONTWRITEBYTECODE=1 \
  XDG_STATE_HOME="$state_home" \
    bash "$bundle/install.sh" --yes --json >"$TEMP_ROOT/install.json"
)

PYTHONDONTWRITEBYTECODE=1 python3 - "$target" "$bundle" "$REPO" "$TAG" "$EXPECTED_SHA" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

root, bundle = map(Path, sys.argv[1:3])
repository, tag, expected_sha = sys.argv[3:]
sys.path.insert(0, str(root / ".baton/lib"))
from codex_config_contract import assert_codex_config

manifest_path = bundle / "baton-manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
metadata = json.loads((root / ".baton/metadata.json").read_text(encoding="utf-8"))
assert manifest["schema"] == "baton.release-bundle/v1"
assert manifest["channel"] == "stable"
assert manifest["stableTag"] == tag
assert manifest["source"]["repository"] == repository
assert manifest["source"]["commit"] == expected_sha
assert metadata["schemaVersion"] == 3
assert metadata["installationStatus"] == "Installed"
assert metadata["source"] == {
    "repository": repository,
    "channel": "stable",
    "tag": tag,
    "commit": expected_sha,
    "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
}
assert {path.name for path in root.iterdir()} == {
    ".git", ".baton", ".agents", ".codex", "AGENTS.md"
}
assert not (root / ".codex/skills").exists()
assert not (root / ".codex/skills").is_symlink()
assert not (root / "install.sh").exists()
team = json.loads((root / ".baton/state/team.json").read_text(encoding="utf-8"))
assert team["preset"] == "software-product"
assert [item["id"] for item in team["consultants"] if item["status"] == "active"] == [
    "product-designer"
]
assert {path.name for path in (root / ".baton/agents").glob("*.toml")} == {
    "management.toml",
    "operations.toml",
    "contractor.toml",
    "internal-audit.toml",
    "consultant-product-designer.toml",
}
assert_codex_config(
    root / ".codex/config.toml",
    [
        "management",
        "operations",
        "contractor",
        "internal_audit",
        "consultant_product_designer",
    ],
)
for link in (root / ".agents/skills").iterdir():
    assert link.is_symlink()
    assert link.resolve().parent == (root / ".baton/skills").resolve()
assert not list(root.rglob("__pycache__"))
assert not list(root.rglob("*.pyc"))
PY

PYTHONDONTWRITEBYTECODE=1 XDG_STATE_HOME="$state_home" \
  "$target/.baton/bin/baton" status --json >"$TEMP_ROOT/status.json"
PYTHONDONTWRITEBYTECODE=1 XDG_STATE_HOME="$state_home" \
  "$target/.baton/bin/baton" check --json >"$TEMP_ROOT/check.json"
printf 'PASS: immutable Baton stable release smoke at %s@%s (%s)\n' "$REPO" "$TAG" "$EXPECTED_SHA"
