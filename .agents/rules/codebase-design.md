# Design Deep Modules at Deliberate Seams

Title:
Design Deep Modules at Deliberate Seams

Type:
Rule

Purpose:
Improve maintainability by concentrating policy behind clear interfaces and stable boundaries.

Scope:
New modules, refactors, integrations, architecture reviews, and interface changes.

Definition:
A **module** is an interface plus its implementation at any scale. Its **interface** is everything callers must know, including operations, invariants, ordering, errors, configuration, and relevant performance behavior. A **seam** is where behavior can vary without changing the caller, and an **adapter** is one concrete implementation at that seam. **Depth** is the leverage a small interface provides over meaningful hidden complexity; **locality** keeps a capability's knowledge, changes, defects, and verification with one clear owner. A deep module concentrates coherent policy behind a small stable interface at a deliberate seam.

How to Apply:

1. Identify the user or system capability and the volatile details around it.
2. Describe the intended interface, invariants, failure behavior, ordering, and relevant performance constraints before expanding implementation.
3. Place policy with the owner that can enforce its invariants.
4. Introduce an adapter only where behavior genuinely varies; two justified implementations normally establish a real seam.
5. Apply the deletion test: deleting a shallow module merely moves complexity, while deleting a deep module spreads meaningful policy back into callers.
6. Verify callers and tests use the same public interface rather than hidden internals.
7. For a consequential, long-lived, high-fan-out, or uncertain interface, begin from a non-overlapping Ready investigation and have Delivery dispatch multiple independent design workers with contrasting constraints before recommending an interface.

Do:

- Prefer cohesive interfaces over pass-through wrappers.
- Make ownership, invariants, failure behavior, and lifecycle explicit.
- Use evidence from current callers and tests.
- Use `module`, `interface`, `implementation`, `depth`, `seam`, `adapter`, `leverage`, and `locality` precisely.

Don't:

- Equate a module with a file, directory, package, class, component, or service.
- Split modules solely by file count, aesthetics, or nouns.
- Leak storage, transport, or vendor details through public contracts.
- Add abstractions without a demonstrated seam or benefit.

Example:

- A reporting service owns filtering and pagination policy while adapters translate database and export formats at the boundary.

Validation:
The module has a documented capability, small interface, meaningful hidden implementation, clear ownership, justified seams/adapters, representative tests, deletion-test leverage, and no unnecessary leakage. Consequential interfaces include contrasting independent proposals from Delivery-dispatched workers.

References:

- `docs/workflow.md`
- `.agents/rules/testing.md`

Notes:

- Small, low-risk changes need only proportional design evidence.
