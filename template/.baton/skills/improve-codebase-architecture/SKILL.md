---
name: improve-codebase-architecture
description: Inspect a codebase for evidence-backed opportunities to deepen modules and improve locality. Use when the user asks for architecture improvement, refactoring candidates, or module-boundary review.
---

# Improve codebase architecture

Perform read-only discovery first. Do not propose an interface or edit production code until the user selects a candidate.

## Find candidates

Follow `AGENTS.md`, validate state, inspect direction, accepted decisions, ownership, current Git state, relevant architecture, callers, tests, and recent pressure. Respect a user-supplied scope; otherwise select one narrow hotspot from recurring change or defects. Exclude generated/vendor code and uncommitted owned work.

Stop at three candidates. Look for scattered policy, caller knowledge, shallow pass-through interfaces, coupled seams, tests forced through internals, or repeated defects around one orchestration path. Apply the deletion test from `rules/design.md`. Reject aesthetics, file count, novelty, and hypothetical reuse.

For each candidate record exact files, callers, tests, current interface, observed friction, hidden-complexity failure, expected depth/locality gain, dependency category, accepted-decision relationship, ownership/readiness, and strength: `Strong`, `Worth exploring`, or `Speculative`.

## Report

Write one timestamped standalone HTML report under `${TMPDIR:-/tmp}` and return its absolute path. Escape repository text. Use inline CSS; use Mermaid from a CDN only when a graph materially helps. State the repository, date, scope, Git reference, and that proposed directions are unapproved.

Each of at most three cards includes the evidence above plus clearly labelled **Current** and **Proposed direction — not approved** visuals. End with one evidence-backed recommendation and its safe checkpoint or blocker. The report never authorizes refactoring.

Ask exactly one question: which candidate, if any, should be explored?

## Explore and record

For the selected candidate, use the Brainstorm skill one decision at a time. Resolve constraints, callers, invariants, errors, ordering, performance, dependencies, migration, tests, runtime proof, and non-goals. Consequential or uncertain interfaces require a bounded Ready investigation and contrasting independent Operations-dispatched proposals.

Offer an ADR only for a costly-to-reverse, non-obvious trade-off. Record accepted further work as `Backlog`, `Blocked`, or `Ready` under normal gates. Do not wake Operations for an unselected report or unresolved intent.
