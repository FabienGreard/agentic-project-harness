# Run Permanent Roles to Delegated Idle

Title:
Run Permanent Roles to Delegated Idle

Type:
Rule

Purpose:
Make permanent-role activity event-driven, keep wake authority explicit, and prevent persistent-goal loops, silent abandonment, or polling.

Scope:
Permanent Management, Operations, and active Consultant activity.

Definition:
Management, Operations, and every active Consultant are permanent top-level tasks. An explicit new message to that task is the sole wake mechanism. Each valid run completes currently actionable work, delegates owned work with a named return trigger, and ends when no meaningful action remains. Codex persistent goals are not role identity or a lifecycle control plane and must never be created, inspected, resumed, recreated, attached, paused, cleared, completed, or otherwise operated by these roles. Contractors and Internal Audit are disposable. Repository project goals under `docs/state/goals.json` are ordinary milestone data and are unrelated to Codex persistent goals.

How to Apply:

1. Confirm that the run was woken by an explicit new task message.
2. Refresh live state once.
3. Classify actionable work, dependencies, and decisions.
4. Complete safe owned actions or delegate through the authorized path.
5. Record owner, action, dependency, and return trigger before ending the run.
6. If a legacy automatic continuation resumes the task without a new message, treat it as a non-wake event: perform no speculative work or persistent-goal operation, report it for user or administrative removal, and end immediately.

Do:

- Resume only when a task message delivers a named event such as a result, blocker, decision, or review request.
- Leave the repository control plane sufficient for the next role to act.
- Treat this repository policy as superseding any older onboarding prompt that requests a persistent goal.

Don't:

- Poll delegated work or unchanged state.
- Idle while an owned actionable task is available.
- Use any persistent-goal operation, even when the surface exposes complete goal controls.
- Treat repository changes, timers, automatic continuations, or remembered onboarding instructions as wakes without a new task message.

Example:

- After dispatching a bounded implementation, Operations records the Contractor and return trigger, then ends the run. A Contractor return or blocker wakes Operations only through an explicit message to the Operations task. If an obsolete goal causes an automatic continuation first, Operations reports the legacy continuation for removal and performs no work.

Validation:
Every active run begins with a new task message, every idle transition has a named owner and return trigger, no persistent-goal operation occurs, legacy auto-resumes do no speculative work, and no actionable work is abandoned or repeatedly polled.

References:

- `docs/workflow.md`
- `docs/state/ownership.json`
- `docs/decisions/ADR-0001-task-message-wake-only.md`

Notes:

- Waiting for an event is normal; delegated idle is neither blocked nor complete.
