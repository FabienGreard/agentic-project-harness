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
Only `Ready` work enters execution. Ready work has an objective, context, scope, non-goals, acceptance, dependencies, affected systems, risks, owner, verification, resolved test rigor, explicit human-review stages, and major decisions explicit.

How to Apply:

1. Identify the controlling goal, records, and intended milestone.
2. Confirm every readiness field is explicit and testable.
3. Decompose broad work into coherent reviewable slices.
4. Obtain Management outcome-readiness approval.
5. Have Operations confirm executable dependencies, ownership, and verification.
6. Resolve ticket assurance from project defaults; record a human-authorized reason for any override.
7. Record every applicable active Consultant ID in `requiredConsultantIds` and an approved `Readiness` review for each one.
8. If human review is required at `Readiness`, record its approval before promotion.
9. Promote state transactionally only after applicable gates pass.
10. Record discoveries as separate backlog work.

Do:

- State non-goals and affected-system boundaries.
- Record unresolved ticket intent as `Backlog` and dependencies as `Blocked`.
- Permit bounded investigations that gather evidence without expanding behavior.

Don't:

- Start from `Backlog` or `Blocked`.
- Require a Contractor to invent missing intent.
- Expand an active ticket when unrelated work appears.
- Leave test rigor or human-review timing implicit.

Example:

- A migration task is not Ready until its target data, compatibility boundary, rollback, acceptance, dependency owners, and verification command are explicit.

Validation:
Every executed scope traces to Ready work with explicit acceptance, assurance, approvals, dependencies, ownership, verification, and approved readiness from every Consultant named by ID and every required human `Readiness` review.

References:

- `docs/workflow.md`
- `docs/state/tickets.json`
- `docs/state/goals.json`
- `docs/state/reviews.json`
- `docs/roles/management.md`
- `docs/roles/operations.md`

Notes:

- Urgency changes response speed, not the need for a bounded objective and owner.
