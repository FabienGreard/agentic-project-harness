# Template setup checklist

Complete this checklist before starting implementation.

## Repository identity

- [ ] Rename the repository and update the README title/description.
- [ ] Choose and document the license appropriate for the project.
- [ ] Replace starter placeholders and remove unused examples.
- [ ] Configure repository visibility, branch protection, issues, discussions, and required reviews.
- [ ] Configure secrets only in an approved secret store; never commit them.

## Direction and governance

- [ ] Write `docs/overview.md` from verified project state.
- [ ] Define intended outcomes, users/stakeholders, constraints, non-goals, and human gates in `docs/direction.md`.
- [ ] Decide which role owns publication, releases, or external actions.
- [ ] Keep only the permanent Leads that represent recurring authority boundaries.
- [ ] Record permanent task/thread identifiers in `docs/thread-registry.md` or a private local override.

## Work readiness

- [ ] Create the first decision, PRD, and ticket using `docs/templates/`.
- [ ] Record dependencies, scope, non-goals, acceptance, verification, affected systems, and owner.
- [ ] Confirm specialist readiness when expert acceptance is required.
- [ ] Promote only genuinely executable work to `Ready`.
- [ ] Synchronize `docs/project-state.json` with the human-readable records.

## Verification

- [ ] Run `python3 tools/harness_eval.py`.
- [ ] Run the canonical scenario smoke evaluation after material harness customization.
- [ ] Confirm local links resolve and no private identifiers or example-only claims remain.
- [ ] Commit the governance baseline before implementation begins.
