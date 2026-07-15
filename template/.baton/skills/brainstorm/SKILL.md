---
name: brainstorm
description: Explore and refine a proposed project change with Management, one outcome decision at a time, then record the confirmed result in the repository control plane. Use when the user invokes $brainstorm or asks to explore, challenge, compare, clarify, or scope a feature, policy, workflow, technical change, or other project outcome before implementation.
---

# Brainstorm

Run this as a Management outcome-definition conversation. A different role may gather read-only facts, but it must return outcome decisions to Management and must not mutate project state.

## Ground the idea

1. Follow the repository startup order in `AGENTS.md` and read the Management role.
2. Read the closest approved direction, PRDs, ADRs, tickets, recent reports, and active ownership. Inspect code or other project artifacts when they can answer a factual question.
3. Restate the change seed in one or two sentences. Identify its nearest approved concepts and any immediate contradiction, duplication, dependency, or overlap.
4. Classify its relationship to active work as superseding, parallel, queued, or informational. Do not interrupt or reprioritize work yet.

## Walk the decision tree

Interview the user until both sides share the same model of the change.

- Ask exactly one decision question per turn and wait for the answer.
- Give a recommended answer first, with a concise reason and the main trade-off.
- Look up discoverable facts instead of asking the user. Product and outcome decisions remain the user's; do not answer them on the user's behalf.
- Resolve prerequisite decisions before dependent details.
- Challenge conflicts with approved direction, needless complexity, ambiguous terminology, hidden assumptions, and weak stakeholder value.
- Stress-test decisions with concrete normal, failure, edge, and user-visible scenarios.
- Explore only relevant branches: intended outcome and principles; core interaction; success and failure; scope and non-goals; user and stakeholder effects; controls and accessibility; authority and persistence; performance and platform limits; slice boundaries; acceptance and evidence.
- Keep a concise in-conversation ledger of confirmed choices, rejected alternatives, unresolved questions, and discovered facts.
- Match the user's language while preserving canonical repository terms.

Do not batch questions, start implementation, dispatch Contractors, wake a permanent role, or silently turn the idea into active scope.

## Sharpen project language

Use the repository's existing vocabulary instead of creating a parallel glossary. When a term is vague or conflicts with the approved direction, name the conflict and propose one precise canonical term.

After the user confirms the shared understanding, place stable language in the narrow owning section of the direction, PRD, or ticket artifact. Do not create a catch-all context file.

Create or revise an ADR only when the decision is all three: costly to reverse, surprising without its rationale, and the result of a real trade-off. Otherwise record it in the relevant direction, PRD, or ticket artifact.

## Confirmation gate

When the meaningful branches are resolved, summarize:

- intended outcome and stakeholder value;
- agreed behavior, scope, and non-goals;
- rejected alternatives and why;
- unresolved decisions and risks;
- expected architecture, testing, operational, and documentation implications; and
- recommended incoming-change classification and next artifact/status.

Then ask one final question: whether the summary represents shared understanding. Do not enact the plan before the user confirms it.

## Record the outcome

After confirmation, Management:

1. checks current file ownership and avoids planning-file overlap;
2. updates the smallest appropriate project artifacts, ADR index, PRD, ticket, backlog, overview, dependencies, and wake conditions as one coherent transaction;
3. records incomplete ticket work as `Backlog` or `Blocked`, never `Ready` merely because brainstorming ended;
4. routes expert-heavy definition to the relevant active Consultant and executable Ready work to Operations only through documented wake conditions; and
5. reports the durable paths changed, final classification, next owner, and exact return trigger.

If another role owns an affected file, preserve the confirmed ledger and hand it to that owner instead of editing across the reservation.
