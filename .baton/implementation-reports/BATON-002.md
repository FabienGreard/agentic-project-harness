# BATON-002 — Implementation report

Prepared: 2026-07-15

Reviewed by: Operations

Goal ID: BATON-GOAL-002

Candidate boundary: unpublished Baton v0.7.0 working candidate on base `ebb65efc252e854bbeb4d3f76fa10790a3ec38e1`. The final immutable candidate SHA is recorded only after review fixes, state reconciliation, and a local candidate commit.

## Outcome

Baton now supplies an explicit Management-first bootstrap and one project-local company memory. Fresh projects receive schema-valid starter memory, a generated permanent-task registry, role-scoped memory instructions, and two explicitly invoked skills: `$bootstrap-baton` for resumable onboarding/task registration and `$memory` for inspection and controlled mutations.

Every permanent coworker and reusable Consultant/Contractor record can have a stable professional name, bounded working style, employment/task status, assignment history, evidence-linked reviews, and contextual performance summaries without a universal score, rank, forced rotation, or novelty quota. Memory remains supportive context rather than a second project-management authority.

No release, push, tag, asset upload, latest-stable change, or permanent adopter task creation occurred.

## Changed systems

- Added schema-versioned `.baton/memory/memory.json` and `.baton/memory/history.jsonl` plus deterministic validation, authority, privacy, task, bootstrap, personnel, review, context-selection, initialization, transaction, rollback, and recovery behavior in `baton_memory.py`.
- Added `$bootstrap-baton` and `$memory` with explicit invocation metadata and individual non-drifting `.agents/skills/` discovery links.
- Added generated `.baton/thread-registry.md` behavior for new projects and reviewed activation; older project-owned registries remain preserved.
- Integrated company memory with Consultant hire/fire, Codex role configs, dashboard generation, metadata baselines, installation, adoption, activation, updates, release projection, and static evaluation.
- Kept the complete starter agent map and generated dashboard browsable inside mature-adoption quarantine through baseline-managed relative bridges to shared Baton runtime. Update regenerates that view; activation promotes only real starter content and skips every bridge.
- Added privacy-filtered personnel/history dashboard views, neutral role/name-ordered assignment context, reviewed assignment types, evidence-linked observable outcomes, explicit source provenance, and an unverified self-reflection label. Removed highest/lowest, completion-percentage ordering, assignment-share charts, duplicate permanent seats, and other leaderboard framing.
- Added exact fallback prompts per permanent seat. Consultant prompts include stable Consultant ID, title, domain, exact config path, and acceptance boundary.
- Added explicit collision-safe `_memory initialize` for older updated installations whose two memory files are both absent. Initialization transactionally registers both files as project-owned while keeping them outside `managedFiles`; update itself never creates or overwrites project-owned memory.
- Updated public installation, getting-started, customization, architecture, release, README, and changelog guidance for v0.7.0 while preserving the no-auto-release boundary.

## Transaction and recovery contract

- One shared external mutation lock serializes memory, state, team, installation, activation, and update operations.
- Memory mutations write a prepared external report first, replace full history first, replace `memory.json` as the logical commit marker, refresh generated dashboard/registry/metadata views, validate, and retain external backup/rollback evidence.
- Consultant hire/fire composes team, config, memory, history, dashboard, registry, and metadata under one write-ahead transaction with the same history-first and commit-marker semantics.
- Recognized interrupted before/after/mixed digest states recover deterministically; unknown states fail closed.
- Explicit initialization recovers process death both before and after the logical commit marker. One-file, symlink, occupied-path, or invalid-schema collisions fail without replacing project data.
- Idempotency keys are bound to normalized request semantics, including set-like fields and initial-claim defaults. Exact or semantically equivalent replay is idempotent; reusing a key for different semantics is rejected.

## Bootstrap and task-provider evidence

The live Codex surface used for this candidate exposes list, create, stable returned task identity, read, and message operations (`list_threads`, `create_thread`, `read_thread`, and `send_message_to_thread`). That is the complete capability set the bootstrap skill is required to probe. The reproducible inventory and successful read-only list/read probes are recorded in [the provider-capability trace](../review-packets/BATON-002-provider-capability-trace.json). No adopter task was created because the user authorized implementation, not an explicit adopter `$bootstrap-baton` run; create/send were not speculatively exercised.

Deterministic forward fixtures prove:

- Management/Operations/active-Consultant seats only; direct roster mutations and reconciler paths both reject Contractor, Internal Audit, inactive Consultant, and former/replaced seats.
- Fresh native reconciliation transactionally persists the exact named roster before returning create actions, normalizes even reversed input to Management-first order, rejects later-seat registration until Management is online, reuses exact registered tasks, and rejects duplicate task/personnel identities.
- Partial/unavailable task surfaces create no task, persist stable named personnel and `awaiting-task` roster state transactionally, and return one copy-ready prompt plus registration instruction per affected coworker.
- Two simultaneous Consultants receive visibly distinct role/domain/config/acceptance prompts.
- Mixed online/awaiting rosters survive interruption and resume without duplicate personnel or prompts.
- Discovery remains available while delivery readiness remains false; confirmation records project intent but cannot mark bootstrap complete until every required roster task has a stable ID and wake path.
- Older installs update without memory mutation, then explicitly initialize and pass a complete Baton check.

## Memory and context evidence

Deterministic fixtures cover remember, inspect, pending candidate, confirm/reject, correct/supersede, forget/local-history redaction, Git-retention warning, secret/sensitive rejection, personnel identity, hire/fire/rehire/replacement, evidence-linked reviews, repeated-evidence summaries, exact replay, stale revision rejection, mixed-artifact rollback, and interrupted recovery.

Automatic briefings include confirmed claims only, filter out claims whose role relevance excludes the waking project role, exclude inactive personnel context, cap at 10 claims, 1,800 UTF-8 bytes, and an estimated 600 tokens, and never load full memory/candidates/history into role startup instructions. Exact Management, Operations, Consultant, and Contractor fixtures assert non-empty role-matching packets, exclusion of every other project role, and the byte/token caps. Separate automatic and on-demand Internal Audit fixtures require an explicit authorized evaluation boundary, return the same capped confirmed projection with `read-only-evaluation` authority, and prove that Internal Audit remains outside personnel, permanent task, and mutation roles.

## Dashboard, conversation, and accessibility evidence

The linked [implementation acceptance packet](../review-packets/BATON-002-acceptance-evidence.md) records the live provider trace, two actual agent-rendered transcript exercises, a committed representative memory projection, browser captures, semantic output, keyboard/focus behavior, axe-core output, contrast, reduced motion, and reflow measurements.

- Bootstrap recording covers native-capability planning, Management-first introduction, one-question discovery, final summary/confirmation, 768 interruption/resume, mixed online/awaiting seats, task failure/retry, duplicate reconciliation, and `Needs Integration`.
- Memory recording covers remember, inspect, personal-inference candidate, confirm, correct, candidate review, secret rejection without echo, forget/Git-retention warning, mutation failure, and recovery.
- `320×568`, `768×1024`, and `1440×900` representative dashboard runs have no horizontal page overflow, retain vertical scrolling, show four active/awaiting/former/rehired dossiers, five observable outcomes, ten safe evidence links, and no duplicate permanent seat. Every outcome, including a repeated-evidence summary, carries its own source labels and links.
- The 720×450 effective CSS viewport for a 1440×900 surface at 200% has no horizontal page overflow and reflows memory to one column. The unavailable persistent native page-zoom override is disclosed rather than falsely claimed.
- axe-core 4.11.4 reports zero violations and zero serious/critical violations at all three target widths. Its two incomplete checks are documented; manual contrast measures 15.39:1 body, 16.18:1 heading, 13.11:1 muted, and 17.52:1 focus treatment.
- Keyboard ArrowLeft/ArrowRight updates selected tab/focus/canonical URL; Escape closes the goal dialog and restores the exact invoking goal button. Reduced motion computes representative transitions/animations to `0.00001s`, one iteration. Final console warnings/errors: zero.
- The semantic snapshot exposes source classes and evidence groups. `Self Reflection · Unverified` is never presented as accepted performance truth. Candidates, secrets, raw private claims, forgotten values, and ranking surfaces remain absent from the rendered personnel/history view.

## Verification performed

- `PYTHONDONTWRITEBYTECODE=1 python3 tests/run_smokes.py` — PASS, 80/80 after canonical completion and the namespaced review-packet regression.
- `PYTHONDONTWRITEBYTECODE=1 bash tests/install_smoke.sh` — PASS, 80/80 through the installed/source smoke entrypoint.
- `PYTHONDONTWRITEBYTECODE=1 python3.9 tests/run_smokes.py` — PASS, 80/80.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/harness_eval.py --strict --json` — PASS, 17/17.
- `.baton/bin/baton check --json` — PASS.
- `bash -n scripts/install.sh tests/install_smoke.sh tests/install_remote_smoke.sh` — PASS.
- `git diff --check` — PASS.
- Focused corrected boundary — PASS, 61/61 memory/team/lifecycle tests.
- Explicit initialization process-death and older-install end-to-end fixtures — PASS, 3/3 targeted tests.
- Fresh, mature-adoption, and cross-version `Needs Integration` Markdown link audits — PASS; every local target resolves, including the generated quarantine dashboard and bounded links to shared metadata, roles, rules, skills, templates, and workflow.
- Live dashboard browser verification — PASS at 320×568, 768×1024, and 1440×900 with zero final console warnings/errors.
- Disposable Internal Audit `IA-BATON-002-20260716T011303+0200-ebb65efc-dirty` — **PASS**, 98/100, no hard gates and no P0–P3 findings. It independently reproduced all three corrected failures, reran all three 79/79 matrices, strict evaluation 17/17, source state, syntax, JSON/JSONL, JavaScript, diff, cache, exact five-asset projection, and lifecycle safety checks without modifying the repository.
- Focused packaging Internal Audit `019f6824-0872-75c2-b186-621b073d389c` at base `2df94a9038a320659524a507bb7551e6a3a065f0` and dirty-diff SHA-256 `612bcd18327745694304cd8c967332272af4e66b0e6e27d23ed56f05fd1b0f2f` — **PASS**, 99/100, no hard gates and no P0–P3 findings. It independently reran strict 17/17, current Python 80/80, Python 3.9 80/80, installed entrypoint 80/80, Baton state, shell, and diff checks; verified projection provenance, symlink containment, update baselines, activation skips/collisions, project preservation, and link regressions; edited nothing; and did not approve Release.

Resolved test rigor: Thorough.

Required human review stages and current status: Release — pending; no release action has occurred.

## Initial review findings and corrections

- Standards/architecture initially returned REVISE for team-memory crash recovery, disposable permanent-task registration, role-irrelevant context disclosure, missing older-install initialization, and unbound idempotency keys. The follow-up approved those corrections and reported three bounded P2s: direct roster validation, initialization ownership classification, and normalization of set-like request semantics. All three P2s are now corrected with regressions.
- Specification/evidence follow-up closed fallback persistence, neutral dashboard, and stale narrative findings, then retained REVISE only for the missing four-role/provider/Product Designer/Internal Audit/clean-commit evidence sequence. Four-role, provider, Product Designer, and Internal Audit evidence are now present; exact clean-commit packaging remains the final local evidence step.
- Product Designer follow-up closed ranking, prompt specificity, and mobile-header findings, then retained REVISE for representative interaction evidence and missing dossier outcomes/provenance. The dashboard now renders assignment types, outcomes, evidence paths, source classes, and unverified self-reflection; the linked acceptance packet records the required conversations, representative states, browser, axe, keyboard, focus, contrast, reflow, and reduced-motion evidence.
- The first disposable Internal Audit (`IA-BATON-002-20260716T004517+0200-312be149`) returned FAIL, 79/100, for three P1 defects: fresh native reconciliation returned unregistrable personnel IDs and did not enforce Management-first registration; Internal Audit could not request its authorized read-only memory briefing; and the PRD contradicted recorded Product Designer Acceptance. The candidate now persists native roster/personnel state transactionally before create actions, enforces Management-first registration, provides an explicit-boundary read-only Internal Audit selector, reconciles the PRD, and includes direct regressions. Fresh independent re-audit `IA-BATON-002-20260716T011303+0200-ebb65efc-dirty` reproduced and closed IA-001 through IA-003, returned PASS at 98/100 with no hard gates and no P0–P3 findings, and did not approve Release.
- Exact post-commit mature-adoption smoke exposed broken local links because the starter agent map was active while its canonical records were quarantined, and the quarantine lacked its generated dashboard. The correction projects the map with starter content, generates a complete browsable quarantine with safe shared-runtime bridges, preserves project identity, and adds install/update/activation/link regressions. All three 80/80 matrices and strict 17/17 checks pass after the correction; the original unpublished commit was amended rather than publishing the defective asset set.

Product Designer acceptance is **APPROVED**. The first bounded acceptance run accepted PD-03 and requested one P1 correction for repeated-summary provenance. After the summary projection, renderer, fixture, and per-item regressions were corrected, the one follow-up run closed PD-05-01 with no remaining P0–P3 Product Designer findings. Corrected disposable Internal Audit is also **PASS**. Operations integration Acceptance is **APPROVED** in [the dedicated packet](../review-packets/BATON-002-operations-acceptance.md). None of these decisions authorize publication; the human Release decision remains distinct.

## Known limitations and release boundary

- Immutable-SHA standalone remote smoke and public stable installer verification require an approved public release with all five immutable assets. They remain mandatory release gates and cannot be truthfully completed on this unpublished working candidate.
- Exact clean-commit release bundle hashes are produced only after review fixes and canonical-state reconciliation are committed locally; publication still requires a separate explicit human Release instruction.
- Auto-review and permission controls can remain constrained by Codex/app or managed-workspace settings, and already-running tasks can retain their selected permission mode.
- Mature project state is never inferred from arbitrary Markdown. Existing projects remain in `Needs Integration` until a complete schema-valid migration is reviewed and explicitly activated.

## Return condition

Corrected two-axis review, Product Designer acceptance, disposable Internal Audit, deterministic verification, Operations integration acceptance, and canonical completion are recorded. Operations now creates the local candidate commit, verifies the exact clean-commit bundle/install evidence, and returns the unpublished v0.7.0 candidate to Management. Publication remains separately human-gated.
