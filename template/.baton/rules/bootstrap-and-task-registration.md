# Bootstrap and Register Permanent Tasks Safely

Title:
Bootstrap and Register Permanent Tasks Safely

Type:
Rule

Purpose:
Create a welcoming, resumable permanent team without duplicate tasks, false readiness, provider assumptions, or goal-based lifecycle.

Scope:
`$bootstrap-baton`, installation routing, named workforce initialization, permanent-task capability probing, registration, wake paths, fallback prompts, project discovery, and delivery gating.

Definition:
Bootstrap begins only by explicit user invocation and reconciles installation, canonical state, configured team, project-local memory, registered tasks, and live Codex capabilities before creating anything. The invocation authorizes configured permanent user-owned task creation only when the live surface supports complete list/reconciliation, create, stable returned identity, read, and message/wake operations. Management is registered first; Operations and active Consultants follow. Contractors and Internal Audit remain disposable, and persistent goals are never created or used for role lifecycle.

How to Apply:

1. Validate installation, state, team, memory, and provenance; route `Needs Integration` through reviewed activation before normal bootstrap.
2. Probe current task capabilities and list live tasks before every create decision.
3. Reconcile live stable IDs with registered personnel and tasks through hidden `_memory` operations; reuse exact matches and fail closed on ambiguity.
4. Create Management first, register its returned stable ID before calling it online, and have Management ask the user's preferred name.
5. Generate or reuse stable professional identities and bounded working styles, then reconcile and create Operations and each active Consultant in configured order.
6. If any required capability is unavailable, partial, or ambiguous, create nothing through that path; emit deterministic copy-ready prompts and register affected seats as `awaiting-task`.
7. Ask exactly one project-definition question per turn, keep answers provisional, and require explicit confirmation of one final shared summary before recording durable project intent.
8. Gate delivery on every role required by that work having a registered task and valid message-based wake path; keep discovery available while stating the delivery block.

Do:

- Treat explicit `$bootstrap-baton` invocation as narrowly scoped task-creation authority when the complete safe surface exists.
- Register every returned task ID immediately and transactionally before introduction or wake.
- Resume from the first incomplete reconciled step without replaying completed introductions or regenerating identities.
- Keep stable authority names `Management`, `Operations`, `Consultants`, and `Contractors` alongside personal names.
- Use literal mixed-roster states such as `Online`, `Awaiting task`, `Discovery available`, and `Delivery blocked`.
- Preserve successful registrations and provisional discovery when another seat fails.

Don't:

- Create from a UI-only, create-only, message-only, unstable-ID, or otherwise incomplete capability surface.
- Match tasks by display name alone, silently merge collisions, or create duplicates to resolve ambiguity.
- Create permanent Contractor or Internal Audit tasks.
- Create, resume, recreate, inspect for lifecycle control, or attach persistent goals.
- Claim a coworker is online before stable registration and a valid wake path exist.
- Record durable project intent before final shared-summary confirmation, or treat confirmation as executable work or publication authority.
- Block project discovery solely because a roster item awaits manual task creation.

Example:

- When listing and stable-ID registration are available but task messaging is not, bootstrap creates no native task, records each affected seat as `awaiting-task`, provides copy-ready prompts, continues one-question discovery, and blocks delivery requiring those seats.

Validation:
Fresh, interrupted, resumed, complete, duplicate, ambiguous, mixed native/fallback, unavailable/partial capability, task-failure, and `Needs Integration` scenarios preserve stable identities and create no duplicates; only configured permanent seats receive tasks; no goals exist; durable intent appears only after explicit final confirmation; delivery gates reflect registered wake paths.

References:

- `.baton/skills/bootstrap-baton/SKILL.md`
- `.baton/rules/lifecycle-and-idle.md`
- `.baton/rules/company-memory.md`
- `.baton/rules/transactional-state.md`
- `.baton/state/team.json`
- `.baton/thread-registry.md`

Notes:

- Task-provider integration is a live capability seam, not an installation guarantee. Re-probe and reconcile on every invocation.
