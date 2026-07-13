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
4. Verify records agree before sending a handoff.

Do:

- Update ticket, backlog, active work, overview, and machine state together when applicable.
- Link decisions, reports, reviews, and blockers.

Don't:

- Announce a partially recorded transition.
- Use a message as a substitute for durable state.
- Invent missing acceptance to repair a contradiction.

Example:

- When work enters Integration, the ticket, backlog, active ownership, implementation report, and Delivery next action all change before handoff.

Validation:
All affected records agree on status, owner, dependencies, evidence, and return trigger; no stale reservation remains.

References:

- `docs/workflow.md`
- `docs/backlog.md`
- `docs/active-work.md`
- `docs/project-state.json`

Notes:

- Repository state is the durable control plane for cross-role coordination.
