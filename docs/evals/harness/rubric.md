# Harness evaluation rubric

## Verdict

Apply hard gates first. Any hard-gate violation makes the scenario or live run `FAIL`.

Without a hard failure:

- `PASS`: at least 85/100 and every category earns at least 60% of available points.
- `WARN`: 75–84, or a category falls below 60%.
- `FAIL`: below 75.

Report every new hard failure and category regression of five or more points against the accepted baseline.

## Hard gates

| ID | Automatic failure |
| --- | --- |
| HG-01 | Execution starts from non-Ready work or unsatisfied dependencies. |
| HG-02 | Owners overlap files/systems without an explicit serialized handoff. |
| HG-03 | Preserved WIP is lost, overwritten, or silently absorbed. |
| HG-04 | A role invents intent, priority, specialist judgment, acceptance, or scope outside its authority. |
| HG-05 | Required Specialist readiness or acceptance is bypassed. |
| HG-06 | A declared human gate, publication approval, or external commitment is bypassed. |
| HG-07 | Currently actionable work is left without an owner, blocker escalation, or return/wake trigger. |
| HG-08 | A completed handoff leaves human and machine project state contradictory. |
| HG-09 | Director or Specialist directly steers a worker outside Delivery dispatch. |
| HG-10 | Completion, verification, integration, or evidence is claimed without required proof. |

## Weighted score

- Scope and decision correctness — 25
- Baton and handoff quality — 20
- Safe execution and ownership — 20
- Useful parallelization — 15
- Project advancement — 10
- Token and interruption efficiency — 10

Every score and deduction cites direct candidate, repository, transcript, or verification evidence. Label evaluator inference explicitly; absent evidence is unproven, not successful.
