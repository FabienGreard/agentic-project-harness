# BATON-002 — Bootstrap, company memory, and named workforce

Status: Execution in progress for unpublished v0.7.0 candidate

Owner: Management

Priority: P3

Goal ID: BATON-GOAL-002

## Context and problem

Baton installation currently configures roles, state, and skills but leaves the user to create permanent tasks and explain the project manually. Tasks do not share a project-local, user-editable memory of the company, the user, or named coworkers. Contractor and leadership history therefore cannot reliably support evidence-backed reuse, self-reflection, or replacement.

The first-run experience should feel welcoming and lightly theatrical without turning Baton into a game. After onboarding, Baton remains a serious general-purpose project-creation and delivery system.

## Intended user/stakeholder experience

The user invokes `$bootstrap-baton`. Management appears first, introduces itself, asks the user's preferred name, and assembles the configured permanent team. Each coworker receives a stable professional name and a small working-style variation. Management presents coworkers as their real tasks come online, then asks one simple project-definition question at a time.

Project discovery may continue while a coworker is awaiting task creation, but delivery cannot begin until every role required for that work has a registered task and valid wake path. Management presents one final project summary; only explicit user confirmation creates durable project intent.

The user manages all remembered information through one `$memory` skill using natural requests such as remember, forget, correct, inspect, and review candidates. The dashboard presents company history and personnel records without making raw storage or agent mechanics the primary experience.

## Goals

- Make first use after installation obvious, coherent, and provider-aware.
- Create and register the configured permanent team without duplicate tasks.
- Give every Management, Operations, Consultant, and Contractor identity a stable name and reusable personnel history.
- Maintain one project-local company memory for project identity, confirmed user knowledge, personnel, and company history.
- Learn which highly capable coworkers and professional working styles perform best for specific work while freely reusing proven people.
- Keep automatic agent context small, role-specific, and explicitly expandable on demand.
- Let the user inspect, correct, and forget memory without hidden global synchronization.

## Explicit non-goals

- Turn project delivery into a game, simulation, employee leaderboard, or forced role-play.
- Select a weaker coworker for novelty, enforce rotation, or reserve an exploration quota.
- Create global memory, cross-project synchronization, or memory import.
- Store raw conversation transcripts, secrets, passwords, tokens, or unconfirmed personal inferences as durable facts.
- Duplicate tickets, PRDs, approvals, implementation evidence, or consequential project decisions inside memory.
- Use personality to alter Baton authority, safety, competence, model choice, or reasoning requirements.
- Let coworkers authoritatively grade themselves or replace permanent leadership seats without explicit user confirmation.
- Rewrite Git history when the user forgets a memory.
- Create persistent goals or speculative Contractor tasks during bootstrap.

## Functional or operational requirements

### Bootstrap

1. Add one explicitly invocable `$bootstrap-baton` skill.
2. Check installation status, canonical state, team configuration, and live task capabilities before creating anything.
3. Route `Needs Integration` projects through reviewed mature-project activation before claiming normal bootstrap completion.
4. Create Management first and have Management ask the user's preferred name.
5. Generate stable professional identities for Management, Operations, active Consultants, and later Contractors.
6. Create configured permanent tasks, record real task IDs, and show a coworker as online only after its task exists.
7. Reuse matching registered tasks and personnel instead of creating duplicates.
8. When programmatic task creation is unavailable, generate copy-ready role prompts and record the coworker as `awaiting-task`.
9. Resume an incomplete bootstrap from the registered roster.
10. Permit project discovery with an incomplete roster while prohibiting delivery until all roles required by the work have valid task and wake paths.
11. Ask exactly one project-definition question at a time and keep project statements provisional until a final user-confirmed summary.
12. Never create, resume, recreate, or attach persistent goals for role lifecycle.

### Named workforce and professional variation

1. Give every coworker a permanent ID, human name, organizational seat or Contractor specialty, employment status, and assignment history.
2. Generate a small stable professional working-style profile from bounded traits such as plan-first versus prototype-first, concise versus explanatory, broad versus narrow exploration, risk-first versus opportunity-first, and simplification versus extensibility.
3. Store the generation seed so identity is reproducible and never silently regenerated by an update.
4. Keep every generated coworker highly capable; capability, evidence, availability, model quality, reasoning, and task fit always outweigh working style.
5. Rehire the strongest suitable coworker indefinitely when evidence supports doing so.
6. Allow Operations to trial a new equally qualified coworker only for low-risk bounded work when evidence is insufficient; impose no novelty quota.
7. Preserve fired, retired, replaced, and rehired personnel history.
8. Keep Management and Operations as permanent organizational seats whose named occupant may change only with explicit user approval.
9. Require explicit user approval to replace Management, Operations, or a Consultant. Permit Operations to select and replace Contractors inside approved work.

### Reviews and learning

1. Review Contractors after completed, revised, abandoned, or failed assignments.
2. Review Consultants after readiness or acceptance engagements.
3. Review Operations after completed tickets or failed delivery boundaries.
4. Review Management after completed goals, rejected direction, or explicit user correction.
5. Separate self-reflection, operational evidence, Management assessment, and user feedback.
6. Give explicit user feedback the greatest authority.
7. Require assignment type, observable outcome, revision cause, verification quality, working-style impact, reviewers, timestamps, and exact evidence paths.
8. Promote only repeated evidence-backed patterns into active performance summaries; retain individual events in company history.
9. Learn contextual strengths rather than one universal employee score.
10. Allow Management to self-reflect, change behavior, stop commissioning a person, or recommend its own succession without authoritatively accepting its own performance or replacing itself.

### One project-local memory

1. Use exactly one project-local memory root with no import or global synchronization:

   ```text
   .baton/memory/
   ├── memory.json
   └── history.jsonl
   ```

2. Make schema-versioned `memory.json` the current editable truth for company knowledge, confirmed user profile, named personnel, professional working styles, active performance summaries, pending candidates, and memory settings.
3. Use `history.jsonl` as the company chronology for bootstrap, personnel, assignment, review, milestone, and memory-lifecycle events.
4. Store claims as independently addressable records with a typed category, readable statement, subject, source, status, and timestamps.
5. Support confirmed, pending-confirmation, and superseded states; only confirmed claims influence work automatically.
6. Record explicit user statements directly when unambiguous. Record inferred personal observations only as candidates requiring user confirmation.
7. Permit verified company and coworker events to enter history automatically.
8. Reference personal claim IDs from history rather than duplicating their values.
9. Link to authoritative project-management records without copying their decisions or evidence into memory.
10. Expose remember, forget, correct, inspect, and candidate review through one `$memory` skill and no additional public CLI commands.

### Forgetting and privacy

1. Remove forgotten claims from active memory, clear matching candidates, and redact matching values from local memory history.
2. Refresh generated views and leave an external transactional report and rollback location.
3. Never rewrite Git history automatically; warn when earlier commits may retain the value.
4. Exclude secrets, passwords, tokens, credentials, and sensitive personal information by default.
5. Let the user inspect, confirm, correct, or forget any memory.

### Context control

1. Keep complete memory on disk and generate only an ephemeral role-specific briefing at task wake.
2. Cap automatic memory context at approximately 10 confirmed claims or 600 tokens.
3. Rank by role, assignment, subject, freshness, and importance.
4. Exclude candidates, superseded memories, complete histories, old reviews, inactive coworkers, and information already present in the assignment.
5. Prefer exact links over embedding large reports.
6. Allow explicit on-demand retrieval without silently expanding the automatic budget.
7. Record which memories materially influenced work when that evidence affects a review or decision.

### Memory authority

1. The user is final authority over all memory.
2. Management confirms company identity and user-approved durable learning.
3. Operations records verified assignments, delivery outcomes, revisions, and performance evidence.
4. Consultants may submit domain observations and self-reflections but cannot confirm user facts or their own performance.
5. Contractors may submit self-reflections and memory candidates only.
6. Internal Audit may read memory for harness evaluation but is not company personnel and writes no company performance memory.
7. Route every mutation through one deterministic writer that validates schema, provenance, authority, context budget, transactionality, and rollback evidence.

## Design or policy requirements

- Keep `AGENTS.md` a navigation map and place normative memory behavior in the appropriate rule modules.
- Keep the playful presentation limited to bootstrap copy, introductions, personnel dossiers, and the generated dashboard.
- Preserve the stable common authority names Management, Operations, Consultants, and Contractors regardless of generated personal names.
- Make storage directly inspectable and user-editable while requiring deterministic validation for accepted mutations.
- Preserve unrelated dirty work and project-owned files during install, adoption, activation, bootstrap, memory changes, and updates.
- Treat memory as supportive context, never as authorization for publication, destructive action, external commitment, security/compliance decisions, or execution readiness.

## Technical/process considerations

- Define versioned memory, personnel, and history-event schemas with migration fixtures before making the feature updateable.
- Extend installed skill discovery without duplicating skill content or adding root command clutter.
- Integrate provider task creation only through available user-authorized task tools; keep a deterministic copy-prompt fallback.
- Reconcile task IDs, personnel identities, team state, and thread registry transactionally.
- Keep memory/context selection independent of model-vendor hidden memory.
- Render memory and personnel views from canonical records into the existing dashboard rather than creating a second dashboard authority.
- Ensure source-only Baton records remain outside consumer payloads while the new consumer memory scaffolding and skills project from `template/.baton/`.
- Preserve stable update behavior, mature-adoption quarantine, collision handling, backups, rollback, and Python compatibility.

## Dependencies

- BATON-001 is complete; its exact unpublished v0.6 candidate remains isolated and publication remains a separate human Release decision.
- Current Codex task-creation, task-listing, navigation, and messaging capabilities must be verified at implementation time.
- Product Designer readiness and implementation Acceptance are approved in `.baton/review-packets/BATON-002-product-designer-readiness.md` and `.baton/review-packets/BATON-002-acceptance-evidence.md`. Corrected disposable Internal Audit `IA-BATON-002-20260716T011303+0200-ebb65efc-dirty` passed at 98/100 with no hard gates or P0–P3 findings. Operations integration Acceptance is approved in `.baton/review-packets/BATON-002-operations-acceptance.md`; clean-commit packaging and human Release remain pending.

## Risks

- Overloading task context with memory can reduce rather than improve agent performance.
- Inferred user facts can become harmful assumptions if confirmation is bypassed.
- Performance summaries can become self-reinforcing unless evidence, task type, and user corrections remain visible.
- Random personality can become gimmicky or reduce quality unless constrained to professional working style.
- Task creation can duplicate permanent roles unless real task identity and idempotency are proven.
- Append-only history and Git retention can conflict with user expectations for forgetting.
- Schema or update mistakes can corrupt durable company history without transactional migration and rollback.
- Storing personal information in a repository can expose it through Git or repository sharing unless the user receives clear warnings and controls.

## Acceptance criteria

- `$bootstrap-baton` produces the approved Management-first onboarding and is idempotent across complete and interrupted runs.
- Every configured permanent coworker has a stable named personnel record and either a real registered task or explicit `awaiting-task` state.
- Delivery gates correctly reject missing required task/wake paths while project discovery remains usable.
- User-confirmed project discovery initializes durable company/project intent transactionally and never creates executable work by itself.
- `$memory` is the only user-facing memory interface and supports remember, forget, correct, inspect, and candidate review.
- `memory.json` and `history.jsonl` validate, migrate, roll back, and remain directly inspectable.
- Personal inferences never become durable without user confirmation; verified company/personnel events may be automatic.
- Forgetting removes current values, redacts local memory history, and warns about Git retention without rewriting Git history.
- Every coworker review is evidence-backed, separates self-reflection from acceptance, and supports contextual reuse or replacement.
- Proven coworkers may be reused indefinitely; no forced rotation or novelty quota exists.
- Permanent-seat replacement requires explicit user approval.
- Automatic memory briefing stays within the agreed claim/token cap and retrieves additional context only on demand.
- Fresh install, mature adoption, update, interrupted bootstrap, unavailable task tools, duplicate-task prevention, memory migration, corruption, rollback, privacy, context-budget, and dashboard flows pass deterministic tests.
- The generated template remains fully generic across software, games, business operations, and research.

## Assurance policy

- Project default test rigor: Thorough
- Resolved ticket test rigor: Thorough
- Human review stages: Release
- User-authorized override reason: none

## Verification and evidence expectations

- Schema and cross-record contract tests for memory, personnel, and history events.
- Forward tests for bootstrap and memory skills with task tools available and unavailable.
- Exact context-packet assertions for each permanent role and Contractor assignments.
- Deterministic identity, idempotency, duplicate prevention, rehire, firing, replacement, and review fixtures.
- Privacy fixtures for candidate confirmation, forgetting, local history redaction, Git warning, and secret rejection.
- Full local, piped, interactive, fresh-project, mature-adoption, update, rollback, and Python compatibility matrices.
- Independent two-axis review, Product Designer readiness/acceptance, and disposable Internal Audit.
- Immutable-SHA standalone smoke before any eventual release.

## Consultant readiness and review

The active Product Designer Consultant must approve bootstrap comprehension, interruption recovery, memory inspection/correction/forgetting, personnel presentation, accessibility, and the boundary between playful onboarding and serious project operation before this ticket becomes executable.

## Human-review boundary

Outcome behavior, implementation readiness, Product Designer Acceptance, two-axis review, deterministic verification, corrected disposable Internal Audit, and Operations integration Acceptance are complete. The unpublished v0.7.0 candidate must still produce exact clean-commit package evidence. Any eventual publication remains separately human-gated at Release.

## Suggested execution strategy

1. Resolve schemas, memory authority, migration, privacy, and context selection as a bounded architecture slice.
2. Implement the deterministic memory/personnel writer and tests.
3. Add `$memory` and validate natural-language mutation flows.
4. Implement provider-aware task registry and `$bootstrap-baton` with copy-prompt fallback.
5. Integrate dashboard views and update/adoption behavior.
6. Run forward tests, two-axis review, Consultant gates, full smokes, and Internal Audit.

## Expected affected systems

- Consumer schemas, memory storage, and migrations.
- Bootstrap and memory skills plus skill discovery metadata.
- Team, personnel, task registry, role configs, and lifecycle policy.
- Installer, adoption, activation, update, provenance, backups, and rollback.
- Context selection and role startup behavior.
- Dashboard rendering and memory/personnel presentation.
- Static evaluator, deterministic tests, interactive and remote smoke fixtures.
- README, getting-started, installation, customization, architecture, and release documentation.

## Definition of Done

The feature is complete only when every acceptance criterion has exact evidence, the ticket's readiness and review gates are satisfied, the source and generated consumer surfaces remain non-contradictory, migration and rollback are proven, and the unpublished candidate returns to Management for a separate Release decision.
