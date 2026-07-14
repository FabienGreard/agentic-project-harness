# Code Review Axes

## Finding contract

Every finding must contain:

- a stable finding ID and confidence (`Confirmed`, `Proven`, or `Plausible`);
- severity (`P0`–`P3`) and a short imperative title;
- exact file and tight line or hunk location;
- a concrete trigger and evidence that it is reachable in supported use;
- expected versus actual behavior, impact, and likelihood;
- concrete evidence from the pinned change or a clearly violated invariant;
- the violated rule, ADR, requirement, acceptance criterion, or non-goal;
- a realistic failure or maintenance scenario;
- the smallest correction direction and owning role; and
- whether existing tests or evidence expose the problem and a practical regression test.

`Hypothetical` concerns require unsupported inputs, impossible state, or stacked assumptions. Do not report them as defects. Omit them or, when decision-relevant, state them as non-blocking residual uncertainty. Also omit praise, summaries, formatter/linter output, duplicates, and findings outside the reviewed boundary.

No reproduction, violated invariant, or credible supported path means the concern is not a finding. Security, privacy, irreversible data, and incorrect money movement may use a credible proof when reproduction would be unsafe or impractical.

## Severity and verdict

- **P0:** immediate catastrophic loss, exploitable security failure, repository corruption, or release-blocking incident.
- **P1:** incorrect required behavior, authority/security violation, major regression, missing acceptance criterion, or evidence that makes integration unsafe.
- **P2:** real but bounded failure case, test gap, lifecycle leak, performance risk, or architecture problem likely to cause defects or repeated changes.
- **P3:** low-risk actionable defect worth tracking. Omit subjective polish and optional refactors.

A confirmed or proven P0, or a plausible P0 with a credible supported path, blocks. Only a confirmed or proven P1 blocks. P2 and P3 are non-blocking unless an exact acceptance criterion makes the observed behavior a P1 requirement violation. Do not escalate a label merely to force revision.

The final verdict is `APPROVE`, `REVISE`, or `BLOCKED`, using the meanings defined by the Code Review skill. `APPROVE` means the bounded change is safe enough under approved acceptance and risk criteria; it is not merge, release, or publication authority.

## Standards and architecture axis

Check the pinned change against applicable repository rules and accepted architecture: package, authority, protocol, asset, and role boundaries; depth, interface leverage, locality, justified seams/adapters, and the deletion test; behavior tests through caller-facing interfaces; lifecycle cleanup, concurrency ordering, stale-result handling, validation, errors, and resource release; security and malformed input; performance and regression risk; compatibility, migration, rollback, preserved behavior; ticket scope, non-goals, ownership, generated files, and repository safety.

Skip checks deterministically enforced by passing tooling unless the reviewed evidence shows the tool is missing or bypassed.

Possible smell heuristics include Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, and Refused Bequest. Label these as `possible` and require a concrete cost.

## Specification and evidence axis

Check the pinned change and evidence against every approved requirement, invariant, user revision, non-goal, acceptance criterion, test, implementation-report command/result, runtime or operational claim, and applicable Consultant evidence. Report missing, partial, wrong, or unrequested behavior and unproven required evidence. Do not turn unsupported speculation into a finding. Code presence is not proof.

## Reviewer briefs

### Standards reviewer

> Review only the pinned target. Report documented standards or accepted-architecture violations with exact source citations, plus possible smell findings only when they have a concrete reachable cost. Distinguish hard requirements from heuristics. Skip tooling-enforced style and anything outside the manifest. Return findings only, under 500 words.

### Specification reviewer

> Review only the pinned target against the supplied ticket, PRD, ADRs, non-goals, acceptance criteria, user revisions, and evidence. Report missing/partial/wrong behavior, scope creep, and unproven required evidence with exact citations and a supported reachable path. Do not invent project intent or report Hypothetical concerns as defects. Return findings only, under 500 words.
