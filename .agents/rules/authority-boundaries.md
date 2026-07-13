# Respect Role Authority Boundaries

Title:
Respect Role Authority Boundaries

Type:
Rule

Purpose:
Keep decisions, dispatch, specialist acceptance, evaluation, and execution distinct.

Scope:
Every decision, assignment, review, handoff, and repository change.

Definition:
The Project Director owns outcomes, priority, scope, readiness, durable decisions, publication, and human-review gates. The Delivery Lead owns planning, dispatch, ownership, integration, verification, and completion evidence. The Specialist Lead defines and accepts its approved domain while dormant otherwise. The Harness Evaluator independently assesses orchestration. Execution Workers perform only assigned work.

How to Apply:

1. Identify the authority required by the decision.
2. Route execution scope and revisions through Delivery.
3. Keep specialist acceptance separate from technical integration acceptance.
4. Record decisions and handoffs in repository state.

Do:

- Escalate missing outcome intent to the Project Director.
- Escalate missing specialist requirements to the owning Specialist Lead.
- Keep Delivery as the single dispatch center.

Don't:

- Let a worker redefine priority or product intent.
- Let a Specialist Lead dispatch a competing execution path.
- Let an evaluator mutate active work.

Example:

- A data-specialist review may define evidence requirements; Delivery assigns implementation and accepts integration after those requirements are recorded.

Validation:
Each decision and handoff has one authorized owner, and no role performs another role's exclusive authority.

References:

- `docs/workflow.md`
- `docs/roles/project-director.md`
- `docs/roles/delivery-lead.md`
- `docs/roles/specialist-lead.md`
- `docs/roles/harness-evaluator.md`
- `docs/roles/execution-worker.md`

Notes:

- The standard Specialist Lead is mandatory but remains dormant without an approved recurring domain trigger.
