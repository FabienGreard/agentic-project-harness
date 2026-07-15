# Govern Project-Local Company Memory

Title:
Govern Project-Local Company Memory

Type:
Rule

Purpose:
Provide useful, bounded company and personnel context without creating hidden authority, unsafe personal inference, or unfulfillable privacy claims.

Scope:
Every memory inspection, mutation, candidate, personnel event, review, role briefing, dashboard projection, migration, backup, and forgetting request.

Definition:
`.baton/memory/memory.json` is the editable schema-versioned current truth and `.baton/memory/history.jsonl` is its subordinate value-minimized chronology. `$memory` is the sole user-facing memory interface; all reads, context selection, bootstrap reconciliation, and authority-checked mutations use hidden deterministic `.baton/bin/baton _memory` plumbing. Memory supports work but never replaces canonical project state, evidence, decisions, approvals, or authority.

How to Apply:

1. Inspect through the privacy-filtered hidden reader and identify claims by stable ID, subject, category, source, status, and timestamps.
2. Route every mutation through the deterministic writer with actor authority, expected revision, provenance, validation, shared locking, external backup/report evidence, and rollback on failure.
3. Confirm explicit unambiguous user statements when eligible; keep inferred personal observations as pending candidates until the user confirms them.
4. Record verified company and personnel events in value-minimized history and link canonical records instead of duplicating their content.
5. At each project-role wake, request only a role- and assignment-specific briefing. For a disposable Internal Audit run, require the exact authorized evaluation boundary and return a read-only evaluation briefing without adding Internal Audit to personnel or permanent task roles. Include confirmed claims only, at most 10 claims and 1,800 UTF-8 bytes using the configured conservative 600-token estimate; retrieve more only on explicit demand.
6. For forgetting, remove active claims, clear matching candidates, redact matching values from local memory history, refresh generated views, and return external report/rollback evidence.
7. Record personnel reviews after completed, revised, abandoned, or failed engagements with assignment type, observable outcome, revision cause, verification quality, working-style impact, source class, reviewers, timestamps, and exact evidence paths. Promote only repeated evidence-backed patterns into contextual performance summaries.

Do:

- Treat the user as final authority over memory.
- Let Management confirm company identity and user-approved durable learning.
- Let Operations record verified assignments, outcomes, revisions, and performance evidence.
- Let Consultants submit domain observations and self-reflections without confirming user facts or their own performance.
- Let Contractors submit self-reflections and candidates only.
- Let Internal Audit read bounded memory for authorized harness evaluation without writing company memory.
- Give explicit user feedback greatest authority and preserve separate self-reflection, operational evidence, Management assessment, and user-feedback sources.
- Preserve stable personnel IDs, names, generation seeds, bounded professional styles, employment status, assignment history, and evidence-linked contextual strengths.
- Prefer capability, task fit, evidence, availability, model quality, and required reasoning over working style. Reuse the strongest suitable coworker indefinitely when evidence supports it; Operations may trial an equally qualified coworker for low-risk bounded work when evidence is insufficient.
- Record stable claim IDs when memory materially influences a review or decision.

Don't:

- Auto-inject full memory, candidates, superseded claims, complete histories, old reviews, inactive personnel, or assignment-duplicated context.
- Store raw transcripts, passwords, tokens, credentials, secrets, or sensitive personal information by default.
- Let a role confirm beyond its mutation authority, grade itself authoritatively, or replace a permanent seat without explicit user approval.
- Duplicate tickets, PRDs, decisions, approvals, implementation evidence, or consequential project decisions in memory.
- Use memory to authorize publication, destructive action, external commitment, security/compliance decisions, execution readiness, or priority.
- Create a universal personnel score, ranking, leaderboard, forced rotation, or novelty quota.
- Let working style weaken competence, evidence, safety, authority, model choice, or reasoning requirements.
- Claim forgetting rewrites Git history or removes prior values from remotes, clones, caches, repository backups, or external transaction backups.

Example:

- An explicit user preference becomes a confirmed claim through `$memory`; a Contractor's inference becomes a candidate with no automatic effect until the user confirms it.

Validation:
Schemas and cross-record checks pass; every mutation has authorized provenance, expected-revision protection, external transaction evidence, and rollback behavior; automatic packets contain only confirmed relevant claims within both caps; secret rejection and forgetting never echo removed values; local redaction and Git/backup retention warnings are explicit.

References:

- `.baton/skills/memory/SKILL.md`
- `.baton/rules/transactional-state.md`
- `.baton/rules/authority-boundaries.md`
- `.baton/roles/management.md`
- `.baton/roles/operations.md`
- `.baton/roles/consultant.md`
- `.baton/roles/contractor.md`
- `.baton/roles/internal-audit.md`

Notes:

- Memory schema versions migrate independently from project-state schema versions. Active project-owned memory is not overwritten by Baton updates.
- Forgetting is the only local-history rewrite exception; external rollback evidence remains human-controlled.
