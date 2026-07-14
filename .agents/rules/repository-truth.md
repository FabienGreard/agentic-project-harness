# Ground Every Task in Repository Truth

Title:
Ground Every Task in Repository Truth

Type:
Rule

Purpose:
Prevent stale assumptions, invented direction, and work based on an outdated state.

Scope:
Every role, Contractor, Internal Audit run, and task operating in the repository.

Definition:
Repository records and the verified live checkout are authoritative for direction, priority, readiness, ownership, implementation state, and acceptance.

How to Apply:

1. Start at the root map and identify applicable rules.
2. Read `docs/overview.md`, `docs/direction.md`, and the canonical records under `docs/state/`.
3. Read the controlling ticket record and any linked decision or narrative, then the assigned role contract.
4. Verify material claims against the current checkout or runtime.
5. Report contradictions to the owning role without inventing a resolution.

Do:

- Distinguish durable rules from current project state.
- Use live evidence when documentation may have drifted.

Don't:

- Infer direction from a repository name, example, or unrelated project.
- Treat stale documentation as verified.

Example:

- Before changing an API, verify the assigned ticket, current ownership record, and the live interface rather than relying on an earlier report.

Validation:
The controlling artifacts are identified, material claims agree with live evidence, and contradictions are recorded for the correct owner.

References:

- `AGENTS.md`
- `docs/overview.md`
- `docs/direction.md`
- `docs/workflow.md`

Notes:

- Role instructions add requirements but do not bypass repository grounding.
