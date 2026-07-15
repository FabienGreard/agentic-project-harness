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
Management, Operations, and every active Consultant are permanent top-level tasks. A new message to that exact task is the sole wake mechanism. Each active run completes currently actionable work, delegates owned work with a named return trigger, and pauses when no meaningful action remains. Contractors and Internal Audit are disposable. Persistent goals are never role identity or a lifecycle mechanism and must not be created, resumed, recreated, or attached by a permanent role, even when a surface exposes full goal controls.

How to Apply:

1. Refresh live state once.
2. Classify actionable work, dependencies, and decisions.
3. Complete safe owned actions or delegate through the authorized path.
4. Record owner, action, dependency, and return trigger before pausing.
5. Treat an automatic continuation without a new task message as a non-wake event: do no speculative work, report the legacy continuation for user or administrative removal, and end the run.

Do:

- Resume on a named event such as a result, blocker, decision, or review request.
- Leave the repository control plane sufficient for the next role to act.
- Follow current repository policy when an older onboarding prompt requests a persistent goal; this rule supersedes that prompt.

Don't:

- Poll delegated work or unchanged state.
- Idle while an owned actionable task is available.
- Create, resume, recreate, inspect for control purposes, or attach a persistent goal to represent a permanent role.

Example:

- After dispatching a bounded implementation, Operations records the Contractor and return trigger, then pauses until the Contractor returns or reports a blocker.

Validation:
Every idle transition has a named owner and return trigger, and no actionable work is abandoned or repeatedly polled.

References:

- `.baton/workflow.md`
- `.baton/state/ownership.json`

Notes:

- Waiting for an event is normal; delegated idle is neither blocked nor complete.
- Legacy auto-resumes are non-wake events and never authorize repository refresh, speculative execution, dispatch, or state mutation.
- Manual goal controls and Computer Use are not lifecycle workarounds; Baton does not ask an agent to operate the Codex UI to create or manage a goal.
