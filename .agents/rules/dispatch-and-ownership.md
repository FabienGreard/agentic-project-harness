# Dispatch Work Through Explicit Ownership

Title:
Dispatch Work Through Explicit Ownership

Type:
Rule

Purpose:
Enable safe parallel execution without overlap, ambiguity, or orphaned work.

Scope:
Planning, Contractor assignment, file ownership, parallelization, handoff, and integration.

Definition:
Operations is the single dispatch center. Each Contractor receives one bounded objective, exclusive file or system scope, dependencies, acceptance, verification, and return destination before editing.

How to Apply:

1. Confirm the work is Ready and dependencies are satisfied.
2. Inspect live state and register ownership before edits.
3. Decompose independent scopes and name integration order.
4. Route revisions through Operations.
5. Release ownership only after evidence and handoff are complete.

Do:

- Prefer Contractors for substantial separable execution.
- Record why tightly coupled or sensitive work stays with Operations.
- Preserve unrelated changes at boundaries.

Don't:

- Assign overlapping ownership without explicit coordination.
- Dispatch work from undefined or blocked intent.
- Let Contractors create a competing dispatch path.

Example:

- Documentation and test updates may run in parallel when their files and dependencies are disjoint; Operations integrates both after review.

Validation:
Every edit has one registered owner, bounded acceptance, dependencies, verification, and a return destination.

References:

- `docs/state/ownership.json`
- `docs/workflow.md`
- `docs/roles/operations.md`
- `docs/roles/contractor.md`

Notes:

- Coherent system scope may be narrower than a single file.
