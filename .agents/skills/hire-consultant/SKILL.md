---
name: hire-consultant
description: Hire a curated or schema-valid custom Consultant into an Agentic Project Harness team. Use when the user explicitly asks to hire, add, recruit, or onboard a recurring expert role, or invokes $hire-consultant. Do not use for disposable execution work, which Operations assigns to Contractors.
---

# Hire a Consultant

Use the installed deterministic team engine. Do not hand-edit agent configs or `docs/state/team.json`.

## Prepare the requisition

1. Read `AGENTS.md`, applicable authority, lifecycle, repository-safety, transactional-state, and LLM-first rules, plus `docs/state/team.json` and `docs/roles/consultant.md`.
2. Run `python3 tools/harness_team.py check --project-root . --json`.
3. Confirm the user wants a recurring expert acceptance boundary. Route bounded implementation or one-off expertise to Operations as a Contractor instead.
4. Inspect the current preset catalog with `python3 tools/harness_team.py catalog --preset <preset> --field consultants --json`.
5. Recommend the closest curated Consultant first. Use a custom definition only when no curated domain fits.

## Hire

For a curated Consultant, run:

```sh
python3 tools/harness_team.py hire --project-root . --consultant <id> --yes --json
```

For a custom Consultant, prepare a temporary JSON object matching `docs/schemas/consultant.schema.json`, then run:

```sh
python3 tools/harness_team.py hire --project-root . --custom <temporary-json-path> --yes --json
```

Use `--yes` only after the user's instruction identifies or approves the exact Consultant. The engine rejects duplicate titles/IDs, invalid domains, unsafe paths, and incomplete definitions; it generates the config, updates team state and dashboard, records the managed baseline, and keeps an external transactional backup/report.

Never grant a Consultant overall priority, Contractor dispatch, technical integration, or publication authority. Every custom definition must include a unique ID/title, headline, domain, readiness requirements, evidence requirements, and acceptance authority.

## Verify and report

Run `python3 tools/harness_team.py check --project-root . --json` and `python3 tools/harness_state.py check --json`. Report the hired title, domain, config path, transaction/report/backup paths, and task-message wake requirement. Do not start or wake the new Consultant task unless the user separately requests it.
