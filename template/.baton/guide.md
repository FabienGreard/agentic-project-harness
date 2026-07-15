# Baton lifecycle guide

This file is generated into Baton projects. It documents the Baton contract; it does not authorize deletion, external commitments, publication, or release.

## One stable lifecycle

Use the single `install.sh` from a stable GitHub release. It is a remote bootstrapper and is never copied into the project. Its smart default installs or enters additive Adoption mode, `status` reports the local record, and `update` performs a guarded stable update. Do not use a moving branch, prerelease, unverified fork, or second updater.

`.baton/metadata.json` records version, immutable provenance, ownership classes, baseline checksums, lifecycle status, migrations, and transaction IDs. Updates reconstruct a trusted origin baseline before comparing it with local state and the target release. Modified managed files, ambiguous provenance, unsupported origins, and unsafe paths block rather than guess. Project-owned and unrelated files are never retired automatically. External transaction backups and preserved legacy originals remain until a human authorizes deletion. One external per-project lock serializes supported state, team, installation, and update mutations across processes.

The public lifecycle remains deliberately small: the stable installer URL, `.baton/bin/baton status`, `.baton/bin/baton update`, and `.baton/bin/baton check`, plus `--json`, `--yes`, and `--help`. Mature adoption has one intentionally hidden migration seam: after a human reviews a complete schema-valid proposal, run `.baton/bin/baton _activate --from PATH`; unchanged starter state cannot be activated.

## One company layer

The stable common names are Management, Operations, Consultants, and Contractors. The selected preset supplies professional personas and a bounded Consultant/Contractor catalog through `.baton/state/team.json`. Internal Audit is hidden independent Baton evaluation, not project QA or a project-team member.

Invoke `$hire-consultant` to add a curated or schema-valid custom Consultant and `$fire-consultant` to offboard one. The skills use `.baton/lib/harness_team.py` as the sole deterministic team engine, preserve history, and write external transaction evidence. Offboarding removes only an unchanged generated config; modified files remain with a manual action.

## Project state

Canonical schema-versioned JSON under `.baton/state/` records project/baton, goals, tickets, ownership, reviews, and team. Narrative Markdown stores direction, decisions, requirements, reports, and supporting rationale. Run `.baton/bin/baton _team check` and `.baton/bin/baton _state check` before relying on state. The state writer executes the committed JSON schemas before checking cross-record repository semantics. Apply only authorized schema-valid state operations. `.baton/dashboard/index.html` is a generated local view, not a second authority.

The project record defines assurance defaults. Every ticket records resolved `Lean`, `Standard`, or `Thorough` test rigor and explicit human-review stages: `Readiness`, `Acceptance`, and/or `Release`; `[]` explicitly means none. A human-authorized override records why it differs from the defaults. Readiness review gates execution, Acceptance review gates completion, and Release review remains a separate publication gate.

Baton is LLM-first and human-governed. LLMs may inspect evidence, execute validated operations, and follow generated cleanup prompts. Humans retain authority for intent, ambiguity, destructive deletion, external commitments, security/compliance, and publication.

## Codex contract

Keep on-request approvals, `approvals_reviewer = "auto_review"`, workspace-write sandboxing, sandbox network access, `max_threads = 4`, and `max_depth = 1` unless an approved governance change replaces them. Four threads is a ceiling, not a target; an execution surface can impose less. Depth one preserves Operations as the shallow dispatch center. Auto-review can be limited by app/workspace policy, and existing conversations can retain their selected permission mode.

Management, Operations, and active Consultants are permanent top-level tasks with event-driven run-to-idle lifecycles. Each active run drains meaningful work, records the next owner/action/return trigger, and pauses without polling when no meaningful action remains.
