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
> - `worker_plan`: exclusive scopes, dependencies, integration order, return destination
> - `direct_lead_work`: retained work and justification
> - `verification_and_review`
> - `next_baton`: owner, action, return/wake trigger
> - `explicit_non_actions`
> - `rationale`

Use the four change classifications only for a new instruction or discovery. Use `not_applicable` for execution, readiness, result, review, and lifecycle scenarios without incoming-change triage.
