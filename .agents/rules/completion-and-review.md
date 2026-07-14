# Prove Completion Before Advancing

Title:
Prove Completion Before Advancing

Type:
Rule

Purpose:
Ensure completed work matches acceptance and leaves usable evidence for integration and review.

Scope:
Every implementation, document, investigation, handoff, release candidate, and completion transition.

Definition:
Work is complete only when scope and acceptance are met, proportional verification passes, boundaries are reviewed, documentation and state are current, and the required Operations, Consultant, Internal Audit, and human reviews are recorded.

How to Apply:

1. Re-read objective, non-goals, acceptance, and constraints.
2. Review the exact diff and affected boundaries.
3. Run focused, regression, operational, and other proportional checks.
4. Record commands, results, limitations, and follow-ups in an implementation report.
5. Synchronize state and obtain the ticket's required `Acceptance` reviews before advancing.
6. For every ID in `requiredConsultantIds`, record an approved Consultant `Acceptance` review linked to evidence.
7. Keep any required human `Release` review pending until publication or release is actually requested.

Do:

- Match evidence to impact and risk.
- Keep publication and other human-gated actions separate from technical completion.
- Report limitations explicitly.

Don't:

- Treat a passing unit test as universal acceptance.
- Mark work complete with undocumented failures or stale state.
- Bypass a declared human-review gate.
- Treat an approved `Acceptance` review as an approved `Release` review.

Example:

- A service change is complete after its contract tests, affected integration check, diff review, report, and required approval are recorded.

Validation:
Acceptance, resolved test rigor, verification, documentation, state, integration review, and required Consultant/human approvals are all evidenced. Every approval identifies its stage; a required `Release` approval remains a separate publication gate.

References:

- `docs/workflow.md`
- `docs/implementation-reports/README.md`
- `docs/review-packets/README.md`
- `docs/state/reviews.json`

Notes:

- Operations owns integration acceptance; Consultant and human gates remain distinct.
