# Agentic Project Harness agent map

This file is a navigation map only. Normative rules live under `.agents/rules/`; role contracts, current state, and delivery records live under `docs/`.

Use each rule's `Scope` section to determine whether it applies to the current task.

## Rule map

| Topic | Rule |
| --- | --- |
| Repository truth and startup grounding | [.agents/rules/repository-truth.md](.agents/rules/repository-truth.md) |
| Role authority and handoff boundaries | [.agents/rules/authority-boundaries.md](.agents/rules/authority-boundaries.md) |
| Permanent-role lifecycle and delegated idle | [.agents/rules/lifecycle-and-idle.md](.agents/rules/lifecycle-and-idle.md) |
| Incoming changes and interruption decisions | [.agents/rules/incoming-change-triage.md](.agents/rules/incoming-change-triage.md) |
| Deep modules, interfaces, seams, and design alternatives | [.agents/rules/codebase-design.md](.agents/rules/codebase-design.md) |
| Vertical behavior development and tests | [.agents/rules/testing.md](.agents/rules/testing.md) |
| Worker dispatch and exclusive ownership | [.agents/rules/dispatch-and-ownership.md](.agents/rules/dispatch-and-ownership.md) |
| Transactional status and handoff state | [.agents/rules/transactional-state.md](.agents/rules/transactional-state.md) |
| Definition of Ready and bounded scope | [.agents/rules/readiness-and-scope.md](.agents/rules/readiness-and-scope.md) |
| Completion, verification, and review | [.agents/rules/completion-and-review.md](.agents/rules/completion-and-review.md) |
| Independent harness evaluation | [.agents/rules/harness-evaluation.md](.agents/rules/harness-evaluation.md) |
| Actionable external notifications | [.agents/rules/external-notifications.md](.agents/rules/external-notifications.md) |
| Repository safety and existing work | [.agents/rules/repository-safety.md](.agents/rules/repository-safety.md) |
| Rule authoring template | [.agents/rules/_template.md](.agents/rules/_template.md) |

## Skill map

| Need | Skill |
| --- | --- |
| Challenge and refine an initiative before implementation | [.agents/skills/brainstorm/SKILL.md](.agents/skills/brainstorm/SKILL.md) |
| Find evidence-backed architecture improvements | [.agents/skills/improve-codebase-architecture/SKILL.md](.agents/skills/improve-codebase-architecture/SKILL.md) |
| Review changes against intent and completion evidence | [.agents/skills/code-review/SKILL.md](.agents/skills/code-review/SKILL.md) |

## Current-state artifacts

| Need | Source |
| --- | --- |
| Current status and next actions | [docs/overview.md](docs/overview.md) |
| Direction, stakeholders, constraints, and gates | [docs/direction.md](docs/direction.md) |
| Priorities and work queue | [docs/backlog.md](docs/backlog.md) |
| Active scopes and ownership | [docs/active-work.md](docs/active-work.md) |
| Machine-readable project state | [docs/project-state.json](docs/project-state.json) |

## Role contracts

| Role | Contract |
| --- | --- |
| Project Director | [docs/roles/project-director.md](docs/roles/project-director.md) |
| Delivery Lead | [docs/roles/delivery-lead.md](docs/roles/delivery-lead.md) |
| Specialist Lead | [docs/roles/specialist-lead.md](docs/roles/specialist-lead.md) |
| Harness Evaluator | [docs/roles/harness-evaluator.md](docs/roles/harness-evaluator.md) |
| Execution Worker | [docs/roles/execution-worker.md](docs/roles/execution-worker.md) |

## Workflow and delivery map

| Need | Source |
| --- | --- |
| Status, readiness, execution, completion, and handoffs | [docs/workflow.md](docs/workflow.md) |
| Delivery records and implementation evidence | [docs/implementation-reports/README.md](docs/implementation-reports/README.md) |
| Review packets and acceptance evidence | [docs/review-packets/README.md](docs/review-packets/README.md) |
| Decisions and durable rationale | [docs/decisions/README.md](docs/decisions/README.md) |
| Harness evaluation procedure | [docs/evals/harness/README.md](docs/evals/harness/README.md) |
| Installation and customization | [docs/installation.md](docs/installation.md) |
