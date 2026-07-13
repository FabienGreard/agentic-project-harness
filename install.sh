#!/usr/bin/env bash
set -eu

DEFAULT_REPO="FabienGreard/agentic-project-harness"
DEFAULT_REF="main"
DEFAULT_DIRECTOR_REASONING="high"
DEFAULT_DELIVERY_REASONING="high"
DEFAULT_SPECIALIST_REASONING="high"
DEFAULT_WORKER_REASONING="medium"
DEFAULT_EVALUATOR_REASONING="high"

PROJECT_NAME=""
TARGET=""
REPO="$DEFAULT_REPO"
REF="$DEFAULT_REF"
DIRECTOR_REASONING="$DEFAULT_DIRECTOR_REASONING"
DELIVERY_REASONING="$DEFAULT_DELIVERY_REASONING"
SPECIALIST_REASONING="$DEFAULT_SPECIALIST_REASONING"
WORKER_REASONING="$DEFAULT_WORKER_REASONING"
EVALUATOR_REASONING="$DEFAULT_EVALUATOR_REASONING"
SPECIALIST_MODE="ask"
ASSUME_YES=0
NO_GIT=0
DRY_RUN=0
SOURCE_MODE="remote"
SOURCE_DIR=""
SOURCE_METADATA_REF="$REF"
SOURCE_REVISION=""
SOURCE_DIRTY="unknown"

usage() {
  cat <<'EOF'
Agentic Project Harness installer for Codex

Usage:
  bash install.sh [options]

Required in non-interactive mode:
  --project-name NAME             Human-readable project name
  --target DIRECTORY              New empty destination
  --yes                           Disable prompts and accept safe defaults

Per-role Codex reasoning:
  --director-reasoning LEVEL      Default: high
  --delivery-reasoning LEVEL      Default: high
  --worker-reasoning LEVEL        Default: medium
  --evaluator-reasoning LEVEL     Default: high
  --with-specialist               Include the optional Specialist Lead
  --without-specialist            Omit the optional Specialist Lead
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

prompt_text() {
  label="$1"
  default="$2"
  printf '%s [%s]: ' "$label" "$default" >&3
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
  while :; do
    answer=$(prompt_text "$role reasoning (inherit/none/minimal/low/medium/high/xhigh/max/ultra)" "$default")
    case "$answer" in
      inherit|none|minimal|low|medium|high|xhigh|max|ultra)
        printf '%s' "$answer"
        return
        ;;
      *) printf 'Choose a documented reasoning level. Model support varies.\n' >&3 ;;
    esac
  done
}

prompt_yes_no() {
  label="$1"
  default="$2"
  while :; do
    printf '%s [%s]: ' "$label" "$default" >&3
    IFS= read -r answer <&3 || die "interactive input ended unexpectedly"
    [ -n "$answer" ] || answer="$default"
    case "$answer" in
      y|Y|yes|YES|Yes) printf 'yes'; return ;;
      n|N|no|NO|No) printf 'no'; return ;;
      *) printf 'Answer yes or no.\n' >&3 ;;
    esac
  done
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
      shift 2
      ;;
    --delivery-reasoning)
      need_value "$@"
      DELIVERY_REASONING="$2"
      shift 2
      ;;
    --specialist-reasoning)
      need_value "$@"
      SPECIALIST_REASONING="$2"
      [ "$SPECIALIST_MODE" != "ask" ] || SPECIALIST_MODE="yes"
      shift 2
      ;;
    --worker-reasoning)
      need_value "$@"
      WORKER_REASONING="$2"
      shift 2
      ;;
    --evaluator-reasoning)
      need_value "$@"
      EVALUATOR_REASONING="$2"
      shift 2
      ;;
    --with-specialist)
      SPECIALIST_MODE="yes"
      shift
      ;;
    --without-specialist)
      SPECIALIST_MODE="no"
      shift
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

if [ "$ASSUME_YES" -eq 0 ]; then
  if [ ! -t 1 ] || [ ! -r /dev/tty ] || [ ! -w /dev/tty ]; then
    die "interactive installation needs a terminal; use --yes with explicit --project-name and --target"
  fi
  exec 3<>/dev/tty
  printf '\nAgentic Project Harness for Codex\n' >&3
  printf 'No model is pinned. You choose how much reasoning each role should use.\n\n' >&3
  PROJECT_NAME=$(prompt_text "Project name" "My Project")
  default_target="./$(printf '%s' "$PROJECT_NAME" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9._-' | sed 's/--*/-/g; s/^-//; s/-$//')"
  [ "$default_target" != "./" ] || default_target="./my-project"
  TARGET=$(prompt_text "New project directory" "$default_target")
  if [ "$SPECIALIST_MODE" = "ask" ]; then
    SPECIALIST_MODE=$(prompt_yes_no "Include an optional Specialist Lead?" "no")
  fi
  DIRECTOR_REASONING=$(prompt_reasoning "Project Director" "$DIRECTOR_REASONING")
  DELIVERY_REASONING=$(prompt_reasoning "Delivery Lead" "$DELIVERY_REASONING")
  if [ "$SPECIALIST_MODE" = "yes" ]; then
    SPECIALIST_REASONING=$(prompt_reasoning "Specialist Lead" "$SPECIALIST_REASONING")
  fi
  WORKER_REASONING=$(prompt_reasoning "Execution worker" "$WORKER_REASONING")
  EVALUATOR_REASONING=$(prompt_reasoning "Harness Evaluator" "$EVALUATOR_REASONING")
else
  [ -n "$PROJECT_NAME" ] || die "--project-name is required with --yes"
  [ -n "$TARGET" ] || die "--target is required with --yes"
  [ "$SPECIALIST_MODE" != "ask" ] || SPECIALIST_MODE="no"
fi

[ -n "$PROJECT_NAME" ] || die "project name cannot be empty"
[ -n "$TARGET" ] || die "target cannot be empty"
case "$PROJECT_NAME" in
  *$'\n'*|*$'\r'*) die "project name cannot contain newlines" ;;
esac
case "$TARGET" in
  *$'\n'*|*$'\r'*) die "target cannot contain newlines" ;;
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
SOURCE_METADATA_REF="$REF"

command -v python3 >/dev/null 2>&1 || die "python3 is required"
TARGET_ABS=$(python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)
TARGET="$TARGET_ABS"

if [ -e "$TARGET" ]; then
  [ -d "$TARGET" ] || die "target exists and is not a directory: $TARGET"
  [ -z "$(find "$TARGET" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ] || die "target must be empty: $TARGET"
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
printf '  Target: %s\n' "$TARGET"
if [ "$SOURCE_MODE" = "local" ]; then
  printf '  Source: local working tree (%s)\n' "$SOURCE_DIR"
else
  printf '  Source: %s @ %s\n' "$REPO" "$REF"
fi
printf '  Project Director: %s\n' "$DIRECTOR_REASONING"
printf '  Delivery Lead: %s\n' "$DELIVERY_REASONING"
if [ "$SPECIALIST_MODE" = "yes" ]; then
  printf '  Specialist Lead: %s\n' "$SPECIALIST_REASONING"
else
  printf '  Specialist Lead: omitted\n'
fi
printf '  Execution worker: %s\n' "$WORKER_REASONING"
printf '  Harness Evaluator: %s\n' "$EVALUATOR_REASONING"
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

python3 - "$INSTALL_DIR" "$PROJECT_NAME" "$REPO" "$SOURCE_METADATA_REF" "$SOURCE_MODE" "$SOURCE_REVISION" "$SOURCE_DIRTY" "$DIRECTOR_REASONING" "$DELIVERY_REASONING" "$SPECIALIST_REASONING" "$WORKER_REASONING" "$EVALUATOR_REASONING" "$SPECIALIST_MODE" <<'PY'
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    target_raw,
    project_name,
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
    specialist_mode,
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
    "specialistLead": specialist_reasoning if specialist_mode == "yes" else None,
    "executionWorker": worker_reasoning,
    "harnessEvaluator": evaluator_reasoning,
}
metadata = {
    "schemaVersion": 1,
    "harnessVersion": (target / "VERSION").read_text(encoding="utf-8").strip(),
    "provider": "codex",
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
    if filename == "specialist-lead.toml" and specialist_mode != "yes":
        path.unlink(missing_ok=True)
        continue
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

specialist_row = (
    f"| Specialist Lead | `{specialist_reasoning}` |"
    if specialist_mode == "yes"
    else "| Specialist Lead | Not installed |"
)
reasoning_table = "\n".join(
    [
        "| Agent role | Reasoning |",
        "| --- | --- |",
        f"| Project Director | `{director_reasoning}` |",
        f"| Delivery Lead | `{delivery_reasoning}` |",
        specialist_row,
        f"| Execution worker | `{worker_reasoning}` |",
        f"| Harness Evaluator | `{evaluator_reasoning}` |",
    ]
)

project_readme = f"""# {project_name}

This project was initialized from [Agentic Project Harness](https://github.com/{source_repo}) for Codex.

## Start here

1. Review [BOOTSTRAP_PROMPT.md](BOOTSTRAP_PROMPT.md).
2. Review the Codex role settings under `.codex/agents/`.
3. Open this directory in Codex using the Project Director reasoning level and ask it to follow the bootstrap prompt.
4. Approve the customized governance baseline before implementation begins.

## Configured reasoning

{reasoning_table}

Explicit level support depends on the Codex model selected at runtime. `inherit` means no role-specific override is written.

The reusable harness documentation is preserved in [HARNESS.md](HARNESS.md).
"""
source_readme.write_text(project_readme, encoding="utf-8")

bootstrap = f"""# First Codex bootstrap prompt

Configured role reasoning:

{reasoning_table}

Explicit level support depends on the model selected in Codex. Give the following instruction to the first Codex task opened in this repository:

> Bootstrap **{project_name}** using the repository harness. First read `AGENTS.md`, `.codex/config.toml`, the active role configurations under `.codex/agents/`, `docs/overview.md`, `docs/direction.md`, `docs/backlog.md`, `docs/active-work.md`, `docs/project-state.json`, `docs/workflow.md`, and the relevant role instructions completely. Verify the live repository before trusting starter claims.
>
> This first run is governance-only: do not implement the project, install an application stack, contact external systems, publish, or invent product/business direction. Ask me only for decisions that materially change the intended outcome, constraints, human-review gates, or permanent roles. Then customize the direction, overview, role registry, first decision/requirement/ticket, and machine-readable state. Keep all execution non-Ready until its dependencies and acceptance are explicit. When the current Codex surface supports separate permanent tasks, register the Project Director and Delivery Lead as separate tasks using the configured reasoning levels; register a Specialist Lead only if its recurring authority boundary is approved. Run `python3 tools/harness_eval.py --strict`, report any remaining blockers, and leave the next baton and wake trigger explicit.
"""
(target / "BOOTSTRAP_PROMPT.md").write_text(bootstrap, encoding="utf-8")
PY

printf '\nRunning static harness checks inside the new project...\n'
python3 "$INSTALL_DIR/tools/harness_eval.py"

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
printf '  Bootstrap: %s/BOOTSTRAP_PROMPT.md\n' "$TARGET_ABS"
printf '  Codex roles: %s/.codex/agents\n' "$TARGET_ABS"
if [ -n "$CODEX_PATH" ]; then
  printf '  Codex detected: %s\n' "$CODEX_PATH"
else
  printf '  Codex CLI not detected; use the desktop or IDE surface, or install the CLI later.\n'
fi
printf '\nNext: open the project in Codex at Project Director reasoning `%s` and ask it to read BOOTSTRAP_PROMPT.md.\n' "$DIRECTOR_REASONING"
if [ "$NO_GIT" -eq 0 ]; then
  printf 'Git was initialized on main. Nothing was staged or committed.\n'
fi
