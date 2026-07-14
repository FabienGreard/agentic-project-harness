# Triage Findings by Evidence and Ship Risk

Title:
Triage Findings by Evidence and Ship Risk

Type:
Rule

Purpose:
Prevent hypothetical or low-value concerns from blocking delivery while preserving strong detection of material defects.

Scope:
Every review, diagnosis, investigation, verification, completion audit, Consultant acceptance, and Internal Audit finding.

Definition:
A concern becomes a finding only when it names a concrete trigger, a supported reachable path, expected and actual behavior, impact, likelihood, and evidence or a clearly violated invariant. Confidence and severity are independent. The objective is to decide whether the bounded change is safe enough under its approved acceptance and risk criteria, not to maximize defect count.

How to Apply:

1. Pin the reviewed boundary, acceptance criteria, non-goals, required verification, and critical invariants before looking for defects.
2. Give each candidate finding a stable ID and record its trigger, supported path, expected and actual behavior, impact, likelihood, evidence, and practical regression test.
3. Classify confidence as `Confirmed` when reproduced, `Proven` when a clear invariant is violated, `Plausible` when a supported path is credible but not reproduced, or `Hypothetical` when it depends on unsupported inputs, impossible state, or stacked assumptions.
4. Classify severity independently as `P0` for catastrophic security, privacy, money, data-loss, corruption, or availability impact; `P1` for materially incorrect required behavior or unsafe missing evidence; `P2` for a real bounded and recoverable failure; or `P3` for a low-risk actionable defect.
5. Treat a confirmed or proven P0, or a plausible P0 with a credible supported path, as a blocking credible P0. Treat only a confirmed or proven P1 as blocking. P2, P3, and Hypothetical concerns are non-blocking unless an exact acceptance criterion makes the observed behavior a P1 requirement violation.
6. Perform one initial review and at most one follow-up review. Limit the follow-up to blocking fixes, explicitly selected follow-ups, and their direct consequences.
7. Reopen a closed finding only for new evidence: a failing test, production trace, newly reachable supported path, failed acceptance criterion, or concrete implementation contradiction.
8. Stop when acceptance and required verification pass and no blocking finding remains. Record at most three highest-value non-blocking follow-ups without automatically revising the active scope.
9. If the follow-up still contains a blocker, return `REVISE` and end the automatic review loop; another review requires an explicitly authorized new bounded review task rather than an implicit third pass.

Do:

- Separate confidence that a defect exists from the severity it would have.
- Require evidence proportional to impact and use a credible proof for security or irreversible data risks when reproduction would be unsafe or impractical.
- Prefer telemetry or a bounded follow-up over speculative defensive complexity for low-risk uncertainty.
- Preserve stable finding identities and closure reasons across review passes.

Don't:

- Call a concern a bug without reproduction, a violated invariant, or a credible supported path.
- Block or reopen delivery solely for P2, P3, or Hypothetical concerns.
- Restart a full-repository review after a bounded fix.
- Add defensive behavior whose complexity exceeds the demonstrated risk reduction.

Example:

- A reproducible failure in a supported save-and-reload journey is a confirmed finding; a malformed import format the product cannot accept is not a defect in that change.

Validation:
Every reported finding satisfies the evidence contract, only blocking findings cause revision, the follow-up stays bounded, and the review stops once acceptance, verification, and the blocking threshold pass.

References:

- `.agents/skills/code-review/SKILL.md`
- `.agents/skills/code-review/references/review-axes.md`
- `.agents/rules/testing.md`
- `.agents/rules/completion-and-review.md`
- `docs/evals/harness/rubric.md`

Notes:

- Finding severity is independent of ticket priority even though both use P-level labels.
