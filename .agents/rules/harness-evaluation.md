# Evaluate Harness Changes Independently

Title:
Evaluate Harness Changes Independently

Type:
Rule

Purpose:
Provide impartial evidence that governance changes improve orchestration behavior and do not merely satisfy their authors.

Scope:
Material harness, role, workflow, installer, evaluator, or governance changes.

Definition:
An independent disposable evaluator assesses the candidate against documented scenarios and rubric. Permanent roles do not grade themselves, and evaluator findings do not directly mutate active work.

How to Apply:

1. Identify the exact candidate diff and evaluation boundary.
2. Run static checks and scenario smoke proportionally.
3. Use a disposable environment and independent evaluator.
4. Record inputs, commands, findings, limitations, and disposition.
5. Route actionable findings to Delivery as bounded revisions.

Do:

- Compare behavior against explicit oracles and acceptance.
- Repeat comparisons when a major redesign could affect conclusions.
- Preserve the evaluated candidate while recording its identity.

Don't:

- Let the author certify its own harness change.
- Mutate active work from evaluator output without Delivery routing.
- Treat one happy-path scenario as sufficient evidence.

Example:

- A disposable evaluator runs the documented handoff scenarios against a copied candidate and returns findings for Delivery to triage.

Validation:
The evaluation is independent, reproducible, tied to an exact candidate, and its findings are recorded without bypassing authority boundaries.

References:

- `docs/evals/harness/README.md`
- `docs/roles/harness-evaluator.md`
- `docs/workflow.md`

Notes:

- Evaluation evidence supports a decision; it does not itself publish or release anything.
