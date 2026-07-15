# Installation, adoption, and stable updates

Baton uses one temporary stable-URL bootstrapper for initial installation, mature adoption, legacy migration, and update bootstrapping. The bootstrapper is never installed into the consumer. Once Baton is installed, the public project-local surface is `.baton/bin/baton status`, `update`, and `check`.

> **Availability:** v0.6.0 is an unpublished candidate. The `FabienGreard/baton` stable URLs in this document become usable only after a separate human-authorized release. Do not install from this branch, a source archive, a prerelease, or an unverified fork.

## Requirements

- Bash
- Python 3.9 or newer
- `curl` and `tar`
- Git for empty-project initialization and normal repository use

The installer writes no dependency environment and installs no package. Baton remains dependency-free Python and shell inside the project.

## Stable installer

After a stable release exists, run:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash
```

For review-first execution:

```sh
curl -fsSLo /tmp/baton-install.sh \
  https://github.com/FabienGreard/baton/releases/latest/download/install.sh
less /tmp/baton-install.sh
bash /tmp/baton-install.sh
```

The supported options are:

```text
--target PATH   use PATH instead of the current directory
--yes           confirm safe planned writes without a terminal prompt
--json          emit structured JSON where applicable
--help          show usage
```

`--yes` never authorizes deletion of project files, preserved legacy files, transaction evidence, or backups.

The installer downloads exactly five assets from the latest official stable release: `install.sh`, `baton-new-project.tar.gz`, `baton-adoption.tar.gz`, `baton-manifest.json`, and `SHA256SUMS`. It verifies the checksum file, manifest channel and tag, selected payload checksum, every payload path, and every extracted entry before invoking lifecycle code.

## Smart mode selection

The same installer determines mode from the target rather than asking the user to choose an unsafe path:

| Observed target | Selected behavior |
| --- | --- |
| Empty | New-project install |
| Non-empty, no Baton or legacy metadata | Mature Adoption mode |
| `.baton/metadata.json` present | Stable Baton update |
| Supported `.agent-harness.json` present | Legacy migration through Adoption mode |
| Existing unrecognized `.baton/` | Refuse; ownership is ambiguous |

An empty target receives a Git repository initialized on `main`, but Baton does not create a commit. A non-empty target keeps its existing repository state and unrelated dirty work.

## Interactive setup

For a new installation or adoption, the keyboard-first terminal asks:

1. **Project preset:** Software Product, Game Development, Business Operations, or Research.
2. **Project name:** inferred from the destination folder.
3. **Destination:** defaults to `.`.
4. **Reasoning:** Low, Medium, High, or Custom; Medium is recommended.
5. **Consultants:** a multi-select list seeded with the preset recommendation; selecting none is valid.

Use arrow keys or `j`/`k`, number keys, space to toggle Consultants, and Enter to confirm. `NO_COLOR=1` selects the numbered fallback.

Non-interactive defaults use the current folder name and directory, Software Product, Medium reasoning, and Product Designer:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | \
  bash -s -- --yes
```

Reasoning presets are:

| Preset | Management | Operations | Consultants | Contractors | Internal Audit |
| --- | --- | --- | --- | --- | --- |
| Low | medium | medium | medium | low | high |
| Medium | high | high | high | medium | xhigh |
| High | xhigh | xhigh | xhigh | high | xhigh |

Custom accepts `inherit`, `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, or `ultra` for each common role. Model and account support still determine which explicit reasoning levels are available.

## New-project installation

The new-project archive contains Baton's shared runtime and starter project records. The installer:

1. verifies the exact `new-project` manifest path list and checksums;
2. configures project name, preset, team, reasoning, role files, state, and dashboard;
3. installs everything owned by Baton under `.baton/`;
4. integrates the marked `AGENTS.md` block, Codex config, and individual skill-discovery links; and
5. records schema-v3 metadata with `installationStatus: "Installed"`.

The installed project receives no root `install.sh`, `tools/`, `tests/`, evaluator, source docs, examples, changelog, license, release files, or root version file from Baton. Those belong only to this source/product repository.

## Mature Adoption mode

A non-empty repository is not a blank Baton project. The adoption archive therefore separates runtime from starter content:

- shared runtime lands at its normal `.baton/` path;
- adoption-only guidance lands under `.baton/integration/`;
- template-only direction, state, dashboard inputs, decisions, PRDs, tickets, and report scaffolding stay quarantined at `.baton/integration/starter/`; and
- metadata records `installationStatus: "Needs Integration"`.

Quarantined starter state is never canonical merely because installation succeeded. The root Baton block points agents to `.baton/integration/README.md`, not to an invented project plan.

The external transaction report identifies its backup and cleanup prompt. Use that prompt to inspect the live repository and prepare complete, non-template mature-project records in a separate directory. A proposal needs six regular JSON files—`project`, `goals`, `tickets`, `ownership`, `reviews`, and `team`—either directly or below `state/`. It may also include reviewed `docs/overview.md` and `docs/direction.md`.

After human review, activate the proposal:

```sh
.baton/bin/baton _activate --from /absolute/path/to/reviewed-proposal
```

Activation is internal because it is a one-time adoption gate, not a routine lifecycle command. It validates metadata schema, proposal schemas, cross-record relationships, team preset and reasoning, current baselines, and every destination. Any existing activation target blocks rather than being replaced. A successful transaction writes active `.baton/state/`, dashboard, role configs, the active `AGENTS.md` block, and approved config integration, then records `Installed`.

Activation does not delete `.baton/integration/starter/`, legacy files, cleanup candidates, reports, or backups.

## Collision preservation

Baton has three narrow root integrations:

### `AGENTS.md`

Baton appends or updates exactly one block delimited by `<!-- BATON:START -->` and `<!-- BATON:END -->`. Existing content outside that block is preserved verbatim. Missing, duplicated, or malformed markers fail closed.

### `.codex/config.toml`

If the file is absent, Baton creates its generated semantic contract. If it exists, Baton preserves it regardless of whether its permissions are compatible and writes the desired config to `.baton/integration/codex-config.toml` for manual semantic merge. It never replaces the existing file wholesale.

### Skill discovery

Baton creates only these individual links when each path is free:

```text
.agents/skills/brainstorm
.agents/skills/code-review
.agents/skills/fire-consultant
.agents/skills/hire-consultant
.agents/skills/improve-codebase-architecture
```

Each link targets the single source under `.baton/skills/`. Existing files, directories, or different symlinks are preserved and reported as manual actions. Baton does not install a root `.codex/skills` link or duplicate skill tree.

All other root paths—including `README.md`, `VERSION`, package manifests, license/community files, `.github/`, docs, examples, source, tests, tools, release configuration, and existing governance—are out of bounds.

## v0.2-v0.5 legacy migration

Legacy Agentic Project Harness installations do not have `.baton/bin/baton`. Once v0.6.0 is stable, run the new stable Baton installer directly in the legacy repository.

The migration uses mature Adoption mode even when old starter records exist. It preserves `.agent-harness.json` and every legacy managed path, puts Baton starter state in quarantine, records exact cleanup candidates, and requires reviewed activation. It does not infer canonical state from legacy Markdown or automatically retire old files.

v0.2.0, v0.3.0, and v0.5.0 have verified legacy migration anchors but are not schema-v3 automatic-update origins; they enter the additive legacy Adoption path. No v0.4.0 stable Git tag was published, so v0.4 compatibility is only a migration fixture. Automatic stable origins begin with future v0.6+ updates and must be pinned by both full commit and manifest SHA-256. See [Releasing](releasing.md) for the immutable anchors.

## Status, update, and check

After Baton is installed, use:

```sh
.baton/bin/baton status
.baton/bin/baton update
.baton/bin/baton check
```

All three support `--json`; `update` also supports `--yes`.

`status` is read-only. It reports:

- `batonVersion`, optional `projectVersion`, and state schema version;
- installation status and immutable stable provenance;
- modified or missing managed paths and the marked `AGENTS.md` block status;
- pending integration, human-approved cleanup candidates, and last transaction.

`update` downloads the same latest stable installer. It refuses prereleases, moving branches, forks outside the approved repository set, automatic downgrades, unsupported origins, incomplete provenance, checksum mismatch, modified managed/generated paths, destination collisions, unsafe symlinks, and ambiguous state. A same-version update must match the exact recorded release commit and manifest digest.

`check` validates canonical state and team records. It does not prove product behavior or grant publication authority.

## Version and provenance

Schema-v3 `.baton/metadata.json` is the installation record:

```json
{
  "schemaVersion": 3,
  "batonVersion": "0.6.0",
  "projectVersion": null,
  "installationStatus": "Installed",
  "source": {
    "channel": "stable",
    "tag": "v0.6.0",
    "commit": "<full immutable commit>",
    "manifestSha256": "<sha256>"
  }
}
```

`batonVersion` comes only from the verified manifest. `projectVersion` is separate, optional project information. Baton never reads or rewrites the project's root `VERSION`, package version, Git tag, or release configuration to determine its own version.

Do not hand-edit provenance, managed baselines, transaction IDs, or ownership classes.

## Transactions, rollback, and cleanup

Installation, activation, update, state writes, and team changes share one external per-project process lock. Mutations write reports and backups below the user's state directory, outside the worktree. On a write or validation failure, Baton restores touched paths from that transaction and reports any recovery limitation.

Adoption and migration reports preserve exact cleanup evidence:

- transaction and report paths;
- rollback backup location;
- preserved legacy paths and collisions;
- baseline, current, and target checksums;
- stable release URL;
- immutable GitHub compare URL; and
- direct target file URLs built from each manifest `sourcePath`.

Examples of the required direct evidence shape are:

```text
https://github.com/FabienGreard/baton/compare/<origin-full-sha>...<target-full-sha>
https://github.com/FabienGreard/baton/blob/<target-full-sha>/packages/consumer/.baton/rules/repository-safety.md
```

An LLM may use the cleanup prompt to integrate project intent or prepare a list of archival/deletion candidates. A human must separately approve every destructive action. Never delete transaction backups automatically.

## Codex permissions

When `.codex/config.toml` is absent, Baton generates on-request approvals, automatic approval review, workspace-write sandboxing, sandbox command network access, four maximum open agent threads, and one level of agent nesting. It also registers common and active Consultant configs from `.baton/agents/`.

This is a project default, not an unconditional grant:

- Project config loads only after the repository is trusted.
- The active composer or `/permissions` choice, CLI flags, closer project config, profiles, and admin-managed requirements can override or constrain defaults.
- Existing already-running tasks may retain their currently selected permission mode until the user changes it or starts a new task.
- Auto-review reviews eligible boundary-crossing requests; it does not widen the sandbox or guarantee approval.
- `.git/` and `.codex/` may remain protected in workspace-write mode.
- Command network access does not grant browser, connector, website, Computer Use, account, or publication permissions.
- Subagents inherit the parent turn's active permissions, and an execution surface may support fewer than four threads.

See OpenAI's [sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security), [Auto-review](https://learn.chatgpt.com/docs/sandboxing/auto-review), and [configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic#configuration-precedence) documentation.

Continue with [Getting started](getting-started.md) after installation.
