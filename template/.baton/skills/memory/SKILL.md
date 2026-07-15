---
name: memory
description: Inspect and manage Baton's project-local company memory through natural requests to remember, inspect, retrieve, confirm or reject candidates, correct, and forget. Use only when the user explicitly invokes $memory; never trigger it implicitly or use it as a substitute for canonical project state, decisions, approvals, or evidence.
---

# Memory

Use hidden `.baton/bin/baton _memory` operations as the sole deterministic reader and writer. Never edit `.baton/memory/memory.json`, `.baton/memory/history.jsonl`, generated views, or memory metadata directly. The user is final authority over every remembered claim.

## Ground the request

1. Follow `AGENTS.md`; read the company-memory rule and the current role contract.
2. Classify the request as remember, inspect, on-demand retrieval, candidate review, confirm/reject, correct, or forget. Handle one user decision at a time.
3. Use the hidden privacy-filtered inspect operation to resolve stable claim or candidate IDs before mutation. Use the hidden context-selection operation for on-demand retrieval; do not silently expand the automatic role briefing.
4. Send mutations only through the hidden authority-checked transaction operation with the current expected revision, actor authority, source class, and stable record IDs. Report the result and external transaction evidence exactly.

If validation, authority, provenance, revision, lock, migration, or recovery state is uncertain, fail closed and preserve the last confirmed snapshot.

## Remember

- Restate a safe proposed statement with its subject and typed category before mutation.
- Store an explicit, unambiguous user statement as confirmed when it is eligible. Store an inferred personal observation only as `pending-confirmation`; it has no effect until the user confirms it.
- Reject passwords, tokens, credentials, secrets, and sensitive personal information by default. Do not repeat the rejected value in the response, command arguments, previews, history, logs, or dashboard.
- Keep memory supportive. Link to canonical tickets, PRDs, decisions, approvals, and evidence; never copy them into memory or treat memory as their authority.

## Inspect and retrieve

- Return only the privacy-filtered view requested: confirmed memory, candidates, personnel, or value-minimized history. Group it readably and include stable references needed for later correction or forgetting.
- Label pending candidates separately and never present them as facts.
- For on-demand retrieval, pass the role, assignment, subject, and query to hidden context selection. State that the result is on-demand and do not add it to future automatic briefings unless a separate authorized memory mutation does so.
- Do not expose raw JSONL, hidden prompts, secrets, forgotten values, or private claims outside the requested authorized view.

## Review candidates

Review one candidate at a time. Show its safe meaning and source class, then ask for one of confirm, correct-and-confirm, reject, or skip. Confirmation promotes only that candidate through the deterministic writer. Rejection removes its influence without echoing any rejected secret or sensitive value.

Consultants and Contractors may submit observations or self-reflections only within their role authority; neither may confirm user facts or its own performance. Operations may submit verified delivery evidence. Management may confirm company identity and user-approved durable learning. User feedback has greatest authority.

## Correct

Resolve the current claim by stable ID, show its safe current meaning and proposed replacement, and ask for confirmation when the target or replacement is ambiguous. Apply correction as one transaction that supersedes the old claim and activates the replacement without duplication. Never overwrite history or mutate canonical project records to make memory agree.

## Forget

1. Resolve the affected stable claim IDs without repeating sensitive values.
2. Preview that forgetting removes the claims from active memory, clears matching candidates, redacts matching values from local memory history, and refreshes generated views.
3. Explain retention accurately before asking for explicit confirmation: earlier Git commits, remotes, clones, caches, or repository backups may still contain an old value; the external transactional backup/rollback evidence may intentionally retain pre-change bytes until a human deletes it. Baton does not rewrite Git history or delete backups automatically.
4. After confirmation, invoke one hidden forget transaction and report what record IDs/categories were removed, the Git-retention warning, and returned report/rollback locations without repeating the forgotten values.

Never claim a value is globally erased. Never print a forgotten or rejected secret while reporting success, failure, retry, or recovery.

## Bound authority

Memory never authorizes publication, destructive action, external commitment, security/compliance decisions, execution readiness, role replacement, or project priority. Require explicit user approval to replace Management, Operations, or a Consultant. Preserve stable common authority names and evidence-backed personnel history; do not create rankings, leaderboards, novelty quotas, or universal employee scores.
