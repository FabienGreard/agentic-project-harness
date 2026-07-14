# Operating workflow

## Authority

- Human owner: final authority for declared human-review gates and material external commitments.
- Management: outcomes, priority, scope, readiness, decisions, publication, and review orchestration, expressed through the configured professional persona.
- Operations: execution plan, Contractor dispatch, ownership, integration, verification, and completion evidence, expressed through the configured professional persona.
- Consultant: expert definition and acceptance within one active approved domain.
- Contractor: only the assigned objective and files/systems.
- Internal Audit: hidden independent read-only assessment of the harness; never project QA or a project-team member.

Missing project or outcome intent returns to Management. Missing expert requirements return to the relevant active Consultant. Operations is the only Contractor dispatch and revision-routing path: Management and Consultants do not dispatch or steer Contractors.

## Status vocabulary

Tickets use the small stakeholder-facing lifecycle `Backlog`, `Ready`, `In Progress`, `Blocked`, `In Review`, `Done`, and `Cancelled`.

- `Backlog`: intent, acceptance, or execution scope is still incomplete.
- `Ready`: the work is fully defined and approved for execution.
- `In Progress`: the delivery team is actively assigning, building, integrating, or verifying the work.
- `Blocked`: a named dependency or decision prevents progress.
- `In Review`: returned work is waiting for required acceptance.
- `Done`: the work and required evidence have been accepted.
- `Cancelled`: the work was intentionally stopped.

Only `Ready` work enters execution. Internal delivery detail is recorded on active ownership as `Assigned`, `Building`, `Blocked`, `Integrating`, `Verifying`, or `Awaiting Review`; those work steps do not expand the public ticket lifecycle.

Goals use the smaller lifecycle `Needs Definition`, `Ready`, `Active`, `Review`, and `Done`. `project.currentGoal` identifies at most one non-completed primary goal. A blocked current goal remains current and records its blocker owner and exact resume condition; the pipeline never promotes itself automatically. Each goal carries a concise inline context summary plus optional PRD and decision paths. Optional `plannedStart` and `plannedEnd` ISO dates must be supplied together and place the goal on the generated Gantt timeline. `Done` additionally requires a result summary, completion date, repository evidence, terminal linked tickets, cleared ownership/blockers, and any required human approval.

These repository project goals are observable milestones in the durable project control plane.

## Priority vocabulary

- P0 — critical risk, outage, safety, or broken core outcome
- P1 — essential for the current milestone
- P2 — important improvement
- P3 — valuable but not urgent
- P4 — exploration, polish, or future idea

Dependencies, risk, and integration safety may override simple priority order.

## Permanent-role lifecycle

Management, Operations, and each active Consultant are permanent top-level tasks with event-driven run-to-idle lifecycles. Contractors and Internal Audit are disposable. Each active run drains meaningful work, records a named owner/action/return trigger, and pauses without polling when no meaningful action remains. Delegated idle is neither blocked nor complete.

## Definition of Ready

Work is Ready only when objective, context, scope, non-goals, acceptance, dependencies, affected systems, risks, owner, verification, expected evidence, resolved assurance, and major decisions are explicit. Management approves outcome readiness; Operations confirms execution readiness against live state. `requiredConsultantIds` names every applicable active Consultant, and `docs/state/reviews.json` contains an approved `Readiness` review with evidence for each ID before execution. A ticket that lists human `Readiness` review also requires that approved staged review before execution.

## Assurance controls

`project.assuranceDefaults` sets the project default. Every ticket still stores its resolved `assurance` so an LLM or human can understand the expected validation and review timing without inferring inheritance.

- `Lean`: focused changed-behavior proof and the ticket's explicit required verification.
- `Standard`: Lean plus affected regression and applicable runtime or operational evidence. This is the generated default.
- `Thorough`: Standard plus broader regression, negative or failure paths, and applicable operational or experiential evidence.

`humanReviewStages` is an explicit subset of `Readiness`, `Acceptance`, and `Release`; an empty array explicitly means no human review is required by this ticket. Management may apply a user-authorized per-ticket override, but any setting that differs from project defaults requires a non-empty `overrideReason`. An override cannot waive a separately governing legal, security, compliance, irreversible-action, or publication gate.

Human `Readiness` approval gates entry to execution. Human `Acceptance` approval gates `Done`. Human `Release` approval gates the material publication or release action and does not prevent technical completion. Every approved human record in `docs/state/reviews.json` names the exact stage, reviewer, ISO date, and dedicated regular Markdown packet under `docs/review-packets/`. README, template, symlink, missing, and unattributed packets never satisfy a gate. Keep exactly one canonical human decision per ticket/stage and one Consultant decision per ticket/Consultant/stage; replace it transactionally when the decision changes while Git and packet history preserve the prior decision.

## Management lifecycle

Management uses event-driven run-to-delegated-idle:

1. Confirm a new Management-task message supplied the wake event.
2. Refresh live project and repository truth once.
3. Classify incoming instructions and discoveries.
4. Prepare decisions, readiness, priority, Consultant boundaries, and review gates.
5. Assign the baton with owner, action, dependencies, and return trigger.
6. Complete other safe non-overlapping Management work, then end without polling.

If Management owns an action that is currently possible, it completes it before idling. A future Management action may wait only on a recorded trigger.

## Incoming changes

- **Superseding:** material overlap cannot safely wait; record the decision, request a safe pause, preserve WIP, synchronize state, and create a bounded prerequisite/replacement.
- **Parallel:** contracts and ownership are independent; register a separate lane and let current work continue.
- **Queued:** valid but non-urgent or not Ready; record it without interrupting the active owner.
- **Informational:** answer from verified state without changing ownership.

Prefer checkpoint-boundary adoption for non-urgent tooling, policy, architecture, and scope changes. Interrupt only to avoid material rework, invalid acceptance, WIP loss, unsafe action, or violation of explicit urgency.

## Operations lifecycle

Operations is run-to-idle:

1. Confirm a new Operations-task message supplied the wake event.
2. Refresh live state and select the highest-priority safe Ready work.
3. Register ownership before edits.
4. Decompose exclusive scopes, dependencies, checkpoints, and integration order.
5. Default substantial independent execution to Contractors; record why any Contractor-sized scope remains direct.
6. Review every return and changed file, integrate, and verify.
7. Synchronize state and send one result, blocker, review, or idle-boundary handoff.
8. Continue while meaningful Ready/integration work remains; otherwise end without polling.

Direct Operations work is appropriate for small, tightly coupled, sensitive, integration, conflict-resolution, verification, or narrow revision scopes. Contractor-first is not Contractor-only.

### Substantial integration review

Before substantial acceptance, Operations runs a two-axis review using the [code-review skill](../.agents/skills/code-review/SKILL.md):

- pin the exact committed and dirty-worktree boundary, including relevant untracked files, while excluding unrelated changes;
- obtain independent read-only standards/architecture and specification/evidence findings;
- verify each finding against the pinned diff, controlling requirements, and the [risk-based findings rule](../.agents/rules/risk-based-findings.md); route only a credible P0 or Confirmed/Proven P1 as a blocker and retain at most three P2/P3 follow-ups without automatically revising scope;
- perform one initial review and at most one fix-focused follow-up, then stop when required evidence passes and no blocker remains;
- hand off the pinned diff, both findings sets, implementation report, exact verification evidence, limitations, and next baton to Management.

Reviewers do not edit, accept, integrate, update state, or route revisions. This review precedes substantial acceptance. Consultant domain approval remains a separate expert gate and does not replace technical acceptance or Operations integration.

## Consultant lifecycle

Every active Consultant is a permanent top-level run-to-idle task. A Consultant begins only when `docs/state/team.json` records its approved recurring domain and a new Consultant-task message delivers a definition or review trigger. It defines proportional requirements, reviews returned evidence, accepts or requests exact revisions, and hands executable work to Operations. It does not set overall priority, dispatch Contractors, integrate implementation, remain active after offboarding, or wake itself from repository state.

Management performs final-audit mode on substantial returned work by consuming Operations' pinned diff, two-axis findings, implementation report, and exact evidence. Management does not dispatch reviewers or steer Contractors; implementation revisions route through Operations. A final audit and Consultant approval do not by themselves authorize publication or satisfy a separate human-review gate.

## Control-plane communication

Repository records are authoritative. Canonical schema-versioned JSON is the operational state used for project outcome/baton, goals, tickets, ownership, reviews, transitions, and the generated local dashboard; narrative Markdown remains the source for direction, decisions, requirements, reports, and optional supporting rationale. The project outcome explains why the project exists, goals are observable milestones, and tickets are bounded work under a goal. Before a material transition, the authorized owner loads the operational state and uses `python3 tools/harness_state.py check`; only a schema-defined, authorized operation may be applied with `python3 tools/harness_state.py apply`. The state writer executes the committed JSON schemas before repository-level relationship and authority checks. Supported state, team, installation, and update mutators share one external per-project cross-process lock. The tools and generated `docs/index.html` are views and writers for this existing repository control plane, not a second maintenance authority.

Messages signal wake, pause, blocker, decision, review, urgent invalidation, result, or idle boundary. A new task message is the only signal that wakes a permanent role. Returning roles synchronize their owned records, send one explicit handoff to the registered destination, and stop without polling.

Every handoff names controlling IDs, current status, owner, scope, dependencies, evidence, and return/wake trigger. A transition is incomplete until canonical JSON, generated view, and affected narrative records agree. LLMs may prepare and execute validated operational updates, but human authority remains required for intent, ambiguity, destructive deletion, external commitments, security/compliance, and publication.

## Definition of Done

Work becomes Done only when:

- implementation/output matches approved scope and acceptance;
- proportional automated, operational, experiential, and regression checks pass;
- affected boundaries are reviewed;
- documentation and project state are current;
- an implementation report records changes, choices, commands/results, limitations, and follow-ups;
- Operations accepts integration;
- required Consultant and human reviews are recorded.

For every Consultant ID required by the ticket, `docs/state/reviews.json` must also contain an approved `Acceptance` review linked to the evidence. Readiness approval does not substitute for acceptance, and either Consultant stage remains separate from Operations integration and human gates.

Completion does not bypass a separate publication, release, financial, legal, customer, or milestone approval gate.

## Harness evaluation

Use [evals/harness/README.md](evals/harness/README.md): static checks after state changes, scenario smoke after material harness changes, repeated comparisons before accepting a major redesign, and independent live-trace audits at meaningful checkpoints or after orchestration incidents.
