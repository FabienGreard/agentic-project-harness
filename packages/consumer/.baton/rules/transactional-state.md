# Update Shared State Transactionally

Title:
Update Shared State Transactionally

Type:
Rule

Purpose:
Prevent contradictory statuses, owners, dependencies, evidence, and wake conditions.

Scope:
Every status transition, ownership change, dispatch, blocker, review, completion, and release-state change.

Definition:
A state transition is one logical transaction. Every affected canonical record is reconciled before the transition is announced or handed off.

How to Apply:

1. Identify the event, authorized transition, and affected records.
2. Prepare status, owner, dependency, evidence, and next-action changes together.
3. Transfer ownership within the same change set.
4. Route state, team, installation, and update mutations through their deterministic tools; they share one external per-project cross-process lock.
5. Verify records agree before sending a handoff.

Do:

- Update goal, ticket, active ownership, review, project baton, and generated view together when applicable.
- Link decisions, reports, reviews, and blockers.
- Execute the committed JSON schemas first, then apply repository-level relationship and authority checks.

Don't:

- Announce a partially recorded transition.
- Use a message as a substitute for durable state.
- Invent missing acceptance to repair a contradiction.
- Bypass the shared mutation lock with an ad hoc writer.

Example:

- When ownership enters `Integrating`, the ticket remains `In Progress` while active ownership, the implementation report, and Operations' next action change together before handoff.

Validation:
All affected records agree on status, owner, dependencies, evidence, and return trigger; committed schemas execute; concurrent supported mutations serialize without lost updates; no stale reservation remains.

References:

- `.baton/workflow.md`
- `.baton/state/tickets.json`
- `.baton/state/ownership.json`
- `.baton/state/project.json`
- `.baton/state/goals.json`
- `.baton/state/reviews.json`

Notes:

- Repository state is the durable control plane for cross-role coordination.
