---
name: fire-consultant
description: Safely offboard an active Agentic Project Harness Consultant while preserving history and user-modified files. Use when the user explicitly asks to fire, remove, retire, dismiss, or offboard a Consultant, or invokes $fire-consultant. Do not use to stop a disposable Contractor assignment.
---

# Fire a Consultant

Use the installed deterministic team engine. Do not delete or edit Consultant files by hand.

## Confirm the boundary

1. Read `AGENTS.md`, applicable authority, lifecycle, repository-safety, transactional-state, and LLM-first rules, plus `docs/state/team.json` and `docs/roles/consultant.md`.
2. Run `python3 tools/harness_team.py check --project-root . --json`.
3. Confirm the exact active Consultant ID and explicit user offboarding intent. Firing does not delete decisions, reviews, reports, project-owned files, or transaction backups.

## Fire

Run:

```sh
python3 tools/harness_team.py fire --project-root . --consultant <id> --yes --json
```

The engine marks the Consultant inactive and preserves employment/domain history. It removes only an unchanged generated config. If the config differs from its generated baseline, the engine preserves it, records a manual action, and reports that cleanup remains required; never delete, overwrite, move, or normalize that file automatically.

An inactive Consultant task must perform no project work. Report stale task/config cleanup to the user, but do not attempt to control the Codex app.

## Verify and report

Run `python3 tools/harness_team.py check --project-root . --json` and `python3 tools/harness_state.py check --json`. Report the fired title, inactive status, whether the config was removed or preserved, all manual actions, and transaction/report/backup paths. Human approval remains required before deleting a preserved modified config or backup.
