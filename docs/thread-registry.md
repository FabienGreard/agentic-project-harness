# Permanent task registry

Do not commit private task URLs, credentials, notification recipients, or secrets. If identifiers are sensitive, keep a private local override and commit only role names and lifecycle rules.

| Role | Task/thread ID | Lifecycle | Operating instructions |
| --- | --- | --- | --- |
| Project Director | `<configure>` | event-driven run-to-delegated-idle | [Project Director](roles/project-director.md) |
| Delivery Lead | `<configure>` | run-to-idle | [Delivery Lead](roles/delivery-lead.md) |
| Specialist Lead | `<configure>` | run-to-idle; dormant until domain assignment | [Specialist Lead](roles/specialist-lead.md) |

The Harness Evaluator is disposable and is never registered as a permanent Lead.

## Message protocol

- Wake messages name the trigger, IDs, priority, dependencies, scope, and expected first action.
- Pause messages name the overlapping boundary and required WIP evidence.
- Results name exact outputs, verification, limitations, and recommended next baton.
- Non-urgent ideas belong in repository state rather than messages to active roles.
