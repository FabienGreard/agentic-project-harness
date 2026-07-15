# Contributing

Thank you for helping improve Baton.

## Good contributions

- Reproducible orchestration failure scenarios.
- Clearer role, readiness, handoff, or evaluation contracts.
- Cross-domain examples that preserve the core authority model.
- Static checks that remain dependency-light and read-only.
- Accessibility, documentation, and onboarding improvements.

Avoid weakening a safety or human-review gate merely to make a scenario pass. Prefer the smallest general rule that explains a demonstrated failure.

## Workflow

1. Open an issue for substantial behavior changes or new authority models.
2. Fork the repository and create a focused branch.
3. Keep example/domain content generic and free of private data.
4. Add or update a scenario whenever behavior changes.
5. Run:

   ```sh
   python3 tools/harness_eval.py --strict
   python3 tests/run_smokes.py
   ```

6. Open a pull request using the repository template.

## Pull-request expectations

- Explain the problem and why it is generalizable.
- Name the rules, scenarios, and examples affected.
- Include verification evidence.
- Identify compatibility or migration implications for existing Baton installations.
- Keep unrelated cleanup outside the pull request.

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
