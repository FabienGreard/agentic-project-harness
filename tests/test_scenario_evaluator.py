#!/usr/bin/env python3
"""Executable scenario and verification-trace evaluator regressions."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import harness_scenario_eval  # noqa: E402


RESPONDER = r'''#!/usr/bin/env python3
import json
import sys

packet = json.load(sys.stdin)
variant = sys.argv[1]
if packet["kind"] == "candidate":
    scenario = packet["scenarioId"]
    evidence = {
        "failure_classifications": ["evidence-method", "timing-method"],
        "retry_policy": "bounded-classify-first",
        "known_bad_good_proof": True,
        "failed_attempts_preserved": True,
        "increment_boundaries": ["domain", "seam", "assembled"],
        "feedback_ladder": ["unit", "contract", "integration", "smoke", "end-to-end"],
        "test_portfolio": {
            "unit": "broad-base",
            "integration": "fewer-focused",
            "end_to_end": "fewest-critical"
        },
        "primary_debugging_loop": "focused",
        "intermediate_review": True,
        "certification_runs": 1,
        "reuse_prior_certification": False,
        "invalidation_reason": "Relevant source and evidence-method identities changed.",
        "controlled_advancement": "production-rules-only",
        "smoke_preserved": True,
        "duration_policy": "diagnostic-no-arbitrary-ceiling",
        "gate_durations_recorded": True,
        "final_gate_preserved": True
    }
    if variant == "bad-h015" and scenario == "H-015":
        evidence["primary_debugging_loop"] = "end-to-end"
        evidence["test_portfolio"]["end_to_end"] = "broad-base"
    if variant == "bad-h016" and scenario == "H-016":
        evidence["certification_runs"] = 3
        evidence["reuse_prior_certification"] = True
        evidence["invalidation_reason"] = ""
    print(json.dumps({
        "classification": "not_applicable",
        "should_interrupt_active_work": False,
        "repository_transitions": [],
        "task_messages": [],
        "expected_returns": [],
        "contractor_plan": {},
        "direct_operations_work": {},
        "verification_and_review": {},
        "next_baton": {},
        "explicit_non_actions": [],
        "rationale": "Use the cheapest owning seam, then preserve final certification.",
        "policy_evidence": evidence
    }))
else:
    print(json.dumps({
        "runId": packet["runId"],
        "mode": packet["mode"],
        "harnessRevision": packet["harnessRevision"],
        "verdict": "PASS",
        "hardGateFailures": [],
        "categoryScores": {
            "scope": 25,
            "baton": 20,
            "safety": 20,
            "parallelism": 15,
            "advancement": 10,
            "efficiency": 10
        },
        "totalScore": 100,
        "findings": [],
        "recommendation": "accept"
    }))
'''


def safe_gate(event_id: str, **overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "eventId": event_id,
        "type": "gate",
        "layer": "unit",
        "purpose": "iteration",
        "lowerLayerAvailable": False,
        "durationSeconds": 0.2,
        "result": "pass",
    }
    event.update(overrides)
    return event


def certification(event_id: str, **overrides: object) -> dict[str, object]:
    event = safe_gate(
        event_id,
        layer="certification-e2e",
        purpose="certification",
        durationSeconds=30,
        candidateFingerprint="candidate-a",
        relevantSourceFingerprint="source-a",
        methodIdentity="method-a",
        acceptanceIdentity="acceptance-a",
        coveredRisks=["journey", "lifecycle"],
    )
    event.update(overrides)
    return event


class ScenarioEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="baton-scenario-test-")
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Path(self.temporary.name)
        self.responder = self.fixture / "responder.py"
        self.responder.write_text(textwrap.dedent(RESPONDER), encoding="utf-8")

    def run_scenario(self, scenario: str, variant: str = "good") -> tuple[dict[str, object], Path]:
        artifacts = self.fixture / f"artifacts-{scenario}-{variant}"
        artifacts.mkdir()
        report = harness_scenario_eval.run_scenario_once(
            ROOT,
            scenario,
            mode="scenario-smoke",
            candidate_command=[sys.executable, str(self.responder), variant],
            judge_command=[sys.executable, str(self.responder), variant],
            timeout=15,
            artifact_root=artifacts,
            repetition=1,
        )
        run_root = next(artifacts.iterdir())
        return report, run_root

    def test_private_contract_scenarios_pass_with_matching_policy_evidence(self) -> None:
        for scenario in ("H-014", "H-015", "H-016"):
            with self.subTest(scenario=scenario):
                report, run_root = self.run_scenario(scenario)
                self.assertEqual(report["verdict"], "PASS")
                candidate_packet = json.loads((run_root / "candidate-packet.json").read_text(encoding="utf-8"))
                judge_packet = json.loads((run_root / "judge-packet.json").read_text(encoding="utf-8"))
                self.assertNotIn("privateOracle", candidate_packet)
                self.assertNotIn("privateMachineContract", candidate_packet)
                self.assertIn("privateOracle", judge_packet)
                self.assertIn("privateMachineContract", judge_packet)

    def test_private_contract_overrides_a_permissive_judge(self) -> None:
        h015, _ = self.run_scenario("H-015", "bad-h015")
        self.assertEqual(h015["verdict"], "FAIL")
        self.assertIn("HG-13", h015["hardGateFailures"])

        h016, _ = self.run_scenario("H-016", "bad-h016")
        self.assertEqual(h016["verdict"], "FAIL")
        self.assertIn("HG-14", h016["hardGateFailures"])

    def test_live_trace_accepts_a_layered_single_certification_run(self) -> None:
        report = harness_scenario_eval.audit_live_trace(
            {
                "traceId": "trace-safe",
                "harnessRevision": "revision-a",
                "events": [safe_gate("unit"), safe_gate("integration", layer="integration"), certification("certification")],
            }
        )
        self.assertEqual(report["verdict"], "PASS")

    def test_live_trace_accepts_valid_matching_artifact_reuse(self) -> None:
        report = harness_scenario_eval.audit_live_trace(
            {
                "traceId": "trace-valid-reuse",
                "harnessRevision": "revision-a",
                "events": [
                    safe_gate(
                        "reuse",
                        layer="integration",
                        purpose="checkpoint",
                        candidateFingerprint="candidate-a",
                        relevantSourceFingerprint="source-a",
                        methodIdentity="method-a",
                        acceptanceIdentity="acceptance-a",
                        coveredRisks=["journey"],
                        reusedArtifact=True,
                        artifactIdentity="artifact-a",
                        artifactCandidateFingerprint="candidate-a",
                        artifactRelevantSourceFingerprint="source-a",
                        artifactMethodIdentity="method-a",
                        artifactAcceptanceIdentity="acceptance-a",
                        artifactCoveredRisks=["journey", "lifecycle"],
                        artifactInvalidated=False,
                    )
                ],
            }
        )
        self.assertEqual(report["verdict"], "PASS")

    def test_live_trace_rejects_expensive_primary_iteration(self) -> None:
        report = harness_scenario_eval.audit_live_trace(
            {
                "traceId": "trace-inner-loop",
                "harnessRevision": "revision-a",
                "events": [
                    safe_gate(
                        "e2e-loop",
                        layer="feature-e2e",
                        purpose="iteration",
                        lowerLayerAvailable=True,
                        durationSeconds=40,
                    )
                ],
            }
        )
        self.assertEqual(report["verdict"], "FAIL")
        self.assertIn("HG-13", report["hardGateFailures"])

    def test_live_trace_rejects_duplicate_or_stale_certification(self) -> None:
        duplicate = harness_scenario_eval.audit_live_trace(
            {
                "traceId": "trace-duplicate",
                "harnessRevision": "revision-a",
                "events": [certification("cert-a"), certification("cert-b")],
            }
        )
        self.assertIn("HG-14", duplicate["hardGateFailures"])

        stale = harness_scenario_eval.audit_live_trace(
            {
                "traceId": "trace-stale",
                "harnessRevision": "revision-a",
                "events": [
                    certification(
                        "reused",
                        reusedArtifact=True,
                        artifactIdentity="artifact-a",
                        artifactCandidateFingerprint="candidate-a",
                        artifactRelevantSourceFingerprint="source-old",
                        artifactMethodIdentity="method-a",
                        artifactAcceptanceIdentity="acceptance-a",
                        artifactCoveredRisks=["journey", "lifecycle"],
                        artifactInvalidated=False,
                    )
                ],
            }
        )
        self.assertIn("HG-14", stale["hardGateFailures"])

    def test_live_trace_requires_gate_duration(self) -> None:
        event = safe_gate("missing-duration")
        del event["durationSeconds"]
        report = harness_scenario_eval.audit_live_trace(
            {"traceId": "trace-duration", "harnessRevision": "revision-a", "events": [event]}
        )
        self.assertEqual(report["verdict"], "FAIL")
        self.assertIn("HG-10", report["hardGateFailures"])


if __name__ == "__main__":
    unittest.main()
