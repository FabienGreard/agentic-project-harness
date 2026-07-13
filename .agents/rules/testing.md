# Develop Behavior Through Vertical Red-to-Green Slices

Title:
Develop Behavior Through Vertical Red-to-Green Slices

Type:
Rule

Purpose:
Use behavior-focused tests to guide implementation and preserve evidence at important interfaces.

Scope:
New behavior, bug fixes, revisions, tests, mocks, integrations, and refactors.

Definition:
For deterministic behavior, establish a public seam and independent expected result, observe a meaningful failing test, implement the smallest passing slice, then deepen or refactor after green.

How to Apply:

1. Record the seam, observable behavior, expected result, and test layer.
2. Write and run one focused failing behavior test.
3. Implement only enough to pass.
4. Run focused, affected, and authoritative checks.
5. Refactor after behavior is green and preserve coverage.

Do:

- Test public capabilities through real owned interfaces.
- Control only true external effects.
- Record red and green commands and results.

Don't:

- Test private implementation details or collaborator call order.
- Mock modules the repository owns when they can run deterministically.
- Treat automated tests as proof of human or operational acceptance.

Example:

- For a CSV import rule, a test first proves the accepted row and error result independently, then the smallest parser change makes it pass.

Validation:
Evidence shows an ordered behavior test cycle, focused and affected checks pass, and required non-test review is complete.

References:

- `.agents/rules/codebase-design.md`
- `.agents/rules/completion-and-review.md`
- `docs/workflow.md`

Notes:

- Exploratory diagnostics may use a bounded hypothesis instead of strict red-to-green, with regression coverage for stable behavior.
