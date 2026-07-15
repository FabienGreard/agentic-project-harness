# Project overview

This starter contains no approved project direction or executable work yet.

## Start here

1. Define verified outcomes, stakeholders, constraints, non-goals, and review gates in [direction.md](direction.md).
2. Use `.baton/bin/baton _state apply <operation.json>` to record the project outcome, default assurance, one current goal, its linked tickets, and the next goals under `.baton/state/`. Every ticket resolves `Lean`, `Standard`, or `Thorough` rigor and explicit human-review timing.
3. Open the [generated dashboard](../dashboard/index.html). Its responsive compact Gantt timeline is centered on today, scrolls inside its own bounded viewport, and keeps a narrow sticky goal column. Select a goal bar to open its PRD and linked tickets in a side sheet; the searchable project-wide ticket list shows each ticket's resolved assurance below.
4. Run `.baton/bin/baton _state check` and `.baton/bin/baton check` before the first execution handoff.

Only work whose canonical ticket record satisfies the Definition of Ready may enter execution. The installed preset configures Management and Operations, recommends a removable starting Consultant, and gives Operations a hidden Contractor capability bench. Internal Audit remains outside the project team.
