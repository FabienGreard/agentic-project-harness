# Getting started

## 1. Verify the installation

```sh
./install.sh status --json
python3 tools/harness_team.py check --json
python3 tools/harness_state.py check --json
```

Confirm the installed version/provenance, selected preset, professional Management and Operations personas, and active Consultants. Resolve any Adoption cleanup prompt before implementation.

## 2. Open the first Management task

Copy the complete **First project prompt** from the generated repository `README.md`. Management owns project outcomes, priority, scope, readiness, publication, and human-review gates. Its professional persona is recorded in `docs/state/team.json`.

During project definition, confirm the default assurance policy: generated projects start with `Standard` test rigor and no universal human review stage. Every ticket records its resolved rigor and any human review required at `Readiness`, `Acceptance`, or `Release`; user-authorized overrides record why they differ from the project default.

## 3. Establish direction and the company

Management verifies live repository truth, records approved direction, and confirms whether the starting Consultants match the project’s recurring acceptance domains. Use `$hire-consultant` and `$fire-consultant` for team changes; never hand-edit team state or generated configs.

## 4. Create bounded work

Record the durable outcome in `docs/direction.md`, observable goals in `docs/state/goals.json`, decisions under `docs/decisions/`, requirements under `docs/prds/`, bounded tickets in `docs/state/tickets.json`, and results under `docs/implementation-reports/`. Every executable ticket links to a goal.

## 5. Synchronize state

Prepare a schema-valid operation and run `python3 tools/harness_state.py apply`. Then run state/team checks and the evaluator. Open `docs/index.html` for the generated timeline, goal details, ticket search, and company directory.

## 6. Hand Ready work to Operations

Operations owns Contractor dispatch, exclusive ownership, integration, verification, and completion evidence. Management and Consultants never steer Contractors directly. Applicable Consultant acceptance, human gates, and publication authority remain separate.

## 7. Run to delegated idle

Management, Operations, and active Consultants are permanent top-level tasks. Each active run drains safe actionable work, records the next owner/action/return trigger, sends one handoff, and pauses without polling when no meaningful action remains.
