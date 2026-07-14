---
name: code-review
description: "Review a committed or work-in-progress project change against two independent axes: repository standards and architecture, then approved specification and completion evidence. Use when the user invokes $code-review, asks to review a branch, PR, Contractor return, integrated ticket, dirty worktree, release checkpoint, or changes since a ref; also use before Operations integration acceptance or a Management final Git/release audit."
---

# Code Review

Run a read-only, evidence-backed delivery-safety review rather than an unbounded bug search. Report findings; do not edit, stage, commit, push, revise Contractors, or change project state from the review itself.

## Select the authority mode

- **Operations integration review:** own the review, dispatch two independent read-only reviewers when the boundary is substantial, verify every returned finding, and decide accept, revise, or reject. All Contractor revision instructions still flow through Operations.
- **Management final audit:** consume Operations' verified diff, implementation report, and two-axis findings. Perform a bounded direct audit without dispatching Contractors; route technical revisions to Operations, outcome decisions to Management, and expert questions to the relevant active Consultant.
- **Consultant domain review:** review only the approved domain and return findings or acceptance input to Operations; do not set overall priority or dispatch a competing Contractor path.
- **Independent evaluator:** inspect the supplied candidate or disposable harness behavior read-only, report evidence-backed findings, and do not mutate active work or grade itself.
- **Contractor self-check:** review only the supplied scope, make no acceptance decision outside that role's authority, and return findings to the owning Operations task or user.

## Pin the exact review boundary

1. Prefer a user-supplied base. Otherwise use the ticket's recorded readiness/checkpoint commit or verified PR base. Ask only when no unambiguous base exists; never assume `main` or a stale remote ref.
2. Verify the base with `git rev-parse --verify`, record merge base when appropriate, current `HEAD`, branch, commit list, and `git status --short`.
3. For committed work, review `<base>...HEAD`. For WIP or an integrated dirty tree, include committed, staged, unstaged, and relevant untracked files. Record exact commands and path manifest so neither axis reviews a different change.
4. Compare the manifest with active work, ticket/report changed-file boundary, and current ownership. Exclude unrelated user or agent changes. If the target cannot be isolated safely, return `BLOCKED` and name the overlap instead of reviewing a mixed diff.
5. Stop on a bad ref or empty target. Do not manufacture findings from files outside the pinned boundary.

## Pin intent and standards

Identify controlling sources before review: explicit user revision, ticket, PRD, accepted ADRs, acceptance criteria, implementation report, applicable `.agents/rules/` including `risk-based-findings.md`, contributing guidance, package/authority boundaries, non-goals, and local conventions. If no specification exists, say so; do not invent one.

Read [references/review-axes.md](references/review-axes.md) for the two reviewer briefs, smell heuristics, severity scale, and finding format.

## Run the two axes

When acting as Operations on a substantial boundary, dispatch both read-only reviewers concurrently because their analytical scopes are independent:

1. **Standards and architecture reviewer:** inspect only the pinned target against standards and architecture heuristics.
2. **Specification and evidence reviewer:** inspect the same target against approved intent, non-goals, acceptance criteria, tests, and runtime or operational evidence.

For a small review or Management audit, inspect the two axes sequentially in the current context. Do not create review Contractors outside Operations authority. Reviewers may read the same diff but must not edit files, run mutating commands, send role messages, or accept the change.

## Validate and report

Validate every proposed finding against the pinned diff, cited source, and risk-based finding contract. Require a stable ID, confidence, severity, trigger, supported reachability, expected and actual behavior, impact, likelihood, evidence or violated invariant, and a practical regression test. Reject Hypothetical, enforced, outside-scope, duplicate, or merely stylistic concerns as defects. Report under:

1. `## Standards and architecture`
2. `## Specification and evidence`
3. `## Non-blocking follow-ups` — at most three P2/P3 items
4. `## Residual risks and unverified evidence`
5. `## Verdict`

Keep axes separate. Use `APPROVE` when acceptance and required evidence are present and no blocking finding remains. Use `REVISE` only for a credible P0 or a Confirmed/Proven P1. Use `BLOCKED` when the review boundary or controlling intent is unreliable. P2, P3, and Hypothetical concerns do not force revision; an exact acceptance violation may instead qualify as P1. State the worst finding in each axis without collapsing the review into a score.

Perform one initial review and at most one follow-up review. The follow-up inspects only blocking fixes, explicitly selected follow-ups, and direct consequences. Do not reopen a closed finding or restart the full review without new evidence, and stop when required evidence passes with no blocker. If a blocker remains after the follow-up, return `REVISE` and require an explicitly authorized new bounded review task instead of silently beginning a third pass.

An `APPROVE` review is not ticket completion, Consultant acceptance, human milestone approval, release authorization, or permission for the next slice.

## Route the result

Operations validates every finding, issues bounded Contractor revisions only for blockers or explicitly selected follow-ups, integrates, reruns proportional verification, and updates completion evidence. Management receives the verified result for outcome acceptance, intentional Git actions, version decisions, and human-review gates. Active Consultants remain acceptance owners for approved domains. Record unrelated discoveries as separate backlog items; do not expand the reviewed ticket.
