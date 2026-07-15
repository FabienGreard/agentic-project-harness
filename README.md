# Baton

Baton is a project-scoped operating system for Codex teams. It gives a repository explicit authority, bounded delivery, transactional project state, stable updates, and evidence-backed review while leaving the surrounding project under its owners' control.

> **v0.7.0 status:** this checkout is an unpublished candidate built on the isolated v0.6 architecture candidate. The Baton release URL below is intentionally not live until a separate human-authorized stable release. The latest published historical release remains [Agentic Project Harness v0.5.0](https://github.com/FabienGreard/agentic-project-harness/releases/tag/v0.5.0).

## One company layer

Every Baton project uses the same common names:

- **Management** owns outcomes, priority, scope, readiness, publication, and human-review gates.
- **Operations** plans delivery, dispatches Contractors, integrates returns, and verifies evidence.
- **Consultants** are optional recurring experts with one approved readiness and acceptance domain.
- **Contractors** are disposable execution capacity for bounded assignments owned by Operations.
- **Internal Audit** independently evaluates Baton behavior. It is not a project-team member, product QA, or a Consultant.

The selected preset adds professional context without changing those authorities. Every ticket also states its resolved `Lean`, `Standard`, or `Thorough` test rigor and any human review required at `Readiness`, `Acceptance`, or `Release`.

| Preset | Management persona | Operations persona | Recommended Consultant |
| --- | --- | --- | --- |
| Software Product | Product Manager | Engineering Manager | Product Designer |
| Game Development | Game Director | Producer | Art Director |
| Business Operations | Program Director | Operations Manager | Change Manager |
| Research | Principal Investigator | Research Program Manager | Research Methodologist |

## A source repository, not a project template

This repository contains Baton's product source, tests, documentation, evaluator, installer, and release tooling. Its root [`.baton/`](.baton/) is Baton's own live project control plane and is always source-only. Source lifecycle utilities are consolidated under [`scripts/`](scripts/); the release builder publishes `scripts/install.sh` as the top-level `install.sh` release asset.

Consumer content has a separate source at [`template/.baton/`](template/.baton/). The release builder classifies every tracked source file and produces two exact, checksum-bound payloads:

- `baton-new-project.tar.gz` activates starter state in an empty project.
- `baton-adoption.tar.gz` installs runtime into a mature repository while quarantining starter state under `.baton/integration/starter/`.

Both archives contain only `.baton/` paths. A consumer never receives this repository's root `README.md`, `VERSION`, `CHANGELOG.md`, license/community files, `docs/`, `scripts/`, `tests/`, evaluator, release machinery, or an installed root `install.sh`. See [Architecture](docs/architecture.md) for the complete boundary.

## Install or adopt

After a Baton stable release is explicitly published, run its one installer from the project directory:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash
```

For folder-aware defaults without the interactive menus:

```sh
curl -fsSL https://github.com/FabienGreard/baton/releases/latest/download/install.sh | bash -s -- --yes
```

To delegate only the installation to an LLM, copy this prompt:

```text
Install the latest stable Baton release into the current repository using the
official https://github.com/FabienGreard/baton release assets. Inspect the live
target first, preserve every existing project-owned file and unrelated change,
and use Baton's single stable installer in its folder-aware mode. Do not install
from a branch, prerelease, fork, or source checkout. Afterward run
`.baton/bin/baton status --json`; if the result is Needs Integration, stop
without activating starter state, deleting legacy files, or performing cleanup.
Report the installed Baton version, selected mode, pending/manual actions, exact
transaction report, and backup/rollback location.
```

The same verified installer chooses the safe mode from the target:

| Target | Result |
| --- | --- |
| Empty directory | Installs the new-project payload, initializes Git on `main` without a commit, and records `Installed`. |
| Non-empty directory | Uses additive Adoption mode, preserves project files, quarantines starter records, and records `Needs Integration`. |
| Baton metadata present | Offers or runs a stable update through the adoption payload. |
| Supported v0.2-v0.5 legacy metadata present | Migrates through Adoption mode and preserves every legacy path; only checksum-verified unchanged managed paths become human-approved cleanup candidates. |
| Unrecognized `.baton/`, unsafe path, ambiguous provenance, or managed-file drift | Fails closed without guessing ownership. |

Outside `.baton/`, Baton may touch only:

- its idempotent marked block in `AGENTS.md`;
- `.codex/config.toml` when it is absent, or a quarantined merge proposal when it already exists; and
- individual `.agents/skills/<name>` discovery links when those paths are free.

Every collision is preserved. Baton never replaces a project-owned file wholesale, renames or deletes project content, stages changes, or commits during installation or adoption. The marked `AGENTS.md` block is the only shared-file content Baton updates automatically.

Read [Installation](docs/installation.md) before adopting a mature repository.

## Installed command surface

An installed project has no root Baton installer or maintenance tools. Use the project-local command:

```sh
.baton/bin/baton status
.baton/bin/baton update
.baton/bin/baton check
```

`status --json` reports the installed Baton version, project version field, immutable release provenance, installation status, managed-file integrity, pending integration, cleanup candidates, and last transaction. `update` fetches only the latest official stable installer and refuses downgrades, unsupported origins, modified managed files, or ambiguous provenance. `check` validates canonical state and team records.

Mature adoption remains non-authoritative until a human reviews a complete schema-valid proposal and the generated cleanup prompt invokes the internal activation step. Activation and updates are transactional, keep backups outside the worktree, and do not authorize deletion.

## Bootstrap the company

After status and checks pass, invoke `$bootstrap-baton` in Codex. Management starts first, asks your preferred name, gives every configured permanent coworker a stable professional identity, and reconciles the real Codex tasks for Management, Operations, and active Consultants. When the active Codex surface cannot safely list, create, identify, and wake tasks, bootstrap provides copy-ready prompts and marks those coworkers `Awaiting task` instead of guessing or creating duplicates.

Management then asks exactly one project-definition question at a time and presents one final summary for confirmation. Discovery can continue while a task is awaiting creation, but delivery requiring that role remains blocked until a real task ID and wake path are registered. Bootstrap never creates persistent goals, permanent Contractor tasks, or Internal Audit tasks.

One project-local memory lives at `.baton/memory/memory.json` with its value-minimized chronology at `.baton/memory/history.jsonl`. Invoke `$memory` to remember, inspect, confirm or reject candidates, correct, forget, or retrieve more context. Only confirmed claims enter automatic role briefings, capped at 10 claims and approximately 600 tokens; complete memory is never injected automatically. Forgetting redacts active local memory and local chronology transactionally, while warning that Git history and retained external backups may still contain earlier values. Baton never rewrites Git history automatically.

Memory is supportive context, not project-management authority. Tickets, PRDs, decisions, ownership, approvals, and evidence remain authoritative in their existing records. Credentials, secrets, and sensitive personal values are rejected by default.

## Baton version is not the project version

`.baton/metadata.json` schema v3 keeps two independent fields:

- `batonVersion` comes only from the checksum-verified stable release manifest and immutable source provenance.
- `projectVersion` is optional project information and starts as `null` unless the project has an approved way to supply it.

Baton never treats a root `VERSION`, package manifest, Git tag, or release file as its own version. It does not create, replace, or reinterpret the project's version source.

## Safe cleanup and direct evidence

Adoption and migration preserve legacy files and transaction backups. Their generated report and cleanup prompt identify exact candidates, available baseline/current/target checksums, the stable release, an immutable GitHub comparison, and direct target-source links such as:

```text
https://github.com/FabienGreard/baton/compare/<origin-full-sha>...<target-full-sha>
https://github.com/FabienGreard/baton/blob/<target-full-sha>/template/<source-path>
```

An LLM may inspect that evidence and prepare a cleanup recommendation. Only a human may approve archival or deletion, and neither `--yes` nor successful activation grants that authority.

Early v0.2-v0.4 metadata has no trustworthy per-file baselines, so Baton does not guess: it preserves every non-metadata path and records the available immutable source evidence for manual comparison. Remote v0.2/v0.3 metadata did not record the installed commit; Baton reports that absence and labels the official stable tag/commit only as a version anchor. v0.5 paths become candidates only when their recorded ownership is Baton-managed and their current checksum still equals the legacy baseline; project-owned, modified, missing, or invalid entries remain preserved.

## Codex permission contract

When no project config exists, Baton proposes this base contract and registers the generated `.baton/agents/*.toml` files:

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

The caveats matter:

- Project `.codex/config.toml` loads only for a trusted repository. A closer project config, CLI override, permissions selection, profile, or admin-managed requirement can change or constrain the effective setting.
- Existing already-running Codex tasks may retain their currently selected permission mode until the user changes it or starts a new task.
- Auto-review changes who reviews eligible approval requests; it does not grant permission, expand writable roots, enable network by itself, weaken protected paths, or replace app-level Computer Use approvals.
- `workspace-write` permits routine work inside the active workspace, but `.git/` and `.codex/` can remain protected. A commit or config write may still need approval.
- Network access applies to commands in the workspace-write sandbox. Website, browser, connector, and external-service permissions remain separate.
- Subagents inherit the parent turn's active permission mode. `max_threads = 4` is a ceiling, while `max_depth = 1` permits direct children but prevents recursive fan-out.

See OpenAI's current [sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security), [Auto-review](https://learn.chatgpt.com/docs/sandboxing/auto-review), and [project configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#project-config-files-codexconfigtoml) documentation.

## Start using Baton

After installation:

1. Run `.baton/bin/baton status --json`.
2. If status is `Needs Integration`, complete the reviewed quarantine/activation flow in [Getting started](docs/getting-started.md).
3. Run `.baton/bin/baton check --json`.
4. Read `AGENTS.md` and `.baton/AGENTS.md`, then invoke `$bootstrap-baton`.

Management, Operations, and active Consultants are permanent event-driven tasks. New messages to those exact tasks are their sole wake mechanism; Baton never uses persistent goals as role identity or lifecycle control. They drain actionable work, leave an explicit owner/action/return trigger, and pause without polling. Operations is the only Contractor dispatch and revision-routing center.

## Documentation

- [Getting started](docs/getting-started.md)
- [Installation, adoption, and updates](docs/installation.md)
- [Customization](docs/customization.md)
- [Architecture](docs/architecture.md)
- [Release policy and stable procedure](docs/releasing.md)
- [Historical changes](CHANGELOG.md)

## License

MIT. Adapted skill material and attribution are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
