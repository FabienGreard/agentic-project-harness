# Template setup checklist

Complete this checklist before starting implementation.

## Repository identity

- [ ] Follow [docs/installation.md](docs/installation.md) and choose a Codex reasoning level for each active role.
- [ ] Rename the repository and update the README title/description.
- [ ] Choose and document the license appropriate for the project.
- [ ] Replace starter placeholders and remove unused examples.
- [ ] Configure repository visibility, branch protection, issues, discussions, and required reviews.
- [ ] Configure secrets only in an approved secret store; never commit them.

## Direction and governance

- [ ] Write `docs/overview.md` from verified project state.
- [ ] Define intended outcomes, users/stakeholders, constraints, non-goals, and human gates in `docs/direction.md`.
- [ ] Decide which role owns publication, releases, or external actions.
- [ ] Confirm the preset personas and keep only Consultants that represent recurring acceptance boundaries.
- [ ] Use `$hire-consultant` and `$fire-consultant` for Consultant changes; do not hand-edit generated team configs.
- [ ] Record permanent task/thread identifiers in `docs/thread-registry.md` or a private local override.

## Work readiness

- [ ] Create the first decision, PRD, and ticket using `docs/templates/`.
- [ ] Record dependencies, scope, non-goals, acceptance, verification, affected systems, and owner.
- [ ] Confirm active Consultant readiness when expert acceptance is required.
- [ ] Promote only genuinely executable work to `Ready`.
- [ ] Apply schema-valid project, goal, ticket, ownership, and review records under `docs/state/` and regenerate `docs/index.html`.

## Verification

- [ ] Run `python3 tools/harness_eval.py`.
- [ ] Run `python3 tools/harness_team.py check --json` and `python3 tools/harness_state.py check --json`.
- [ ] Confirm `.agent-harness.json` and `docs/state/project.json` both identify Codex.
- [ ] Review every active `.codex/agents/*.toml` reasoning level against the selected model's supported levels and expected cost/latency.
- [ ] Run the canonical scenario smoke evaluation after material harness customization.
- [ ] Confirm local links resolve and no private identifiers or example-only claims remain.
- [ ] Commit the governance baseline before implementation begins.
