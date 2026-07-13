# First Codex bootstrap prompt

The project-scoped role configurations under `.codex/agents/` use these starter reasoning levels:

| Agent role | Reasoning |
| --- | --- |
| Project Director | `high` |
| Delivery Lead | `high` |
| Specialist Lead (optional) | `high` |
| Execution worker | `medium` |
| Harness Evaluator | `high` |

Support for a reasoning level depends on the model selected in Codex. Give the following instruction to the first Codex task opened in this repository:

> Bootstrap this project using the repository harness. First read `AGENTS.md`, `.codex/config.toml`, the active role configurations under `.codex/agents/`, `docs/overview.md`, `docs/direction.md`, `docs/backlog.md`, `docs/active-work.md`, `docs/project-state.json`, `docs/workflow.md`, and the relevant role instructions completely. Verify the live repository before trusting starter claims.
>
> This first run is governance-only: do not implement the project, install an application stack, contact external systems, publish, or invent product/business direction. Ask me only for decisions that materially change the intended outcome, constraints, human-review gates, or permanent roles. Then customize the direction, overview, role registry, first decision/requirement/ticket, and machine-readable state. Keep all execution non-Ready until its dependencies and acceptance are explicit. When the current Codex surface supports separate permanent tasks, register the Project Director and Delivery Lead as separate tasks using the configured reasoning levels; register a Specialist Lead only if its recurring authority boundary is approved. Run `python3 tools/harness_eval.py --strict`, report any remaining blockers, and leave the next baton and wake trigger explicit.
