---
name: code-review
description: "Review a committed or work-in-progress project change against two independent axes: repository standards and architecture, then approved specification and completion evidence. Use when the user invokes $code-review, asks to review a branch, PR, worker return, integrated ticket, dirty worktree, release checkpoint, or changes since a ref; also use before Delivery integration acceptance or a Project Director final Git/release audit."
---

# Code Review

Run a read-only, evidence-backed review. Report findings; do not edit, stage, commit, push, revise workers, or change project state from the review itself.

## Select the authority mode

- **Delivery Lead integration review:** own the review, dispatch two independent read-only reviewers when the boundary is substantial, verify every returned finding, and decide accept, revise, or reject. All worker revision instructions still flow through Delivery.
- **Project Director final audit:** consume Delivery's verified diff, implementation report, and two-axis findings. Perform a bounded direct audit without dispatching workers; route code revisions to Delivery, product or outcome decisions to the Project Director authority, and specialist questions to the owning Specialist Lead.
- **Specialist Lead domain review:** review only the approved specialist domain and return findings or acceptance input to Delivery; do not set overall priority or dispatch a competing worker path.
- **Independent evaluator:** inspect the supplied candidate or disposable harness behavior read-only, report evidence-backed findings, and do not mutate active work or grade itself.
- **Execution-worker self-check:** review only the supplied scope, make no acceptance decision outside that role's authority, and return findings to the owning Delivery Lead or user.

## Pin the exact review boundary

1. Prefer a user-supplied base. Otherwise use the ticket's recorded readiness/checkpoint commit or verified PR base. Ask only when no unambiguous base exists; never assume `main` or a stale remote ref.
2. Verify the base with `git rev-parse --verify`, record merge base when appropriate, current `HEAD`, branch, commit list, and `git status --short`.
3. For committed work, review `<base>...HEAD`. For WIP or an integrated dirty tree, include committed, staged, unstaged, and relevant untracked files. Record exact commands and path manifest so neither axis reviews a different change.
4. Compare the manifest with active work, ticket/report changed-file boundary, and current ownership. Exclude unrelated user or agent changes. If the target cannot be isolated safely, return `BLOCKED` and name the overlap instead of reviewing a mixed diff.
5. Stop on a bad ref or empty target. Do not manufacture findings from files outside the pinned boundary.

## Pin intent and standards

Identify controlling sources before review: explicit user revision, ticket, PRD, accepted ADRs, acceptance criteria, implementation report, applicable `.agents/rules/`, contributing guidance, package/authority boundaries, non-goals, and local conventions. If no specification exists, say so; do not invent one.

Read [references/review-axes.md](references/review-axes.md) for the two reviewer briefs, smell heuristics, severity scale, and finding format.

## Run the two axes

When acting as Delivery on a substantial boundary, dispatch both read-only reviewers concurrently because their analytical scopes are independent:

1. **Standards and architecture reviewer:** inspect only the pinned target against standards and architecture heuristics.
2. **Specification and evidence reviewer:** inspect the same target against approved intent, non-goals, acceptance criteria, tests, and runtime or operational evidence.

For a small review or Project Director audit, inspect the two axes sequentially in the current context. Do not create review workers outside Delivery authority. Reviewers may read the same diff but must not edit files, run mutating commands, send role messages, or accept the change.

## Validate and report

Reproduce every proposed finding against the pinned diff and cited source. Reject speculative, enforced, outside-scope, or merely stylistic findings. Report actionable findings first under:

1. `## Standards and architecture`
2. `## Specification and evidence`
3. `## Residual risks and unverified evidence`
4. `## Verdict`

Keep axes separate. Use `APPROVE` only when no actionable finding remains and required evidence is present, `REVISE` when a bounded correction is required, and `BLOCKED` when the review boundary or controlling intent is unreliable. State the worst finding in each axis without collapsing the review into a score.

An `APPROVE` review is not ticket completion, specialist acceptance, human milestone approval, release authorization, or permission for the next slice.

## Route the result

Delivery reviews every finding, issues bounded worker revisions, integrates, reruns proportional verification, and updates completion evidence. The Project Director receives the verified result for outcome acceptance, intentional Git actions, version decisions, and human-review gates. Specialist Leads remain acceptance owners for approved specialist domains. Record unrelated discoveries as separate backlog items; do not expand the reviewed ticket.
