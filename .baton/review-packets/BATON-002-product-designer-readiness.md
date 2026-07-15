# BATON-004 — Product Designer readiness for BATON-002

Status: Approved
Review owner: Product Designer Consultant
Ticket ID: BATON-002
Stage: Readiness

## Outcome under review

This packet defines product-design readiness for the Management-first bootstrap, company memory controls, and personnel/history dashboard described in the [approved outcome](../prds/BATON-002-bootstrap-memory.md) and [accepted architecture](../decisions/BATON-002-architecture.md). It does not accept an implementation, technical integration, or publication.

## Target user and Management-first journey

The target user is a person starting or adopting a project with Baton who needs guided setup without understanding task-provider mechanics or memory storage.

1. The user explicitly invokes `$bootstrap-baton` and meets Management first.
2. Management introduces itself briefly, asks the user's preferred name, then assembles the configured team. A coworker is called online only after a real task is registered; otherwise the interface states what remains manual.
3. Management asks exactly one project-definition question at a time. Discovery may continue while roster work is incomplete, but the interface distinguishes discovery from delivery readiness.
4. Management presents one plain-language project summary, identifies unresolved roster or integration limits, and asks for explicit confirmation.
5. Confirmation creates durable project intent. The theatrical introduction ends here; subsequent work uses stable role names, professional coworker names, and direct operational language.

## Interaction contract

- One-question rhythm: each turn contains at most one user-answerable project-definition question. Status context may accompany it, but no second decision or bundled questionnaire may compete for an answer.
- Plain feedback: use concrete labels such as `Creating task`, `Online`, `Awaiting task`, `Needs Integration`, `Could not create task`, `Ready for confirmation`, and `Complete`. Never imply success while work is pending or failed.
- Final confirmation: show the proposed project identity, purpose, users, intended outcome, known constraints, team/task readiness, and unresolved items in a reviewable summary. The only committing action is an explicit confirm response; correction returns to the relevant single question without discarding prior answers.
- Tone boundary: playful copy is limited to the initial welcome, coworker introductions, and restrained personnel details. Errors, privacy choices, recovery, delivery gates, and all post-confirmation operation are concise and literal.

## Required states

| State | Required presentation and behavior |
| --- | --- |
| Normal | Show the current single question, saved provisional answers, roster progress, and the next meaningful action without exposing agent mechanics. |
| Resumed or interrupted | Resume at the first incomplete step, preserve prior provisional answers and stable identities, say what completed and what remains, and never replay completed introductions or create duplicate work. |
| Complete | Show the confirmed summary, named roster, task readiness, and a direct next-step entry into normal Baton operation; do not restart onboarding by default. |
| Native task | Mark a coworker `Online` only after safe capability probing and successful registration of a stable task identity and wake path. |
| Fallback or partial task | Mark each affected coworker `Awaiting task`, provide one copy-ready prompt and registration instruction, keep discovery usable, and explain that delivery requiring that role remains unavailable. Mixed native and fallback rosters remain legible per coworker. |
| Task failure | Name the failed coworker/seat, retain successful work and answers, explain whether retry or fallback is available, and place focus on the recovery action. Never claim bootstrap completion. |
| Duplicate reconciliation | Reuse the matching registered task/personnel identity, state that an existing coworker was found, and present any ambiguous collision for explicit resolution without silently merging or creating another task. |
| Needs Integration | Explain that the mature project needs reviewed activation, preserve existing project files, provide the exact next action, and do not present normal bootstrap completion. |
| Secret rejection | Refuse to store the value without echoing it, explain that credentials and sensitive values do not belong in memory, and offer a safe category or external-secret-storage direction. The rejected value must not appear in history, previews, logs, or the dashboard. |
| Forget and Git retention | Before confirmation, distinguish removal from active memory/local memory history from possible retention in earlier Git commits. After success, identify what was removed without repeating the value, provide the external report/rollback location, and never imply Git history was rewritten. |

Delivery controls must clearly separate `Discovery available` from `Delivery blocked` whenever a required role lacks a valid task or wake path.

## Memory flows

All flows begin through `$memory` in natural language and use one decision at a time.

| Flow | Acceptance behavior |
| --- | --- |
| Remember | Restate the proposed claim in safe, readable language with its subject and category. An explicit, unambiguous user statement may be stored as confirmed; an inference is stored only as a candidate and is labeled as having no effect yet. Show success or a specific rejection. |
| Inspect | Return a privacy-filtered, readable view grouped by confirmed memory, candidates, personnel, or history as requested. Provide stable claim references for correction/forgetting and disclose when results are filtered or empty. |
| Confirm | Show the exact candidate meaning and source class, then offer confirm, correct, or reject. Only confirmation promotes it into usable memory; success states what will influence future work. |
| Correct | Show the current meaning and proposed replacement, obtain confirmation when the request is ambiguous, then mark the old claim superseded and report the new active meaning without duplicating it. |
| Forget | Preview the affected claim(s), local-history redaction, generated-view refresh, rollback evidence, and Git-retention warning. Require explicit confirmation, then report completion without repeating the forgotten value. |
| Candidate review | List pending candidates separately from confirmed facts. Review one candidate at a time with confirm, edit-and-confirm, reject, or skip; candidates never influence work or appear as established user facts before confirmation. |

Failures in any mutation keep the previous confirmed state, identify the failed step in plain language, preserve the user's input when safe, and offer retry, correction, or recovery evidence as applicable.

## Dashboard personnel and history presentation

- Present each person by professional name plus stable authority label (`Management`, `Operations`, `Consultant`, or `Contractor`), employment/task status, bounded working-style traits, relevant assignment types, and evidence-linked observable outcomes.
- Describe contextual fit and repeated evidence without a universal score, rank, leaderboard, winner/loser framing, novelty pressure, or unsupported quality claim.
- Distinguish user feedback, Management assessment, operational evidence, and self-reflection. Never render self-reflection as accepted performance truth.
- Render an allowlisted, value-minimized chronology. Do not expose raw private claims, candidates, secrets, source JSON/JSONL, forgotten values, hidden prompts, task IDs by default, or evidence content beyond a deliberate user-opened link.
- Provide clear empty, loading, stale, filtered, and error states. Names never replace stable role labels, and status is never communicated by color alone.

## Accessibility and responsive acceptance

- Keyboard: every bootstrap, memory, confirmation, dashboard filter, disclosure, retry, and recovery action is operable in a logical order without a pointer or keyboard trap; Escape closes transient layers when safe.
- Focus: focus is always visible, moves to new questions, validation summaries, or recovery headings after state changes, and returns to the invoking control after a dialog closes. Destructive confirmation starts on the non-destructive choice.
- Screen reader: semantic headings, landmarks, labels, table structure, field instructions, and associated errors expose the same meaning as the visual interface. Status changes use restrained live announcements, and names are announced with stable roles.
- Contrast: text meets WCAG AA contrast (4.5:1 normal text, 3:1 large text); controls, focus indicators, charts, and meaningful non-text boundaries meet 3:1 against adjacent colors.
- Responsive: complete representative flows at 320×568, 768×1024, and 1440×900 without clipped content, horizontal page scrolling, obscured focus, inaccessible actions, or loss of status/context. Tables become labeled cards or an equivalently understandable narrow layout.
- Reduced motion: `prefers-reduced-motion` removes non-essential entrance, progress, and celebration motion; no information or completion cue depends on animation.
- Recovery: errors preserve safe input and completed progress, identify the affected item, expose retry/correct/fallback actions, and remain understandable after refresh, back navigation, interruption, and assistive-technology re-entry.

## Representative evidence required for later acceptance

- Recorded fresh native-task bootstrap at 320×568 and 1440×900, including the one-question rhythm, final summary, explicit confirmation, and transition out of theatrical onboarding.
- Recorded interruption/resume at 768×1024 plus fixtures for complete bootstrap, mixed native/fallback roster, task failure/retry, duplicate reconciliation, and `Needs Integration`.
- Recorded `$memory` remember, inspect, confirm, correct, candidate-review, secret-rejection, and forget/Git-retention flows, including mutation failure and recovery.
- Dashboard captures with representative active, awaiting, former, and rehired personnel and mixed history sources at all target widths; fixture assertions prove candidates, secrets, raw private claims, forgotten values, rankings, and leaderboards are absent.
- Keyboard-only recordings for bootstrap and memory mutation, focus-order/focus-restoration assertions, and accessibility-tree or screen-reader transcripts for changing status, errors, confirmation, personnel, and history.
- Automated WCAG checks with no serious or critical violations, measured contrast evidence, 200% zoom/reflow checks, and reduced-motion captures.
- Plain-language content review covering every required state, empty/error/recovery copy, and the distinction between discovery availability and delivery readiness.

## Known risks and boundary

Implementation must prove that partial task capability, privacy rejection, and interruption recovery remain comprehensible without exposing internal mechanics. Product-design approval does not replace Operations verification, technical acceptance, human release approval, or evidence from implemented representative flows.

Implemented representative evidence is recorded separately in [`BATON-002-acceptance-evidence.md`](BATON-002-acceptance-evidence.md), with its source-only provider trace and representative memory projection. That packet does not change this readiness contract or grant Product Designer acceptance by itself.

## Readiness verdict

**APPROVED** — BATON-002 has explicit target users, journey, interaction states, content behavior, accessibility acceptance, recovery behavior, and representative evidence requirements inside the Product Designer domain. Return these requirements to Operations for execution planning; implementation acceptance remains pending.
