# Agentic Project Harness

A project-scoped operating system for Codex teams. It gives a repository explicit authority, bounded delivery, transactional project state, safe stable upgrades, and evidence-backed review without asking users to learn agent orchestration jargon.

## Your company, in four names

Every project uses the same thin operating layer:

- **Management** decides outcomes, priority, scope, readiness, publication, and human-review gates.
- **Operations** plans execution, dispatches Contractors, integrates returns, and verifies results.
- **Consultants** are optional recurring experts hired for one acceptance domain.
- **Contractors** are disposable execution capacity selected by Operations for bounded assignments.

**Internal Audit** is hidden harness infrastructure. It independently evaluates orchestration behavior; it is not a project-team member, product QA, or a Consultant.

Each project has a user-overridable assurance default. Every ticket explicitly shows `Lean`, `Standard`, or `Thorough` test rigor plus any human review required before readiness, acceptance, or release, so shipping pace and validation are visible instead of implicit.

The installer gives Management and Operations professional context without changing those common names or authority boundaries:

| Preset | Management persona | Operations persona | Default Consultant |
| --- | --- | --- | --- |
| Game Development | Game Director | Producer | Art Director |
| Software Product | Product Manager | Engineering Manager | Product Designer |
| Business Operations | Program Director | Operations Manager | Change Manager |
| Research | Principal Investigator | Research Program Manager | Research Methodologist |

The default Consultant is only a recommendation. During installation, keep it, select any number from the preset menu, or choose none. Later, invoke `$hire-consultant` for another curated or schema-valid custom Consultant and `$fire-consultant` to offboard one. Consultants never own overall priority, Contractor dispatch, technical integration, or publication.

Operations chooses disposable Contractors from the selected preset’s capability bench when work is Ready. Their conversational job title is optional; users do not configure or maintain a roster.

## Install or adopt

Run the latest stable installer inside the project folder:

```sh
curl -fsSL https://github.com/FabienGreard/agentic-project-harness/releases/latest/download/install.sh | bash
```

The keyboard-first flow asks:

1. What are you building? Choose one of the four presets; there is no vague Other preset.
2. What is the project name? The current folder name is prefilled.
3. Where should it be installed? `.` is the default.
4. How much reasoning should the team use? Low, Medium, High, or Custom; Medium is selected by default.
5. Which Consultants should join? Use a multi-select list seeded with the preset default.

Arrow keys, `j`/`k`, number keys, space, and Enter cover the full flow. Set `NO_COLOR=1` for a plain terminal fallback. In a non-empty folder, the installer enters additive Adoption mode: existing files are never overwritten, renamed, deleted, staged, or committed.

For folder-aware defaults, including Software Product, Medium reasoning, and Product Designer:

```sh
curl -fsSL https://github.com/FabienGreard/agentic-project-harness/releases/latest/download/install.sh | bash -s -- --yes
```

### Copy this into an LLM

```text
Install Agentic Project Harness into the current repository using only the latest stable release.

First inspect the current directory and preserve every existing file. Run:

curl -fsSL https://github.com/FabienGreard/agentic-project-harness/releases/latest/download/install.sh | bash -s -- --yes

Then run `./install.sh status --json`, `python3 tools/harness_team.py check --json`, and `python3 tools/harness_state.py check --json`. Report the installed version, immutable provenance, selected preset and Consultants, installation status, managed-file integrity, preserved legacy files, conflicts or manual actions, and transactional backup/rollback location. If a cleanup prompt was generated, follow it without deleting user files or backups. Do not implement the project, customize governance, commit, push, publish, or release during this installation task.
```

The installed project README contains a second copy-ready prompt for first-run project definition. It is inline—there is no separate `BOOTSTRAP_PROMPT.md` to drift.

## Keep the command surface small

One script owns installation and stable updates:

```sh
./install.sh
./install.sh status
./install.sh update
```

The common flags are `--json`, `--yes`, and `--help`. Running the stable installer in a repository that already contains harness metadata detects the installation, reports its version, and offers a stable update. It never silently downgrades or consumes a prerelease.

Team changes are skill-driven:

```text
$hire-consultant
$fire-consultant
```

The skills select the right deterministic `tools/harness_team.py` operation. Hiring offers the current preset’s curated Consultants and accepts a custom JSON definition matching `docs/schemas/consultant.schema.json`. Offboarding removes only an unchanged generated config; if a user modified it, the file is preserved with an exact manual cleanup action. Both operations keep Consultant history and external transactional backup/report evidence.

## Safe versioning and updates

`.agent-harness.json` records the installed harness version, immutable stable provenance, lifecycle status, managed ownership classes, baseline checksums, migrations, and transaction IDs. `./install.sh status --json` is the local truth.

An update reconstructs the installed baseline from its allowlisted immutable stable release before comparing baseline, local state, and the target release. It fails closed on ambiguous provenance, modified harness-managed/generated files, unsupported origins, unsafe paths, or incomplete transactions. Project-owned files and unrelated work are never retired automatically. Legacy Markdown is preserved during structured-state migration, and cleanup guidance links the release, compare view, and exact GitHub files so an LLM or human can inspect every difference.

Only stable releases are update candidates. Immutable-SHA standalone smoke and the normal release gates remain mandatory before publication.

## Operational state

Canonical schema-versioned JSON under `docs/state/` records the project/baton, goals, tickets, ownership, reviews, and team. Narrative Markdown remains the source for direction, decisions, requirements, implementation reports, and supporting rationale.

Use the deterministic state tool instead of parsing Markdown or hand-editing the generated dashboard:

```sh
python3 tools/harness_state.py check --json
python3 tools/harness_state.py apply operation.json --json
```

`docs/index.html` is a self-contained local view of the canonical records, including a responsive project timeline, goal details, ticket search, and company directory. It is a generated view, not a second control plane.

This is **LLM-first and human-governed**: structures, commands, identifiers, evidence, and migration reports are optimized for reliable machine use; humans retain authority for intent, ambiguity, destructive deletion, external commitments, security/compliance, and release or publication.

## Codex configuration

Every generated project receives this project-scoped configuration:

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

`max_threads = 4` is a ceiling, not a Contractor target; an execution surface may impose a lower cap. `max_depth = 1` preserves Operations as the shallow single dispatch center. **Approve for me** / Auto-review can still be constrained by the user’s Codex app or managed workspace, and already-running conversations may retain their selected permission mode.

Reasoning presets apply to the common roles:

| Preset | Management | Operations | Consultants | Contractors | Internal Audit |
| --- | --- | --- | --- | --- | --- |
| Low | medium | medium | medium | low | high |
| Medium (default) | high | high | high | medium | xhigh |
| High | xhigh | xhigh | xhigh | high | xhigh |

Custom exposes each role individually. Supported explicit levels still depend on the selected Codex model.

## Lifecycle and review

Management, Operations, and every active Consultant are permanent top-level tasks with event-driven run-to-idle lifecycles. Each active run drains meaningful work, records the next owner/action/return trigger, and pauses without polling when no meaningful action remains.

Only Ready work executes. Operations is the sole Contractor dispatch/revision center and registers one exclusive owner per file or coherent system scope before edits. Substantial work receives independent read-only standards/architecture and specification/evidence review before Operations accepts integration. Consultant domain acceptance, Management final audit, human approval, Internal Audit, and release authorization remain separate gates.

## Preset examples and documentation

- [Game Development](examples/game-development/README.md)
- [Software Product](examples/software-product/README.md)
- [Business Operations](examples/business-operations/README.md)
- [Research](examples/research/README.md)
- [Installation and permissions](docs/installation.md)
- [Customization and custom Consultants](docs/customization.md)
- [Operating workflow](docs/workflow.md)
- [Stable release process](docs/releasing.md)

The repository itself is the reusable template. `AGENTS.md` is only a navigation map; normative behavior lives under `.agents/rules/`, project-scoped skills under `.agents/skills/`, role contracts under `docs/roles/`, and deterministic checks under `tools/` and `tests/`.

## License

MIT. Adapted skill material and attribution are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
