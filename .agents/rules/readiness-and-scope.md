# Start Only Ready and Bounded Work

Title:
Start Only Ready and Bounded Work

Type:
Rule

Purpose:
Ensure execution begins from approved intent, explicit boundaries, and verifiable outcomes.

Scope:
Every ticket, initiative, revision, investigation, and implementation scope.

Definition:
Only `Ready` work enters execution. Ready work has an objective, context, scope, non-goals, acceptance, dependencies, affected systems, risks, owner, verification, and major decisions explicit.

How to Apply:

1. Identify the controlling records and intended milestone.
2. Confirm every readiness field is explicit and testable.
3. Decompose broad work into coherent reviewable slices.
4. Obtain Project Director outcome-readiness approval.
5. Have Delivery confirm executable dependencies, ownership, and verification.
6. Promote state transactionally only after applicable gates pass.
7. Record discoveries as separate backlog work.

Do:

- State non-goals and affected-system boundaries.
- Record unresolved intent as `Needs Definition` and dependencies as `Blocked`.
- Permit bounded investigations that gather evidence without expanding behavior.

Don't:

- Start from `Idea`, `Needs Definition`, or `Blocked`.
- Require a worker to invent missing intent.
- Expand an active ticket when unrelated work appears.

Example:

- A migration task is not Ready until its target data, compatibility boundary, rollback, acceptance, dependency owners, and verification command are explicit.

Validation:
Every executed scope traces to Ready work with explicit acceptance, approvals, dependencies, ownership, and verification.

References:

- `docs/workflow.md`
- `docs/backlog.md`
- `docs/roles/project-director.md`
- `docs/roles/delivery-lead.md`

Notes:

- Urgency changes response speed, not the need for a bounded objective and owner.
