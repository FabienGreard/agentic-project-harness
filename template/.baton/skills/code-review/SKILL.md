---
name: code-review
description: Review committed or work-in-progress changes against repository standards and approved intent. Use for a requested review, Operations integration acceptance, or Management final audit.
---

# Code review

Run a read-only delivery-safety review. Do not edit, stage, commit, publish, route revisions, or mutate state from the review.

## Pin the boundary

Prefer the user’s base; otherwise use the ticket checkpoint or verified PR base. Never assume `main` or a stale remote. Record the verified base, merge base when relevant, `HEAD`, branch, commits, and `git status --short`.

Review `<base>...HEAD` plus relevant staged, unstaged, and untracked work. Record a path manifest and compare it with the Ticket, linked Report, and ownership. Exclude unrelated changes. Return `BLOCKED` for a bad ref, empty target, mixed boundary, or unreliable controlling intent.

Read the explicit user revision, ticket, requirements, accepted decisions, acceptance, non-goals, report, mandatory rules, local standards, and relevant evidence. Do not invent a missing specification.

## Review two independent axes

1. **Standards and architecture:** correctness, security, reliability, repository conventions, ownership, seams, coupling, duplication, failure behavior, and maintainability.
2. **Specification and evidence:** approved behavior, scope, non-goals, acceptance, tests, runtime evidence, documentation, migration, rollback, and completion claims.

For a substantial Operations review, use two independent read-only reviewers on the same pinned manifest. Other authorized modes inspect both axes sequentially. Reviewers never edit or accept work.

Treat tests, fixtures, validators, retry logic, and evidence selection as production code. Confirm:

- coherent increments proved risky assumptions early;
- most cases live in unit tests, real seams in focused integration tests, and only critical journeys in end-to-end tests;
- changed evidence methods reject a preserved known-bad case and accept a known-good case;
- failures are classified before product or method changes;
- attempts and rejected samples remain attributable;
- one runner owned each external resource and artifact root;
- one frozen candidate/source fingerprint, method, artifact, and invalidation boundary govern shared certification; and
- the required final gate passed without retry-until-green or invalid split evidence.

## Findings and verdict

Each finding needs a stable ID, confidence (`Confirmed`, `Proven`, or `Plausible`), severity (`P0`–`P3`), exact location, reachable trigger or violated invariant, expected and actual behavior, impact, likelihood, controlling contract, evidence, smallest correction owner, and regression test.

Do not report praise, style preferences, duplicates, formatter output, outside-boundary issues, or Hypothetical concerns as defects. Security, privacy, irreversible data, money, corruption, and availability claims need evidence proportional to impact.

Report:

1. `## Standards and architecture`
2. `## Specification and evidence`
3. `## Non-blocking follow-ups` — at most three P2/P3 items
4. `## Residual risks and unverified evidence`
5. `## Verdict`

Use `APPROVE` when required evidence passes and no blocker remains, `REVISE` only for a credible P0 or Confirmed/Proven P1, and `BLOCKED` when the boundary or authority is unreliable. Keep the axes separate. Run one initial review and at most one fix-focused follow-up; a remaining blocker needs a newly authorized bounded review.

Approval is not Ticket completion, Consultant acceptance, a Goal or Ticket Clearance, release authority, or permission for the next Goal or Ticket. Operations validates and routes findings; Management owns outcome and publication decisions; Consultants retain domain acceptance.
