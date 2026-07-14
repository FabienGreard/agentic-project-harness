# Installation, updates, and permissions

Agentic Project Harness uses one `install.sh` lifecycle for fresh installation, additive adoption, status, and stable updates. Requirements are Bash, Python 3.9 or newer, `curl`, `tar`, and Git for a fresh empty-folder installation.

## Stable install

```sh
mkdir example-project && cd example-project
curl -fsSL https://github.com/FabienGreard/agentic-project-harness/releases/latest/download/install.sh | bash
```

For review-first execution:

```sh
curl -fsSLo /tmp/agentic-project-harness-install.sh \
  https://github.com/FabienGreard/agentic-project-harness/releases/latest/download/install.sh
less /tmp/agentic-project-harness-install.sh
bash /tmp/agentic-project-harness-install.sh
```

Do not substitute a moving branch, prerelease, development checkout, unverified fork, or second updater for a stable project installation.

## Interactive flow

The keyboard-first terminal asks five things:

1. **Project preset:** Software Product, Game Development, Business Operations, or Research. There is no Other/custom preset.
2. **Project name:** inferred from the destination folder.
3. **Destination:** defaults to the current directory (`.`).
4. **Reasoning:** Low, Medium, High, or Custom; Medium is selected by default.
5. **Consultants:** a multi-select list from the chosen preset, seeded with its recommended default. Keep it, add others, or select none.

Use arrow keys or `j`/`k` to move, number keys for direct choices, space to toggle Consultants, and Enter to confirm. `NO_COLOR=1` gives a plain numbered fallback.

The preset’s professional titles are written into `docs/state/team.json` and generated Codex configs, while the user-facing authority layer remains Management, Operations, Consultants, Contractors, and hidden Internal Audit.

| Preset | Management | Operations | Recommended Consultant |
| --- | --- | --- | --- |
| Game Development | Game Director | Producer | Art Director |
| Software Product | Product Manager | Engineering Manager | Product Designer |
| Business Operations | Program Director | Operations Manager | Change Manager |
| Research | Principal Investigator | Research Program Manager | Research Methodologist |

Available Consultant menus are intentionally finite during installation:

- Game Development: Art Director, Lead Game Designer, Technical Director, Narrative Director, Audio Director, QA Lead.
- Software Product: Product Designer, Principal Engineer, Security Lead, Platform/SRE Lead, Data Lead, Accessibility Lead, QA Lead.
- Business Operations: Compliance Officer, Financial Controller, Legal Counsel, Risk Manager, People Operations Lead, Data Governance Lead, Change Manager, Quality Manager.
- Research: Research Methodologist, Statistician, Research Ethics Lead, Data Steward, Reproducibility Lead, Subject-Matter Expert, Computational Research Lead.

Custom project presets are deliberately unsupported. Custom Consultants are supported later through the validated hire workflow.

## Non-interactive folder-aware defaults

```sh
curl -fsSL https://github.com/FabienGreard/agentic-project-harness/releases/latest/download/install.sh | \
  bash -s -- --yes
```

This uses the current folder name and directory, Software Product, Medium reasoning, and Product Designer. `--json` produces machine-readable output.

## Reasoning presets

| Preset | Management | Operations | Consultants | Contractors | Internal Audit |
| --- | --- | --- | --- | --- | --- |
| Low | medium | medium | medium | low | high |
| Medium (default) | high | high | high | medium | xhigh |
| High | xhigh | xhigh | xhigh | high | xhigh |

Custom asks for every common role individually. The supported level names are `inherit`, `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`; actual availability depends on the selected Codex model. `inherit` omits the role-specific override.

Internal Audit receives the former evaluator reasoning profile, but it remains hidden harness infrastructure—not part of the user’s project team and not project QA.

## Empty and non-empty folders

An empty destination receives the harness and a new Git repository without a commit. A non-empty destination enters additive Adoption mode. Existing collisions are preserved and reported; user files are never overwritten, renamed, deleted, staged, or committed.

Adoption writes `.agent-harness.json` with `Needs Integration` when collisions remain and generates an external cleanup prompt. After the user or LLM integrates the preserved paths, `./install.sh update` validates the project and records those paths as project-owned. A project-owned path is never retired automatically by future updates.

Unreadable folders, symlink traversal, ambiguous state, and injected or real write failures fail closed. Transactional rollback evidence lives outside the worktree.

## Status and stable updates

```sh
./install.sh status
./install.sh update
```

Running `./install.sh` with no subcommand detects existing harness metadata and offers the appropriate status/update flow. Updates consider only stable releases. They reconstruct the installed baseline from immutable official provenance, preserve project-owned files and unrelated work, block on modified managed/generated files, and never silently downgrade. Installation, update, canonical-state writes, and Consultant team changes share one external per-project cross-process lock so supported concurrent mutations cannot overwrite one another.

The intentionally small public lifecycle interface is:

- `./install.sh`, `./install.sh status`, `./install.sh update`
- `--json`, `--yes`, `--help`

## Hire and fire Consultants

Installation and later team changes use project-scoped skills:

```text
$hire-consultant
$fire-consultant
```

`$hire-consultant` lists the current preset’s curated Consultants and can pass a custom definition matching `docs/schemas/consultant.schema.json` to the deterministic team engine. Every Consultant must define a unique ID/title, headline, domain, readiness requirements, evidence requirements, and acceptance authority. The engine always enforces the non-authorities: overall priority, Contractor dispatch, technical integration, and publication.

`$fire-consultant` marks the Consultant inactive and keeps history through the same engine. It removes only an unchanged generated config. A modified config is preserved with an exact manual cleanup action. Decisions, reviews, reports, backups, and project files are never deleted by offboarding.

The skills are the user interface; `tools/harness_team.py` is internal deterministic plumbing, not another public root command.

## Project-scoped Codex permissions

Every generated project receives:

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
sandbox_mode = "workspace-write"

[agents]
max_threads = 4
max_depth = 1

[sandbox_workspace_write]
network_access = true
```

Four threads is a concurrency ceiling, not a Contractor target; a runtime can impose a lower cap. Depth one preserves Operations as the single dispatch center and prevents recursive Contractor fan-out. **Approve for me** / Auto-review can be constrained by the user’s Codex app or managed workspace. Existing conversations may retain their previously selected permission mode.

## First task

Open the generated `README.md` and copy its complete **First project prompt** into a new Codex task using the Management reasoning level. The prompt is inline so no bootstrap file can drift. It is governance-only: establish direction, confirm the configured company, prepare canonical state, and leave one explicit baton before project implementation begins.

Management, Operations, and active Consultants are permanent top-level tasks woken only by new task messages. They never operate persistent Codex goals, even when complete controls exist. Current repository policy supersedes older onboarding prompts; legacy automatic continuations perform no speculative work and are reported for removal.

## Local candidate testing

To test an unpublished checkout without using GitHub:

```sh
tmp=$(mktemp -d)
cd "$tmp"
bash /absolute/path/to/agentic-project-harness/install.sh --yes
./install.sh status --json
python3 tools/harness_team.py check --json
python3 tools/harness_state.py check --json
```

The repository’s complete candidate gates are documented in [releasing.md](releasing.md). Local-development installs are test fixtures, not stable upgrade origins.
