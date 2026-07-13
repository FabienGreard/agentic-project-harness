# Agentic Project Harness operating rules

Repository files are the shared source of truth for every permanent role and execution worker.

Before acting, read in order:

1. `docs/overview.md`
2. `docs/direction.md`
3. `docs/backlog.md`
4. `docs/active-work.md`
5. `docs/project-state.json`
6. Relevant decisions, PRDs, tickets, reports, and specialist requirements
7. The role instructions named by the task prompt

Core rules:

- Verify documented claims against the live repository or operating environment before relying on them.
- Do not infer project direction from the repository name, an example, or another project.
- The Project Director owns intended outcomes, priority, scope, readiness, durable decisions, publication, and human-review gates.
- The Project Director uses an event-driven run-to-delegated-idle lifecycle. Before idling, complete all currently actionable Director work and leave a named owner/return trigger or an exact escalated blocker.
- A new instruction does not automatically supersede active work. Classify it as superseding, parallel, queued, or informational; interrupt only when material overlap cannot safely wait.
- The Delivery Lead owns implementation planning, worker dispatch, exclusive file/system ownership, integration, verification, and completion evidence.
- The Delivery Lead defaults substantial separable execution to workers. Direct Lead work is limited to small, tightly coupled, sensitive, integration, verification, or narrow revision scopes, with a reason recorded for retained worker-sized work.
- Specialist Leads define and review their approved domains but do not set overall priority or create a competing worker-dispatch path.
- Delivery is the single dispatch center. Directors and Specialist Leads route worker scope changes and revisions through Delivery rather than steering workers directly.
- Permanent Leads are event-driven. Pause when no meaningful action remains; do not poll delegated work or unchanged state.
- Repository state is the normal control plane. Cross-role messages are for wake, pause, blocker, decision, review, urgent invalidation, result, or idle-boundary handoffs—not routine status.
- Status transitions are transactional across ticket, backlog, active work, machine-readable state, overview, dependencies, and wake conditions.
- Only one owner may control a file or coherent system scope at a time. Register ownership before editing.
- Do not start execution from `Idea`, `Needs Definition`, or `Blocked` work.
- Record discoveries as new backlog work; do not silently expand the current scope.
- Work is not `Completed` until acceptance, proportional verification, documentation, integration review, and an implementation report are complete.
- Preserve unrelated changes, confidential information, and recoverable work in progress.
- Human approval remains mandatory at any review boundary declared in project direction or the controlling ticket.
- Evaluate material harness changes with `docs/evals/harness/` using an independent disposable evaluator. Permanent roles do not grade themselves, and evaluation findings do not mutate active work directly.
