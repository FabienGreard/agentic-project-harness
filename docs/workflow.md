# Operating workflow

## Authority

- Human owner: final authority for declared human-review gates and material external commitments.
- Project Director: outcomes, priority, scope, readiness, decisions, publication, and review orchestration.
- Delivery Lead: execution plan, worker dispatch, ownership, integration, verification, and completion evidence.
- Specialist Lead: expert definition and acceptance within an approved domain.
- Execution worker: only the assigned objective and files/systems.
- Harness Evaluator: independent read-only assessment of orchestration behavior.

Missing product or outcome intent returns to the Project Director. Missing specialist requirements return to the owning Specialist Lead. Delivery is the only worker dispatch and revision-routing path: Project Director and Specialist Lead do not dispatch or steer workers.

## Status vocabulary

`Idea`, `Needs Definition`, `PRD in Progress`, `Ready`, `Queued`, `In Progress`, `Dispatched`, `Blocked`, `Integration`, `Verification`, `In Review`, `Completed`, and `Abandoned`.

Only Ready work enters execution. Blocked means a named dependency or decision prevents progress; Needs Definition means intent, acceptance, or execution scope is incomplete.

## Priority vocabulary

- P0 — critical risk, outage, safety, or broken core outcome
- P1 — essential for the current milestone
- P2 — important improvement
- P3 — valuable but not urgent
- P4 — exploration, polish, or future idea

Dependencies, risk, and integration safety may override simple priority order.

## Definition of Ready

Work is Ready only when objective, context, scope, non-goals, acceptance, dependencies, affected systems, risks, owner, verification, expected evidence, and major decisions are explicit. The Director approves outcome readiness; Delivery confirms execution readiness against live state. Any required Specialist Lead confirms proportional specialist readiness before execution.

## Director lifecycle

The Director uses event-driven run-to-delegated-idle:

1. Refresh live project and repository truth once.
2. Classify incoming instructions and discoveries.
3. Prepare decisions, readiness, priority, and review boundaries.
4. Assign the baton with owner, action, dependencies, and return trigger.
5. Complete other safe non-overlapping Director work, then idle without polling.

If the Director owns an action that is currently possible, it completes it before idling. A future Director action may wait only on a recorded trigger.

## Incoming changes

- **Superseding:** material overlap cannot safely wait; record the decision, request a safe pause, preserve WIP, synchronize state, and create a bounded prerequisite/replacement.
- **Parallel:** contracts and ownership are independent; register a separate lane and let current work continue.
- **Queued:** valid but non-urgent or not Ready; record it without interrupting the active owner.
- **Informational:** answer from verified state without changing ownership.

Prefer checkpoint-boundary adoption for non-urgent tooling, policy, architecture, and scope changes. Interrupt only to avoid material rework, invalid acceptance, WIP loss, unsafe action, or violation of explicit urgency.

## Delivery lifecycle

Delivery is run-to-idle:

1. Refresh live state and select the highest-priority safe Ready work.
2. Register ownership before edits.
3. Decompose exclusive scopes, dependencies, checkpoints, and integration order.
4. Default substantial independent execution to workers; record why any worker-sized scope remains direct.
5. Review every return and changed file, integrate, and verify.
6. Synchronize state and send one result, blocker, review, or idle-boundary handoff.
7. Continue while meaningful Ready/integration work remains; otherwise pause without polling.

Direct Delivery work is appropriate for small, tightly coupled, sensitive, integration, conflict-resolution, verification, or narrow revision scopes. Worker-first is not worker-only.

### Substantial integration review

Before substantial acceptance, Delivery runs a two-axis review using the [code-review skill](../.agents/skills/code-review/SKILL.md):

- pin the exact committed and dirty-worktree boundary, including relevant untracked files, while excluding unrelated changes;
- obtain independent read-only standards/architecture and specification/evidence findings;
- verify each finding against the pinned diff and controlling requirements, then accept, revise, or reject as Delivery;
- hand off the pinned diff, both findings sets, implementation report, exact verification evidence, limitations, and next baton to the Project Director.

Reviewers do not edit, accept, integrate, update state, or route revisions. This review precedes substantial acceptance. Specialist domain approval remains a separate expert gate and does not replace technical acceptance or Delivery integration.

## Specialist lifecycle

The Specialist Lead is a standard run-to-idle role. It remains dormant until an approved recurring expert domain creates a definition or review trigger. It defines proportional requirements, reviews returned evidence, accepts or requests exact revisions, and hands executable work to Delivery. It does not set overall priority, dispatch workers, integrate implementation, or remain active without a domain trigger.

The Project Director performs final-audit mode on substantial returned work by consuming Delivery's pinned diff, two-axis findings, implementation report, and exact evidence. The Director does not dispatch reviewers or steer workers; implementation revisions route through Delivery. A final audit and Specialist approval do not by themselves authorize publication or satisfy a separate human-review gate.

## Control-plane communication

Repository records are authoritative. Messages signal wake, pause, blocker, decision, review, urgent invalidation, result, or idle boundary. Returning roles synchronize their owned records, send one explicit handoff to the registered destination, and stop without polling.

Every handoff names controlling IDs, current status, owner, scope, dependencies, evidence, and return/wake trigger. A transition is incomplete until human-readable and machine-readable state agree.

## Definition of Done

Work becomes Completed only when:

- implementation/output matches approved scope and acceptance;
- proportional automated, operational, experiential, and regression checks pass;
- affected boundaries are reviewed;
- documentation and project state are current;
- an implementation report records changes, choices, commands/results, limitations, and follow-ups;
- Delivery accepts integration;
- required Specialist and human reviews are recorded.

Completion does not bypass a separate publication, release, financial, legal, customer, or milestone approval gate.

## Harness evaluation

Use [evals/harness/README.md](evals/harness/README.md): static checks after state changes, scenario smoke after material harness changes, repeated comparisons before accepting a major redesign, and independent live-trace audits at meaningful checkpoints or after orchestration incidents.
