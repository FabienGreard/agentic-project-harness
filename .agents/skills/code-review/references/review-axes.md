# Code Review Axes

## Finding contract

Every finding must contain:

- severity (`P0`–`P3`) and a short imperative title;
- exact file and tight line or hunk location;
- concrete evidence from the pinned change;
- the violated rule, ADR, requirement, acceptance criterion, or non-goal;
- a realistic failure or maintenance scenario;
- the smallest correction direction and owning role; and
- whether existing tests or evidence expose the problem.

Do not report praise, summaries, formatter/linter output, hypothetical concerns without a failure mode, or findings outside the reviewed boundary.

## Severity and verdict

- **P0:** immediate catastrophic loss, exploitable security failure, repository corruption, or release-blocking incident.
- **P1:** incorrect required behavior, authority/security violation, major regression, missing acceptance criterion, or evidence that makes integration unsafe.
- **P2:** real but bounded failure case, test gap, lifecycle leak, performance risk, or architecture problem likely to cause defects or repeated changes.
- **P3:** low-risk actionable defect worth fixing in this scope. Omit subjective polish and optional refactors.

The final verdict is `APPROVE`, `REVISE`, or `BLOCKED`, using the meanings defined by the Code Review skill.

## Standards and architecture axis

Check the pinned change against applicable repository rules and accepted architecture: package, authority, protocol, asset, and role boundaries; depth, interface leverage, locality, justified seams/adapters, and the deletion test; behavior tests through caller-facing interfaces; lifecycle cleanup, concurrency ordering, stale-result handling, validation, errors, and resource release; security and malformed input; performance and regression risk; compatibility, migration, rollback, preserved behavior; ticket scope, non-goals, ownership, generated files, and repository safety.

Skip checks deterministically enforced by passing tooling unless the reviewed evidence shows the tool is missing or bypassed.

Possible smell heuristics include Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, and Refused Bequest. Label these as `possible` and require a concrete cost.

## Specification and evidence axis

Check the pinned change and evidence against every approved requirement, invariant, user revision, non-goal, acceptance criterion, test, implementation-report command/result, runtime or operational claim, and applicable specialist evidence. Report missing, partial, wrong, unrequested, speculative, or unproven behavior. Code presence is not proof.

## Reviewer briefs

### Standards reviewer

> Review only the pinned target. Report documented standards or accepted-architecture violations with exact source citations, plus concrete possible smell findings. Distinguish hard requirements from heuristics. Skip tooling-enforced style and anything outside the manifest. Return findings only, under 500 words.

### Specification reviewer

> Review only the pinned target against the supplied ticket, PRD, ADRs, non-goals, acceptance criteria, user revisions, and evidence. Report missing/partial/wrong behavior, scope creep, and unproven required evidence with exact citations. Do not invent project intent. Return findings only, under 500 words.
