#!/usr/bin/env bash
set -eu

OFFICIAL_REPO="FabienGreard/baton"
COMMAND="smart"
ASSUME_YES=0
AS_JSON=0
TEMP_DIR=""
TARGET_OVERRIDE=""

usage() {
  cat <<'EOF'
Baton stable installer and updater for AI agent teams

Usage:
  ./install.sh                 Install, adopt, or auto-detect a stable update
  ./install.sh update          Update an existing supported installation

Options:
  --json                       Emit structured JSON where applicable
  --yes                        Confirm safe planned writes without prompting
  --target PATH                Install or update PATH instead of the current folder
  --help                       Show this help

Examples:
  ./install.sh
  ./install.sh --target /absolute/project --yes --json
  ./install.sh update --target /absolute/project --yes --json

The installer uses official stable GitHub release assets only. --yes never
authorizes deletion of Repository files, preserved legacy files, or backups.
After installation, invoke `$boot` through your agent. Use
`.baton/bin/baton boot status --json` only to inspect installation status.
EOF
}

die() {
  if [ "$AS_JSON" -eq 1 ]; then
    python3 - "$*" <<'PY'
import json, sys
print(json.dumps({"ok": False, "error": sys.argv[1]}))
PY
  else
    printf '\nBaton / installer\nAttention required: %s\n' "$*" >&2
  fi
  exit 1
}

cleanup() {
  [ -z "$TEMP_DIR" ] || rm -rf "$TEMP_DIR"
}
trap cleanup EXIT HUP INT TERM

case "${1:-}" in
  update)
    COMMAND="$1"
    shift
    ;;
esac

while [ "$#" -gt 0 ]; do
  case "$1" in
    --json) AS_JSON=1 ;;
    --yes) ASSUME_YES=1 ;;
    --target)
      shift
      [ "$#" -gt 0 ] || die "--target requires a path"
      TARGET_OVERRIDE="$1"
      ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    *) die "unknown option or command: $1" ;;
  esac
  shift
done
[ "$#" -eq 0 ] || die "unexpected positional arguments: $*"

command -v python3 >/dev/null 2>&1 || die "python3 is required"

CURRENT_ROOT=$(pwd -P)

confirm_update() {
  [ "$ASSUME_YES" -eq 0 ] || return 0
  [ -r /dev/tty ] && [ -w /dev/tty ] || die "an existing Baton installation was detected; rerun with --yes or use a terminal"
  printf '\nUpdate to the latest stable release? [y/N] ' >/dev/tty
  IFS= read -r answer </dev/tty || die "interactive input ended unexpectedly"
  case "$answer" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) printf '\nBaton / upgrade\nNo changes were made.\n'; exit 0 ;;
  esac
}

PROJECT_TYPE="software-product"
TARGET="${TARGET_OVERRIDE:-$CURRENT_ROOT}"
PROJECT_NAME=$(python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().absolute().name)
PY
)
[ -n "$PROJECT_NAME" ] || PROJECT_NAME="My Project"
REASONING_PRESET="medium"
MANAGEMENT_REASONING="high"
OPERATIONS_REASONING="high"
CONSULTANT_REASONING="high"
CONTRACTOR_REASONING="medium"
AUDIT_REASONING="xhigh"
CONSULTANTS_JSON="[]"
READINESS_PROTOCOL="Standard Protocol"
CLEARANCE_PROTOCOL="Release Clearance"

EARLY_METADATA=0
[ ! -f "$TARGET/.baton/metadata.json" ] || EARLY_METADATA=1
[ ! -f "$TARGET/.agent-harness.json" ] || EARLY_METADATA=1
if [ "$EARLY_METADATA" -eq 1 ]; then
  COMMAND="update"
  confirm_update
fi

TARGET=$(python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().absolute())
PY
)
REASONING_JSON=$(printf '{"management":"%s","operations":"%s","consultants":"%s","contractors":"%s","internalAudit":"%s"}' \
  "$MANAGEMENT_REASONING" "$OPERATIONS_REASONING" "$CONSULTANT_REASONING" "$CONTRACTOR_REASONING" "$AUDIT_REASONING")

PAYLOAD_ROOT=""
MANIFEST_PATH=""
MANIFEST_SHA=""
PAYLOAD=""

download_bundle() {
  command -v tar >/dev/null 2>&1 || die "tar is required"
  command -v curl >/dev/null 2>&1 || [ -n "${BATON_RELEASE_DIR:-}" ] || die "curl is required for stable installation and updates"
  TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/baton.XXXXXX")
  bundle="$TEMP_DIR/bundle"
  mkdir -p "$bundle"
  for asset in install.sh baton-new-project.tar.gz baton-adoption.tar.gz baton-manifest.json SHA256SUMS; do
    if [ -n "${BATON_RELEASE_DIR:-}" ]; then
      cp "$BATON_RELEASE_DIR/$asset" "$bundle/$asset"
    else
      [ "$AS_JSON" -eq 1 ] || printf 'Downloading latest stable Baton...\n' >&2
      curl -fsSL "https://github.com/$OFFICIAL_REPO/releases/latest/download/$asset" -o "$bundle/$asset"
    fi
  done
  PAYLOAD_ROOT="$TEMP_DIR/payload"
  mkdir -p "$PAYLOAD_ROOT"
  MANIFEST_SHA=$(python3 - "$bundle" "$PAYLOAD_ROOT" "$PAYLOAD" <<'PY'
import hashlib, json, os, sys, tarfile
from pathlib import Path, PurePosixPath

bundle, target = map(Path, sys.argv[1:3])
payload = sys.argv[3]
expected = {}
for line in (bundle / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    parts = line.split("  ")
    if len(parts) != 2 or parts[1] in expected:
        raise SystemExit("invalid SHA256SUMS")
    expected[parts[1]] = parts[0]
required = {"install.sh", "baton-new-project.tar.gz", "baton-adoption.tar.gz", "baton-manifest.json"}
if set(expected) != required:
    raise SystemExit("SHA256SUMS does not match the stable bundle contract")
for name, digest in expected.items():
    actual = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"checksum mismatch: {name}")
manifest = json.loads((bundle / "baton-manifest.json").read_text(encoding="utf-8"))
if manifest.get("schema") != "baton.release-bundle/v1" or manifest.get("channel") != "stable":
    raise SystemExit("release manifest is not stable")
if manifest.get("stableTag") != "v" + str(manifest.get("version")):
    raise SystemExit("release tag and version do not match")
record = manifest.get("payloads", {}).get(payload)
if not isinstance(record, dict):
    raise SystemExit("release manifest does not contain the selected payload")
archive_name = record.get("artifact")
if archive_name not in {"baton-new-project.tar.gz", "baton-adoption.tar.gz"}:
    raise SystemExit("selected payload artifact is invalid")
archive = tarfile.open(bundle / archive_name, "r:gz")
with archive:
    members = archive.getmembers()
    names = set()
    symlinks = set()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
            raise SystemExit(f"unsafe archive path: {member.name}")
        if member.name in names:
            raise SystemExit(f"duplicate archive path: {member.name}")
        names.add(member.name)
        if member.issym():
            symlinks.add(path)
    for member in members:
        path = PurePosixPath(member.name)
        if any(parent in symlinks for parent in path.parents):
            raise SystemExit(f"archive path passes through a symlink: {member.name}")
        destination = target.joinpath(*path.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if member.isfile():
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"cannot read archive member: {member.name}")
            destination.write_bytes(source.read())
            destination.chmod(member.mode & 0o777)
        elif member.issym():
            link = PurePosixPath(member.linkname)
            if link.is_absolute():
                raise SystemExit(f"unsafe archive symlink: {member.name}")
            resolved = (destination.parent / member.linkname).resolve(strict=False)
            if target.resolve() != resolved and target.resolve() not in resolved.parents:
                raise SystemExit(f"archive symlink escapes target: {member.name}")
            destination.symlink_to(member.linkname)
        else:
            raise SystemExit(f"unsupported archive entry: {member.name}")
print(hashlib.sha256((bundle / "baton-manifest.json").read_bytes()).hexdigest())
PY
  ) || die "stable release bundle verification failed"
  MANIFEST_PATH="$bundle/baton-manifest.json"
}

HAS_METADATA=0
[ ! -f "$TARGET/.baton/metadata.json" ] || HAS_METADATA=1
HAS_LEGACY=0
[ ! -f "$TARGET/.agent-harness.json" ] || HAS_LEGACY=1
if [ "$COMMAND" = "update" ] && [ "$HAS_METADATA" -eq 0 ] && [ "$HAS_LEGACY" -eq 0 ]; then
  die "update requires an existing Baton or supported legacy installation"
fi
if [ "$HAS_METADATA" -eq 1 ] || [ "$HAS_LEGACY" -eq 1 ]; then
  COMMAND="update"
  PAYLOAD="adoption"
elif [ -d "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
  PAYLOAD="adoption"
else
  PAYLOAD="new-project"
fi

download_bundle

ENGINE="$PAYLOAD_ROOT/.baton/lib/baton_lifecycle.py"
[ -f "$ENGINE" ] || die "verified source is missing the lifecycle engine"
TEAM_ENGINE="$PAYLOAD_ROOT/.baton/lib/harness_team.py"
[ -f "$TEAM_ENGINE" ] || die "verified source is missing the team engine"

if [ "$COMMAND" = "smart" ] && [ "$HAS_METADATA" -eq 0 ] && [ "$HAS_LEGACY" -eq 0 ]; then
  CONSULTANTS_JSON=$(python3 "$TEAM_ENGINE" catalog --preset "$PROJECT_TYPE" --field defaults --json)
fi

if [ "$HAS_METADATA" -eq 1 ]; then
  set -- python3 "$ENGINE" update --project-root "$TARGET" --payload-root "$PAYLOAD_ROOT" \
    --payload adoption --manifest "$MANIFEST_PATH" --manifest-sha256 "$MANIFEST_SHA"
else
  set -- python3 "$ENGINE" install --project-root "$TARGET" --payload-root "$PAYLOAD_ROOT" \
    --payload "$PAYLOAD" --manifest "$MANIFEST_PATH" --manifest-sha256 "$MANIFEST_SHA" \
    --project-name "$PROJECT_NAME" --project-type "$PROJECT_TYPE" \
    --readiness-protocol "$READINESS_PROTOCOL" --clearance-protocol "$CLEARANCE_PROTOCOL" \
    --reasoning-preset "$REASONING_PRESET" --reasoning-json "$REASONING_JSON" \
    --consultants-json "$CONSULTANTS_JSON"
fi
[ "$AS_JSON" -eq 0 ] || set -- "$@" --json
"$@"
