# Static check contract

Stable check identifiers for `tools/harness_eval.py` and future extensions.

## Repository

- `ST-001`: required harness files exist.
- `ST-002`: repository-local Markdown targets resolve.
- `ST-003`: JSON state and schema files parse.
- `ST-004`: no merge-conflict markers or trailing-whitespace errors exist in governed text files.
- `ST-005`: all fixed and active-Consultant Codex role configurations are valid and the parsed project config exactly matches on-request/Auto-review, workspace-write, sandbox-network, four-thread, and depth-one defaults.
- `ST-040`: `AGENTS.md` is a navigational map, all built-in and project-specific rules are mapped, required built-ins exist, local links resolve, and every `.agents/rules/*.md` file shares the common section template.
- `ST-041`: the five project skills, skill metadata/support notice, and relative `.codex/skills -> ../.agents/skills` discovery symlink exist without a duplicate copy.
- `ST-042`: substantive Management and Operations integration-review/final-audit contracts are present while Consultant acceptance, Internal Audit, and Contractor execution remain separate and Operations remains the dispatch center.
- `ST-043`: metadata schema/version/state values, the shared external mutation lock, and the minimal install/status/update public lifecycle agree.
- `ST-044`: the runtime executes the committed JSON schemas before repository-semantic checks, and canonical records exactly match the generated dashboard snapshot.
- `ST-045`: LLM-readable state and deterministic tools remain subordinate to human authority for consequential decisions.
- `ST-046`: permanent leadership roles are top-level, event-driven, run-to-idle tasks with explicit owner/action/return-trigger handoffs and no polling.
- `ST-047`: the exact four-preset catalog, common names, professional personas, recommended Consultants, typed readiness/acceptance gates, authority exclusions, and skill-only hire/fire operations agree; user documentation does not expose the internal mutation command.
- `ST-048`: project assurance defaults, resolved per-ticket rigor, staged human-review gates, override reasons, dashboard rendering, and state/update smoke coverage agree.
- `ST-049`: risk-based finding confidence, severity, blocking thresholds, bounded review passes, and H-012/H-013 scenario coverage agree across rules, review skill, rubric, and evaluator prompt.

## Tickets and state

- `ST-016`: goal IDs are unique and the current-goal pointer names a non-completed goal.
- `ST-017`: goal dependency IDs exist and no goal depends on itself.
- `ST-018`: every executable ticket links to a known goal.
- `ST-019`: completed goals have result summaries, completion dates, and repository evidence.
- `ST-010`: ticket IDs are unique and any optional narrative paths exist.
- `ST-011`: dependency IDs exist and no ticket depends on itself.
- `ST-012`: active-work tickets exist and use active-compatible status.
- `ST-013`: each active ownership work step maps to the compatible public ticket status; active work may not remain Ready.
- `ST-014`: Ready dependencies are Done.
- `ST-015`: Done tickets have implementation-report evidence.

## Ownership and baton

- `ST-020`: active scopes do not overlap between owners.
- `ST-021`: baton owner, action, and return trigger are non-empty.
- `ST-022`: active work names an owner, scope, status, and return destination.
- `ST-023`: generated evaluation artifacts are ignored.

## Privacy and template hygiene

- `ST-030`: no obvious committed secret files are present.
- `ST-031`: strict/project mode rejects unresolved `<configure>` and `<optional>` registry placeholders.
- `ST-032`: template mode is explicit until customization is complete.
- `ST-033`: canonical project provider and lifecycle metadata consistently identify Codex and accepted source provenance.
- `ST-034`: installed per-role reasoning files match lifecycle metadata.

The checker is read-only, emits check IDs with evidence, and exits nonzero on failure.
