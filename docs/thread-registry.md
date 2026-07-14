# Permanent task registry

Do not commit private task URLs, credentials, notification recipients, or secrets. If identifiers are sensitive, keep a private local override and commit only role names and lifecycle rules.

| Role | Task/thread ID | Lifecycle | Operating instructions |
| --- | --- | --- | --- |
| Management (`<configured persona>`) | `<configure>` | permanent top-level; event-driven run-to-delegated-idle | [Management](roles/management.md) |
| Operations (`<configured persona>`) | `<configure>` | permanent top-level; event-driven run-to-idle | [Operations](roles/operations.md) |
| Consultant (`<one row per active Consultant>`) | `<configure>` | permanent top-level; event-driven run-to-idle; inactive after `$fire-consultant` | [Consultant](roles/consultant.md) |

Contractors and Internal Audit are disposable and are never registered as permanent tasks. Internal Audit is not project QA or a project-team member.

Management, Operations, and every active Consultant run on named events, record the next owner/action/return trigger, and pause without polling when no meaningful action remains.

## Message protocol

- Wake messages name the trigger, IDs, priority, dependencies, scope, and expected first action. No other event wakes a permanent role.
- Pause messages name the overlapping boundary and required WIP evidence.
- Results name exact outputs, verification, limitations, and recommended next baton.
- Non-urgent ideas belong in repository state rather than messages to active roles.
