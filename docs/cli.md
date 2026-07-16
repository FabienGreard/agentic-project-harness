# CLI reference

Use Baton skills for normal work:

| Skill | Purpose |
| --- | --- |
| `$boot` | Onboard or adopt a Project. |
| `$control` | Inspect or change Project controls. |
| `$roster` | Manage the permanent team. |
| `$terminal` | Inspect status or open the control room. |
| `$upgrade` | Install a stable update. |
| `$doctor` | Diagnose or recover Baton. |
| `$scrap` | Remove Baton through a reviewed plan. |

Use the CLI only when you need an exact operation, JSON, or automation. Add `--json` for machine-readable output. Run `.baton/bin/baton --help` or append `--help` to any command for details.

Workflow skills such as `$brainstorm`, `$code-review`, and `$improve-codebase-architecture` do not add CLI families.

## Installer

Run from the Repository you want Baton to manage:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash

curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash -s -- --target /absolute/path/to/repository --yes --json

./install.sh --help

./install.sh update --target /absolute/path/to/repository --yes
```

`--yes` approves only the exact planned safe writes. It does not authorize deletion. After installation, invoke `$boot`; use `boot status` only to inspect installation state.

## Boot

Preferred: `$boot`.

```sh
.baton/bin/baton boot status --json
.baton/bin/baton boot inspect --section summary --json
.baton/bin/baton boot initialize --json
.baton/bin/baton boot record /tmp/onboarding-operation.json --json
.baton/bin/baton boot next /tmp/onboarding-context.json --json
.baton/bin/baton boot catalog --field presets --json
.baton/bin/baton boot configure --preset software-product --consultant product-designer --invocation-task-id TASK_ID --yes --json
.baton/bin/baton boot activate --from /absolute/path/to/reviewed-proposal --yes --json
```

`record`, `next`, and `configure` are normally driven by `$boot`. `activate --yes` confirms the reviewed proposal; it never authorizes cleanup of quarantined or legacy paths.

## Control

Preferred: `$control`.

```sh
.baton/bin/baton control show --json
.baton/bin/baton control check --json
.baton/bin/baton control apply /tmp/replace-records.json --json
.baton/bin/baton control protocols --readiness "Standard Protocol" --clearance "Release Clearance" --json
.baton/bin/baton control memory inspect --section summary --json
.baton/bin/baton control memory transact /tmp/memory-operation.json --json
```

Valid Readiness values are `Waived`, `Field Check`, `Standard Protocol`, and `Full Certification`. Valid Clearance values are `Autonomous`, `Release Clearance`, `Completion Clearance`, and `Continuous Clearance`.

## Roster

Preferred: `$roster`.

```sh
.baton/bin/baton roster list
.baton/bin/baton roster check --json
.baton/bin/baton roster catalog --field presets --json
.baton/bin/baton roster hire --consultant security-lead --yes --json
.baton/bin/baton roster fire --consultant security-lead --yes --json
.baton/bin/baton roster configure --preset research --no-consultants --invocation-task-id TASK_ID --yes --json
```

## Terminal

Preferred: `$terminal`.

```sh
.baton/bin/baton terminal status --json
.baton/bin/baton terminal view --open
```

## Upgrade

Preferred: `$upgrade`.

```sh
.baton/bin/baton upgrade status --json
.baton/bin/baton upgrade apply --yes --json
```

Upgrade fails closed on managed drift, unsupported provenance, unsafe paths, and downgrades.

## Doctor

Preferred: `$doctor`.

```sh
.baton/bin/baton doctor check --json
.baton/bin/baton doctor recover --json
```

Recovery reports the recovered transaction IDs, results, and external Report paths. It does not guess at unrecognized or unsafe state.

## Scrap

Preferred: `$scrap`.

```sh
.baton/bin/baton scrap plan --output /tmp/baton-scrap-plan.json --json
.baton/bin/baton scrap apply --plan /tmp/baton-scrap-plan.json --yes --json
```

Scrap preserves collisions, creates an external backup and Report, and rolls back on failure. `--yes` approves the exact plan only.
