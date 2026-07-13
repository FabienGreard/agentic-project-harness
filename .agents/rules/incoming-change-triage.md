# Classify Incoming Changes Before Interrupting Work

Title:
Classify Incoming Changes Before Interrupting Work

Type:
Rule

Purpose:
Protect active work while responding correctly to new instructions and discoveries.

Scope:
New instructions, defects, discoveries, policy changes, and scope requests during active work.

Definition:
An incoming change is superseding, parallel, queued, or informational. Interrupt only when waiting would cause material rework, invalid acceptance, unsafe action, lost work, or an explicit urgent requirement.

How to Apply:

1. Compare the change with active scope, ownership, acceptance, and dependencies.
2. Classify it and record the classification.
3. For superseding work, preserve WIP, synchronize state, and route a bounded pause or replacement through Delivery.
4. For other changes, record them without interrupting safe work.

Do:

- Prefer checkpoint-boundary adoption for non-urgent changes.
- Record discoveries as separate backlog work when they exceed scope.

Don't:

- Treat every new message as superseding.
- Expand an active scope silently.

Example:

- A newly requested report unrelated to an implementation lane is queued with its own owner rather than interrupting the active worker.

Validation:
The classification, impact, owner, and next action are explicit, and active work remains recoverable.

References:

- `docs/workflow.md`
- `docs/backlog.md`
- `docs/active-work.md`

Notes:

- An exact safety or acceptance invalidation may justify immediate interruption.
