# Static distribution check contract

`python3 scripts/harness_eval.py --strict` is the read-only source evaluator for the Baton v0.6.0 distribution boundary. It emits stable check IDs with concrete evidence and exits nonzero when any check fails.

## Product and payload boundary

- `BT-001`: `VERSION` is exactly the candidate Baton version.
- `BT-002`: active source identity, repository URL, product naming, and normal non-template repository contract agree.
- `BT-003`: reusable consumer source exists only under `template/.baton/`; source utilities are consolidated under `scripts/`; obsolete `packages/`, `examples/`, `tools/`, `release/`, root installer source, source-classification inventory, evaluator docs nesting, and split release-policy paths are absent; source-repository state cannot enter a payload.
- `BT-004`: consumer projection is rooted exclusively at `template/.baton/`, with shared defaults and explicit starter/adoption-only exceptions; source-repository paths are never eligible.
- `BT-005`: new-project and adoption projections are exact, distinct where required, and contain only safe `.baton/` paths.
- `BT-012`: consumer integration is limited to `.baton/`, the marked `AGENTS.md` block, individual skill-discovery links, and project-scoped host-adapter configuration; mature adoption uses non-authoritative `.baton/migration/`, while later Roster proposals stay in external transaction evidence.

## Stable release and lifecycle

- `BT-006`: the release builder, manifest, checksums, and exact five-asset contract are present and fail closed.
- `BT-007`: the single installer/updater acquires or refreshes a verified stable release with folder-aware, local-fixture, target, JSON, and noninteractive behavior; Project choices happen through Boot afterward.
- `BT-008`: the installed public CLI is exactly `boot`, `control`, `roster`, `terminal`, `upgrade`, `doctor`, and `scrap`; its human terminal, leaf help, examples, and recovery behavior remain discoverable; each matching skill delegates only to its family, while advanced privacy/inspection remains a CLI-only `control memory` seam.
- `BT-014`: candidate documentation and machinery preserve the explicit no-auto-publication boundary.

## Host adapter, discovery, and project state

- `BT-009`: the source repository's parsed host-adapter configuration has the exact supported permission, concurrency, and role semantics.
- `BT-010`: installed host-adapter configuration and generated fixed/active role registrations use the same semantic contract.
- `BT-011`: the ten Baton skills have one source under `.baton/skills/` and are discovered through individual `.agents/skills/<name>` links, without a duplicated skill tree.
- `BT-013`: the shipped starter builds valid project, goals, tickets, ownership, reviews, team, views, and work layout.

## Compatibility and verification

- `BT-015`: supported Python code compiles on the current interpreter, Python 3.9 remains syntax-compatible when available, and Git-visible/bounded source paths contain no cache artifacts without traversing ignored vendor trees.
- `BT-016`: public `docs/` contains only the six product guides and exact three PNG brand assets, while the focused deterministic suite, evaluator specifications under `tests/evals/`, and local/remote smoke entrypoints are present.
- `BT-017`: Boot and internal-Memory schemas, preset confirmation/change, invoking-task continuation, progressive disclosure, private transactions, bounded role briefings, generated views, and Consultant personnel-history integration are present; the source may use its own live Memory while consumer starters remain pristine.
- `BT-018`: the eight-rule inventory, mandatory startup order, role and skill maps, Markdown links, provider-neutral consumer prose, schema-backed workflow states, generated-role routing, duplicate-contract detection, review semantics, and canonical iteration scenarios agree without prose snapshots.
- `BT-019`: the isolated scenario runner, private machine contracts, candidate/oracle separation, permissive-judge override, live verification-trace schema, and negative regressions executablely reject assembled E2E as the primary loop, duplicate certification, stale evidence reuse, and missing duration evidence.

Scenario IDs under `scenarios/` are a separate behavioral-evaluation surface. They do not replace these deterministic source/distribution gates, and permanent roles never grade their own candidate.
