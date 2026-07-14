# ADR-0001 — Task messages are the sole permanent-role wake mechanism

Status: Accepted
Date: 2026-07-14
Owners: Management

## Context

Management, Operations, and active Consultants need durable role identity and event-driven run-to-idle behavior across Codex surfaces. Persistent-goal controls vary by surface, can generate automatic continuations, and can conflict with explicit repository state and task-message handoffs. Older onboarding prompts may still request that a permanent role create or attach a persistent goal.

Repository project goals under `docs/state/goals.json` are milestone records. They are unrelated to Codex persistent goals and do not provide runtime wake behavior.

## Options considered

- Use persistent goals whenever complete create, inspect, pause, resume, and clear controls exist.
- Use persistent goals only as optional role execution aids.
- Prohibit persistent-goal operations and use explicit task messages as the sole wake mechanism.

## Decision

Management, Operations, and every active Consultant are permanent top-level tasks. A new message to the relevant task is the sole wake mechanism. Permanent roles never create, inspect, resume, recreate, attach, pause, clear, complete, or otherwise operate persistent goals, even when complete controls are available.

Current repository policy supersedes every older onboarding prompt that requests a persistent goal. An automatic continuation without a new task message is a non-wake event. The role performs no speculative work or goal operation, reports the legacy continuation for user or administrative removal, and ends immediately.

## Rationale

One explicit wake path is portable, observable, and easy to audit. Repository state remains the durable coordination record, while task messages carry intentional events. Removing a second runtime lifecycle mechanism prevents recursive work, idle polling, and accidental work caused by obsolete goals.

## Consequences

- Permanent tasks run only after explicit task messages and end at delegated idle.
- Delegated idle is neither blocked nor complete.
- Repository changes and timers cannot wake a role by themselves.
- Legacy goals must be removed by the user or an administrator; agents report them but perform no goal operation.
- Evaluator fixtures must fail candidates that call a goal operation or perform speculative work on a legacy auto-resume.

## Evidence

- `.agents/rules/lifecycle-and-idle.md`
- `docs/evals/harness/scenarios/inputs/H-011.md`
- `docs/evals/harness/scenarios/oracles/H-011.md`

## Systems or processes affected

- Permanent-role contracts and Codex agent configurations
- Task registry and handoff protocol
- Harness scenario evaluation and static checks
- Generated project onboarding guidance
