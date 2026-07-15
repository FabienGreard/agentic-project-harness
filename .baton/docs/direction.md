# Baton direction

## Intended outcome

Give teams a self-contained, updateable multi-agent project control plane without taking ownership of the surrounding repository.

## Product boundary

- Baton-managed runtime, state, governance, dashboards, roles, schemas, and reports live under `.baton/` in consuming projects.
- Root project identity, licensing, community files, source, tests, examples, release machinery, and documentation remain project-owned.
- Root integration is limited to one idempotent `AGENTS.md` block, project Codex configuration when safely mergeable, and individual repository skill-discovery links.
- Stable updates preserve project-owned and legacy files, produce explicit cleanup candidates, and require human approval before destructive deletion.

## Assurance

- Default test rigor: `Thorough` for the active product refactor.
- Human review: `Release` remains required before publication.
