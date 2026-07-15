# Optional ticket narratives

Canonical tickets live in [`.baton/state/tickets.json`](../state/tickets.json), link to observable goals in [`.baton/state/goals.json`](../state/goals.json), and are changed transactionally with `.baton/bin/baton _state apply`. Use this directory only when a ticket needs supporting rationale too large for its structured record, then set that ticket's optional `narrativePath`.

Every ticket includes an `assurance` object with resolved `testRigor`, explicit `humanReviewStages`, and `overrideReason`. Use `Lean`, `Standard`, or `Thorough`. Human review stages are `Readiness`, `Acceptance`, and `Release`; `[]` explicitly means none. If a ticket differs from `.baton/state/project.json` defaults, record the user-authorized reason rather than relying on conversation history.

Start from the [ticket operation example](../templates/ticket.operation.json), merge the existing ticket array rather than dropping unrelated records, and keep non-executable umbrellas out of Operations' Ready queue.
