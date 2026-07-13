#!/usr/bin/env bash
set -eu

DEFAULT_REPO="FabienGreard/agentic-project-harness"
DEFAULT_REF="main"
DEFAULT_PROJECT_TYPE="software-product"
DEFAULT_REASONING_PRESET="balanced"
DEFAULT_DIRECTOR_REASONING="high"
DEFAULT_DELIVERY_REASONING="high"
DEFAULT_SPECIALIST_REASONING="high"
DEFAULT_WORKER_REASONING="medium"
DEFAULT_EVALUATOR_REASONING="xhigh"

PROJECT_NAME=""
TARGET=""
PROJECT_TYPE="$DEFAULT_PROJECT_TYPE"
REASONING_PRESET="$DEFAULT_REASONING_PRESET"
REPO="$DEFAULT_REPO"
REF="$DEFAULT_REF"
DIRECTOR_REASONING="$DEFAULT_DIRECTOR_REASONING"
DELIVERY_REASONING="$DEFAULT_DELIVERY_REASONING"
SPECIALIST_REASONING="$DEFAULT_SPECIALIST_REASONING"
WORKER_REASONING="$DEFAULT_WORKER_REASONING"
EVALUATOR_REASONING="$DEFAULT_EVALUATOR_REASONING"
ASSUME_YES=0
NO_GIT=0
DRY_RUN=0
SOURCE_MODE="remote"
SOURCE_DIR=""
SOURCE_METADATA_REF="$REF"
SOURCE_REVISION=""
SOURCE_DIRTY="unknown"
USE_ANSI=0
STYLE_RESET=""
STYLE_BOLD=""
STYLE_MUTED=""
STYLE_ACCENT=""
STYLE_SUCCESS=""
STYLE_WARNING=""
DIRECTOR_REASONING_SET=0
DELIVERY_REASONING_SET=0
SPECIALIST_REASONING_SET=0
WORKER_REASONING_SET=0
EVALUATOR_REASONING_SET=0

usage() {
  cat <<'EOF'
Agentic Project Harness installer for Codex

Usage:
  bash install.sh [options]

Required in non-interactive mode:
  --project-name NAME             Human-readable project name
  --target DIRECTORY              New empty destination
  --yes                           Disable prompts and accept safe defaults

Project setup:
  --project-type TYPE             software-product, game-development,
                                  business-operations, research, or other
  --reasoning-preset PRESET       balanced, deep, or custom; default: balanced

Per-role Codex reasoning:
  --director-reasoning LEVEL      Default: high
  --delivery-reasoning LEVEL      Default: high
  --worker-reasoning LEVEL        Default: medium
  --evaluator-reasoning LEVEL     Default: xhigh
  --specialist-reasoning LEVEL    Default: high

Other options:
  --repo OWNER/NAME               Public template repository
  --ref REF                       Branch or tag to download; default: main
  --no-git                        Do not initialize a new Git repository
  --dry-run                       Validate and print the plan without writing
  --help                          Show this help

Reasoning LEVEL:
  inherit, none, minimal, low, medium, high, xhigh, max, or ultra

Explicit reasoning support depends on the model selected in Codex. The
installer does not select or pin a model and never changes global Codex config.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

need_value() {
  [ "$#" -ge 2 ] || die "$1 requires a value"
}

validate_reasoning() {
  case "$2" in
    inherit|none|minimal|low|medium|high|xhigh|max|ultra) ;;
    *) die "$1 must be one of: inherit, none, minimal, low, medium, high, xhigh, max, ultra" ;;
  esac
}

validate_project_type() {
  case "$1" in
    software-product|game-development|business-operations|research|other) ;;
    *) die "--project-type must be one of: software-product, game-development, business-operations, research, other" ;;
  esac
}

validate_reasoning_preset() {
  case "$1" in
    balanced|deep|custom) ;;
    *) die "--reasoning-preset must be one of: balanced, deep, custom" ;;
  esac
}

project_type_label() {
  case "$1" in
    software-product) printf 'Software / product' ;;
    game-development) printf 'Game development' ;;
    business-operations) printf 'Business operations' ;;
    research) printf 'Research / knowledge work' ;;
    other) printf 'Other' ;;
  esac
}

project_type_index() {
  case "$1" in
    software-product) printf '0' ;;
    game-development) printf '1' ;;
    business-operations) printf '2' ;;
    research) printf '3' ;;
    other) printf '4' ;;
  esac
}

reasoning_preset_index() {
  case "$1" in
    balanced) printf '0' ;;
    deep) printf '1' ;;
    custom) printf '2' ;;
  esac
}

reasoning_index() {
  case "$1" in
    inherit) printf '0' ;;
    none) printf '1' ;;
    minimal) printf '2' ;;
    low) printf '3' ;;
    medium) printf '4' ;;
    high) printf '5' ;;
    xhigh) printf '6' ;;
    max) printf '7' ;;
    ultra) printf '8' ;;
  esac
}

apply_reasoning_preset() {
  case "$REASONING_PRESET" in
    balanced)
      [ "$DIRECTOR_REASONING_SET" -eq 1 ] || DIRECTOR_REASONING="high"
      [ "$DELIVERY_REASONING_SET" -eq 1 ] || DELIVERY_REASONING="high"
      [ "$SPECIALIST_REASONING_SET" -eq 1 ] || SPECIALIST_REASONING="high"
      [ "$WORKER_REASONING_SET" -eq 1 ] || WORKER_REASONING="medium"
      [ "$EVALUATOR_REASONING_SET" -eq 1 ] || EVALUATOR_REASONING="xhigh"
      ;;
    deep)
      [ "$DIRECTOR_REASONING_SET" -eq 1 ] || DIRECTOR_REASONING="xhigh"
      [ "$DELIVERY_REASONING_SET" -eq 1 ] || DELIVERY_REASONING="xhigh"
      [ "$SPECIALIST_REASONING_SET" -eq 1 ] || SPECIALIST_REASONING="xhigh"
      [ "$WORKER_REASONING_SET" -eq 1 ] || WORKER_REASONING="high"
      [ "$EVALUATOR_REASONING_SET" -eq 1 ] || EVALUATOR_REASONING="xhigh"
      ;;
    custom) ;;
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
        menu_default=""
        [ "$menu_i" -ne "$selected" ] || menu_default=" [default]"
        printf '  %d) %s%s\n' "$((menu_i + 1))" "${menu_options[$menu_i]}" "$menu_default" >&3
        menu_i=$((menu_i + 1))
      done
      printf 'Choose 1-%d [%d]: ' "$menu_count" "$((selected + 1))" >&3
      IFS= read -r menu_answer <&3 || die "interactive input ended unexpectedly"
      [ -n "$menu_answer" ] || menu_answer=$((selected + 1))
      case "$menu_answer" in
        *[!0-9]*|'') printf 'Choose one of the listed numbers.\n' >&3 ;;
        *)
          if [ "$menu_answer" -ge 1 ] && [ "$menu_answer" -le "$menu_count" ]; then
            printf '%s' "$((menu_answer - 1))"
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

    IFS= read -r -s -n 1 menu_key <&3 || die "interactive input ended unexpectedly"
    if [ "$menu_key" = $'\033' ]; then
      menu_suffix=""
      IFS= read -r -s -n 2 -t 1 menu_suffix <&3 || true
      menu_key="$menu_key$menu_suffix"
    fi

    menu_confirm=0
    case "$menu_key" in
      ''|$'\r'|$'\n') menu_confirm=1 ;;
      $'\033[A'|k|K) selected=$(((selected + menu_count - 1) % menu_count)) ;;
      $'\033[B'|j|J) selected=$(((selected + 1) % menu_count)) ;;
      [1-9])
        menu_number=$((menu_key - 1))
        if [ "$menu_number" -lt "$menu_count" ]; then
          selected="$menu_number"
          menu_confirm=1
        fi
        ;;
    esac

    if [ "$menu_confirm" -eq 1 ]; then
      printf '\n' >&3
      printf '%s' "$selected"
      return
    fi
    printf '\033[%dA' "$((menu_count + 1))" >&3
  done
}

prompt_text() {
  label="$1"
  default="$2"
  printf '\n%s%s%s\n' "$STYLE_BOLD" "$label" "$STYLE_RESET" >&3
  printf '  %sDefault: %s%s\n  %s›%s ' "$STYLE_MUTED" "$default" "$STYLE_RESET" "$STYLE_ACCENT" "$STYLE_RESET" >&3
  IFS= read -r answer <&3 || die "interactive input ended unexpectedly"
  if [ -n "$answer" ]; then
    printf '%s' "$answer"
  else
    printf '%s' "$default"
  fi
}

prompt_reasoning() {
  role="$1"
  default="$2"
  choice=$(menu_select "$role reasoning" "$(reasoning_index "$default")" \
    "Inherit — use the parent Codex setting" \
    "None — no explicit reasoning" \
    "Minimal — lowest explicit effort" \
    "Low — fast bounded work" \
    "Medium — balanced execution" \
    "High — careful project work" \
    "XHigh — deep reasoning" \
    "Max — model-dependent maximum" \
    "Ultra — model-dependent extended effort")
  case "$choice" in
    0) printf 'inherit' ;;
    1) printf 'none' ;;
    2) printf 'minimal' ;;
    3) printf 'low' ;;
    4) printf 'medium' ;;
    5) printf 'high' ;;
    6) printf 'xhigh' ;;
    7) printf 'max' ;;
    8) printf 'ultra' ;;
  esac
}

target_is_unavailable() {
  [ ! -L "$1" ] || return 0
  [ -e "$1" ] || return 1
  [ -d "$1" ] || return 0
  target_entry=$(find "$1" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null) || return 0
  [ -n "$target_entry" ]
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project-name)
      need_value "$@"
      PROJECT_NAME="$2"
      shift 2
      ;;
    --target)
      need_value "$@"
      TARGET="$2"
      shift 2
      ;;
    --project-type)
      need_value "$@"
      PROJECT_TYPE="$2"
      shift 2
      ;;
    --reasoning-preset)
      need_value "$@"
      REASONING_PRESET="$2"
      shift 2
      ;;
    --repo)
      need_value "$@"
      REPO="$2"
      shift 2
      ;;
    --ref)
      need_value "$@"
      REF="$2"
      shift 2
      ;;
    --director-reasoning)
      need_value "$@"
      DIRECTOR_REASONING="$2"
      DIRECTOR_REASONING_SET=1
      shift 2
      ;;
    --delivery-reasoning)
      need_value "$@"
      DELIVERY_REASONING="$2"
      DELIVERY_REASONING_SET=1
      shift 2
      ;;
    --specialist-reasoning)
      need_value "$@"
      SPECIALIST_REASONING="$2"
      SPECIALIST_REASONING_SET=1
      shift 2
      ;;
    --worker-reasoning)
      need_value "$@"
      WORKER_REASONING="$2"
      WORKER_REASONING_SET=1
      shift 2
      ;;
    --evaluator-reasoning)
      need_value "$@"
      EVALUATOR_REASONING="$2"
      EVALUATOR_REASONING_SET=1
      shift 2
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --no-git)
      NO_GIT=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *) die "unknown option: $1" ;;
  esac
done

[ "$#" -eq 0 ] || die "unexpected positional arguments: $*"
validate_project_type "$PROJECT_TYPE"
validate_reasoning_preset "$REASONING_PRESET"

if [ "$ASSUME_YES" -eq 0 ]; then
  if [ ! -t 1 ] || [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
    die "interactive installation needs a terminal; use --yes with explicit --project-name and --target"
  fi
  exec 3<>/dev/tty
  if [ -z "${NO_COLOR:-}" ] && [ "${TERM:-}" != "dumb" ]; then
    USE_ANSI=1
    STYLE_RESET=$'\033[0m'
    STYLE_BOLD=$'\033[1m'
    STYLE_MUTED=$'\033[2m'
    STYLE_ACCENT=$'\033[38;5;81m'
    STYLE_SUCCESS=$'\033[38;5;84m'
    STYLE_WARNING=$'\033[38;5;214m'
  fi

  printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$STYLE_ACCENT" "$STYLE_RESET" >&3
  printf '%s│%s  %sAGENTIC PROJECT HARNESS%s                     %s│%s\n' "$STYLE_ACCENT" "$STYLE_RESET" "$STYLE_BOLD" "$STYLE_RESET" "$STYLE_ACCENT" "$STYLE_RESET" >&3
  printf '%s│%s  Bootstrap a Codex-native project in minutes  %s│%s\n' "$STYLE_ACCENT" "$STYLE_RESET" "$STYLE_ACCENT" "$STYLE_RESET" >&3
  printf '%s╰──────────────────────────────────────────────╯%s\n' "$STYLE_ACCENT" "$STYLE_RESET" >&3

  type_choice=$(menu_select "What are you building?" "$(project_type_index "$PROJECT_TYPE")" \
    "Software / product — app, service, platform, or library" \
    "Game development — playable or interactive experience" \
    "Business operations — process, policy, or service delivery" \
    "Research / knowledge work — investigation or evidence program" \
    "Other — start from the generic harness")
  case "$type_choice" in
    0) PROJECT_TYPE="software-product" ;;
    1) PROJECT_TYPE="game-development" ;;
    2) PROJECT_TYPE="business-operations" ;;
    3) PROJECT_TYPE="research" ;;
    4) PROJECT_TYPE="other" ;;
  esac

  folder_name=$(basename "$PWD")
  case "$folder_name" in
    ''|'/'|'.') folder_name="My Project" ;;
  esac
  PROJECT_NAME=$(prompt_text "Project name" "$folder_name")
  TARGET=$(prompt_text "Where should the harness be installed?" ".")
  fallback_target="./$(printf '%s' "$PROJECT_NAME" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9._-' | sed 's/--*/-/g; s/^-//; s/-$//')"
  [ "$fallback_target" != "./" ] || fallback_target="./my-project"
  while target_is_unavailable "$TARGET"; do
    printf '\n  %s!%s %sThat location is not empty or cannot be safely inspected.%s Existing files are never overwritten.\n' "$STYLE_WARNING" "$STYLE_RESET" "$STYLE_BOLD" "$STYLE_RESET" >&3
    TARGET=$(prompt_text "Choose a new empty directory" "$fallback_target")
  done

  preset_choice=$(menu_select "How much reasoning should the team use?" "$(reasoning_preset_index "$REASONING_PRESET")" \
    "Balanced — high leads, medium workers, xhigh evaluator (recommended)" \
    "Deep — xhigh leads, high workers, xhigh evaluator" \
    "Custom — choose every role individually")
  case "$preset_choice" in
    0) REASONING_PRESET="balanced" ;;
    1) REASONING_PRESET="deep" ;;
    2) REASONING_PRESET="custom" ;;
  esac
  apply_reasoning_preset

  if [ "$REASONING_PRESET" = "custom" ]; then
    DIRECTOR_REASONING=$(prompt_reasoning "Project Director" "$DIRECTOR_REASONING")
    DELIVERY_REASONING=$(prompt_reasoning "Delivery Lead" "$DELIVERY_REASONING")
    SPECIALIST_REASONING=$(prompt_reasoning "Specialist Lead" "$SPECIALIST_REASONING")
    WORKER_REASONING=$(prompt_reasoning "Execution worker" "$WORKER_REASONING")
    EVALUATOR_REASONING=$(prompt_reasoning "Harness Evaluator" "$EVALUATOR_REASONING")
  fi
else
  [ -n "$PROJECT_NAME" ] || die "--project-name is required with --yes"
  [ -n "$TARGET" ] || die "--target is required with --yes"
  apply_reasoning_preset
fi

[ -n "$PROJECT_NAME" ] || die "project name cannot be empty"
[ -n "$TARGET" ] || die "target cannot be empty"
case "$PROJECT_NAME" in
  *$'\n'*|*$'\r'*) die "project name cannot contain newlines" ;;
esac
case "$TARGET" in
  *$'\n'*|*$'\r'*) die "target cannot contain newlines" ;;
esac
case "/$TARGET/" in
  *'/../'*) die "target cannot contain .. path segments" ;;
esac
case "$REPO" in
  */*) ;;
  *) die "--repo must use OWNER/NAME form" ;;
esac
case "$REPO" in
  *[!A-Za-z0-9._/-]*|*//*|/*|*/) die "--repo contains unsupported characters" ;;
esac
case "${REPO#*/}" in
  */*) die "--repo must contain exactly one slash in OWNER/NAME form" ;;
esac
case "$REF" in
  ""|*..*|*[!A-Za-z0-9._/-]*|-*) die "--ref contains unsupported characters" ;;
esac

validate_reasoning "--director-reasoning" "$DIRECTOR_REASONING"
validate_reasoning "--delivery-reasoning" "$DELIVERY_REASONING"
validate_reasoning "--specialist-reasoning" "$SPECIALIST_REASONING"
validate_reasoning "--worker-reasoning" "$WORKER_REASONING"
validate_reasoning "--evaluator-reasoning" "$EVALUATOR_REASONING"
validate_project_type "$PROJECT_TYPE"
validate_reasoning_preset "$REASONING_PRESET"
SOURCE_METADATA_REF="$REF"

command -v python3 >/dev/null 2>&1 || die "python3 is required"
if python3 - "$TARGET" <<'PY'
import os
import stat
import sys
from pathlib import Path

raw_path = Path(os.path.expanduser(sys.argv[1]))
if raw_path.is_absolute():
    path = Path(os.path.abspath(raw_path))
else:
    path = Path(os.path.abspath(Path.cwd().resolve() / raw_path))
for candidate in (path, *path.parents):
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError:
        continue
    if stat.S_ISLNK(mode):
        raise SystemExit(0)
raise SystemExit(1)
PY
then
  die "target path must not be or pass through a symbolic link: $TARGET"
fi
TARGET_ABS=$(python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)
TARGET="$TARGET_ABS"

if [ -e "$TARGET" ]; then
  [ -d "$TARGET" ] || die "target exists and is not a directory: $TARGET"
  TARGET_ENTRY=$(find "$TARGET" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null) || die "target cannot be safely inspected: $TARGET"
  [ -z "$TARGET_ENTRY" ] || die "target must be empty: $TARGET"
fi

SCRIPT_SOURCE=${BASH_SOURCE[0]:-}
if [ -n "$SCRIPT_SOURCE" ] && [ -f "$SCRIPT_SOURCE" ]; then
  SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_SOURCE")" 2>/dev/null && pwd)
  if [ -f "$SCRIPT_DIR/AGENTS.md" ] && [ -f "$SCRIPT_DIR/tools/harness_eval.py" ]; then
    SOURCE_MODE="local"
    SOURCE_DIR="$SCRIPT_DIR"
    SOURCE_METADATA_REF="local-working-tree"
    if command -v git >/dev/null 2>&1 && git -C "$SOURCE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      SOURCE_REVISION=$(git -C "$SOURCE_DIR" rev-parse HEAD 2>/dev/null || true)
      if [ -n "$(git -C "$SOURCE_DIR" status --porcelain 2>/dev/null || true)" ]; then
        SOURCE_DIRTY="true"
      else
        SOURCE_DIRTY="false"
      fi
    fi
  fi
fi

printf '\nInstall plan\n'
printf '  Project: %s\n' "$PROJECT_NAME"
printf '  Type: %s\n' "$(project_type_label "$PROJECT_TYPE")"
printf '  Target: %s\n' "$TARGET"
if [ "$SOURCE_MODE" = "local" ]; then
  printf '  Source: local working tree (%s)\n' "$SOURCE_DIR"
else
  printf '  Source: %s @ %s\n' "$REPO" "$REF"
fi
printf '  Project Director: %s\n' "$DIRECTOR_REASONING"
printf '  Delivery Lead: %s\n' "$DELIVERY_REASONING"
printf '  Specialist Lead: %s\n' "$SPECIALIST_REASONING"
printf '  Execution worker: %s\n' "$WORKER_REASONING"
printf '  Harness Evaluator: %s\n' "$EVALUATOR_REASONING"
printf '  Reasoning preset: %s\n' "$REASONING_PRESET"
printf '  Initialize Git: %s\n' "$([ "$NO_GIT" -eq 1 ] && printf 'no' || printf 'yes')"

if [ "$DRY_RUN" -eq 1 ]; then
  printf '\nDry run complete; no files were written.\n'
  exit 0
fi

command -v tar >/dev/null 2>&1 || die "tar is required"
if [ "$NO_GIT" -eq 0 ]; then
  command -v git >/dev/null 2>&1 || die "git is required unless --no-git is used"
fi

TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/agentic-project-harness.XXXXXX")
TARGET_PREEXISTED=0
TARGET_POPULATED=0
INSTALL_COMPLETE=0
[ -d "$TARGET" ] && TARGET_PREEXISTED=1
cleanup() {
  if [ "$INSTALL_COMPLETE" -eq 0 ] && [ "$TARGET_POPULATED" -eq 1 ]; then
    if [ "$TARGET_PREEXISTED" -eq 1 ]; then
      find "$TARGET" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    else
      rm -rf "$TARGET"
    fi
  fi
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' HUP TERM

if [ "$SOURCE_MODE" = "remote" ]; then
  command -v curl >/dev/null 2>&1 || die "curl is required when install.sh is run outside the template checkout"
  SOURCE_ARCHIVE="$TEMP_DIR/source.tar.gz"
  SOURCE_DIR="$TEMP_DIR/source"
  mkdir -p "$SOURCE_DIR"
  printf '\nDownloading %s @ %s...\n' "$REPO" "$REF"
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/$REF" -o "$SOURCE_ARCHIVE"
  tar -xzf "$SOURCE_ARCHIVE" -C "$SOURCE_DIR" --strip-components=1
  [ -f "$SOURCE_DIR/AGENTS.md" ] || die "downloaded source is not an Agentic Project Harness checkout"
fi

TEMPLATE_ARCHIVE="$TEMP_DIR/template.tar"
SOURCE_ABS=$(python3 - "$SOURCE_DIR" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)
TARGET_EXCLUDE=""
case "$TARGET_ABS/" in
  "$SOURCE_ABS"/*)
    TARGET_EXCLUDE=${TARGET_ABS#"$SOURCE_ABS"/}
    ;;
esac

if [ -n "$TARGET_EXCLUDE" ]; then
  tar -C "$SOURCE_DIR" --exclude='.git' --exclude='.artifacts' --exclude='__pycache__' --exclude='*.pyc' --exclude="$TARGET_EXCLUDE" -cf "$TEMPLATE_ARCHIVE" .
else
  tar -C "$SOURCE_DIR" --exclude='.git' --exclude='.artifacts' --exclude='__pycache__' --exclude='*.pyc' -cf "$TEMPLATE_ARCHIVE" .
fi
INSTALL_DIR="$TEMP_DIR/install"
mkdir -p "$INSTALL_DIR"
tar -xf "$TEMPLATE_ARCHIVE" -C "$INSTALL_DIR"

python3 - "$INSTALL_DIR" "$PROJECT_NAME" "$PROJECT_TYPE" "$REASONING_PRESET" "$REPO" "$SOURCE_METADATA_REF" "$SOURCE_MODE" "$SOURCE_REVISION" "$SOURCE_DIRTY" "$DIRECTOR_REASONING" "$DELIVERY_REASONING" "$SPECIALIST_REASONING" "$WORKER_REASONING" "$EVALUATOR_REASONING" <<'PY'
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    target_raw,
    project_name,
    project_type,
    reasoning_preset,
    source_repo,
    source_ref,
    source_mode,
    source_revision,
    source_dirty_raw,
    director_reasoning,
    delivery_reasoning,
    specialist_reasoning,
    worker_reasoning,
    evaluator_reasoning,
) = sys.argv[1:]

target = Path(target_raw).resolve()
today = datetime.now(timezone.utc).date().isoformat()
installed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

state_path = target / "docs/project-state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
state["project"]["name"] = project_name
state["project"]["agentProvider"] = "codex"
state["project"]["lastVerified"] = today
state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

reasoning = {
    "projectDirector": director_reasoning,
    "deliveryLead": delivery_reasoning,
    "specialistLead": specialist_reasoning,
    "executionWorker": worker_reasoning,
    "harnessEvaluator": evaluator_reasoning,
}
metadata = {
    "schemaVersion": 1,
    "harnessVersion": (target / "VERSION").read_text(encoding="utf-8").strip(),
    "provider": "codex",
    "projectType": project_type,
    "reasoningPreset": reasoning_preset,
    "source": source_repo,
    "ref": source_ref,
    "sourceMode": source_mode,
    "sourceRevision": source_revision or None,
    "sourceDirty": None if source_dirty_raw == "unknown" else source_dirty_raw == "true",
    "installed": True,
    "installedAt": installed_at,
    "reasoning": reasoning,
}
(target / ".agent-harness.json").write_text(
    json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)

agent_settings = {
    "project-director.toml": director_reasoning,
    "delivery-lead.toml": delivery_reasoning,
    "specialist-lead.toml": specialist_reasoning,
    "execution-worker.toml": worker_reasoning,
    "harness-evaluator.toml": evaluator_reasoning,
}
for filename, level in agent_settings.items():
    path = target / ".codex/agents" / filename
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^model_reasoning_effort = "[^"]+"\n', "", text, flags=re.MULTILINE)
    if level != "inherit":
        marker = re.search(r'^description = .*\n', text, flags=re.MULTILINE)
        if marker is None:
            raise RuntimeError(f"missing description in {path}")
        text = text[: marker.end()] + f'model_reasoning_effort = "{level}"\n' + text[marker.end() :]
    path.write_text(text, encoding="utf-8")

source_readme = target / "README.md"
harness_readme = target / "HARNESS.md"
source_readme.replace(harness_readme)

reasoning_table = "\n".join(
    [
        "| Agent role | Reasoning |",
        "| --- | --- |",
        f"| Project Director | `{director_reasoning}` |",
        f"| Delivery Lead | `{delivery_reasoning}` |",
        f"| Specialist Lead | `{specialist_reasoning}` |",
        f"| Execution worker | `{worker_reasoning}` |",
        f"| Harness Evaluator | `{evaluator_reasoning}` |",
    ]
)

project_type_labels = {
    "software-product": "Software / product",
    "game-development": "Game development",
    "business-operations": "Business operations",
    "research": "Research / knowledge work",
    "other": "Other",
}
project_type_label = project_type_labels[project_type]
overlay_instruction = {
    "game-development": "Read `examples/game-development/README.md` as optional domain guidance.",
    "business-operations": "Read `examples/business-operations/README.md` as optional domain guidance.",
}.get(project_type, "Use `docs/customization.md` to adapt role names and review gates only after direction is verified.")

first_project_prompt = f"""Bootstrap {project_name} using the repository harness. It was categorized during installation as {project_type_label}; treat that only as onboarding context, never as permission to invent direction. {overlay_instruction}

First read AGENTS.md, the applicable rules under .agents/rules/, the project-scoped skills under .agents/skills/ (discovered through .codex/skills), .codex/config.toml, the active role configurations under .codex/agents/, docs/overview.md, docs/direction.md, docs/backlog.md, docs/active-work.md, docs/project-state.json, docs/workflow.md, and the relevant role instructions completely. Verify the live repository before trusting starter claims.

This first project run is governance-only: do not implement the project, install an application stack, contact external systems, publish, or invent product or business direction. Ask me only for decisions that materially change the intended outcome, constraints, human-review gates, or permanent roles. Then customize the direction, overview, role registry, first decision or requirement or ticket, and machine-readable state. Keep all execution non-Ready until dependencies and acceptance are explicit. When the current Codex surface supports separate permanent tasks, register the Project Director, Delivery Lead, and Specialist Lead as separate tasks using the configured reasoning levels. Keep the Specialist Lead dormant until a recurring expert authority domain is approved. Run python3 tools/harness_eval.py --strict, report any remaining blockers, and leave the next baton and wake trigger explicit."""

project_readme = f"""# {project_name}

This project was initialized from [Agentic Project Harness](https://github.com/{source_repo}) for Codex.

- Project type: **{project_type_label}**
- Reasoning setup: **{reasoning_preset}**
- Codex permissions: **on-request approval with Auto-review in a workspace-write sandbox**

## Start here

1. Review `AGENTS.md` and the Codex role settings under `.codex/agents/`.
2. Open this directory in Codex using the Project Director reasoning level.
3. Copy the complete **First project prompt** below into that task.
4. Approve the customized governance baseline before implementation begins.

## First project prompt

```text
{first_project_prompt}
```

## Configured reasoning

{reasoning_table}

Explicit level support depends on the Codex model selected at runtime. `inherit` means no role-specific override is written.

The reusable harness documentation is preserved in [HARNESS.md](HARNESS.md).
"""
source_readme.write_text(project_readme, encoding="utf-8")
PY

printf '\nRunning static harness checks inside the new project...\n'
python3 "$INSTALL_DIR/tools/harness_eval.py"

[ -L "$INSTALL_DIR/.codex/skills" ] || die "generated project is missing the .codex/skills discovery symlink"
[ "$(readlink "$INSTALL_DIR/.codex/skills")" = "../.agents/skills" ] || die "generated .codex/skills link must be relative to ../.agents/skills"
[ -d "$INSTALL_DIR/.codex/skills" ] || die "generated .codex/skills discovery link does not resolve"

if [ "$NO_GIT" -eq 0 ]; then
  if ! git -C "$INSTALL_DIR" init -q -b main 2>/dev/null; then
    git -C "$INSTALL_DIR" init -q
    git -C "$INSTALL_DIR" symbolic-ref HEAD refs/heads/main
  fi
fi

FINAL_ARCHIVE="$TEMP_DIR/final.tar"
tar -C "$INSTALL_DIR" --exclude='__pycache__' --exclude='*.pyc' -cf "$FINAL_ARCHIVE" .
mkdir -p "$TARGET"
TARGET_POPULATED=1
tar -xf "$FINAL_ARCHIVE" -C "$TARGET"
INSTALL_COMPLETE=1

CODEX_PATH=""
if command -v codex >/dev/null 2>&1; then
  CODEX_PATH=$(command -v codex)
elif [ -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]; then
  CODEX_PATH="/Applications/ChatGPT.app/Contents/Resources/codex"
fi

printf '\nInstallation complete.\n'
printf '  Project: %s\n' "$TARGET_ABS"
printf '  First project prompt: %s/README.md\n' "$TARGET_ABS"
printf '  Codex roles: %s/.codex/agents\n' "$TARGET_ABS"
if [ -n "$CODEX_PATH" ]; then
  printf '  Codex detected: %s\n' "$CODEX_PATH"
else
  printf '  Codex CLI not detected; use the desktop or IDE surface, or install the CLI later.\n'
fi
printf '\nNext: open the project in Codex at Project Director reasoning `%s`.\n' "$DIRECTOR_REASONING"
printf 'Copy the `First project prompt` block from README.md into the task.\n\n'
if [ "$NO_GIT" -eq 0 ]; then
  printf 'Git was initialized on main. Nothing was staged or committed.\n'
fi
