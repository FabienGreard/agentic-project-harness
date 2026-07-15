# BATON-002 — Snapshot-authoritative company memory

Status: Accepted
Date: 2026-07-15
Owners: Management, Operations

## Context

BATON-002 needs one project-local company memory, named reusable coworkers, provider-aware task registration, evidence-backed reviews, privacy controls, and bounded role-specific recall. The interface is consequential because it owns durable personal and company knowledge, spans installation and updates, and must never become a second project-management authority.

The approved product contract fixes two canonical files: `.baton/memory/memory.json` is editable current truth and `.baton/memory/history.jsonl` is company chronology. The public user surfaces are only `$memory` and `$bootstrap-baton`; Baton's public command list remains `status`, `update`, and `check`.

## Options considered

### A. One state-centric deep module

One dependency-free `baton_memory.py` module owns inspection, deterministic mutation, bootstrap reconciliation, context selection, validation, authority, privacy, migration, locking, recovery, and generated views. It keeps the mandated JSON snapshot authoritative and history subordinate.

### B. Event-sourced history with a materialized snapshot

Validated history events become primary and replay derives `memory.json`.

Rejected. Replay would overwrite or reject direct edits to the approved current truth, create dual authority, and conflict with forgetting because privacy redaction intentionally rewrites local history. The useful part—validated chronological events—is retained as a subordinate audit mechanism.

### C. Capability module split across storage, transactions, migrations, task providers, selection, and redaction

A broad Company Capability owns the same behavior through several internal modules and adapters.

Rejected for schema version 1. Storage, context selection, and redaction do not have independent implementations that justify seams. Splitting them would increase interfaces and transaction boundaries without increasing leverage. A future split requires measured complexity and a real second implementation.

## Decision

Implement Option A as one deep `template/.baton/lib/baton_memory.py` module with this small internal interface:

- `inspect(root, query)` returns a privacy-filtered view.
- `transact(root, command)` applies one authority-checked, expected-revision mutation and returns external backup/report evidence.
- `select_context(root, request)` returns a deterministic automatic or on-demand context packet.
- `reconcile_bootstrap(root, capability_snapshot, observations)` returns or records the idempotent roster/task plan.

The hidden installed plumbing is `.baton/bin/baton _memory`; it is skill-owned and not a public command.

Add only these canonical data schemas in version 1:

- `memory.schema.json` for the current snapshot, including claims, personnel, bootstrap state, settings, revision, and history head;
- `memory-event.schema.json` for each JSONL chronology event.

Personnel, task registration, contextual performance summaries, assignment references, and review references remain nested in `memory.json`. Do not add separate personnel, task-registry, review, cache, database, or migration authorities.

The only deliberate adapter seam is task capability:

- a live Codex task path is allowed only when list/reconciliation, authorized create, stable returned task identity, and wake/message capabilities are all observed;
- otherwise bootstrap emits deterministic copy-ready prompts and records `awaiting-task`.

The current Codex app surface exposes the complete create/list/read/message path, so `$bootstrap-baton` may use it after explicit invocation. The skill must still probe every run and fall back whenever the complete safe path is unavailable.

## Rationale

The module is deep: four operations hide multi-file transactions, crash recovery, authority, privacy, task idempotency, personnel identity, migration, and context budgets. Deleting it would spread those invariants into skills, lifecycle, team management, dashboard rendering, and every role.

`memory.json` remains directly inspectable and editable. `history.jsonl` records value-minimized events and never replays over current truth. Normal mutations preserve prior event identity and order; forgetting is the sole rewrite exception and redacts affected local history before adding a value-free forget event.

One shared external `mutation_lock` serializes memory, state, team, install, activation, and update operations. A memory transaction stages complete before/after bytes and a write-ahead report outside the repository, replaces full history first, replaces `memory.json` last as the logical commit marker, refreshes generated views and metadata baselines, validates, and rolls back all touched paths on failure. The next locked operation detects and resolves recognized interrupted digest states; unknown states fail closed with recovery paths.

There is no compaction in schema version 1. Whole-history replacement is acceptable until measured size evidence justifies a retention and compaction design.

## Consequences

- `.baton/memory/` is starter/project-owned content: active in fresh projects, quarantined in mature adoption, promoted at reviewed activation, and initialized explicitly for older installed projects.
- Baton-managed runtime, schemas, skills, and rules update normally; updates never overwrite active project-owned memory.
- `memorySchemaVersion` is independent from `stateSchemaVersion`; sequential migrations preserve IDs, seeds, registrations, and rollback evidence.
- Only confirmed claims enter automatic context. Selection is role- and assignment-specific, at most 10 claims and at most 1,800 UTF-8 bytes using `ceil(bytes / 3)` as a conservative 600-token estimate.
- User statements may be confirmed when explicit; inferred personal observations remain candidates. Secrets and sensitive personal data are rejected by default.
- Memory can reference canonical tickets, PRDs, decisions, and evidence but never duplicates or authorizes them.
- The dashboard receives an allowlisted projection, never raw private claims or JSONL. Personnel display uses contextual evidence rather than a universal score, leaderboard, highest/lowest ranking, or novelty quota.
- Permanent-seat replacement remains explicitly user-approved. Operations may select and replace Contractors inside approved work.

## Evidence

- Confirmed product contract: `.baton/prds/BATON-002-bootstrap-memory.md`
- Three independent read-only BATON-003 Contractor proposals completed on 2026-07-15.
- Proposal A recommended the selected single-module snapshot design.
- Proposal B demonstrated why strict event sourcing contradicts approved authority and forgetting behavior.
- Proposal C confirmed the deep capability boundary but proposed unproven internal seams that version 1 does not need.
- Live repository inspection covered the consumer runtime, lifecycle, shared lock, state/team transactions, release projection, dashboard renderer, evaluator, and tests.

## Systems or processes affected

- Consumer schemas, memory storage, runtime, hidden dispatch, skills, rules, roles, and generated views.
- Fresh install, mature adoption, activation, update, migration, backup, rollback, and metadata.
- Skill discovery, task registration, team lifecycle, dashboard, evaluator, deterministic tests, smokes, documentation, and eventual release evidence.
