#!/usr/bin/env python3
"""Run isolated Baton scenarios or audit a recorded verification trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


REPORT_KEYS = {
    "runId",
    "mode",
    "harnessRevision",
    "verdict",
    "hardGateFailures",
    "categoryScores",
    "totalScore",
    "findings",
    "recommendation",
}
SCORE_LIMITS = {
    "scope": 25,
    "baton": 20,
    "safety": 20,
    "parallelism": 15,
    "advancement": 10,
    "efficiency": 10,
}
REQUIRED_CANDIDATE_KEYS = {
    "classification",
    "should_interrupt_active_work",
    "repository_transitions",
    "task_messages",
    "expected_returns",
    "contractor_plan",
    "direct_operations_work",
    "verification_and_review",
    "next_baton",
    "explicit_non_actions",
    "rationale",
}
GATE_PATTERN = re.compile(r"^HG-[0-9]{2}$")


class ScenarioEvaluationError(AssertionError):
    """A scenario packet, response, report, or trace is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScenarioEvaluationError(message)


def read_json_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScenarioEvaluationError(f"{path}: invalid JSON: {error}") from error
    require(isinstance(value, dict), f"{path}: expected one JSON object")
    return value


def parse_json_object(raw: str, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ScenarioEvaluationError(f"{label}: command did not emit one JSON object: {error}") from error
    require(isinstance(value, dict), f"{label}: expected one JSON object")
    return value


def source_identity(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    head = completed.stdout.strip() if completed.returncode == 0 else "uncommitted"
    digest = hashlib.sha256()
    for relative in (
        ".baton/AGENTS.md",
        ".baton/rules/verification.md",
        ".baton/workflow.md",
        ".baton/skills/code-review/SKILL.md",
        "tests/evals/rubric.md",
    ):
        path = root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"{head}+policy.{digest.hexdigest()[:16]}"


def scenario_paths(root: Path, scenario_id: str) -> Tuple[Path, Path, Path]:
    require(re.fullmatch(r"H-[0-9]{3}", scenario_id) is not None, f"invalid scenario ID: {scenario_id}")
    base = root / "tests/evals/scenarios"
    paths = (
        base / f"inputs/{scenario_id}.md",
        base / f"oracles/{scenario_id}.md",
        base / f"contracts/{scenario_id}.json",
    )
    for path in paths:
        require(path.is_file(), f"scenario resource is missing: {path}")
    return paths


def candidate_context(root: Path) -> Dict[str, str]:
    paths = {
        "agentMap": ".baton/AGENTS.md",
        "verificationRule": ".baton/rules/verification.md",
        "workflow": ".baton/workflow.md",
        "operationsRole": ".baton/roles/operations.md",
        "codeReviewSkill": ".baton/skills/code-review/SKILL.md",
    }
    return {name: (root / relative).read_text(encoding="utf-8") for name, relative in paths.items()}


def nested_value(value: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def assertion_passes(candidate: Mapping[str, Any], assertion: Mapping[str, Any]) -> bool:
    actual = nested_value(candidate, str(assertion.get("path", "")))
    operation = assertion.get("operation")
    expected = assertion.get("expected")
    if operation == "equals":
        return actual == expected
    if operation == "non_empty":
        return isinstance(actual, str) and bool(actual.strip())
    if operation == "min_items":
        return isinstance(actual, list) and isinstance(expected, int) and len(actual) >= expected
    if operation == "contains_all":
        return isinstance(actual, list) and isinstance(expected, list) and all(item in actual for item in expected)
    if operation == "ordered_subset":
        if not isinstance(actual, list) or not isinstance(expected, list):
            return False
        position = -1
        for item in expected:
            try:
                position = actual.index(item, position + 1)
            except ValueError:
                return False
        return True
    raise ScenarioEvaluationError(f"unsupported contract operation: {operation!r}")


def evaluate_contract(candidate: Mapping[str, Any], contract: Mapping[str, Any]) -> List[Dict[str, str]]:
    failures: List[Dict[str, str]] = []
    assertions = contract.get("assertions")
    require(isinstance(assertions, list), "scenario contract assertions must be an array")
    for index, assertion in enumerate(assertions):
        require(isinstance(assertion, dict), f"scenario assertion {index} must be an object")
        gate = assertion.get("hardGate")
        message = assertion.get("message")
        require(isinstance(gate, str) and GATE_PATTERN.fullmatch(gate) is not None, f"invalid assertion hard gate: {gate!r}")
        require(isinstance(message, str) and bool(message), f"assertion {index} needs a message")
        if not assertion_passes(candidate, assertion):
            failures.append({"hardGate": gate, "message": message, "path": str(assertion.get("path", ""))})
    return failures


def validate_candidate(candidate: Mapping[str, Any]) -> None:
    missing = sorted(REQUIRED_CANDIDATE_KEYS - set(candidate))
    require(not missing, f"candidate response is missing fields: {missing}")
    require(candidate["classification"] in {"superseding", "parallel", "queued", "informational", "not_applicable"}, "invalid classification")
    require(isinstance(candidate["should_interrupt_active_work"], bool), "should_interrupt_active_work must be boolean")
    for key in ("repository_transitions", "task_messages", "expected_returns", "explicit_non_actions"):
        require(isinstance(candidate[key], list), f"candidate field must be an array: {key}")
    for key in ("contractor_plan", "direct_operations_work", "verification_and_review", "next_baton"):
        require(isinstance(candidate[key], dict), f"candidate field must be an object: {key}")
    require(isinstance(candidate["rationale"], str) and bool(candidate["rationale"].strip()), "candidate rationale is empty")
    if "policy_evidence" in candidate:
        require(isinstance(candidate["policy_evidence"], dict), "policy_evidence must be an object")


def expected_verdict(report: Mapping[str, Any]) -> str:
    if report["hardGateFailures"]:
        return "FAIL"
    total = float(report["totalScore"])
    floors_met = all(float(report["categoryScores"][key]) >= maximum * 0.6 for key, maximum in SCORE_LIMITS.items())
    if total >= 85 and floors_met:
        return "PASS"
    if total >= 75:
        return "WARN"
    return "FAIL"


def validate_report(report: Mapping[str, Any], *, run_id: str, mode: str, revision: str) -> None:
    require(set(report) == REPORT_KEYS, f"judge report fields differ from schema: {sorted(set(report) ^ REPORT_KEYS)}")
    require(report["runId"] == run_id, "judge report runId does not match the packet")
    require(report["mode"] == mode, "judge report mode does not match the packet")
    require(report["harnessRevision"] == revision, "judge report harnessRevision does not match the packet")
    require(report["verdict"] in {"PASS", "WARN", "FAIL"}, "invalid judge verdict")
    gates = report["hardGateFailures"]
    require(isinstance(gates, list) and len(gates) == len(set(gates)), "hardGateFailures must be a unique array")
    require(all(isinstance(item, str) and GATE_PATTERN.fullmatch(item) is not None for item in gates), "invalid hard gate ID")
    scores = report["categoryScores"]
    require(isinstance(scores, dict) and set(scores) == set(SCORE_LIMITS), "categoryScores differ from the report schema")
    for key, maximum in SCORE_LIMITS.items():
        value = scores[key]
        require(isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= maximum, f"invalid score: {key}")
    total = report["totalScore"]
    require(isinstance(total, (int, float)) and not isinstance(total, bool), "totalScore must be numeric")
    require(abs(float(total) - sum(float(scores[key]) for key in SCORE_LIMITS)) < 0.0001, "totalScore does not equal category scores")
    require(isinstance(report["findings"], list) and all(isinstance(item, dict) for item in report["findings"]), "findings must be objects")
    require(report["recommendation"] in {"accept", "revise", "reject"}, "invalid recommendation")
    require(report["verdict"] == expected_verdict(report), "judge verdict is inconsistent with hard gates or scores")
    if report["verdict"] == "PASS":
        require(report["recommendation"] == "accept", "a PASS report must recommend accept")
    if report["verdict"] == "FAIL":
        require(report["recommendation"] in {"revise", "reject"}, "a FAIL report cannot recommend accept")


def apply_contract_failures(report: Dict[str, Any], failures: Sequence[Mapping[str, str]]) -> Dict[str, Any]:
    if not failures:
        return report
    gates: Set[str] = set(str(item) for item in report["hardGateFailures"])
    findings = list(report["findings"])
    for index, failure in enumerate(failures, start=1):
        gates.add(failure["hardGate"])
        findings.append(
            {
                "id": f"machine-contract-{index}",
                "hardGate": failure["hardGate"],
                "path": failure["path"],
                "message": failure["message"],
                "source": "private-machine-contract",
            }
        )
    report["hardGateFailures"] = sorted(gates)
    report["findings"] = findings
    report["verdict"] = "FAIL"
    report["recommendation"] = "reject"
    return report


def execute_json_command(command: Sequence[str], packet: Mapping[str, Any], *, timeout: int, label: str) -> Tuple[Dict[str, Any], str]:
    require(bool(command), f"{label}: command is empty")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix=f"baton-{label}-") as raw:
        try:
            completed = subprocess.run(
                list(command),
                cwd=raw,
                env=environment,
                input=json.dumps(packet, ensure_ascii=False),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise ScenarioEvaluationError(f"{label}: command exceeded {timeout} seconds") from error
    require(completed.returncode == 0, f"{label}: command exited {completed.returncode}: {completed.stderr.strip()}")
    require(len(completed.stdout.encode("utf-8")) <= 1_000_000, f"{label}: JSON output exceeds 1 MB")
    return parse_json_object(completed.stdout, label), completed.stderr


def run_scenario_once(
    root: Path,
    scenario_id: str,
    *,
    mode: str,
    candidate_command: Sequence[str],
    judge_command: Sequence[str],
    timeout: int,
    artifact_root: Path,
    repetition: int,
) -> Dict[str, Any]:
    input_path, oracle_path, contract_path = scenario_paths(root, scenario_id)
    contract = read_json_object(contract_path)
    require(contract.get("scenarioId") == scenario_id, f"contract scenarioId mismatch: {contract_path}")
    revision = source_identity(root)
    run_id = f"{scenario_id.lower()}-{time.time_ns()}-r{repetition}"
    run_root = artifact_root / run_id
    run_root.mkdir(parents=True, exist_ok=False)

    candidate_packet = {
        "kind": "candidate",
        "runId": run_id,
        "mode": mode,
        "scenarioId": scenario_id,
        "harnessRevision": revision,
        "operatorPrompt": (root / "tests/evals/operator-prompt.md").read_text(encoding="utf-8"),
        "scenarioInput": input_path.read_text(encoding="utf-8"),
        "candidateHarness": candidate_context(root),
    }
    candidate, candidate_stderr = execute_json_command(candidate_command, candidate_packet, timeout=timeout, label="candidate")
    validate_candidate(candidate)
    contract_failures = evaluate_contract(candidate, contract)

    judge_packet = {
        "kind": "judge",
        "runId": run_id,
        "mode": mode,
        "scenarioId": scenario_id,
        "harnessRevision": revision,
        "judgePrompt": (root / "tests/evals/judge-prompt.md").read_text(encoding="utf-8"),
        "rubric": (root / "tests/evals/rubric.md").read_text(encoding="utf-8"),
        "scenarioInput": input_path.read_text(encoding="utf-8"),
        "privateOracle": oracle_path.read_text(encoding="utf-8"),
        "privateMachineContract": contract,
        "candidateOutput": candidate,
    }
    judge, judge_stderr = execute_json_command(judge_command, judge_packet, timeout=timeout, label="judge")
    validate_report(judge, run_id=run_id, mode=mode, revision=revision)
    report = apply_contract_failures(dict(judge), contract_failures)
    validate_report(report, run_id=run_id, mode=mode, revision=revision)

    for name, value in (
        ("candidate-packet.json", candidate_packet),
        ("candidate-output.json", candidate),
        ("judge-packet.json", judge_packet),
        ("report.json", report),
    ):
        (run_root / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_root / "candidate-stderr.txt").write_text(candidate_stderr, encoding="utf-8")
    (run_root / "judge-stderr.txt").write_text(judge_stderr, encoding="utf-8")
    return report


def trace_finding(identifier: str, hard_gate: str, message: str, event_ids: Iterable[str]) -> Dict[str, Any]:
    return {
        "id": identifier,
        "hardGate": hard_gate,
        "message": message,
        "eventIds": list(event_ids),
        "source": "deterministic-live-trace-audit",
    }


def audit_live_trace(trace: Mapping[str, Any]) -> Dict[str, Any]:
    trace_id = trace.get("traceId")
    revision = trace.get("harnessRevision")
    events = trace.get("events")
    require(isinstance(trace_id, str) and bool(trace_id), "live trace needs traceId")
    require(isinstance(revision, str) and bool(revision), "live trace needs harnessRevision")
    require(isinstance(events, list) and all(isinstance(item, dict) for item in events), "live trace events must be objects")

    findings: List[Dict[str, Any]] = []
    certifications: Dict[Tuple[str, str, str, str], List[Tuple[Set[str], str]]] = {}
    for index, event in enumerate(events):
        event_id = event.get("eventId")
        require(isinstance(event_id, str) and bool(event_id), f"trace event {index} needs eventId")
        event_type = event.get("type")
        require(event_type in {"gate", "review", "change"}, f"unsupported trace event type: {event_type!r}")
        if event_type != "gate":
            continue
        duration = event.get("durationSeconds")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
            findings.append(trace_finding(f"trace-duration-{index}", "HG-10", "Gate duration is absent or invalid.", [event_id]))
        layer = event.get("layer")
        purpose = event.get("purpose")
        if layer in {"feature-e2e", "certification-e2e", "broad-suite", "human-review"} and purpose == "iteration" and event.get("lowerLayerAvailable") is True:
            findings.append(
                trace_finding(
                    f"trace-inner-loop-{index}",
                    "HG-13",
                    "A long assembled or human gate was used as the primary iteration loop despite an available lower owning seam.",
                    [event_id],
                )
            )
        if layer == "certification-e2e" and event.get("result") == "pass":
            risks = event.get("coveredRisks")
            require(isinstance(risks, list) and all(isinstance(item, str) for item in risks), f"certification event needs coveredRisks: {event_id}")
            key = (
                str(event.get("candidateFingerprint", "")),
                str(event.get("relevantSourceFingerprint", "")),
                str(event.get("methodIdentity", "")),
                str(event.get("acceptanceIdentity", "")),
            )
            require(all(key), f"certification identity is incomplete: {event_id}")
            risk_set = set(risks)
            overlapping = [prior_id for prior_risks, prior_id in certifications.get(key, []) if prior_risks & risk_set]
            if overlapping:
                findings.append(
                    trace_finding(
                        f"trace-duplicate-certification-{index}",
                        "HG-14",
                        "Equivalent successful certification was repeated for the same frozen candidate with overlapping covered risks.",
                        [*overlapping, event_id],
                    )
                )
            certifications.setdefault(key, []).append((risk_set, event_id))
        if event.get("reusedArtifact") is True:
            required = (
                "artifactIdentity",
                "artifactCandidateFingerprint",
                "candidateFingerprint",
                "artifactRelevantSourceFingerprint",
                "relevantSourceFingerprint",
                "artifactMethodIdentity",
                "methodIdentity",
                "artifactAcceptanceIdentity",
                "acceptanceIdentity",
            )
            missing = [name for name in required if not isinstance(event.get(name), str) or not str(event.get(name)).strip()]
            stale = bool(missing) or event.get("artifactInvalidated") is True
            stale = stale or event.get("artifactCandidateFingerprint") != event.get("candidateFingerprint")
            stale = stale or event.get("artifactRelevantSourceFingerprint") != event.get("relevantSourceFingerprint")
            stale = stale or event.get("artifactMethodIdentity") != event.get("methodIdentity")
            stale = stale or event.get("artifactAcceptanceIdentity") != event.get("acceptanceIdentity")
            artifact_risks = event.get("artifactCoveredRisks")
            current_risks = event.get("coveredRisks")
            if not isinstance(artifact_risks, list) or not all(isinstance(item, str) for item in artifact_risks):
                stale = True
            if not isinstance(current_risks, list) or not all(isinstance(item, str) for item in current_risks):
                stale = True
            if isinstance(artifact_risks, list) and isinstance(current_risks, list):
                stale = stale or not set(current_risks).issubset(set(artifact_risks))
            if stale:
                findings.append(
                    trace_finding(
                        f"trace-stale-evidence-{index}",
                        "HG-14",
                        "Certification evidence was reused with incomplete or invalidated source, method, artifact, or acceptance identity.",
                        [event_id],
                    )
                )

    hard_gates = sorted({str(item["hardGate"]) for item in findings})
    if hard_gates:
        scores = {"scope": 18, "baton": 14, "safety": 14, "parallelism": 11, "advancement": 7, "efficiency": 5}
        verdict = "FAIL"
        recommendation = "reject"
    else:
        scores = dict(SCORE_LIMITS)
        verdict = "PASS"
        recommendation = "accept"
    report: Dict[str, Any] = {
        "runId": trace_id,
        "mode": "live-trace",
        "harnessRevision": revision,
        "verdict": verdict,
        "hardGateFailures": hard_gates,
        "categoryScores": scores,
        "totalScore": sum(scores.values()),
        "findings": findings,
        "recommendation": recommendation,
    }
    validate_report(report, run_id=trace_id, mode="live-trace", revision=revision)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = result.add_subparsers(dest="command", required=True)

    scenario = subparsers.add_parser("scenario", help="run isolated candidate and judge commands")
    scenario.add_argument("--scenario", action="append", dest="scenarios")
    scenario.add_argument("--mode", choices=("scenario-smoke", "scenario-release"), default="scenario-smoke")
    scenario.add_argument("--repetitions", type=int, default=1)
    scenario.add_argument("--candidate-command", required=True)
    scenario.add_argument("--judge-command", required=True)
    scenario.add_argument("--timeout", type=int, default=300)
    scenario.add_argument("--output", type=Path)

    trace = subparsers.add_parser("live-trace", help="audit a recorded verification trace")
    trace.add_argument("--trace", type=Path, required=True)
    trace.add_argument("--output", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    if args.command == "live-trace":
        report = audit_live_trace(read_json_object(args.trace.resolve()))
        if args.output:
            output = args.output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["verdict"] == "PASS" else 1

    require(args.timeout > 0, "timeout must be positive")
    if args.mode == "scenario-release":
        require(args.repetitions >= 3, "scenario-release requires at least three repetitions")
    else:
        require(args.repetitions == 1, "scenario-smoke requires exactly one repetition")
    scenarios = args.scenarios or sorted(path.stem for path in (root / "tests/evals/scenarios/contracts").glob("H-*.json"))
    require(bool(scenarios), "no scenarios selected")
    output = (args.output or root / ".artifacts/harness-eval").resolve()
    output.mkdir(parents=True, exist_ok=True)
    candidate_command = shlex.split(args.candidate_command)
    judge_command = shlex.split(args.judge_command)
    reports = []
    for scenario_id in scenarios:
        for repetition in range(1, args.repetitions + 1):
            reports.append(
                run_scenario_once(
                    root,
                    scenario_id,
                    mode=args.mode,
                    candidate_command=candidate_command,
                    judge_command=judge_command,
                    timeout=args.timeout,
                    artifact_root=output,
                    repetition=repetition,
                )
            )
    payload = {"ok": all(report["verdict"] == "PASS" for report in reports), "reports": reports}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ScenarioEvaluationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
