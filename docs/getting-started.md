# Getting started with Baton

This guide begins after a stable Baton installer has completed. Baton v0.7.0 is still an unpublished candidate in this source checkout; do not treat candidate files or a moving branch as an installable stable release.

## 1. Inspect local truth

From the project root, run:

```sh
.baton/bin/baton status --json
```

Read these fields before doing anything else:

- `batonVersion` and immutable `source` provenance identify Baton itself.
- `projectVersion` is independent project information and may be `null`.
- `installationStatus` is either `Installed` or `Needs Integration` for a current Baton installation.
- `integrity`, `pendingIntegration`, `legacyCleanupCandidates`, and `lastTransactionId` identify work that still needs review.

Do not substitute a root `VERSION`, package manifest, branch name, generated dashboard, or old `.agent-harness.json` for `.baton/metadata.json`.

## 2. Finish mature adoption when required

An empty new project starts as `Installed`; skip to the next section.

A non-empty project starts as `Needs Integration`. In that state:

- `AGENTS.md` tells agents not to treat starter state as authoritative.
- `.baton/integration/starter/` contains a browsable agent map, generated dashboard, and quarantined examples—not live project facts.
- `.baton/integration/codex-config.toml` may contain a proposed config merge when the project already owned `.codex/config.toml`.
- the external transaction directory contains `update-report.json`, `cleanup-prompt.txt`, and the rollback backup.

Follow the generated cleanup prompt. Inspect the mature repository and prepare non-template reviewed state in a separate temporary directory. It must contain complete schema-valid `project.json`, `goals.json`, `tickets.json`, `ownership.json`, `reviews.json`, and `team.json` files, either directly or under `state/`. Optional reviewed `docs/overview.md` and `docs/direction.md` may accompany them.

Do not mechanically parse legacy Markdown, invent missing intent, edit the quarantined starter into place, or delete a legacy file.

After a human confirms that the proposal is complete, activate it:

```sh
.baton/bin/baton _activate --from /absolute/path/to/reviewed-proposal
```

The `_activate` command is intentionally internal. It validates metadata schema, team preset and reasoning, all six canonical records, cross-record constraints, managed baselines, and destination collisions before making a transaction. `--yes` may confirm an already reviewed activation in automation; it never authorizes cleanup or deletion.

Activation changes the installation to `Installed`, generates the active dashboard and role configs, updates only Baton's managed `AGENTS.md` block and approved config integration, and records an external backup. Quarantined and legacy evidence remains until a separate human cleanup decision.

## 3. Validate the active control plane

Run both public checks:

```sh
.baton/bin/baton status --json
.baton/bin/baton check --json
```

`status` must report `Installed` with no modified or missing managed files and an intact `AGENTS.md` block. `check` validates canonical state and team records. Open `.baton/dashboard/index.html` only after those commands pass; it is a generated view, not authority.

If either command fails, stop the affected scope and inspect the exact report, pending action, or modified path. Do not repair provenance or managed baselines by hand.

## 4. Read the repository map

Read root `AGENTS.md`, then every applicable link from `.baton/AGENTS.md`. Repository records and the live checkout are authoritative.

The durable split is:

- `.baton/state/*.json` for canonical project, goal, ticket, ownership, review, and team records;
- `.baton/docs/`, `.baton/decisions/`, `.baton/prds/`, and `.baton/implementation-reports/` for narrative intent and evidence;
- `.baton/workflow.md`, `.baton/rules/`, and `.baton/roles/` for operating contracts; and
- `.baton/memory/memory.json` for current company, user, and coworker memory plus `.baton/memory/history.jsonl` for value-minimized chronology;
- `.baton/thread-registry.md` for the generated permanent-task registration view; and
- `.baton/dashboard/index.html` for the generated local project and company view.

Use validated state operations rather than hand-editing generated views. Team changes go through `$hire-consultant` and `$fire-consultant` so history, configs, and transaction evidence stay consistent.

## 5. Bootstrap Management and the permanent team

Invoke the explicit project skill:

```text
$bootstrap-baton
```

Bootstrap verifies installation and state before doing anything. Management asks your preferred name, creates or reconciles the configured permanent Codex tasks when the complete safe task surface is available, and otherwise gives you copy-ready prompts for each missing task. It is resumable and does not recreate completed identities or tasks.

Management asks exactly one project-definition question per turn. Nothing becomes durable project intent until you confirm the final summary. The short company introduction ends after onboarding; normal operation uses direct status and authority language. Bootstrap never creates persistent goals, permanent Contractor tasks, or Internal Audit tasks.

Use `$memory` whenever you want to remember, inspect, confirm, correct, forget, or retrieve project-local company memory. Candidates and inferred personal observations have no effect until confirmed. Automatic task briefings contain only role-relevant confirmed claims and remain within the fixed claim/token budget.

Management owns outcomes, priority, scope, readiness, publication, and declared human-review gates. It does not dispatch Contractors.

## 6. Promote only bounded Ready work

Every executable ticket must have an objective, context, scope, non-goals, acceptance, dependencies, affected systems, risks, owner, verification, expected evidence, resolved assurance, and applicable review gates. Only `Ready` work enters execution.

Management approves outcome readiness. Operations confirms execution readiness, registers exclusive ownership, dispatches Contractors, integrates returns, and verifies completion evidence. Consultants define and accept only their approved recurring domains. Human `Release` approval remains separate from technical completion.

## 7. Run to delegated idle

Management, Operations, and active Consultants are permanent top-level tasks. Each wake drains safe actionable work, synchronizes the repository control plane, records the next owner/action/return trigger, sends one handoff, and stops without polling.

A new message to the exact permanent task is the sole wake mechanism. Do not create, resume, recreate, or attach persistent goals for role lifecycle, even if the Codex surface exposes complete goal controls; current repository policy supersedes older onboarding prompts that requested one. A legacy automatic continuation without a new task message performs no work and should be reported for user or administrative removal.

Contractors and Internal Audit are disposable. Contractors return exact changed paths, commands/results, limitations, blockers, and ownership release to Operations. Internal Audit independently evaluates Baton behavior and never mutates project work.

For lifecycle details, continue with [Installation](installation.md). For ownership-safe changes, see [Customization](customization.md).
