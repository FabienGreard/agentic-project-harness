# Installation

Baton installs or updates only from verified stable release assets. The current source checkout is an unpublished candidate.

## Requirements

- Bash
- Git
- Python 3.9 or later
- `curl`

Run from the repository Baton should manage:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash
```

Then open that repository in your LLM coding agent and invoke:

```text
$boot
```

For a non-interactive install:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash -s -- --yes
```

Options are `--target PATH`, `--yes`, `--json`, and `--help`. `--yes` approves only the planned safe writes. It never authorizes deletion.

## Mode selection

| Target | Result |
| --- | --- |
| Empty directory | Creates a new Project. Git starts on `main` without a commit. |
| Existing repository | Adds Baton and quarantines starter State for review. |
| Baton already installed | Runs a stable update. |
| Supported older Baton | Migrates while preserving old files. |
| Unsafe or unclear target | Stops without guessing. |

Installation never stages or commits Repository work.

## Mature-repository adoption

Adoption installs the runtime but keeps starter State and host-config proposals under `.baton/migration/`. They are not active.

Invoke `$boot`. It inspects the repository, guides the review, and asks before activation. Activation does not delete quarantine, old files, collisions, or backups.

## Root integration

Outside `.baton/`, Baton may touch only:

- its marked block in root `AGENTS.md`;
- the host config when absent, or a merge proposal when present; and
- skill links when their paths are free.

A skill-link collision stops installation. Other collisions are preserved. Baton never replaces a Project-owned file.

## Manage Baton

Use the skill that matches the task:

| Skill | Purpose |
| --- | --- |
| `$boot` | Onboard a Project or activate mature adoption. |
| `$control` | Inspect or change Project controls. |
| `$roster` | Manage the permanent team. |
| `$terminal` | Inspect status or open the control room. |
| `$upgrade` | Inspect or install a stable Baton release. |
| `$doctor` | Diagnose or recover Baton. |
| `$scrap` | Plan and approve safe removal. |

Each skill uses its matching local command family. Use the [CLI reference](cli.md) only for exact commands, JSON, or automation.

`batonVersion` identifies Baton. It never replaces the Repository's own version.

## Migration, recovery, and removal

Invoke `$upgrade` for supported migrations, `$doctor` for recovery, and `$scrap` for removal.

Baton preserves old and Project-owned files unless ownership and checksums prove a path is unchanged. Every write uses a lock, external backup, validation, and Report. Only a human can approve archival or deletion.

Next: [Getting started](getting-started.md).
