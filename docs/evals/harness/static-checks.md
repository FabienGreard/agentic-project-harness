# Static distribution check contract

`python3 scripts/harness_eval.py --strict` is the read-only source evaluator for the Baton v0.6.0 distribution boundary. It emits stable check IDs with concrete evidence and exits nonzero when any check fails.

## Product and payload boundary

- `BT-001`: `VERSION` is exactly the candidate Baton version.
- `BT-002`: active source identity, repository URL, product naming, and normal non-template repository contract agree.
- `BT-003`: reusable consumer source exists only under `template/.baton/`; source utilities are consolidated under `scripts/`; obsolete `packages/`, `examples/`, `tools/`, root installer source, and split release-policy paths are absent; source-repository state cannot enter a payload.
- `BT-004`: every Git-visible candidate path has exactly one valid source classification and no classification drifts from the enforced layout.
- `BT-005`: new-project and adoption projections are exact, distinct where required, and contain only safe `.baton/` paths.
- `BT-012`: consumer integration is limited to `.baton/`, the marked `AGENTS.md` block, individual skill-discovery links, and project-scoped Codex configuration; forbidden root project identity or source-repository files cannot be adopted.

## Stable release and lifecycle

- `BT-006`: the release builder, manifest, checksums, and exact five-asset contract are present and fail closed.
- `BT-007`: the single installer/updater exposes the approved folder-aware, preset/custom, stable-only, local-fixture, target, JSON, and noninteractive surface.
- `BT-008`: the installed public CLI is exactly `status`, `update`, and `check`; activation/state/team mutations remain internal lifecycle operations.
- `BT-014`: candidate documentation and machinery preserve the explicit no-auto-publication boundary.

## Codex, discovery, and project state

- `BT-009`: the source repository's parsed Codex configuration has exact on-request/Auto-review, workspace-write, network, four-thread, depth-one semantics and valid source roles.
- `BT-010`: installed Codex configuration and generated fixed/active role registrations use the same exact semantic contract.
- `BT-011`: the five Baton skills have one source under `.baton/skills/` and are discovered through individual `.agents/skills/<name>` links, without `.codex/skills` or duplicated copies.
- `BT-013`: Baton's own canonical project, goals, tickets, ownership, reviews, team, dashboard, and current baton validate transactionally.

## Compatibility and verification

- `BT-015`: supported Python code compiles on the current interpreter, Python 3.9 remains syntax-compatible when available, and Git-visible/bounded source paths contain no cache artifacts without traversing ignored vendor trees.
- `BT-016`: the focused deterministic suite and local/remote smoke entrypoints required by the release procedure are present.

Scenario IDs under `scenarios/` are a separate behavioral-evaluation surface. They do not replace these deterministic source/distribution gates, and permanent roles never grade their own candidate.
