# Verification

Develop in the smallest coherent, reviewable increment that proves one behavior, assumption, interface, or risk. Before editing, name the expected result, changed boundary, cheapest trustworthy failure signal, dependency order, and stop or review condition. A feedback budget is diagnostic, not an arbitrary pass/fail ceiling. Resolve uncertain, irreversible, or high-leverage seams before broad implementation.

Use the lowest layer that can truthfully own a claim:

1. direct inspection or static checks;
2. focused unit tests for rules, state transitions, edge cases, and failures;
3. focused integration or contract tests for real seams;
4. a few critical end-to-end journeys;
5. broader regression, operational, experiential, or human review when required.

Apply the Ticket's resolved Readiness Protocol from `workflow.md` plus `requiredVerification`. A Clearance never substitutes for verification.

Keep a broad unit base, fewer integration tests, and the fewest end-to-end tests without enforcing numeric ratios. Keep a shallow assembled-runtime smoke path. Use feature end-to-end tests for changed journeys, one certification run for a frozen integrated candidate, and soak or performance tests only for an approved risk. Use real wall time only when elapsed behavior matters; controlled clocks may advance production rules but must not fabricate domain outcomes.

For deterministic changes, establish a public seam and independent expected result, observe a meaningful failure, make the smallest passing change, then refactor. Do not test private implementation, widen production interfaces for tests, duplicate the implementation in expected results, mock deterministic repository-owned modules, or repeat the same behavior matrix at every layer.

Before costly or irreversible verification, pin the candidate/source fingerprint, acceptance signal, method, artifact identity, final gate, invalidation boundary, and retry budget. Pass cheap checks and a topology preflight first; give one runner exclusive ownership of ports, external resources, and artifact roots. Preserve every attempt and rejected sample.

Classify each failure before editing as a product defect, test/evidence defect, environment/infrastructure defect, or acceptance/decision gap. A method change must still reject a preserved known-bad case and accept a known-good case without weakening the threshold. Use at most one unchanged replay for a credible transient unless another budget was approved. Repeated failure requires a fix or blocker, never retry-until-green. A quarantined required gate is not a pass. Split green checks do not replace an explicitly required ordered final gate.

Review findings must name a trigger, supported path or violated invariant, expected and actual behavior, impact, likelihood, evidence, and a practical regression test. Confidence is `Confirmed`, `Proven`, `Plausible`, or `Hypothetical`; severity is independent: `P0` catastrophic, `P1` materially wrong or unsafe, `P2` bounded and recoverable, `P3` low risk. A credible P0 or Confirmed/Proven P1 blocks. Other findings do not expand scope automatically. Run one initial and at most one bounded follow-up review; retain at most three valuable non-blocking follow-ups.

Material Baton changes also receive disposable Internal Audit. Pin the candidate and evaluation boundary, isolate candidate from oracle, run proportional static and scenario checks, and record inputs, commands, findings, limitations, and disposition. Internal Audit does not grade its own work, perform product QA, fix findings, mutate state, or publish. Operations alone routes any revision.
