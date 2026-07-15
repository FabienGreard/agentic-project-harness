# Baton source repository agent map

This file is a navigation map only. Normative behavior lives under `rules/`. Product documentation and release infrastructure outside `.baton/` are source-repository concerns and are never consumer payload content.

## Rule map

| Topic | Rule |
| --- | --- |
| Repository truth | [rules/repository-truth.md](rules/repository-truth.md) |
| Authority boundaries | [rules/authority-boundaries.md](rules/authority-boundaries.md) |
| Permanent tasks and delegated idle | [rules/lifecycle-and-idle.md](rules/lifecycle-and-idle.md) |
| Incoming changes | [rules/incoming-change-triage.md](rules/incoming-change-triage.md) |
| Codebase design | [rules/codebase-design.md](rules/codebase-design.md) |
| Testing | [rules/testing.md](rules/testing.md) |
| Risk-based findings | [rules/risk-based-findings.md](rules/risk-based-findings.md) |
| Dispatch and ownership | [rules/dispatch-and-ownership.md](rules/dispatch-and-ownership.md) |
| Transactional state | [rules/transactional-state.md](rules/transactional-state.md) |
| Readiness and scope | [rules/readiness-and-scope.md](rules/readiness-and-scope.md) |
| Completion and review | [rules/completion-and-review.md](rules/completion-and-review.md) |
| Independent Baton evaluation | [rules/harness-evaluation.md](rules/harness-evaluation.md) |
| External notifications | [rules/external-notifications.md](rules/external-notifications.md) |
| Repository safety | [rules/repository-safety.md](rules/repository-safety.md) |
| LLM-first operability | [rules/llm-first-operability.md](rules/llm-first-operability.md) |
| Rule template | [rules/_template.md](rules/_template.md) |

## Skill map

| Need | Skill |
| --- | --- |
| Refine an initiative | [skills/brainstorm/SKILL.md](skills/brainstorm/SKILL.md) |
| Discover architecture candidates | [skills/improve-codebase-architecture/SKILL.md](skills/improve-codebase-architecture/SKILL.md) |
| Review a bounded change | [skills/code-review/SKILL.md](skills/code-review/SKILL.md) |
| Hire a Consultant | [skills/hire-consultant/SKILL.md](skills/hire-consultant/SKILL.md) |
| Fire a Consultant | [skills/fire-consultant/SKILL.md](skills/fire-consultant/SKILL.md) |

## Project control plane

| Need | Source |
| --- | --- |
| Context and direction | [docs/overview.md](docs/overview.md), [docs/direction.md](docs/direction.md) |
| Dashboard | [dashboard/index.html](dashboard/index.html) |
| Project and baton | [state/project.json](state/project.json) |
| Goals and tickets | [state/goals.json](state/goals.json), [state/tickets.json](state/tickets.json) |
| Ownership and reviews | [state/ownership.json](state/ownership.json), [state/reviews.json](state/reviews.json) |
| Team | [state/team.json](state/team.json) |
| Implementation evidence | [implementation-reports/BATON-001.md](implementation-reports/BATON-001.md) |
| Roles | [roles/management.md](roles/management.md), [roles/operations.md](roles/operations.md), [roles/consultant.md](roles/consultant.md), [roles/contractor.md](roles/contractor.md), [roles/internal-audit.md](roles/internal-audit.md) |
| Workflow | [workflow.md](workflow.md) |

## Baton product source

| Need | Source |
| --- | --- |
| Product overview | [../README.md](../README.md) |
| Distribution architecture | [../docs/architecture.md](../docs/architecture.md) |
| Installation and migration | [../docs/installation.md](../docs/installation.md) |
| Stable release process | [../docs/releasing.md](../docs/releasing.md) |
| Source-only evaluator | [../docs/evals/harness/README.md](../docs/evals/harness/README.md) |
