# Static check contract

Stable check identifiers for `tools/harness_eval.py` and future extensions.

## Repository

- `ST-001`: required harness files exist.
- `ST-002`: repository-local Markdown targets resolve.
- `ST-003`: JSON state and schema files parse.
- `ST-004`: no merge-conflict markers or trailing-whitespace errors exist in governed text files.
- `ST-005`: all five Codex role configurations are valid and the parsed project config exactly matches on-request/Auto-review, workspace-write, sandbox-network, four-thread, and depth-one defaults.
- `ST-040`: `AGENTS.md` is a navigational map, all built-in and project-specific rules are mapped, required built-ins exist, local links resolve, and every `.agents/rules/*.md` file shares the common section template.
- `ST-041`: the three generic skills, skill metadata/support notice, and relative `.codex/skills -> ../.agents/skills` discovery symlink exist without a duplicate copy.
- `ST-042`: substantive Project Director and Delivery Lead integration-review/final-audit contracts are present while Specialist acceptance, Evaluator audit, and Worker execution remain separate and Delivery remains the dispatch center.

## Tickets and state

- `ST-010`: ticket IDs are unique and ticket paths exist.
- `ST-011`: dependency IDs exist and no ticket depends on itself.
- `ST-012`: active-work tickets exist and use active-compatible status.
- `ST-013`: ticket and active-work status agree; active work may not remain Ready.
- `ST-014`: Ready dependencies are Completed.
- `ST-015`: Completed tickets have implementation-report evidence.

## Ownership and baton

- `ST-020`: active scopes do not overlap between owners.
- `ST-021`: baton owner, action, and return trigger are non-empty.
- `ST-022`: active work names an owner, scope, status, and return destination.
- `ST-023`: generated evaluation artifacts are ignored.

## Privacy and template hygiene

- `ST-030`: no obvious committed secret files are present.
- `ST-031`: strict/project mode rejects unresolved `<configure>` and `<optional>` registry placeholders.
- `ST-032`: template mode is explicit until customization is complete.

The checker is read-only, emits check IDs with evidence, and exits nonzero on failure.
