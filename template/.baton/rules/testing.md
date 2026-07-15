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
For deterministic behavior, establish a public seam and independent expected result, observe a meaningful failing test, implement the smallest passing slice, then deepen or refactor after green. Each ticket resolves one test-rigor level: `Lean` for focused changed-behavior proof, `Standard` for focused proof plus affected regression and applicable runtime evidence, or `Thorough` for Standard coverage plus broader regression, negative/failure paths, and applicable operational or experiential evidence.

How to Apply:

1. Resolve the ticket's test rigor from the project default or a human-authorized override with a recorded reason.
2. Use `Lean` for isolated, reversible, low-impact behavior; `Standard` for normal product or operational work; and `Thorough` for changes with material security, privacy, authorization, money, migration, irreversible-data, broad-compatibility, concurrency, or failure-path risk.
3. Record the seam, observable behavior, expected result, and test layer.
4. Write and run one focused failing behavior test.
5. Implement only enough to pass.
6. Run the checks required by the resolved rigor and the ticket's explicit `requiredVerification`.
7. Refactor after behavior is green and preserve coverage.

Do:

- Test public capabilities through real owned interfaces.
- Control only true external effects.
- Record red and green commands and results.
- Treat `Lean` as a smaller evidence boundary, never as permission to omit changed-behavior proof.
- Resolve rigor from approved impact and risk rather than escalating it for speculative findings.

Don't:

- Test private implementation details or collaborator call order.
- Mock modules the repository owns when they can run deterministically.
- Treat automated tests as proof of human or operational acceptance.
- Lower test rigor silently or use a test-rigor label to bypass a safety, compliance, irreversible-action, or release gate.
- Expand testing beyond the resolved rigor without a failed acceptance criterion, reachable risk, or new evidence.

Example:

- For a CSV import rule, a test first proves the accepted row and error result independently, then the smallest parser change makes it pass.

Validation:
Evidence shows the resolved test rigor, an ordered behavior test cycle, the checks required at that level, ticket-specific verification, and required non-test review.

References:

- `.baton/rules/codebase-design.md`
- `.baton/rules/risk-based-findings.md`
- `.baton/rules/completion-and-review.md`
- `.baton/workflow.md`

Notes:

- Exploratory diagnostics may use a bounded hypothesis instead of strict red-to-green, with regression coverage for stable behavior.
