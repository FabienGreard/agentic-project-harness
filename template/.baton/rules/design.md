# Design

A module is an interface plus its implementation at any scale. Its interface includes everything callers must know: operations, invariants, ordering, errors, configuration, and relevant performance. A seam allows behavior to vary without changing the caller; an adapter is one implementation at that seam. Depth is the useful complexity hidden behind a small interface; locality keeps a capability’s knowledge, changes, defects, and verification with one owner.

Design from the capability and volatile details. State the interface, invariants, failures, ordering, ownership, and performance constraints before expanding implementation. Put policy where its owner can enforce it. Add an adapter only for demonstrated variation; two justified implementations normally establish a seam. Use the deletion test: removing a deep module spreads meaningful policy into callers, while removing a shallow wrapper only moves syntax.

Do not equate modules with files or packages, split by aesthetics, leak storage/transport/vendor details, or add abstractions without leverage. Callers and tests use the same public interface. For consequential, long-lived, high-fan-out, or uncertain interfaces, Operations commissions contrasting independent proposals from non-overlapping Ready investigations before choosing.
