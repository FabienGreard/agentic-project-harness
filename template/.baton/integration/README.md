# Baton adoption integration

This directory exists only while an existing repository is being adopted or migrated. Baton keeps starter state, desired root integrations, preserved collision evidence, and exact manual actions here until a schema-valid project state is explicitly approved and activated.

Nothing under this directory becomes authoritative merely because Baton was installed. `.baton/metadata.json` remains `Needs Integration` until the migration is complete. Existing project files and legacy harness files are never deleted automatically.

Review the quarantined [starter agent map](starter/AGENTS.md) and [starter dashboard](starter/dashboard/index.html) alongside the live repository. Links inside that starter map deliberately bridge to Baton's shared rules, skills, roles, templates, workflow, and immutable installation metadata without creating a second active control plane.

Create the reviewed proposal outside the repository with `state/project.json`, `goals.json`, `tickets.json`, `ownership.json`, `reviews.json`, and `team.json`; optional `docs/overview.md` and `docs/direction.md` may replace the starter narratives. The project record must describe the mature project, set `templateMode` to `false`, and name a real current goal. After human confirmation, activate it transactionally:

```bash
.baton/bin/baton _activate --from /absolute/path/to/reviewed-proposal
```

Activation promotes the project-owned template records, regenerates the dashboard and Codex role configs, updates the managed `AGENTS.md` block, and records an external backup/report. It never deletes this quarantine or any legacy project file.
