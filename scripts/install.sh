#!/usr/bin/env bash
set -eu

OFFICIAL_REPO="FabienGreard/baton"
COMMAND="smart"
ASSUME_YES=0
AS_JSON=0
USE_ANSI=0
STYLE_RESET=""
STYLE_BOLD=""
STYLE_MUTED=""
STYLE_ACCENT=""
STYLE_WARNING=""
TEMP_DIR=""
TARGET_OVERRIDE=""

usage() {
  cat <<'EOF'
Baton stable installer and updater for Codex

Usage:
  ./install.sh                 Install, adopt, or update from the stable channel

Options:
  --json                       Emit structured JSON where applicable
  --yes                        Confirm safe planned writes without prompting
  --target PATH                Install or update PATH instead of the current folder
  --help                       Show this help

The installer uses official stable GitHub release assets only. --yes never
authorizes deletion of project files, preserved legacy files, or backups.
EOF
}

die() {
  if [ "$AS_JSON" -eq 1 ]; then
    python3 - "$*" <<'PY'
import json, sys
print(json.dumps({"ok": False, "error": sys.argv[1]}))
PY
  else
    printf 'Error: %s\n' "$*" >&2
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
    *) printf 'No changes made.\n'; exit 0 ;;
  esac
}

menu_select() {
  menu_prompt="$1"
  selected="$2"
  shift 2
  menu_options=("$@")
  menu_count=${#menu_options[@]}
  if [ "$USE_ANSI" -eq 0 ]; then
    while :; do
      printf '\n%s\n' "$menu_prompt" >&3
      menu_i=0
      while [ "$menu_i" -lt "$menu_count" ]; do
        default=""
        [ "$menu_i" -ne "$selected" ] || default=" [default]"
        printf '  %d) %s%s\n' "$((menu_i + 1))" "${menu_options[$menu_i]}" "$default" >&3
        menu_i=$((menu_i + 1))
      done
      printf 'Choose 1-%d [%d]: ' "$menu_count" "$((selected + 1))" >&3
      IFS= read -r answer <&3 || die "interactive input ended unexpectedly"
      [ -n "$answer" ] || answer=$((selected + 1))
      case "$answer" in
        *[!0-9]*|'') printf 'Choose one of the listed numbers.\n' >&3 ;;
        *)
          if [ "$answer" -ge 1 ] && [ "$answer" -le "$menu_count" ]; then
            printf '%s' "$((answer - 1))"
            return
          fi
          printf 'Choose one of the listed numbers.\n' >&3
          ;;
      esac
    done
  fi
  printf '\n%s%s%s\n' "$STYLE_BOLD" "$menu_prompt" "$STYLE_RESET" >&3
  while :; do
    menu_i=0
    while [ "$menu_i" -lt "$menu_count" ]; do
      printf '\033[2K\r' >&3
      if [ "$menu_i" -eq "$selected" ]; then
        printf '  %s›%s %s%s%s\n' "$STYLE_ACCENT" "$STYLE_RESET" "$STYLE_BOLD" "${menu_options[$menu_i]}" "$STYLE_RESET" >&3
      else
        printf '    %s%s%s\n' "$STYLE_MUTED" "${menu_options[$menu_i]}" "$STYLE_RESET" >&3
      fi
      menu_i=$((menu_i + 1))
    done
    printf '\033[2K\r  %s↑/↓ or j/k · Enter select · 1-%d quick select%s\n' "$STYLE_MUTED" "$menu_count" "$STYLE_RESET" >&3
    IFS= read -r -s -n 1 key <&3 || die "interactive input ended unexpectedly"
    if [ "$key" = $'\033' ]; then
      suffix=""
      IFS= read -r -s -n 2 -t 1 suffix <&3 || true
      key="$key$suffix"
    fi
    confirm=0
    case "$key" in
      ''|$'\r'|$'\n') confirm=1 ;;
      $'\033[A'|k|K) selected=$(((selected + menu_count - 1) % menu_count)) ;;
      $'\033[B'|j|J) selected=$(((selected + 1) % menu_count)) ;;
      [1-9])
        number=$((key - 1))
        if [ "$number" -lt "$menu_count" ]; then selected="$number"; confirm=1; fi
        ;;
    esac
    if [ "$confirm" -eq 1 ]; then printf '\n' >&3; printf '%s' "$selected"; return; fi
    printf '\033[%dA' "$((menu_count + 1))" >&3
  done
}

menu_multi_select() {
  multi_prompt="$1"
  multi_defaults="$2"
  shift 2
  multi_options=("$@")
  multi_count=${#multi_options[@]}
  multi_cursor=0
  multi_marks=()
  multi_i=0
  while [ "$multi_i" -lt "$multi_count" ]; do
    multi_marks[$multi_i]=0
    case ",$multi_defaults," in *",$multi_i,"*) multi_marks[$multi_i]=1 ;; esac
    multi_i=$((multi_i + 1))
  done
  if [ "$USE_ANSI" -eq 0 ]; then
    printf '\n%s\n' "$multi_prompt" >&3
    multi_i=0
    while [ "$multi_i" -lt "$multi_count" ]; do
      marker=" "
      [ "${multi_marks[$multi_i]}" -eq 0 ] || marker="x"
      printf '  %d) [%s] %s\n' "$((multi_i + 1))" "$marker" "${multi_options[$multi_i]}" >&3
      multi_i=$((multi_i + 1))
    done
    printf "Choose comma-separated numbers, 'none', or Enter for defaults: " >&3
    IFS= read -r answer <&3 || die "interactive input ended unexpectedly"
    if [ -n "$answer" ]; then
      multi_i=0
      while [ "$multi_i" -lt "$multi_count" ]; do multi_marks[$multi_i]=0; multi_i=$((multi_i + 1)); done
      if [ "$answer" != "none" ]; then
        old_ifs=$IFS; IFS=,
        for number in $answer; do
          IFS=$old_ifs
          case "$number" in *[!0-9]*|'') die "Consultant selection must use listed numbers" ;; esac
          [ "$number" -ge 1 ] && [ "$number" -le "$multi_count" ] || die "Consultant selection is out of range"
          multi_marks[$((number - 1))]=1
          IFS=,
        done
        IFS=$old_ifs
      fi
    fi
  else
    printf '\n%s%s%s\n' "$STYLE_BOLD" "$multi_prompt" "$STYLE_RESET" >&3
    while :; do
      multi_i=0
      while [ "$multi_i" -lt "$multi_count" ]; do
        marker="○"
        [ "${multi_marks[$multi_i]}" -eq 0 ] || marker="●"
        printf '\033[2K\r' >&3
        if [ "$multi_i" -eq "$multi_cursor" ]; then
          printf '  %s›%s %s %s%s%s\n' "$STYLE_ACCENT" "$STYLE_RESET" "$marker" "$STYLE_BOLD" "${multi_options[$multi_i]}" "$STYLE_RESET" >&3
        else
          printf '    %s %s%s%s\n' "$marker" "$STYLE_MUTED" "${multi_options[$multi_i]}" "$STYLE_RESET" >&3
        fi
        multi_i=$((multi_i + 1))
      done
      printf '\033[2K\r  %s↑/↓ or j/k · Space toggle · Enter continue%s\n' "$STYLE_MUTED" "$STYLE_RESET" >&3
      IFS= read -r -s -n 1 key <&3 || die "interactive input ended unexpectedly"
      if [ "$key" = $'\033' ]; then
        suffix=""
        IFS= read -r -s -n 2 -t 1 suffix <&3 || true
        key="$key$suffix"
      fi
      case "$key" in
        ''|$'\r'|$'\n') printf '\n' >&3; break ;;
        $'\033[A'|k|K) multi_cursor=$(((multi_cursor + multi_count - 1) % multi_count)) ;;
        $'\033[B'|j|J) multi_cursor=$(((multi_cursor + 1) % multi_count)) ;;
        ' ') if [ "${multi_marks[$multi_cursor]}" -eq 1 ]; then multi_marks[$multi_cursor]=0; else multi_marks[$multi_cursor]=1; fi ;;
      esac
      printf '\033[%dA' "$((multi_count + 1))" >&3
    done
  fi
  result=""
  multi_i=0
  while [ "$multi_i" -lt "$multi_count" ]; do
    if [ "${multi_marks[$multi_i]}" -eq 1 ]; then
      [ -z "$result" ] || result="$result,"
      result="$result$multi_i"
    fi
    multi_i=$((multi_i + 1))
  done
  printf '%s' "$result"
}

prompt_text() {
  label="$1"
  default="$2"
  printf '\n%s%s%s\n' "$STYLE_BOLD" "$label" "$STYLE_RESET" >&3
  printf '  %sDefault: %s%s\n  %s›%s ' "$STYLE_MUTED" "$default" "$STYLE_RESET" "$STYLE_ACCENT" "$STYLE_RESET" >&3
  IFS= read -r answer <&3 || die "interactive input ended unexpectedly"
  if [ -n "$answer" ]; then printf '%s' "$answer"; else printf '%s' "$default"; fi
}

reasoning_index() {
  case "$1" in
    inherit) printf 0 ;; none) printf 1 ;; minimal) printf 2 ;; low) printf 3 ;;
    medium) printf 4 ;; high) printf 5 ;; xhigh) printf 6 ;; max) printf 7 ;; ultra) printf 8 ;;
  esac
}

prompt_reasoning() {
  role="$1"; default="$2"
  choice=$(menu_select "$role reasoning" "$(reasoning_index "$default")" \
    "Inherit — use the parent Codex setting" "None — no explicit reasoning" \
    "Minimal — lowest explicit effort" "Low — fast bounded work" \
    "Medium — balanced execution" "High — careful project work" \
    "XHigh — deep reasoning" "Max — model-dependent maximum" \
    "Ultra — model-dependent extended effort")
  case "$choice" in
    0) printf inherit ;; 1) printf none ;; 2) printf minimal ;; 3) printf low ;;
    4) printf medium ;; 5) printf high ;; 6) printf xhigh ;; 7) printf max ;; 8) printf ultra ;;
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

EARLY_METADATA=0
[ ! -f "$TARGET/.baton/metadata.json" ] || EARLY_METADATA=1
[ ! -f "$TARGET/.agent-harness.json" ] || EARLY_METADATA=1
if [ "$EARLY_METADATA" -eq 1 ]; then
  COMMAND="update"
  confirm_update
elif [ "$COMMAND" = "smart" ] && [ "$ASSUME_YES" -eq 0 ]; then
  [ -t 1 ] && [ -r /dev/tty ] && [ -w /dev/tty ] || die "interactive installation needs a terminal; use --yes for folder-aware defaults"
  exec 3<>/dev/tty
  if [ -z "${NO_COLOR:-}" ] && [ "${TERM:-}" != "dumb" ]; then
    USE_ANSI=1
    STYLE_RESET=$'\033[0m'; STYLE_BOLD=$'\033[1m'; STYLE_MUTED=$'\033[2m'
    STYLE_ACCENT=$'\033[38;5;81m'; STYLE_WARNING=$'\033[38;5;214m'
  fi
  printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$STYLE_ACCENT" "$STYLE_RESET" >&3
  printf '%s│%s  %sBATON%s                                      %s│%s\n' "$STYLE_ACCENT" "$STYLE_RESET" "$STYLE_BOLD" "$STYLE_RESET" "$STYLE_ACCENT" "$STYLE_RESET" >&3
  printf '%s│%s  Stable install, adoption, and safe updates  %s│%s\n' "$STYLE_ACCENT" "$STYLE_RESET" "$STYLE_ACCENT" "$STYLE_RESET" >&3
  printf '%s╰──────────────────────────────────────────────╯%s\n' "$STYLE_ACCENT" "$STYLE_RESET" >&3

  type_choice=$(menu_select "What are you building?" 0 \
    "Software Product — app, service, platform, or library" \
    "Game Development — playable or interactive experience" \
    "Business Operations — process, policy, or service delivery" \
    "Research — investigation or evidence program")
  case "$type_choice" in
    0) PROJECT_TYPE=software-product ;; 1) PROJECT_TYPE=game-development ;;
    2) PROJECT_TYPE=business-operations ;; 3) PROJECT_TYPE=research ;;
  esac
  PROJECT_NAME=$(prompt_text "Project name" "$PROJECT_NAME")
  TARGET=$(prompt_text "Where should Baton be installed?" ".")
  preset_choice=$(menu_select "How much reasoning should the team use?" 1 \
    "Low — medium leadership/Consultants, low Contractors, high Internal Audit" \
    "Medium — high leadership/Consultants, medium Contractors, xhigh Internal Audit (recommended)" \
    "High — xhigh leadership/Consultants, high Contractors/Internal Audit" \
    "Custom — choose every role individually")
  case "$preset_choice" in
    0)
      REASONING_PRESET=low; MANAGEMENT_REASONING=medium; OPERATIONS_REASONING=medium
      CONSULTANT_REASONING=medium; CONTRACTOR_REASONING=low; AUDIT_REASONING=high
      ;;
    1)
      REASONING_PRESET=medium
      ;;
    2)
      REASONING_PRESET=high; MANAGEMENT_REASONING=xhigh; OPERATIONS_REASONING=xhigh
      CONSULTANT_REASONING=xhigh; CONTRACTOR_REASONING=high; AUDIT_REASONING=xhigh
      ;;
    3)
      REASONING_PRESET=custom
      MANAGEMENT_REASONING=$(prompt_reasoning "Management" "$MANAGEMENT_REASONING")
      OPERATIONS_REASONING=$(prompt_reasoning "Operations" "$OPERATIONS_REASONING")
      CONSULTANT_REASONING=$(prompt_reasoning "Consultants" "$CONSULTANT_REASONING")
      CONTRACTOR_REASONING=$(prompt_reasoning "Contractors" "$CONTRACTOR_REASONING")
      AUDIT_REASONING=$(prompt_reasoning "Internal Audit" "$AUDIT_REASONING")
      ;;
  esac
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
  if [ "$ASSUME_YES" -eq 1 ]; then
    CONSULTANTS_JSON=$(python3 "$TEAM_ENGINE" catalog --preset "$PROJECT_TYPE" --field defaults --json)
  else
    CONSULTANT_IDS=()
    CONSULTANT_OPTIONS=()
    while IFS=$'\t' read -r consultant_id consultant_title consultant_headline; do
      [ -n "$consultant_id" ] || continue
      CONSULTANT_IDS+=("$consultant_id")
      CONSULTANT_OPTIONS+=("$consultant_title — $consultant_headline")
    done < <(python3 "$TEAM_ENGINE" catalog --preset "$PROJECT_TYPE" --field consultants)
    DEFAULT_CONSULTANT_IDS=$(python3 "$TEAM_ENGINE" catalog --preset "$PROJECT_TYPE" --field defaults --json)
    DEFAULT_INDEXES=$(python3 - "$DEFAULT_CONSULTANT_IDS" "${CONSULTANT_IDS[@]}" <<'PY'
import json, sys
defaults = set(json.loads(sys.argv[1]))
print(",".join(str(index) for index, value in enumerate(sys.argv[2:]) if value in defaults))
PY
)
    SELECTED_INDEXES=$(menu_multi_select "Hire your starting Consultants (recommendation selected)" "$DEFAULT_INDEXES" "${CONSULTANT_OPTIONS[@]}")
    SELECTED_IDS=""
    old_ifs=$IFS; IFS=,
    for index in $SELECTED_INDEXES; do
      IFS=$old_ifs
      [ -z "$SELECTED_IDS" ] || SELECTED_IDS="$SELECTED_IDS,"
      SELECTED_IDS="$SELECTED_IDS${CONSULTANT_IDS[$index]}"
      IFS=,
    done
    IFS=$old_ifs
    CONSULTANTS_JSON=$(python3 - "$SELECTED_IDS" <<'PY'
import json, sys
print(json.dumps([value for value in sys.argv[1].split(",") if value]))
PY
)
  fi
fi

if [ "$HAS_METADATA" -eq 1 ]; then
  set -- python3 "$ENGINE" update --project-root "$TARGET" --payload-root "$PAYLOAD_ROOT" \
    --payload adoption --manifest "$MANIFEST_PATH" --manifest-sha256 "$MANIFEST_SHA"
else
  set -- python3 "$ENGINE" install --project-root "$TARGET" --payload-root "$PAYLOAD_ROOT" \
    --payload "$PAYLOAD" --manifest "$MANIFEST_PATH" --manifest-sha256 "$MANIFEST_SHA" \
    --project-name "$PROJECT_NAME" --project-type "$PROJECT_TYPE" \
    --reasoning-preset "$REASONING_PRESET" --reasoning-json "$REASONING_JSON" \
    --consultants-json "$CONSULTANTS_JSON"
fi
[ "$AS_JSON" -eq 0 ] || set -- "$@" --json
"$@"
