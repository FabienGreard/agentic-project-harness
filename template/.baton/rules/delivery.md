# Delivery

Only `Ready` work executes. A Ready Ticket states its Goal, objective, context, scope, non-goals, acceptance, dependencies, affected systems, risks, owner, required verification, resolved Readiness Protocol, resolved Clearance Protocol, and applicable Consultants. Its Goal also stores its resolved Clearance Protocol. Management approves outcome readiness; Operations confirms executable boundaries and dependencies. Missing intent stays `Backlog`; unmet dependencies stay `Blocked`. Discoveries outside scope become separate work.

Operations is the single dispatch center. Before edits, it registers one owner for each coherent file or system boundary. A Contractor receives one bounded objective, exclusive scope, dependencies, acceptance, verification, return destination, and blocker protocol. Parallel scopes must be disjoint or explicitly coordinated. Revisions return through Operations. Ownership is released only with a complete handoff.

Every transition is one transaction. Update affected status, owner, dependencies, evidence, reviews, next action, and return trigger together through Baton’s deterministic state tools and shared project lock. Run committed schemas before relationship and authority checks. A message never substitutes for durable state, and a transition is not announced until canonical records agree.

Classify incoming work as `superseding`, `parallel`, `queued`, or `informational`; use `not_applicable` for an ordinary result or blocker. Interrupt only when delay would cause material rework, invalidate acceptance, make an action unsafe, lose work, or violate explicit urgency. Preserve work before replacing it. Adopt safe changes at a checkpoint and keep unaffected work moving.

Completion requires:

- the objective, acceptance, and non-goals satisfied;
- the exact diff and affected boundaries reviewed;
- checks required by the resolved Readiness Protocol and `requiredVerification` passed, or a `Waived` result is explicitly reported as unverified;
- commands, results, limitations, and follow-ups recorded in the Report;
- state, ownership, and evidence synchronized;
- Operations integration acceptance plus every required Consultant `Acceptance` review; and
- every Goal and Ticket Clearance required by the resolved protocol recorded for the exact target and stage.

Apply each Goal or Ticket Clearance at the exact target and stage defined in `workflow.md`; stages never substitute. Report unresolved failures and limitations. Never mark work `Done` with stale State, missing Evidence, or implicit approval.
