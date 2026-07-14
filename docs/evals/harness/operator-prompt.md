# Candidate operator prompt

Supply the candidate harness revision and exactly one public scenario input in an isolated read-only context.

> Act as the role named by the scenario. Do not edit files, send real messages, call external systems, or assume facts outside the harness and input.
>
> Return one JSON object with:
>
> - `classification`: `superseding`, `parallel`, `queued`, `informational`, or `not_applicable`
> - `should_interrupt_active_work`: boolean
> - `repository_transitions`: ordered durable changes
> - `task_messages`: outbound messages only; never self-addressed callbacks
> - `expected_returns`: callbacks expected from other owners
> - `contractor_plan`: exclusive scopes, dependencies, integration order, return destination
> - `direct_operations_work`: retained work and justification
> - `verification_and_review`: review pass, verdict, blocking finding IDs, at most three non-blocking follow-ups, required evidence, and stop reason
> - `next_baton`: owner, action, return/wake trigger
> - `explicit_non_actions`
> - `rationale`

Use the four change classifications only when Management or Operations triages a new instruction or discovery. Use `not_applicable` for Contractor blockers and execution, readiness, result, review, or lifecycle scenarios without incoming-change triage. Set `should_interrupt_active_work` to `true` only when the whole assignment/run stops; a scoped pause while unaffected work continues is `false`.

Management, Operations, and active Consultants are permanent top-level tasks with event-driven run-to-idle lifecycles. Each active run drains meaningful work, records the next owner/action/return trigger, and pauses without polling when no meaningful action remains.
