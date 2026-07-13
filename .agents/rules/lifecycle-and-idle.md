# Run Permanent Roles to Delegated Idle

Title:
Run Permanent Roles to Delegated Idle

Type:
Rule

Purpose:
Make role activity event-driven and prevent silent abandonment or polling.

Scope:
Permanent Project Director, Delivery Lead, and Specialist Lead activity.

Definition:
Each permanent role completes currently actionable work, delegates owned work with a named return trigger, and pauses when no meaningful action remains.

How to Apply:

1. Refresh live state once.
2. Classify actionable work, dependencies, and decisions.
3. Complete safe owned actions or delegate through the authorized path.
4. Record owner, action, dependency, and return trigger before idling.

Do:

- Resume on a named event such as a result, blocker, decision, or review request.
- Leave the repository control plane sufficient for the next role to act.

Don't:

- Poll delegated work or unchanged state.
- Idle while an owned actionable task is available.

Example:

- After dispatching a bounded implementation, Delivery records the worker and return trigger, then pauses until the worker returns or reports a blocker.

Validation:
Every idle transition has a named owner and return trigger; no actionable work is abandoned or repeatedly polled.

References:

- `docs/workflow.md`
- `docs/active-work.md`

Notes:

- Waiting for an event is normal; a named unresolved dependency is a blocker.
