# Classify Incoming Changes Before Interrupting Work

Title:
Classify Incoming Changes Before Interrupting Work

Type:
Rule

Purpose:
Protect active work while responding correctly to new instructions and discoveries.

Scope:
Management or Operations triage of new instructions, defects, discoveries, policy changes, and scope requests during active work.

Definition:
When Management or Operations triages an incoming change, it is superseding, parallel, queued, or informational. Contractor blocker/result scenarios that do not introduce a new instruction use `not_applicable`. Interrupt active work only when waiting would cause material rework, invalid acceptance, unsafe action, lost work, or an explicit urgent requirement. A scoped pause while unaffected assignment work continues is not an interruption of the whole active run.

How to Apply:

1. Compare the change with active scope, ownership, acceptance, and dependencies.
2. Classify it and record the classification.
3. For superseding work, preserve WIP, synchronize state, and route a bounded pause or replacement through Operations.
4. For other changes, record them without interrupting safe work.

Do:

- Prefer checkpoint-boundary adoption for non-urgent changes.
- Record discoveries as separate backlog work when they exceed scope.

Don't:

- Treat every new message as superseding.
- Expand an active scope silently.

Example:

- A newly requested report unrelated to an implementation lane is queued with its own owner rather than interrupting the active Contractor.

Validation:
The classification, impact, owner, next action, and whole-run interruption decision are explicit, and active work remains recoverable.

References:

- `.baton/workflow.md`
- `.baton/state/tickets.json`
- `.baton/state/goals.json`
- `.baton/state/ownership.json`

Notes:

- An exact safety or acceptance invalidation may justify immediate interruption.
