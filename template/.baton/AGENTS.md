# Baton agent map

Baton is a repository-local control plane for teams of AI agents. It defines who decides, who executes, what is ready, and what evidence is required.

## Read in this order

1. Read this file.
2. Read every file in the **Mandatory rules** table below. All apply to every role.
3. Validate Baton with `.baton/bin/baton doctor check`, then read `.baton/state/project.json`, `goals.json`, `tickets.json`, `ownership.json`, `reviews.json`, and `team.json`.
4. Read linked Project records and the controlling Goal and Ticket records. Verify material claims against the live repository.
5. Read only your assigned role contract.
6. Read an invoked skill completely, including only the references it explicitly requires.
7. Request bounded company memory only when the assignment needs it. Never load full memory or history by default.

Do not preload unrelated skills, inactive tickets, historical evidence, or unlinked documents. If records disagree, stop the affected work, preserve evidence, and return the contradiction to its authorized owner.

## Operating model

- **Humans** retain authority for intent, unresolved ambiguity, destructive actions, new external commitments, security or compliance decisions, and the selected Clearance Protocol. That protocol may grant standing authority for routine delivery and publication inside approved scope.
- **Management** owns outcomes, priority, scope, readiness, durable decisions, and required Goal or Ticket Clearances.
- **Operations** owns executable planning, ownership, Contractor dispatch, integration, verification, and completion evidence.
- **Consultants** define and accept work only inside their configured domains.
- **Contractors** execute one bounded assignment and return evidence to Operations.
- **Internal Audit** independently evaluates Baton in one disposable, read-only run.

Canonical JSON under `.baton/state/` holds approved direction and coordinates work. Linked Project, Goal, and Ticket records live under [`.baton/records/<SCOPE>/`](records/README.md). The live repository and runtime prove implementation. Messages notify; they do not replace State, Decisions, or Evidence.

Work moves through `Backlog -> Ready -> In Progress -> In Review -> Done`. Only Ready work executes. Each active scope has one owner, explicit acceptance, verification, and a return trigger. Required Goal and Ticket Clearances remain separate from technical completion.

## Mandatory rules

| Contract | Rule |
| --- | --- |
| Ubiquitous language | [language.md](language.md) |
| States, protocols, and handoffs | [workflow.md](workflow.md) |
| Truth, authority, safety, and human boundaries | [rules/authority.md](rules/authority.md) |
| Readiness, ownership, state transitions, and completion | [rules/delivery.md](rules/delivery.md) |
| Fast feedback, testing, evidence, findings, and independent evaluation | [rules/verification.md](rules/verification.md) |
| Permanent-role wake and idle behavior | [rules/lifecycle.md](rules/lifecycle.md) |
| Project onboarding and permanent-task registration | [rules/bootstrap.md](rules/bootstrap.md) |
| Project-local company memory | [rules/memory.md](rules/memory.md) |
| Module and interface design | [rules/design.md](rules/design.md) |
| Deterministic installation, state, update, and recovery operations | [rules/operations.md](rules/operations.md) |

## Role contracts

| Role | Contract |
| --- | --- |
| Management | [roles/management.md](roles/management.md) |
| Operations | [roles/operations.md](roles/operations.md) |
| Consultant | [roles/consultant.md](roles/consultant.md) |
| Contractor | [roles/contractor.md](roles/contractor.md) |
| Internal Audit | [roles/internal-audit.md](roles/internal-audit.md) |

## Invoked skills

Read a skill only when invoked:

| Need | Skill |
| --- | --- |
| Onboard or adopt a Project | [boot](skills/boot/SKILL.md) |
| Change Project controls or protocols | [control](skills/control/SKILL.md) |
| List, hire, fire, or reconfigure the permanent team | [roster](skills/roster/SKILL.md) |
| Inspect status or open the HTML view | [terminal](skills/terminal/SKILL.md) |
| Upgrade Baton and required data | [upgrade](skills/upgrade/SKILL.md) |
| Diagnose or recover Baton | [doctor](skills/doctor/SKILL.md) |
| Remove Baton through a reviewed plan | [scrap](skills/scrap/SKILL.md) |
| Define one outcome before implementation | [brainstorm](skills/brainstorm/SKILL.md) |
| Find evidence-backed module improvements | [improve-codebase-architecture](skills/improve-codebase-architecture/SKILL.md) |
| Review a pinned change | [code-review](skills/code-review/SKILL.md) |

Generated task routing is in [team tasks](views/team-tasks.md). Adapted material is in [third-party notices](THIRD_PARTY_NOTICES.md).
