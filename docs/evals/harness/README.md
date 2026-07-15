# Harness evaluation

Evaluate observable orchestration behavior rather than prompt wording.

## Modes

- **Static distribution contract:** `python3 tools/harness_eval.py --strict` checks the Baton source/product boundary, exact consumer projections, stable release surface, installed lifecycle, Codex semantics, state, compatibility, and verification inventory without mutation.
- **Deterministic acceptance:** `python3 tests/run_smokes.py` exercises release construction, local/piped/interactive installation, mature adoption, activation, migrations, updates, rollback, target safety, locking, state/team behavior, and evaluator regressions.
- **Scenario smoke:** run each canonical input once after material harness changes.
- **Scenario release:** run each scenario at least three independent times before accepting a major redesign.
- **Live trace:** a disposable evaluator compares real task events with repository and publication evidence at meaningful checkpoints or after incidents.

## Isolation

- Synthetic candidates receive the candidate harness, `operator-prompt.md`, and exactly one `scenarios/inputs/` file.
- Candidates must not access `scenarios/oracles/`, judge instructions, previous answers, live credentials, or live project mutation tools.
- A separate disposable evaluator receives the rubric, input, private oracle, exact candidate output, and bounded evidence.
- Permanent roles never grade themselves.

## Execution

1. Run the strict static checker and deterministic acceptance suite.
2. Run isolated candidates against all applicable inputs after material governance changes.
3. Judge hard gates before numeric scores.
4. Aggregate with [report-template.md](report-template.md) and [report-schema.json](report-schema.json).
5. Compare hard failures, category distributions, variance, and specific regressions—not score alone.
6. Return findings to Management; evaluators never mutate active work.

Generated artifacts belong under `.artifacts/harness-eval/<run-id>/` and remain local unless an intentional baseline or material regression is selected for versioning.
