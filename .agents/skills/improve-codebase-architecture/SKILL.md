---
name: improve-codebase-architecture
description: Scan a project for evidence-backed opportunities to deepen shallow modules, present at most three candidates in a disposable visual report, and help the Project Director select and define a safe next action without refactoring. Use when the user invokes $improve-codebase-architecture or asks to review architecture, improve testability or navigability, reduce cross-file orchestration, find leaking seams, or evaluate a recurring code hotspot.
---

# Improve Codebase Architecture

Run this as a Project Director architecture-discovery workflow. Produce evidence and decisions, not implementation. Keep system-level architecture approval with the Project Director and implementation design, worker dispatch, integration, and verification with the Delivery Lead.

## Ground the review

1. Follow `AGENTS.md`; read the Project Director role, applicable design rules, accepted architecture ADRs, relevant PRDs/tickets/reports, active work, and repository status.
2. Use the exact architecture vocabulary from the applicable design rule: **module**, **interface**, **implementation**, **depth**, **seam**, **adapter**, **leverage**, and **locality**. Use **boundary** only for package, authority, ownership, or task-scope limits.
3. If the user names a module, subsystem, or pain point, keep that scope. Otherwise inspect history, recent reports, roadmap pressure, and recurring changed paths to select a narrow hotspot before scanning.
4. Treat recent change as evidence of future pressure, not proof that refactoring is valuable. Exclude generated/vendor code and avoid scanning the whole repository without a concrete reason.
5. Mark overlap with registered active work. Do not inspect uncommitted work as a refactoring target, edit reserved files, or interrupt an active ticket. A broad investigation beyond bounded read-only discovery must be scoped and routed through Delivery.
6. Use targeted path, symbol, caller, and test searches after the mandatory startup read. Stop when evidence supports at most three candidates. If the first pass cannot establish a narrow scope, ask one scoping question or propose a bounded investigation instead of widening repeatedly.

## Find deepening candidates

Inspect callers, tests, runtime adapters, package seams, and boundary-audit evidence organically. Look for:

- one concept requiring navigation through many small modules;
- an interface nearly as complex as its implementation;
- orchestration or policy leaking into several callers;
- pure helpers extracted for tests while integration bugs lack locality;
- coupled modules leaking knowledge across a seam;
- behavior that cannot be tested through the same interface callers use; and
- repeated change or defects concentrated around the same orchestration path.

Apply the deletion test: deleting a shallow module merely moves its complexity; deleting a deep module spreads meaningful policy and orchestration back into callers. Reject candidates supported only by aesthetics, file count, novelty, or hypothetical reuse.

For each surviving candidate, verify concrete files, callers, tests, observed friction, current interface, complexity it fails to hide, expected gains in depth/leverage/locality and behavior-level testing, dependency category (`in-process`, `locally substitutable`, `remote-but-owned`, or `truly external`), ADR support or conflict, active ownership/dependency/safe-checkpoint constraints, and recommendation strength: `Strong`, `Worth exploring`, or `Speculative`.

Do not propose a replacement interface or edit production code during this scan.

## Present the review

Read [references/report-format.md](references/report-format.md). Write one timestamped HTML report under `${TMPDIR:-/tmp}`; never place it in the repository. Escape all repository-derived text before inserting it into HTML. Return its absolute path and open it only when the environment and user intent support doing so.

Show three or fewer high-signal candidates. Each card must include files, evidence, problem, proposed deepening direction, gains, dependency category, ADR relationship, ownership/readiness state, recommendation strength, and clearly labelled before/proposed-after visuals. End with one evidence-backed top recommendation.

Then ask exactly one question: which candidate, if any, the user wants to explore.

## Explore the selected candidate

After selection, follow the one-decision-at-a-time discipline in [the Brainstorm skill](../brainstorm/SKILL.md): recommend an answer, explain the main trade-off, and wait. Resolve constraints, callers, invariants, errors, ordering, performance, dependencies, migration, preserved tests, runtime proof, and non-goals before suggesting execution.

For a consequential, long-lived, high-fan-out, or uncertain interface, do not design it alone. Have the Project Director prepare a bounded investigation or ticket; once it is Ready and non-overlapping, Delivery registers ownership and dispatches at least three independent design workers with contrasting constraints when the applicable design rule requires it.

## Record the outcome

- Offer an ADR only when a rejected candidate reflects a durable, non-obvious trade-off meeting the repository's normal threshold.
- If the user accepts further work, classify it against active work and record it transactionally as `Idea`, `Needs Definition`, `Blocked`, or `Ready` according to normal gates.
- Do not wake Delivery for a report, an unselected candidate, or unresolved architecture intent.
- Do not change an accepted architecture ADR, production interface, or test boundary until the owning decision and execution workflow authorize it.
- End with the selected outcome, durable paths changed if any, next owner, and exact return trigger.
