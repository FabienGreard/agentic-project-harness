# Migration

This directory is reserved exclusively for adopting or migrating an existing Repository. Its starter State and initial host-configuration proposals are not authoritative. `.baton/metadata.json` remains `Needs Integration`, and existing Repository or legacy files remain untouched. Later Roster changes write proposals to external transaction evidence, never here.

Review the quarantined starter against the live Repository. Prepare a schema-valid proposal outside the Repository containing `state/project.json`, `goals.json`, `tickets.json`, `ownership.json`, `reviews.json`, and `team.json`. Put approved Project direction in `project.json`, set `templateMode` to `false`, and name a real current Goal.

After human confirmation, run:

```sh
.baton/bin/baton boot activate --from /absolute/path/to/proposal
```

Activation promotes project-owned records, regenerates views and host role configuration, updates the managed `AGENTS.md` block, and records recovery evidence. It does not delete this quarantine or any legacy file.
