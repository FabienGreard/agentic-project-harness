# Harness evaluation

Evaluate observable orchestration behavior rather than prompt wording.

## Modes

- **Static distribution contract:** `python3 scripts/harness_eval.py --strict` checks the Baton source/product boundary, exact consumer projections, stable release surface, installed lifecycle, Codex semantics, state, compatibility, and verification inventory without mutation.
- **Deterministic acceptance:** `python3 tests/run_smokes.py` exercises release construction, local/piped/interactive installation, mature adoption, activation, migrations, updates, rollback, target safety, locking, state/team behavior, and evaluator regressions.
- **Scenario smoke:** `python3 scripts/harness_scenario_eval.py scenario ...` runs each selected canonical input once after material harness changes.
- **Scenario release:** the same runner with `--mode scenario-release --repetitions 3` enforces at least three independent runs before accepting a major redesign.
- **Live trace:** `python3 scripts/harness_scenario_eval.py live-trace --trace <trace.json>` deterministically rejects missing duration evidence, assembled E2E as the primary loop, duplicate equivalent certification, and stale certification reuse.

## Isolation

- Synthetic candidates receive the candidate harness, `operator-prompt.md`, and exactly one `scenarios/inputs/` file.
- Candidates must not access `scenarios/oracles/`, judge instructions, previous answers, live credentials, or live project mutation tools.
- A separate disposable evaluator receives the rubric, input, private oracle, exact candidate output, and bounded evidence.
- The candidate process receives no oracle or private machine contract. The judge process receives both; the runner reapplies the private contract after judging.
- Permanent roles never grade themselves.

The runner gives each external command a fresh temporary working directory and JSON on standard input. Each command must emit exactly one JSON object on standard output. A real model adapter must also enforce its own read-only tool and network sandbox; a temporary working directory is process isolation, not a security boundary.

## Execution

1. Run the strict static checker and deterministic acceptance suite.
2. Run isolated candidates against all applicable inputs after material governance changes.
3. Judge hard gates before numeric scores.
4. Aggregate with [report-template.md](report-template.md) and [report-schema.json](report-schema.json).
5. Compare hard failures, category distributions, variance, and specific regressions—not score alone.
6. Return findings to Management; evaluators never mutate active work.

Example isolated invocation:

```sh
python3 scripts/harness_scenario_eval.py scenario \
  --scenario H-015 \
  --scenario H-016 \
  --candidate-command '/absolute/path/to/candidate-adapter' \
  --judge-command '/absolute/path/to/judge-adapter'
```

For release confidence, use `--mode scenario-release --repetitions 3`. Candidate and judge packets, outputs, stderr, and the validated report are retained below the artifact root. The candidate packet is intentionally auditable and must not contain `privateOracle` or `privateMachineContract`.

Live traces conform to [live-trace-schema.json](live-trace-schema.json). Trace every gate duration. Certification events identify the frozen candidate, relevant source, evidence method, acceptance contract, and covered risks; reused artifacts also identify the candidate, source, method, acceptance, and covered-risk identities they were produced against.

Generated artifacts belong under `.artifacts/harness-eval/<run-id>/` and remain local unless an intentional baseline or material regression is selected for versioning.
