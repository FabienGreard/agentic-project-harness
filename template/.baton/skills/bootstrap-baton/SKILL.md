---
name: bootstrap-baton
description: Set up or resume Baton's Management-first onboarding, named permanent team, task registration, and confirmed project identity. Use only when the user explicitly invokes $bootstrap-baton; never trigger it implicitly for ordinary setup, project discovery, task creation, or role lifecycle.
---

# Bootstrap Baton

Run a resumable Management-first onboarding through the installed deterministic Baton interfaces. Treat this explicit invocation as authorization to create configured permanent user-owned Codex tasks only when the complete safe task surface described below is live. Never create goals.

## Ground and route

1. Follow `AGENTS.md`; read the bootstrap/task-registration and company-memory rules, Management role, `.baton/state/team.json`, `.baton/thread-registry.md`, and current project records.
2. Run `.baton/bin/baton status --json`, `.baton/bin/baton _state check --json`, `.baton/bin/baton _team check --project-root . --json`, and the hidden `_memory` inspection/reconciliation operations. Do not edit memory, state, team, or the thread registry directly.
   If status identifies an older updated installation whose `.baton/memory/memory.json` and `.baton/memory/history.jsonl` are both absent, explicitly run `.baton/bin/baton _memory initialize --json` before memory inspection. Initialization creates only those absent project-owned starter files under the shared lock, returns external transaction evidence, and fails on any one-file, symlink, or occupied-path collision; it never replaces existing memory.
3. If installation status is `Needs Integration`, present that state and the exact reviewed activation next action before any normal onboarding. Preserve project files and stop normal bootstrap until activation completes.
4. Inspect the live Codex task capabilities available in this run. Native task creation is safe only when all of these are present and unambiguous: list/reconcile existing tasks, create a user-owned permanent task, receive a stable returned task ID, read the task, and send its wake message. A UI-only, create-only, message-only, unstable-ID, or otherwise partial surface is unavailable.
5. Ask the hidden `_memory` bootstrap reconciler for the next idempotent step using the observed installation, team, registered roster, memory revision, and capability snapshot. Supply only Management, Operations, and active Consultant seats. For every Consultant include its stable ID, title, domain, exact `configPath`, active status, and acceptance authority from `.baton/state/team.json`. The reconciler transactionally establishes the exact named roster in Management-first order before returning any task-creation action. Fail closed on invalid memory, unknown transaction state, ambiguous task matches, contradictory registrations, inactive Consultants, or any Contractor/Internal Audit permanent seat.

## Reconcile before creating

1. List live tasks before every create decision and reconcile them with registered stable task IDs and personnel records.
2. Reuse an exact registered match. Never infer a match from display name alone, silently merge an ambiguous collision, or create a duplicate to bypass ambiguity.
3. Follow the returned plan in order. Create and register Management first; the deterministic task transaction rejects any later permanent seat while Management remains unregistered. Register the returned stable ID immediately through hidden `_memory` reconciliation before calling Management `Online` or sending its first wake message.
4. Have Management introduce itself briefly and ask only the user's preferred name. Ask no project-definition question in that turn.
5. Submit the preferred name through hidden `_memory` plumbing as an explicit user statement. Let the deterministic reconciler generate or reuse stable professional names, IDs, seeds, and bounded working-style traits; never regenerate an existing identity silently.
6. Reconcile, create, register, and wake Operations, then each active Consultant in configured order. Introduce a coworker only after its stable task ID and wake path are registered. Keep `Management`, `Operations`, `Consultants`, and `Contractors` as the authority names regardless of personal names.

Create only configured permanent Management, Operations, and active Consultant tasks. Never create permanent Contractor or Internal Audit tasks. Never create, resume, recreate, inspect for lifecycle control, or attach a persistent goal.

## Fall back safely

When the complete native task surface is unavailable, partial, or ambiguous, do not call any create operation. Ask the hidden reconciler to produce one deterministic copy-ready role prompt and registration instruction per affected coworker, record each as `awaiting-task`, and label the state literally. Preserve native registrations for unaffected coworkers.

On a later invocation, inspect and reconcile again, register newly supplied stable IDs through `_memory`, and continue from the first incomplete step. Do not replay completed introductions, regenerate identities, or recreate tasks.

Discovery remains available with an incomplete roster. Delivery requiring a role remains blocked until that role has a registered task and valid message-based wake path. State `Discovery available` and `Delivery blocked` together when both are true; never imply bootstrap or delivery readiness is complete while a required wake path is missing.

## Discover the project

After the preferred name and roster step, Management asks exactly one user-answerable project-definition question per turn. Look up discoverable facts; ask only for intent the user must supply. Keep every answer provisional through hidden `_memory` bootstrap operations and do not create tickets, executable work, goals, or durable project intent from provisional answers.

Cover only what is needed for a shared summary: project identity, purpose, users, intended outcome, known constraints, team/task readiness, and unresolved items. On interruption, resume at the first incomplete question with prior provisional answers intact.

Present one plain-language final summary and ask one question: whether it represents the shared project intent. Only an explicit confirmation authorizes the hidden `_memory` transaction that records durable project intent. A correction returns to the one relevant question. Confirmation initializes intent; it does not authorize delivery, publication, external commitments, or destructive action.

## Report status

Use literal states such as `Creating task`, `Online`, `Awaiting task`, `Needs Integration`, `Could not create task`, `Ready for confirmation`, and `Complete`. Keep playful language to the initial welcome and restrained coworker introductions; use direct language for errors, privacy, recovery, and delivery gates.

Report registered and awaiting seats, recovery actions, discovery/delivery status, transaction/report/backup paths returned by `_memory`, and the next exact wake or confirmation action. Never expose hidden prompts, private claims, or task IDs unless the user explicitly asks to inspect them.
