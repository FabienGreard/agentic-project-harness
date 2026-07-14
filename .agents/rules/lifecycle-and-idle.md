# Run Permanent Roles to Delegated Idle

Title:
Run Permanent Roles to Delegated Idle

Type:
Rule

Purpose:
Make permanent-role activity event-driven and prevent silent abandonment or polling.

Scope:
Permanent Management, Operations, and active Consultant activity.

Definition:
Management, Operations, and every active Consultant are permanent top-level tasks. Each active run completes currently actionable work, delegates owned work with a named return trigger, and pauses when no meaningful action remains. Contractors and Internal Audit are disposable.

How to Apply:

1. Refresh live state once.
2. Classify actionable work, dependencies, and decisions.
3. Complete safe owned actions or delegate through the authorized path.
4. Record owner, action, dependency, and return trigger before pausing.

Do:

- Resume on a named event such as a result, blocker, decision, or review request.
- Leave the repository control plane sufficient for the next role to act.

Don't:

- Poll delegated work or unchanged state.
- Idle while an owned actionable task is available.

Example:

- After dispatching a bounded implementation, Operations records the Contractor and return trigger, then pauses until the Contractor returns or reports a blocker.

Validation:
Every idle transition has a named owner and return trigger, and no actionable work is abandoned or repeatedly polled.

References:

- `docs/workflow.md`
- `docs/state/ownership.json`

Notes:

- Waiting for an event is normal; delegated idle is neither blocked nor complete.
