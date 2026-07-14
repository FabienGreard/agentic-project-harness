#!/usr/bin/env python3
"""Dependency-free smoke coverage for the canonical state writer."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(sys.argv[1]).resolve()
TOOL = SOURCE_ROOT / "tools/harness_state.py"


def copy_fixture() -> Path:
    target = Path(tempfile.mkdtemp(prefix="harness-state-smoke-"))
    shutil.copytree(SOURCE_ROOT / "docs", target / "docs")
    shutil.copytree(SOURCE_ROOT / "tools", target / "tools")
    return target


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, root / "tools/harness_state.py", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def operation(records: dict) -> dict:
    return {
        "schemaVersion": 1,
        "operation": "replace-records",
        "records": records,
    }


def load_writer(root: Path):
    spec = importlib.util.spec_from_file_location("fixture_harness_state", root / "tools/harness_state.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root / "tools"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    module.ROOT = root
    module.STATE_DIR = root / "docs/state"
    module.SCHEMA_DIR = root / "docs/schemas"
    module.DASHBOARD = root / "docs/index.html"
    return module


fixture = copy_fixture()
state_home = fixture.parent / f"{fixture.name}-external-state"
previous_state_home = os.environ.get("XDG_STATE_HOME")
os.environ["XDG_STATE_HOME"] = str(state_home)
try:
    initial = run(fixture, "check", "--json")
    assert initial.returncode == 0, initial.stdout + initial.stderr
    assert output(initial)["ok"] is True

    help_result = run(fixture, "--help")
    assert help_result.returncode == 0
    assert "check" in help_result.stdout and "apply" in help_result.stdout
    invalid_command = run(fixture, "unknown", "--json")
    assert invalid_command.returncode != 0
    assert invalid_command.stdout == ""

    project = json.loads((fixture / "docs/state/project.json").read_text())
    goals = json.loads((fixture / "docs/state/goals.json").read_text())
    tickets = json.loads((fixture / "docs/state/tickets.json").read_text())
    ownership = json.loads((fixture / "docs/state/ownership.json").read_text())
    reviews = json.loads((fixture / "docs/state/reviews.json").read_text())
    team = json.loads((fixture / "docs/state/team.json").read_text())
    readiness_packet = fixture / "docs/review-packets/DEMO-1-READINESS.md"
    readiness_packet.write_text(
        "# DEMO-1 Readiness approval\n\nApproved by the human owner.\n",
        encoding="utf-8",
    )
    acceptance_packet = fixture / "docs/review-packets/DEMO-1-ACCEPTANCE.md"
    acceptance_packet.write_text(
        "# DEMO-1 Acceptance approval\n\nApproved by the human owner.\n",
        encoding="utf-8",
    )
    boolean_operation = operation({"project": project})
    boolean_operation["schemaVersion"] = True
    boolean_operation_path = fixture / "boolean-operation-version.json"
    boolean_operation_path.write_text(json.dumps(boolean_operation))
    rejected_boolean_operation = run(
        fixture, "apply", str(boolean_operation_path), "--json"
    )
    assert rejected_boolean_operation.returncode == 1
    assert any(
        "schemaVersion" in error
        for error in output(rejected_boolean_operation)["errors"]
    )
    boolean_project = json.loads(json.dumps(project))
    boolean_project["schemaVersion"] = True
    boolean_project_path = fixture / "boolean-record-version.json"
    boolean_project_path.write_text(
        json.dumps(operation({"project": boolean_project}))
    )
    rejected_boolean_project = run(
        fixture, "apply", str(boolean_project_path), "--json"
    )
    assert rejected_boolean_project.returncode == 1
    assert any(
        "schemaVersion" in error
        for error in output(rejected_boolean_project)["errors"]
    )
    (fixture / ".agent-harness.json").write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "managedFiles": {
                    "docs/index.html": {
                        "ownership": "generated-config",
                        "baselineSha256": hashlib.sha256(
                            (fixture / "docs/index.html").read_bytes()
                        ).hexdigest(),
                    }
                },
            },
            indent=2,
        )
        + "\n"
    )
    project["project"]["outcome"] = "Make project progress immediately understandable"
    project["project"]["currentGoal"] = "GOAL-NOW"
    goals["goals"] = [
        {
            "id": "GOAL-DONE", "title": "Establish the project foundation",
            "status": "Done", "priority": "P1", "owner": "Management",
            "objective": "Create a verified foundation for delivery", "dependencies": [],
            "context": "The delivery workflow needs an agreed foundation",
            "blockers": [], "decisionPaths": [],
            "evidencePaths": ["docs/implementation-reports/README.md"],
            "resultSummary": "The project foundation was verified and accepted",
            "plannedStart": "2026-06-29", "plannedEnd": "2026-07-10",
            "completedAt": "2026-07-10",
        },
        {
            "id": "GOAL-NOW", "title": "Ship a reviewable first release",
            "status": "Active", "priority": "P1", "owner": "Operations",
            "objective": "Give the project one safe path to a verified release",
            "context": "Operators need one reviewable path from intent to evidence",
            "dependencies": ["GOAL-DONE"], "blockers": [], "decisionPaths": [], "evidencePaths": [],
            "plannedStart": "2026-07-11", "plannedEnd": "2026-07-24",
            "narrativePath": "docs/prds/README.md",
        },
        {
            "id": "GOAL-NEXT", "title": "Improve the next operator workflow",
            "status": "Needs Definition", "priority": "P2", "owner": "Management",
            "objective": "Define the next observable improvement", "dependencies": ["GOAL-NOW"],
            "context": "The next workflow should wait until the first release is verified",
            "blockers": ["Current goal must complete"], "decisionPaths": [], "evidencePaths": [],
            "plannedStart": "2026-07-25", "plannedEnd": "2026-08-07",
            "blockerOwner": "Operations", "resumeCondition": "GOAL-NOW is Done",
        },
    ]
    tickets["tickets"] = [{
        "id": "DEMO-1", "title": "Demonstrate structured state", "status": "In Progress",
        "priority": "P1", "owner": "Operations", "goal": "GOAL-NOW", "dependencies": [],
        "objective": "Prove the canonical writer contract",
        "scope": ["Canonical state fixture"], "nonGoals": ["Production publication"],
        "affectedSystems": ["docs/state"], "acceptanceCriteria": ["The fixture validates"],
        "requiredVerification": ["Run the smoke"], "expectedEvidence": ["PASS output"],
        "risks": ["Fixture drift"], "requiredConsultantIds": [],
        "assurance": {
            "testRigor": "Standard", "humanReviewStages": [], "overrideReason": ""
        },
        "blockers": [], "openDecisions": [],
    }]
    ownership["ownership"] = [{
        "ticket": "DEMO-1", "owner": "Contractor A", "scopes": ["docs/example.md"],
        "status": "Building", "returnDestination": "Operations",
    }]
    reviews["reviews"] = [{"id": "DEMO-1-human", "ticket": "DEMO-1", "stage": "Acceptance", "status": "Pending", "path": "docs/reviews/DEMO-1.md"}]
    operation_path = fixture / "operation.json"
    operation_path.write_text(json.dumps(operation({
        "project": project, "goals": goals, "tickets": tickets,
        "ownership": ownership, "reviews": reviews,
    }), indent=2) + "\n")
    applied = run(fixture, "apply", str(operation_path), "--json")
    assert applied.returncode == 0, applied.stderr
    assert output(applied)["changed"] == ["project", "goals", "tickets", "ownership", "reviews"]
    dashboard = (fixture / "docs/index.html").read_text()
    for expected in (
        "Goals are scheduled around today", "Goal details", "Goal brief",
        "Related tasks", "Every task across the project", "Search tasks",
        "plannedStart", "plannedEnd", "Ship a reviewable first release",
        "Establish the project foundation", "Improve the next operator workflow",
        "DEMO-1", "mock=1", "Example project", "Illustrative data only",
        "Launch online booking to 20 pilot patients",
        "Default assurance", "Test rigor", "humanReviewStages",
        "#ticket-rows{height:min(420px,48vh)",
        ".gantt-goal-button{background:rgba(7,19,28,.94)",
        ".gantt-bar-done,.gantt-bar-current,.gantt-bar-upcoming{background:var(--phosphor)",
        ".gantt-bar-done:hover,.gantt-bar-current:hover,.gantt-bar-upcoming:hover{background:#fff58a",
        "@media(min-width:761px){.gantt-grid{grid-template-columns:260px var(--timeline-width)}",
        ".gantt-goal-button strong{grid-column:1/-1;line-height:1.25;overflow:visible;text-overflow:clip;white-space:normal}",
        ".gantt-goal-button .status-pill{grid-column:2;grid-row:2}",
        "@media(max-width:1100px){.workforce-distribution{align-content:start;grid-template-columns:1fr}",
        ".workforce-legend{margin-top:.8rem;min-width:0;width:100%}",
        ".workforce-legend-entry,.workforce-legend-entry span{min-width:0}",
    ):
        assert expected in dashboard, expected
    assert "@media(max-width:760px){.site-header" in dashboard
    for expected_mobile_timeline_rule in (
        ".gantt-viewport{-webkit-overflow-scrolling:touch;max-height:none;overflow-x:auto;overflow-y:clip",
        ".gantt-grid{grid-template-columns:var(--timeline-width);width:var(--timeline-width)}",
        ".gantt-label,.gantt-track{grid-column:1}",
        ".gantt-label,.gantt-label:hover{background:transparent;border:0;box-shadow:none}",
        ".gantt-label{height:62px;left:0;overflow:visible;padding:0;pointer-events:none;position:sticky;width:min(calc(100vw - 2rem),420px)",
        ".gantt-track{height:108px;margin-top:-62px;scroll-snap-align:start}",
        ".gantt-bar{height:36px;min-width:72px;top:66px}",
    ):
        assert expected_mobile_timeline_rule in dashboard, expected_mobile_timeline_rule
    for forbidden_mobile_timeline_override in (
        ".gantt-corner,.gantt-dates,.gantt-track{display:none}",
        ".gantt-viewport{background:transparent;border:0;box-shadow:none;max-height:none;overflow:visible}",
        ".gantt-grid{grid-template-columns:150px var(--timeline-width)}",
    ):
        assert forbidden_mobile_timeline_override not in dashboard, (
            forbidden_mobile_timeline_override
        )
    installed_metadata = json.loads(
        (fixture / ".agent-harness.json").read_text(encoding="utf-8")
    )
    assert installed_metadata["managedFiles"]["docs/index.html"][
        "baselineSha256"
    ] == hashlib.sha256((fixture / "docs/index.html").read_bytes()).hexdigest()

    team_before = (fixture / "docs/state/team.json").read_bytes()
    dashboard_before_team_attempt = (fixture / "docs/index.html").read_bytes()
    forbidden_team = json.loads(json.dumps(team))
    forbidden_team["consultants"][0]["status"] = "inactive"
    forbidden_team_path = fixture / "forbidden-team-operation.json"
    forbidden_team_path.write_text(json.dumps(operation({"team": forbidden_team})))
    rejected_team = run(fixture, "apply", str(forbidden_team_path), "--json")
    assert rejected_team.returncode == 1
    assert any(
        "team changes require $hire-consultant or $fire-consultant" in error
        for error in output(rejected_team)["errors"]
    )
    assert (fixture / "docs/state/team.json").read_bytes() == team_before
    assert (fixture / "docs/index.html").read_bytes() == dashboard_before_team_attempt

    unreasoned_override = json.loads(json.dumps(tickets))
    unreasoned_override["tickets"][0]["assurance"]["testRigor"] = "Lean"
    unreasoned_path = fixture / "unreasoned-assurance-override.json"
    unreasoned_path.write_text(json.dumps(operation({"tickets": unreasoned_override})))
    rejected_unreasoned = run(fixture, "apply", str(unreasoned_path), "--json")
    assert rejected_unreasoned.returncode == 1
    assert any(
        "human-authorized overrideReason" in error
        for error in output(rejected_unreasoned)["errors"]
    )

    human_readiness_tickets = json.loads(json.dumps(tickets))
    human_readiness_tickets["tickets"][0]["assurance"] = {
        "testRigor": "Standard",
        "humanReviewStages": ["Readiness"],
        "overrideReason": "User requires review before execution",
    }
    missing_human_readiness_path = fixture / "missing-human-readiness.json"
    missing_human_readiness_path.write_text(
        json.dumps(operation({"tickets": human_readiness_tickets}))
    )
    missing_human_readiness = run(
        fixture, "apply", str(missing_human_readiness_path), "--json"
    )
    assert missing_human_readiness.returncode == 1
    assert any(
        "lacks approved human review for: Readiness" in error
        for error in output(missing_human_readiness)["errors"]
    )

    nonexistent_human_readiness_reviews = json.loads(json.dumps(reviews))
    nonexistent_human_readiness_reviews["reviews"].append(
        {
            "id": "DEMO-1-missing-human-readiness-evidence",
            "ticket": "DEMO-1",
            "stage": "Readiness",
            "status": "Approved",
            "path": "docs/review-packets/DOES-NOT-EXIST.md",
            "reviewer": "Human owner",
            "recordedAt": "2026-07-14",
        }
    )
    nonexistent_human_readiness_path = (
        fixture / "nonexistent-human-readiness-evidence.json"
    )
    nonexistent_human_readiness_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_readiness_tickets,
                    "reviews": nonexistent_human_readiness_reviews,
                }
            )
        )
    )
    rejected_nonexistent_human_readiness = run(
        fixture, "apply", str(nonexistent_human_readiness_path), "--json"
    )
    assert rejected_nonexistent_human_readiness.returncode == 1
    assert any(
        "Approved human review path does not exist or is not a regular file" in error
        for error in output(rejected_nonexistent_human_readiness)["errors"]
    )

    unattributed_human_readiness_reviews = json.loads(json.dumps(reviews))
    unattributed_human_readiness_reviews["reviews"].append(
        {
            "id": "DEMO-1-unattributed-human-readiness",
            "ticket": "DEMO-1",
            "stage": "Readiness",
            "status": "Approved",
            "path": "docs/review-packets/DEMO-1-READINESS.md",
        }
    )
    unattributed_human_readiness_path = fixture / "unattributed-human-readiness.json"
    unattributed_human_readiness_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_readiness_tickets,
                    "reviews": unattributed_human_readiness_reviews,
                }
            )
        )
    )
    rejected_unattributed_human_readiness = run(
        fixture, "apply", str(unattributed_human_readiness_path), "--json"
    )
    assert rejected_unattributed_human_readiness.returncode == 1
    assert any(
        "reviewer" in error or "recordedAt" in error
        for error in output(rejected_unattributed_human_readiness)["errors"]
    )

    generic_human_readiness_reviews = json.loads(json.dumps(reviews))
    generic_human_readiness_reviews["reviews"].append(
        {
            "id": "DEMO-1-generic-human-readiness",
            "ticket": "DEMO-1",
            "stage": "Readiness",
            "status": "Approved",
            "path": "docs/review-packets/README.md",
            "reviewer": "Human owner",
            "recordedAt": "2026-07-14",
        }
    )
    generic_human_readiness_path = fixture / "generic-human-readiness.json"
    generic_human_readiness_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_readiness_tickets,
                    "reviews": generic_human_readiness_reviews,
                }
            )
        )
    )
    rejected_generic_human_readiness = run(
        fixture, "apply", str(generic_human_readiness_path), "--json"
    )
    assert rejected_generic_human_readiness.returncode == 1
    assert any(
        "dedicated Markdown packet" in error
        for error in output(rejected_generic_human_readiness)["errors"]
    )

    symlink_packet = fixture / "docs/review-packets/DEMO-1-SYMLINK.md"
    symlink_packet.symlink_to(readiness_packet.name)
    symlink_human_readiness_reviews = json.loads(json.dumps(reviews))
    symlink_human_readiness_reviews["reviews"].append(
        {
            "id": "DEMO-1-symlink-human-readiness",
            "ticket": "DEMO-1",
            "stage": "Readiness",
            "status": "Approved",
            "path": "docs/review-packets/DEMO-1-SYMLINK.md",
            "reviewer": "Human owner",
            "recordedAt": "2026-07-14",
        }
    )
    symlink_human_readiness_path = fixture / "symlink-human-readiness.json"
    symlink_human_readiness_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_readiness_tickets,
                    "reviews": symlink_human_readiness_reviews,
                }
            )
        )
    )
    rejected_symlink_human_readiness = run(
        fixture, "apply", str(symlink_human_readiness_path), "--json"
    )
    assert rejected_symlink_human_readiness.returncode == 1
    assert any(
        "does not exist or is not a regular file" in error
        for error in output(rejected_symlink_human_readiness)["errors"]
    )

    approved_human_readiness_reviews = json.loads(json.dumps(reviews))
    approved_human_readiness_reviews["reviews"].append(
        {
            "id": "DEMO-1-human-readiness",
            "ticket": "DEMO-1",
            "stage": "Readiness",
            "status": "Approved",
            "path": "docs/review-packets/DEMO-1-READINESS.md",
            "reviewer": "Human owner",
            "recordedAt": "2026-07-14",
        }
    )
    approved_human_readiness_path = fixture / "approved-human-readiness.json"
    approved_human_readiness_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_readiness_tickets,
                    "reviews": approved_human_readiness_reviews,
                }
            )
        )
    )
    approved_human_readiness = run(
        fixture, "apply", str(approved_human_readiness_path), "--json"
    )
    assert approved_human_readiness.returncode == 0, approved_human_readiness.stderr
    conflicting_human_readiness_reviews = json.loads(
        json.dumps(approved_human_readiness_reviews)
    )
    conflicting_human_readiness_reviews["reviews"].append(
        {
            "id": "DEMO-1-human-readiness-rejection",
            "ticket": "DEMO-1",
            "stage": "Readiness",
            "status": "Rejected",
            "path": "docs/review-packets/DEMO-1-READINESS.md",
            "reviewer": "Human owner",
            "recordedAt": "2026-07-15",
        }
    )
    conflicting_human_readiness_path = fixture / "conflicting-human-readiness.json"
    conflicting_human_readiness_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_readiness_tickets,
                    "reviews": conflicting_human_readiness_reviews,
                }
            )
        )
    )
    rejected_conflicting_human_readiness = run(
        fixture, "apply", str(conflicting_human_readiness_path), "--json"
    )
    assert rejected_conflicting_human_readiness.returncode == 1
    assert any(
        "multiple human review decisions" in error
        for error in output(rejected_conflicting_human_readiness)["errors"]
    )
    restored_after_human_readiness = run(fixture, "apply", str(operation_path), "--json")
    assert restored_after_human_readiness.returncode == 0

    consultant_tickets = json.loads(json.dumps(tickets))
    consultant_tickets["tickets"][0]["requiredConsultantIds"] = ["product-designer"]
    missing_readiness_path = fixture / "missing-consultant-readiness.json"
    missing_readiness_path.write_text(
        json.dumps(operation({"tickets": consultant_tickets}))
    )
    missing_readiness = run(
        fixture, "apply", str(missing_readiness_path), "--json"
    )
    assert missing_readiness.returncode == 1
    assert any(
        "lacks approved Consultant readiness" in error
        for error in output(missing_readiness)["errors"]
    )

    consultant_reviews = json.loads(json.dumps(reviews))
    consultant_reviews["consultantReviews"] = [
        {
            "id": "DEMO-1-product-design-readiness",
            "ticket": "DEMO-1",
            "consultantId": "product-designer",
            "stage": "Readiness",
            "status": "Approved",
            "evidencePaths": ["docs/review-packets/README.md"],
            "reviewer": "Product Designer",
            "recordedAt": "2026-07-14",
        }
    ]
    readiness_path = fixture / "approved-consultant-readiness.json"
    readiness_path.write_text(
        json.dumps(
            operation(
                {"tickets": consultant_tickets, "reviews": consultant_reviews}
            )
        )
    )
    approved_readiness = run(fixture, "apply", str(readiness_path), "--json")
    assert approved_readiness.returncode == 0, approved_readiness.stderr
    conflicting_consultant_reviews = json.loads(json.dumps(consultant_reviews))
    conflicting_consultant_reviews["consultantReviews"].append(
        {
            "id": "DEMO-1-product-design-readiness-rejection",
            "ticket": "DEMO-1",
            "consultantId": "product-designer",
            "stage": "Readiness",
            "status": "Rejected",
            "evidencePaths": ["docs/review-packets/README.md"],
            "reviewer": "Product Designer",
            "recordedAt": "2026-07-15",
        }
    )
    conflicting_consultant_path = fixture / "conflicting-consultant-readiness.json"
    conflicting_consultant_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": consultant_tickets,
                    "reviews": conflicting_consultant_reviews,
                }
            )
        )
    )
    rejected_conflicting_consultant = run(
        fixture, "apply", str(conflicting_consultant_path), "--json"
    )
    assert rejected_conflicting_consultant.returncode == 1
    assert any(
        "multiple Consultant review decisions" in error
        for error in output(rejected_conflicting_consultant)["errors"]
    )

    completed_tickets = json.loads(json.dumps(consultant_tickets))
    completed_tickets["tickets"][0]["status"] = "Done"
    completed_tickets["tickets"][0]["reportPath"] = (
        "docs/implementation-reports/README.md"
    )
    empty_ownership = json.loads(json.dumps(ownership))
    empty_ownership["ownership"] = []
    missing_acceptance_path = fixture / "missing-consultant-acceptance.json"
    missing_acceptance_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": completed_tickets,
                    "ownership": empty_ownership,
                    "reviews": consultant_reviews,
                }
            )
        )
    )
    missing_acceptance = run(
        fixture, "apply", str(missing_acceptance_path), "--json"
    )
    assert missing_acceptance.returncode == 1
    assert any(
        "lacks approved Consultant acceptance" in error
        for error in output(missing_acceptance)["errors"]
    )

    consultant_reviews["consultantReviews"].append(
        {
            "id": "DEMO-1-product-design-acceptance",
            "ticket": "DEMO-1",
            "consultantId": "product-designer",
            "stage": "Acceptance",
            "status": "Approved",
            "evidencePaths": ["docs/implementation-reports/README.md"],
            "reviewer": "Product Designer",
            "recordedAt": "2026-07-14",
        }
    )
    acceptance_path = fixture / "approved-consultant-acceptance.json"
    acceptance_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": completed_tickets,
                    "ownership": empty_ownership,
                    "reviews": consultant_reviews,
                }
            )
        )
    )
    approved_acceptance = run(fixture, "apply", str(acceptance_path), "--json")
    assert approved_acceptance.returncode == 0, approved_acceptance.stderr

    human_acceptance_tickets = json.loads(json.dumps(completed_tickets))
    human_acceptance_tickets["tickets"][0]["assurance"] = {
        "testRigor": "Thorough",
        "humanReviewStages": ["Acceptance"],
        "overrideReason": "User requires final acceptance and broader regression",
    }
    missing_human_acceptance_path = fixture / "missing-human-acceptance.json"
    missing_human_acceptance_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_acceptance_tickets,
                    "ownership": empty_ownership,
                    "reviews": consultant_reviews,
                }
            )
        )
    )
    missing_human_acceptance = run(
        fixture, "apply", str(missing_human_acceptance_path), "--json"
    )
    assert missing_human_acceptance.returncode == 1
    assert any(
        "lacks approved human review for: Acceptance" in error
        for error in output(missing_human_acceptance)["errors"]
    )

    approved_human_acceptance_reviews = json.loads(json.dumps(consultant_reviews))
    approved_human_acceptance_reviews["reviews"][0]["status"] = "Approved"
    approved_human_acceptance_reviews["reviews"][0]["path"] = (
        "docs/review-packets/DEMO-1-ACCEPTANCE.md"
    )
    approved_human_acceptance_reviews["reviews"][0]["reviewer"] = "Human owner"
    approved_human_acceptance_reviews["reviews"][0]["recordedAt"] = "2026-07-14"
    approved_human_acceptance_path = fixture / "approved-human-acceptance.json"
    approved_human_acceptance_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": human_acceptance_tickets,
                    "ownership": empty_ownership,
                    "reviews": approved_human_acceptance_reviews,
                }
            )
        )
    )
    approved_human_acceptance = run(
        fixture, "apply", str(approved_human_acceptance_path), "--json"
    )
    assert approved_human_acceptance.returncode == 0, approved_human_acceptance.stderr

    release_review_tickets = json.loads(json.dumps(completed_tickets))
    release_review_tickets["tickets"][0]["assurance"] = {
        "testRigor": "Standard",
        "humanReviewStages": ["Release"],
        "overrideReason": "User requires approval only when release is requested",
    }
    pending_release_reviews = json.loads(json.dumps(consultant_reviews))
    pending_release_reviews["reviews"][0]["stage"] = "Release"
    release_review_path = fixture / "pending-release-after-completion.json"
    release_review_path.write_text(
        json.dumps(
            operation(
                {
                    "tickets": release_review_tickets,
                    "ownership": empty_ownership,
                    "reviews": pending_release_reviews,
                }
            )
        )
    )
    pending_release = run(fixture, "apply", str(release_review_path), "--json")
    assert pending_release.returncode == 0, pending_release.stderr
    restored = run(fixture, "apply", str(operation_path), "--json")
    assert restored.returncode == 0, restored.stderr

    schema_writer = load_writer(fixture)
    assert schema_writer.schema_errors(
        tickets, fixture / "docs/schemas/tickets.schema.json"
    ) == []
    duplicate_scope = json.loads(json.dumps(tickets))
    duplicate_scope["tickets"][0]["scope"] = [
        "Canonical state fixture",
        "Canonical state fixture",
    ]
    direct_schema_errors = schema_writer.schema_errors(
        duplicate_scope, fixture / "docs/schemas/tickets.schema.json"
    )
    assert any("items must be unique" in error for error in direct_schema_errors)
    duplicate_scope_path = fixture / "schema-invalid-duplicate-scope.json"
    duplicate_scope_path.write_text(
        json.dumps(operation({"tickets": duplicate_scope}))
    )
    tickets_before_schema_rejection = (
        fixture / "docs/state/tickets.json"
    ).read_bytes()
    rejected_duplicate_scope = run(
        fixture, "apply", str(duplicate_scope_path), "--json"
    )
    assert rejected_duplicate_scope.returncode == 1
    assert any(
        "items must be unique" in error
        for error in output(rejected_duplicate_scope)["errors"]
    )
    assert (
        fixture / "docs/state/tickets.json"
    ).read_bytes() == tickets_before_schema_rejection

    concurrent_goals = json.loads(json.dumps(goals))
    concurrent_goals["goals"].append({
        "id": "GOAL-OTHER", "title": "Compete for current focus",
        "status": "Active", "priority": "P2", "owner": "Operations",
        "objective": "Prove that only one goal can be active",
        "context": "Concurrent active goals make project focus ambiguous",
        "dependencies": ["GOAL-DONE"], "blockers": [], "decisionPaths": [], "evidencePaths": [],
    })
    concurrent_path = fixture / "concurrent-goals.json"
    concurrent_path.write_text(json.dumps(operation({"goals": concurrent_goals})))
    rejected_concurrent = run(fixture, "apply", str(concurrent_path), "--json")
    assert rejected_concurrent.returncode == 1
    assert any("only one goal" in error for error in output(rejected_concurrent)["errors"])

    incomplete_blocker = json.loads(json.dumps(goals))
    incomplete_blocker["goals"][2].pop("resumeCondition")
    blocker_path = fixture / "incomplete-blocker.json"
    blocker_path.write_text(json.dumps(operation({"goals": incomplete_blocker})))
    rejected_blocker = run(fixture, "apply", str(blocker_path), "--json")
    assert rejected_blocker.returncode == 1
    assert any("resumeCondition" in error for error in output(rejected_blocker)["errors"])

    invalid_schedule = json.loads(json.dumps(goals))
    invalid_schedule["goals"][1]["plannedEnd"] = "2026-07-01"
    schedule_path = fixture / "invalid-goal-schedule.json"
    schedule_path.write_text(json.dumps(operation({"goals": invalid_schedule})))
    rejected_schedule = run(fixture, "apply", str(schedule_path), "--json")
    assert rejected_schedule.returncode == 1
    assert any("plannedEnd cannot be earlier" in error for error in output(rejected_schedule)["errors"])

    completed_current = json.loads(json.dumps(project))
    completed_current["project"]["currentGoal"] = "GOAL-DONE"
    completed_current_path = fixture / "completed-current.json"
    completed_current_path.write_text(json.dumps(operation({"project": completed_current})))
    rejected_completed_current = run(fixture, "apply", str(completed_current_path), "--json")
    assert rejected_completed_current.returncode == 1
    assert any("currentGoal cannot be Done" in error for error in output(rejected_completed_current)["errors"])

    cyclic_goals = json.loads(json.dumps(goals))
    cyclic_goals["goals"][0]["dependencies"] = ["GOAL-NEXT"]
    cyclic_path = fixture / "cyclic-goals.json"
    cyclic_path.write_text(json.dumps(operation({"goals": cyclic_goals})))
    rejected_cycle = run(fixture, "apply", str(cyclic_path), "--json")
    assert rejected_cycle.returncode == 1
    assert any("dependency cycle" in error for error in output(rejected_cycle)["errors"])

    incomplete_goal_dependencies = json.loads(json.dumps(goals))
    incomplete_goal_dependencies["goals"][0]["dependencies"] = ["GOAL-NEXT"]
    incomplete_goal_dependencies["goals"][2]["dependencies"] = []
    incomplete_goal_path = fixture / "incomplete-goal-dependencies.json"
    incomplete_goal_path.write_text(json.dumps(operation({"goals": incomplete_goal_dependencies})))
    rejected_goal_dependencies = run(fixture, "apply", str(incomplete_goal_path), "--json")
    assert rejected_goal_dependencies.returncode == 1
    assert any(
        "Done goal GOAL-DONE has incomplete dependencies" in error
        for error in output(rejected_goal_dependencies)["errors"]
    )

    premature_goals = json.loads(json.dumps(goals))
    premature_goals["goals"][1].update({
        "status": "Done",
        "completedAt": "2026-07-11",
        "resultSummary": "Incorrectly declared complete",
        "evidencePaths": ["docs/implementation-reports/README.md"],
    })
    premature_project = json.loads(json.dumps(project))
    premature_project["project"]["currentGoal"] = "GOAL-NEXT"
    premature_path = fixture / "premature-completion.json"
    premature_path.write_text(json.dumps(operation({
        "project": premature_project, "goals": premature_goals,
    })))
    rejected_premature = run(fixture, "apply", str(premature_path), "--json")
    assert rejected_premature.returncode == 1
    premature_errors = output(rejected_premature)["errors"]
    assert any("non-terminal tickets" in error for error in premature_errors)
    assert any("retains active ownership" in error for error in premature_errors)

    invalid = json.loads((fixture / "docs/state/tickets.json").read_text())
    invalid["tickets"][0]["status"] = "Not A Status"
    (fixture / "docs/state/tickets.json").write_text(json.dumps(invalid) + "\n")
    invalid_check = run(fixture, "check", "--json")
    assert invalid_check.returncode == 1
    assert any("status" in error for error in output(invalid_check)["errors"])
    (fixture / "docs/state/tickets.json").write_text(json.dumps(tickets, indent=2) + "\n")

    before = (fixture / "docs/state/tickets.json").read_bytes()
    malformed = fixture / "malformed.json"
    malformed.write_text(json.dumps({"schemaVersion": 1, "operation": "replace-records", "records": {"tickets": invalid}}))
    failed_apply = run(fixture, "apply", str(malformed), "--json")
    assert failed_apply.returncode == 1
    assert (fixture / "docs/state/tickets.json").read_bytes() == before

    outside_report = fixture.parent / "outside-report.md"
    outside_report.write_text("not repository evidence\n", encoding="utf-8")
    escaped = json.loads(json.dumps(tickets))
    escaped["tickets"][0]["status"] = "Done"
    escaped["tickets"][0]["reportPath"] = str(outside_report)
    escaped_path = fixture / "escaped.json"
    escaped_path.write_text(json.dumps(operation({"tickets": escaped})))
    rejected_escape = run(fixture, "apply", str(escaped_path), "--json")
    assert rejected_escape.returncode == 1
    assert any("inside the repository" in error for error in output(rejected_escape)["errors"])
    assert (fixture / "docs/state/tickets.json").read_bytes() == before
    outside_report.unlink()

    writer = load_writer(fixture)
    replacement = json.dumps(tickets, indent=2) + "\n"
    dashboard_before = (fixture / "docs/index.html").read_bytes()
    original_replace = writer.os.replace
    calls = [0]
    def fail_dashboard_replace(source, destination):
        calls[0] += 1
        if calls[0] == 2:
            raise OSError("simulated dashboard replacement failure")
        return original_replace(source, destination)
    writer.os.replace = fail_dashboard_replace
    try:
        try:
            writer.write_transaction({
                fixture / "docs/state/tickets.json": replacement,
                fixture / "docs/index.html": "replacement dashboard\n",
            })
        except OSError:
            pass
        else:
            raise AssertionError("simulated transaction failure did not fail")
    finally:
        writer.os.replace = original_replace
    assert (fixture / "docs/state/tickets.json").read_bytes() == before
    assert (fixture / "docs/index.html").read_bytes() == dashboard_before

    (fixture / "docs/index.html").write_text("stale\n")
    drift = run(fixture, "check", "--json")
    assert drift.returncode == 1
    assert any("dashboard drift" in error for error in output(drift)["errors"])
    repaired = run(fixture, "apply", str(operation_path), "--json")
    assert repaired.returncode == 0
    assert run(fixture, "check", "--json").returncode == 0

    nested = json.loads((fixture / "docs/state/ownership.json").read_text())
    nested["ownership"].append({
        "ticket": "DEMO-1", "owner": "Contractor B", "scopes": ["docs/example.md/nested"],
        "status": "Assigned", "returnDestination": "Operations",
    })
    nested_path = fixture / "nested.json"
    nested_path.write_text(json.dumps(operation({"ownership": nested})))
    rejected_nested = run(fixture, "apply", str(nested_path), "--json")
    assert rejected_nested.returncode == 1
    assert any("overlapping scopes" in error for error in output(rejected_nested)["errors"])
finally:
    shutil.rmtree(fixture, ignore_errors=True)
    shutil.rmtree(state_home, ignore_errors=True)
    if previous_state_home is None:
        os.environ.pop("XDG_STATE_HOME", None)
    else:
        os.environ["XDG_STATE_HOME"] = previous_state_home

print("PASS: harness state smoke completed")
