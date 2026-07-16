# Baton workflow

`AGENTS.md` and the mandatory rules own behavior. [Ubiquitous language](language.md) owns terminology. This file defines only shared states, protocols, transitions, and handoffs.

## Ticket states

| State | Meaning |
| --- | --- |
| `Backlog` | Intent or execution boundary is incomplete. |
| `Ready` | Defined, approved, and executable. |
| `In Progress` | Assigned, building, integrating, or verifying. |
| `Blocked` | A named dependency or decision prevents progress. |
| `In Review` | Evidence awaits required acceptance. |
| `Done` | Acceptance and required evidence are recorded. |
| `Cancelled` | Intentionally stopped. |

Active ownership may refine `In Progress` as `Assigned`, `Building`, `Blocked`, `Integrating`, `Verifying`, or `Awaiting Review`; it never changes the ticket lifecycle.

## Goal states

Goals use `Needs Definition`, `Ready`, `Active`, `Review`, and `Done`. `project.currentGoal` names at most one unfinished primary goal. A blocked goal stays current with its blocker owner and resume condition. Nothing promotes automatically.

A Done Goal needs a result summary, completion date, repository evidence, terminal linked Tickets, cleared ownership and blockers, and every clearance required by its resolved protocol. Optional `plannedStart` and `plannedEnd` ISO dates appear together.

## Priority and protocols

Priority is `P0` critical, `P1` current-milestone essential, `P2` important, `P3` valuable, or `P4` exploratory. Dependency and safety may override priority order.

Each Ticket resolves one Readiness Protocol:

- `Waived`: no project-imposed verification gate; the result remains explicitly unverified and cannot be represented as verified.
- `Field Check`: focused changed-behavior proof plus explicit required verification.
- `Standard Protocol`: Field Check plus affected regression and applicable runtime evidence.
- `Full Certification`: Standard Protocol plus broader regression, failure paths, and applicable operational or experiential evidence.

Each Goal and Ticket also resolves one Clearance Protocol:

- `Autonomous`: no routine Goal or Ticket Clearance. Work and publication may proceed inside already approved scope, while destructive actions, new external commitments, unresolved ambiguity, and security or compliance decisions remain human-authority boundaries.
- `Release Clearance` (default): no routine Ticket Clearance; one Goal `Release` approval is required for the exact completed candidate before the Goal becomes Done or is published.
- `Completion Clearance`: every Ticket needs `Acceptance`, and the completed Goal needs `Release`; work does not pause for pre-execution clearance.
- `Continuous Clearance`: Goal `Readiness` before work begins, Ticket `Readiness` before execution, Ticket `Acceptance` before completion, and Goal `Release` before the Goal becomes Done or is published.

Every Goal and Ticket stores its resolved Clearance Protocol. Every Ticket stores its resolved Readiness Protocol. An override needs human authority and a recorded reason. Each required clearance has one canonical review record and a dedicated packet; stages and targets never substitute for one another. A material candidate change invalidates its prior Release clearance.

## Transition path

1. Management defines the Goal, its Tickets, Consultant boundaries, and resolved protocols.
2. Management obtains any required Goal `Readiness`; required Consultants and, under Continuous Clearance, humans record Ticket `Readiness` decisions.
3. Operations confirms executable readiness, registers ownership, and executes directly or dispatches bounded Contractors.
4. Operations integrates returns and gathers evidence required by the Ticket's Readiness Protocol.
5. Operations obtains independent review, Consultant `Acceptance`, and any required Ticket `Acceptance` clearance.
6. Operations synchronizes records and returns the completed Goal candidate to Management.
7. Management obtains any required Goal `Release` clearance for the exact candidate, then closes or publishes the Goal within the selected protocol.

## Handoffs

Every handoff names:

- controlling goal and ticket IDs;
- current state and owner;
- exact scope and non-goals;
- dependencies or blocker;
- evidence and verification;
- decision or action requested; and
- return destination and wake trigger.

Synchronize canonical records before sending one handoff. The receiving role acts only after a new message to its registered task. Results, blockers, reviews, urgent invalidations, and idle boundaries are valid wake reasons; unchanged state is not.
