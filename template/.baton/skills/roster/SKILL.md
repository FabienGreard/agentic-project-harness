---
name: roster
description: List and reconfigure Baton's permanent team, including hiring or firing recurring Consultants. Use when the user asks who is on the team, wants a recurring expert added or removed, changes the preset, or explicitly invokes $roster.
---

# Roster

Follow `AGENTS.md`, `rules/operations.md`, and the Consultant role. Use only `.baton/bin/baton roster`; never edit team State or generated configs.

Start with `roster list --json` and `roster check --json`. Show the current permanent seats before proposing one action.

## Hire

Use `roster catalog --preset <preset> --field consultants --json`. Recommend a listed Consultant only when recurring domain readiness and acceptance are needed; route one-off execution to Operations. After the user approves the exact seat, run `roster hire --consultant <id> --yes --json`. A custom definition must validate against `schemas/consultant.schema.json` before `roster hire --custom <path> --yes --json`.

## Fire

Confirm the exact active Consultant and explicit user intent. Run `roster fire --consultant <id> --yes --json`. Preserve employment history, Records, reviews, and modified configs. Report any manual cleanup; do not operate the external task provider without separate authority.

## Reconfigure

During unconfirmed onboarding only, run `roster configure --preset <id> [--consultant <id> | --no-consultants] --invocation-task-id <id> --yes --json` after the user chooses the exact roster.

Finish with `roster check --json` and report the transaction, resulting seats, preserved files, and required external task action.

## Voice

Use the restrained company-terminal voice. Say that a Consultant joined or left the active roster, state `Online`, `Awaiting task`, or `Inactive` literally, preserve the human employment history in the wording, and end with one external task or configuration action. Avoid requisition, exit-interview, or celebratory HR theatre.
