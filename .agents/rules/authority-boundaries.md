# Respect Role Authority Boundaries

Title:
Respect Role Authority Boundaries

Type:
Rule

Purpose:
Keep decisions, dispatch, Consultant acceptance, Internal Audit, and Contractor execution distinct.

Scope:
Every decision, assignment, review, handoff, and repository change.

Definition:
Management owns outcomes, priority, scope, readiness, durable decisions, publication, and human-review gates. Operations owns planning, Contractor dispatch, ownership, integration, verification, and completion evidence. Each active Consultant defines and accepts only its approved domain. Internal Audit independently assesses the harness outside the project team. Contractors perform only assigned work.

How to Apply:

1. Identify the authority required by the decision.
2. Route execution scope and revisions through Operations.
3. Keep Consultant acceptance separate from technical integration acceptance.
4. Record decisions and handoffs in repository state.

Do:

- Escalate missing outcome intent to Management.
- Escalate missing expert requirements to the relevant active Consultant.
- Keep Operations as the single dispatch center.

Don't:

- Let a Contractor redefine priority or project intent.
- Let a Consultant dispatch a competing execution path.
- Let Internal Audit mutate active work or act as project QA.

Example:

- A Data Lead Consultant may define evidence requirements; Operations assigns implementation and accepts integration after those requirements are recorded.

Validation:
Each decision and handoff has one authorized owner, and no role performs another role's exclusive authority.

References:

- `docs/workflow.md`
- `docs/roles/management.md`
- `docs/roles/operations.md`
- `docs/roles/consultant.md`
- `docs/roles/internal-audit.md`
- `docs/roles/contractor.md`

Notes:

- Consultants are optional and unlimited; every active Consultant must conform to the same authority template in `docs/state/team.json`.
