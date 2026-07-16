#!/usr/bin/env python3
"""Canonical state, team, config, and discovery tests for installed Baton."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template/.baton/lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baton_testkit import (  # noqa: E402
    SKILLS,
    assert_no_python_cache,
    baton,
    build_bundle,
    expected_consumer_config,
    install_bundle,
    json_output,
    make_candidate,
    run,
    semantic_toml,
)
import harness_state  # noqa: E402
import baton_memory  # noqa: E402


class StateTeamConfigDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-state-team-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle"
        build_bundle(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def setUp(self) -> None:
        self.target = self.base / self.id().rsplit(".", 1)[-1]
        self.state_home = self.base / ("state-" + self.target.name)
        json_output(install_bundle(self.bundle, self.target, self.state_home))

    def use_source_repository_topology(self) -> None:
        metadata_path = self.target / ".baton/metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["installationStatus"] = "Source Repository"
        metadata["managedFiles"] = {}
        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.target / ".codex/config.toml").write_bytes(
            (ROOT / ".codex/config.toml").read_bytes()
        )
        runtime = self.target / ".baton/lib"
        template_runtime = self.target / "template/.baton/lib"
        shutil.copytree(runtime, template_runtime)
        shutil.rmtree(runtime)
        runtime.symlink_to("../template/.baton/lib")

    def bind_bootstrap_coordinator(self, coordinator: str) -> str:
        baton_memory.reconcile_bootstrap(
            self.target,
            {
                "list": True,
                "create": True,
                "stableIdentity": True,
                "read": True,
                "message": True,
                "title": True,
                "archive": True,
            },
            {
                "seed": "preset-reconfigure-project",
                "invocationTaskId": coordinator,
                "seats": [],
            },
        )
        return coordinator

    def test_project_contract_accepts_any_configured_agent_provider(self) -> None:
        project = json.loads(
            (ROOT / "template/.baton/state/project.json").read_text(encoding="utf-8")
        )
        project["project"]["agentProvider"] = "future-provider"
        errors: list[str] = []
        harness_state.validate_record("project", project, errors)
        self.assertEqual(errors, [])

    def test_record_scopes_are_flat_and_project_is_reserved(self) -> None:
        errors: list[str] = []
        harness_state.scoped_record_path(
            ".baton/records/GOAL-001/nested/brief.md",
            "GOAL-001",
            "fixture.briefPath",
            errors,
            expected_name="brief.md",
        )
        self.assertEqual(
            errors,
            [
                "fixture.briefPath: expected flat "
                ".baton/records/GOAL-001/brief.md"
            ],
        )

        goals = json.loads(
            (ROOT / "template/.baton/state/goals.json").read_text(encoding="utf-8")
        )
        goals["goals"] = [
            {
                "id": "PROJECT",
                "title": "Invalid reserved scope",
                "status": "Needs Definition",
                "priority": "P2",
                "owner": "Management",
                "objective": "Prove the Project scope cannot be reused.",
                "context": "Record scope ids must be unambiguous.",
                "dependencies": [],
                "assurance": {
                    "clearanceProtocol": "Release Clearance",
                    "overrideReason": "",
                },
                "blockers": [],
                "decisionPaths": [],
                "evidencePaths": [],
            }
        ]
        errors = []
        harness_state.validate_record("goals", goals, errors)
        self.assertTrue(any("PROJECT is reserved" in error for error in errors))

    def test_goal_and_ticket_ids_are_globally_unique(self) -> None:
        records = {
            name: json.loads(
                (self.target / f".baton/state/{name}.json").read_text(
                    encoding="utf-8"
                )
            )
            for name in harness_state.RECORD_NAMES
        }
        records["goals"]["goals"] = [
            {
                "id": "SHARED-001",
                "title": "Goal id",
                "status": "Needs Definition",
                "priority": "P2",
                "owner": "Management",
                "objective": "Prove cross-record uniqueness.",
                "context": "Record folders use canonical ids.",
                "dependencies": [],
                "assurance": {
                    "clearanceProtocol": "Release Clearance",
                    "overrideReason": "",
                },
                "blockers": [],
                "decisionPaths": [],
                "evidencePaths": [],
            }
        ]
        records["tickets"]["tickets"] = [
            {
                "id": "SHARED-001",
                "title": "Ticket id",
                "status": "Backlog",
                "priority": "P2",
                "owner": "Operations",
                "dependencies": [],
                "requiredConsultantIds": [],
                "assurance": {
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                    "overrideReason": "",
                },
                "blockers": [],
                "openDecisions": [],
                "decisionPaths": [],
                "evidencePaths": [],
            }
        ]
        errors: list[str] = []
        harness_state.validate_records(records, errors)
        self.assertIn(
            ".baton/state: Goal and Ticket ids must be globally unique: SHARED-001",
            errors,
        )

    def test_state_apply_is_transactional_and_refreshes_dashboard_baseline(self) -> None:
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)
        project_path = self.target / ".baton/state/project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["project"]["phase"] = "Verified by deterministic state smoke"
        operation = self.base / f"{self.target.name}-operation.json"
        operation.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "operation": "replace-records",
                    "records": {"project": project},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        applied = json_output(
            baton(
                self.target,
                ["control", "apply", operation, "--json"],
                self.state_home,
            )
        )
        self.assertEqual(applied["changed"], ["project"])
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)
        dashboard = (self.target / ".baton/views/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("Verified by deterministic state smoke", dashboard)
        status = json_output(baton(self.target, ["terminal", "status", "--json"], self.state_home))
        self.assertTrue(status["ok"])

    def test_control_protocols_updates_project_and_inherited_scopes(self) -> None:
        project = json.loads(
            (self.target / ".baton/state/project.json").read_text(encoding="utf-8")
        )
        project["project"]["currentGoal"] = "PROTOCOL-GOAL"
        goals = {
            "schemaVersion": 1,
            "recordType": "goals",
            "goals": [
                {
                    "id": "PROTOCOL-GOAL",
                    "title": "Exercise inherited protocols",
                    "status": "Needs Definition",
                    "priority": "P2",
                    "owner": "Management",
                    "objective": "Prove Project protocol propagation.",
                    "context": "The scope has no override.",
                    "dependencies": [],
                    "assurance": {
                        "clearanceProtocol": "Release Clearance",
                        "overrideReason": "",
                    },
                    "blockers": [],
                    "decisionPaths": [],
                    "evidencePaths": [],
                }
            ],
        }
        tickets = {
            "schemaVersion": 1,
            "recordType": "tickets",
            "tickets": [
                {
                    "id": "PROTOCOL-TICKET",
                    "title": "Exercise inherited protocols",
                    "status": "Backlog",
                    "priority": "P2",
                    "owner": "Operations",
                    "goal": "PROTOCOL-GOAL",
                    "dependencies": [],
                    "requiredConsultantIds": [],
                    "assurance": {
                        "readinessProtocol": "Standard Protocol",
                        "clearanceProtocol": "Release Clearance",
                        "overrideReason": "",
                    },
                    "blockers": [],
                    "openDecisions": [],
                    "decisionPaths": [],
                    "evidencePaths": [],
                }
            ],
        }
        operation = self.base / f"{self.target.name}-protocol-operation.json"
        operation.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "operation": "replace-records",
                    "records": {"project": project, "goals": goals, "tickets": tickets},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        json_output(
            baton(
                self.target,
                ["control", "apply", operation, "--json"],
                self.state_home,
            )
        )

        changed = json_output(
            baton(
                self.target,
                [
                    "control",
                    "protocols",
                    "--readiness",
                    "Field Check",
                    "--clearance",
                    "Completion Clearance",
                    "--json",
                ],
                self.state_home,
            )
        )
        self.assertEqual(
            changed["assuranceDefaults"],
            {
                "readinessProtocol": "Field Check",
                "clearanceProtocol": "Completion Clearance",
            },
        )
        resolved_project = json.loads(
            (self.target / ".baton/state/project.json").read_text(encoding="utf-8")
        )["project"]
        resolved_goal = json.loads(
            (self.target / ".baton/state/goals.json").read_text(encoding="utf-8")
        )["goals"][0]
        resolved_ticket = json.loads(
            (self.target / ".baton/state/tickets.json").read_text(encoding="utf-8")
        )["tickets"][0]
        self.assertEqual(resolved_project["assuranceDefaults"], changed["assuranceDefaults"])
        self.assertEqual(resolved_goal["assurance"]["clearanceProtocol"], "Completion Clearance")
        self.assertEqual(resolved_ticket["assurance"]["readinessProtocol"], "Field Check")
        self.assertEqual(resolved_ticket["assurance"]["clearanceProtocol"], "Completion Clearance")
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_project_decision_record_is_linked_from_project_state(self) -> None:
        relative = ".baton/records/PROJECT/decision-browser-testing.md"
        decision = self.target / relative
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(
            "# Browser testing\n\nStatus: Accepted\n\nUse repository-owned checks.\n",
            encoding="utf-8",
        )
        project = json.loads(
            (self.target / ".baton/state/project.json").read_text(encoding="utf-8")
        )
        project["project"]["decisionPaths"].append(relative)
        operation = self.base / f"{self.target.name}-project-decision.json"
        operation.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "operation": "replace-records",
                    "records": {"project": project},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        applied = json_output(
            baton(
                self.target,
                ["control", "apply", operation, "--json"],
                self.state_home,
            )
        )
        self.assertEqual(applied["changed"], ["project"])
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_goal_and_ticket_clearances_use_namespaced_dedicated_packets(self) -> None:
        ticket_packet = self.target / ".baton/records/REVIEW-PACKET-TEST/review-acceptance-operations.md"
        ticket_packet.parent.mkdir(parents=True, exist_ok=True)
        ticket_packet.write_text("# Ticket Acceptance\n\nApproved from exact evidence.\n", encoding="utf-8")
        goal_packet = self.target / ".baton/records/CLEARANCE-GOAL/review-release-management.md"
        goal_packet.parent.mkdir(parents=True, exist_ok=True)
        goal_packet.write_text("# Goal Release\n\nApproved exact release candidate.\n", encoding="utf-8")
        reviews_path = self.target / ".baton/state/reviews.json"
        reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
        goals = json.loads(
            (self.target / ".baton/state/goals.json").read_text(encoding="utf-8")
        )
        tickets = json.loads(
            (self.target / ".baton/state/tickets.json").read_text(encoding="utf-8")
        )
        goals["goals"].append(
            {
                "id": "CLEARANCE-GOAL",
                "title": "Verify Goal Clearance",
                "status": "Done",
                "priority": "P3",
                "owner": "Management",
                "objective": "Prove a Goal Release decision is canonical.",
                "context": "Goal and Ticket clearances use distinct targets.",
                "dependencies": [],
                "assurance": {
                    "clearanceProtocol": "Release Clearance",
                    "overrideReason": "",
                },
                "blockers": [],
                "decisionPaths": [],
                "evidencePaths": [
                    ".baton/records/CLEARANCE-GOAL/review-release-management.md"
                ],
                "resultSummary": "Goal Clearance is stored against the Goal.",
                "completedAt": "2026-07-16",
            }
        )
        ticket = "REVIEW-PACKET-TEST"
        tickets["tickets"].append(
            {
                "id": ticket,
                "title": "Verify namespaced review packets",
                "status": "Backlog",
                "priority": "P3",
                "owner": "Management",
                "dependencies": [],
                "requiredConsultantIds": [],
                "assurance": {
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                    "overrideReason": "",
                },
                "blockers": [],
                "openDecisions": [],
                "decisionPaths": [],
                "evidencePaths": [],
            }
        )
        reviews["clearances"] = [
            {
                "id": "management-release",
                "goal": "CLEARANCE-GOAL",
                "stage": "Release",
                "status": "Approved",
                "path": ".baton/records/CLEARANCE-GOAL/review-release-management.md",
                "reviewer": "Management",
                "recordedAt": "2026-07-16",
            },
            {
                "id": "operations-acceptance",
                "ticket": ticket,
                "stage": "Acceptance",
                "status": "Approved",
                "path": ".baton/records/REVIEW-PACKET-TEST/review-acceptance-operations.md",
                "reviewer": "Operations",
                "recordedAt": "2026-07-16",
            }
        ]
        operation = self.base / f"{self.target.name}-review-operation.json"
        operation.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "operation": "replace-records",
                    "records": {
                        "goals": goals,
                        "tickets": tickets,
                        "reviews": reviews,
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        applied = json_output(
            baton(
                self.target,
                ["control", "apply", operation, "--json"],
                self.state_home,
            )
        )
        self.assertEqual(
            set(applied["changed"]), {"goals", "tickets", "reviews"}
        )
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_continuous_clearance_gates_goal_and_ticket_before_and_after_work(self) -> None:
        records = {
            name: json.loads(
                (self.target / f".baton/state/{name}.json").read_text(
                    encoding="utf-8"
                )
            )
            for name in ("project", "goals", "tickets", "reviews")
        }
        records["project"]["project"]["currentGoal"] = "CONTINUOUS-GOAL"
        records["goals"]["goals"] = [
            {
                "id": "CONTINUOUS-GOAL",
                "title": "Exercise every clearance boundary",
                "status": "Active",
                "priority": "P2",
                "owner": "Management",
                "objective": "Prove Continuous Clearance before and after work.",
                "context": "The top protocol reviews every canonical boundary.",
                "dependencies": [],
                "assurance": {
                    "clearanceProtocol": "Continuous Clearance",
                    "overrideReason": "User selected the top clearance tier.",
                },
                "blockers": [],
                "decisionPaths": [],
                "evidencePaths": [],
            }
        ]
        records["tickets"]["tickets"] = [
            {
                "id": "CONTINUOUS-001",
                "title": "Complete one continuously cleared Ticket",
                "status": "Done",
                "priority": "P2",
                "owner": "Operations",
                "goal": "CONTINUOUS-GOAL",
                "dependencies": [],
                "objective": "Exercise Ticket Readiness and Acceptance.",
                "scope": ["Clearance state validation"],
                "nonGoals": ["External publication"],
                "affectedSystems": ["Baton state"],
                "acceptanceCriteria": ["Both Ticket clearances are approved"],
                "requiredVerification": ["Deterministic state check"],
                "expectedEvidence": ["Approved clearance packets"],
                "risks": ["A missing boundary could be accepted"],
                "requiredConsultantIds": [],
                "assurance": {
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Continuous Clearance",
                    "overrideReason": "User selected the top clearance tier.",
                },
                "blockers": [],
                "openDecisions": [],
                "decisionPaths": [],
                "evidencePaths": [],
                "reportPath": ".baton/records/CONTINUOUS-001/report.md",
            }
        ]
        operation = self.base / f"{self.target.name}-continuous-operation.json"
        report = self.target / ".baton/records/CONTINUOUS-001/report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Continuous Ticket report\n\nCompleted.\n", encoding="utf-8")

        def write_operation() -> None:
            operation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "operation": "replace-records",
                        "records": records,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        write_operation()
        denied = baton(
            self.target,
            ["control", "apply", operation, "--json"],
            self.state_home,
            expected=1,
        )
        denied_payload = json.loads(denied.stdout)
        self.assertIn("Goal Clearance for: Readiness", "\n".join(denied_payload["errors"]))
        self.assertIn(
            "Ticket Clearance for: Readiness, Acceptance",
            "\n".join(denied_payload["errors"]),
        )

        clearances = (
            ("goal-readiness", "goal", "CONTINUOUS-GOAL", "Readiness"),
            ("ticket-readiness", "ticket", "CONTINUOUS-001", "Readiness"),
            ("ticket-acceptance", "ticket", "CONTINUOUS-001", "Acceptance"),
        )
        records["reviews"]["clearances"] = []
        for identifier, target_type, target_id, stage in clearances:
            relative = (
                f".baton/records/{target_id}/"
                f"review-{stage.casefold()}-management.md"
            )
            packet = self.target / relative
            packet.parent.mkdir(parents=True, exist_ok=True)
            packet.write_text(
                f"# {target_type.title()} {stage}\n\nApproved.\n",
                encoding="utf-8",
            )
            records["reviews"]["clearances"].append(
                {
                    "id": identifier,
                    target_type: target_id,
                    "stage": stage,
                    "status": "Approved",
                    "path": relative,
                    "reviewer": "Management",
                    "recordedAt": "2026-07-16",
                }
            )
        write_operation()
        applied = json_output(
            baton(
                self.target,
                ["control", "apply", operation, "--json"],
                self.state_home,
            )
        )
        self.assertEqual(
            set(applied["changed"]), {"project", "goals", "tickets", "reviews"}
        )

    def test_hire_and_fire_reconcile_nested_codex_agent_registry(self) -> None:
        memory_path = self.target / ".baton/memory/memory.json"
        self.assertEqual(json.loads(memory_path.read_text(encoding="utf-8"))["revision"], 0)
        hired = json_output(
            baton(
                self.target,
                ["roster", "hire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )
        self.assertEqual(hired["action"], "hire")
        self.assertEqual(hired["manualActions"], [])
        self.assertEqual(hired["memoryRevision"], 1)
        self.assertEqual(len(hired["personnelIds"]), 1)
        security_config = self.target / ".baton/agents/consultant-security-lead.toml"
        self.assertTrue(security_config.is_file())
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(("product-designer", "security-lead")),
        )
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        remembered = next(
            person
            for person in memory["personnel"]
            if person["role"] == "Consultant" and person["seat"] == "security-lead"
        )
        self.assertEqual(remembered["employmentStatus"], "active")
        self.assertIn(
            remembered["name"],
            (self.target / ".baton/views/dashboard.html").read_text(encoding="utf-8"),
        )
        registry = (self.target / ".baton/views/team-tasks.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(remembered["name"], registry)
        metadata = json.loads(
            (self.target / ".baton/metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["managedFiles"][".baton/views/team-tasks.md"]["ownership"],
            "generated-config",
        )
        fired = json_output(
            baton(
                self.target,
                ["roster", "fire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )
        self.assertEqual(fired["action"], "fire")
        self.assertEqual(fired["memoryRevision"], 2)
        self.assertFalse(fired["manualCleanupRequired"])
        self.assertFalse(security_config.exists())
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(),
        )
        team = json.loads((self.target / ".baton/state/team.json").read_text(encoding="utf-8"))
        security = next(item for item in team["consultants"] if item["id"] == "security-lead")
        self.assertEqual(security["status"], "inactive")
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        remembered = next(
            person
            for person in memory["personnel"]
            if person["role"] == "Consultant" and person["seat"] == "security-lead"
        )
        self.assertEqual(remembered["employmentStatus"], "former")
        self.assertEqual(remembered["task"]["status"], "inactive")
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)

    def test_roster_collision_uses_external_transaction_proposal(self) -> None:
        config = self.target / ".codex/config.toml"
        before = config.read_bytes() + b"\n# project-owned\n"
        config.write_bytes(before)

        hired = json_output(
            baton(
                self.target,
                ["roster", "hire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )

        proposal = Path(hired["proposalPath"])
        self.assertTrue(proposal.is_file())
        self.assertNotIn(self.target.resolve(), proposal.resolve().parents)
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse((self.target / ".baton/migration").exists())
        self.assertEqual(
            semantic_toml(proposal),
            expected_consumer_config(("product-designer", "security-lead")),
        )
        self.assertTrue(
            any("external Roster proposal" in action for action in hired["manualActions"])
        )

        report = json.loads(Path(hired["reportPath"]).read_text(encoding="utf-8"))
        artifact = report["externalArtifacts"]["proposals/codex-config.toml"]
        self.assertEqual(artifact["path"], str(proposal))
        self.assertEqual(
            artifact["sha256"], hashlib.sha256(proposal.read_bytes()).hexdigest()
        )
        metadata = json.loads(
            (self.target / ".baton/metadata.json").read_text(encoding="utf-8")
        )
        self.assertNotIn(".codex/config.toml", metadata["managedFiles"])
        self.assertIn(".codex/config.toml", metadata["projectOwnedFiles"])
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )
        proposal.write_bytes(proposal.read_bytes() + b"\n# tampered\n")
        tampered = baton(
            self.target,
            ["doctor", "check", "--json"],
            self.state_home,
            expected=1,
        )
        self.assertIn("external Roster Codex proposal", tampered.stdout)

    def test_bootstrap_can_reconfigure_project_preset_before_coworker_tasks_exist(self) -> None:
        user_file = self.target / "src/project-owned.txt"
        user_file.parent.mkdir(parents=True)
        user_file.write_text("preserve me\n", encoding="utf-8")
        before = user_file.read_bytes()
        coordinator = "preset-bootstrap-task"
        team_before = (self.target / ".baton/state/team.json").read_bytes()
        memory_before = (self.target / ".baton/memory/memory.json").read_bytes()
        unbound = baton(
            self.target,
            [
                "roster",
                "configure",
                "--preset",
                "game-development",
                "--consultant",
                "art-director",
                "--yes",
                "--json",
            ],
            self.state_home,
            expected=1,
        )
        self.assertIn(
            "requires the original invoking task ID",
            unbound.stdout + unbound.stderr,
        )
        self.assertEqual(
            (self.target / ".baton/state/team.json").read_bytes(), team_before
        )
        self.assertEqual(
            (self.target / ".baton/memory/memory.json").read_bytes(), memory_before
        )

        self.bind_bootstrap_coordinator(coordinator)
        team_before = (self.target / ".baton/state/team.json").read_bytes()
        wrong_coordinator = baton(
            self.target,
            [
                "roster",
                "configure",
                "--preset",
                "game-development",
                "--consultant",
                "art-director",
                "--invocation-task-id",
                "another-bootstrap-task",
                "--yes",
                "--json",
            ],
            self.state_home,
            expected=1,
        )
        self.assertIn(
            "original invoking task",
            wrong_coordinator.stdout + wrong_coordinator.stderr,
        )
        self.assertEqual(
            (self.target / ".baton/state/team.json").read_bytes(), team_before
        )

        changed = json_output(
            baton(
                self.target,
                [
                    "roster",
                    "configure",
                    "--preset",
                    "game-development",
                    "--consultant",
                    "art-director",
                    "--invocation-task-id",
                    coordinator,
                    "--yes",
                    "--json",
                ],
                self.state_home,
            )
        )
        self.assertEqual(changed["action"], "reconfigure")
        self.assertEqual(changed["preset"], "game-development")
        self.assertEqual(changed["consultants"], ["art-director"])
        self.assertEqual(changed["manualActions"], [])
        self.assertEqual(user_file.read_bytes(), before)

        team = json.loads(
            (self.target / ".baton/state/team.json").read_text(encoding="utf-8")
        )
        self.assertEqual(team["preset"], "game-development")
        self.assertEqual(team["management"]["title"], "Game Director")
        self.assertEqual(team["operations"]["title"], "Producer")
        self.assertEqual(
            [item["id"] for item in team["consultants"] if item["status"] == "active"],
            ["art-director"],
        )
        self.assertFalse(
            (self.target / ".baton/agents/consultant-product-designer.toml").exists()
        )
        self.assertTrue(
            (self.target / ".baton/agents/consultant-art-director.toml").is_file()
        )
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(("art-director",)),
        )
        metadata = json.loads(
            (self.target / ".baton/metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["projectType"], "game-development")
        memory = json.loads(
            (self.target / ".baton/memory/memory.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            memory["bootstrap"]["provisionalProject"],
            {
                "coordinatorTaskId": coordinator,
                "projectPreset": "game-development",
                "projectPresetConfirmed": True,
                "consultantSeats": ["art-director"],
                "projectPresetEpoch": 1,
            },
        )
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_preset_reconfigure_fails_closed_on_modified_generated_role_config(self) -> None:
        coordinator = self.bind_bootstrap_coordinator("modified-management-task")
        management = self.target / ".baton/agents/management.toml"
        before = management.read_bytes() + b"# project-owned adjustment\n"
        management.write_bytes(before)
        team_before = (self.target / ".baton/state/team.json").read_bytes()
        memory_before = (self.target / ".baton/memory/memory.json").read_bytes()

        failed = baton(
            self.target,
            [
                "roster",
                "configure",
                "--preset",
                "game-development",
                "--consultant",
                "art-director",
                "--invocation-task-id",
                coordinator,
                "--yes",
                "--json",
            ],
            self.state_home,
            expected=1,
        )
        self.assertIn("modified generated role config", failed.stdout + failed.stderr)
        self.assertEqual(management.read_bytes(), before)
        self.assertEqual(
            (self.target / ".baton/state/team.json").read_bytes(), team_before
        )
        self.assertEqual(
            (self.target / ".baton/memory/memory.json").read_bytes(), memory_before
        )

    def test_preset_reconfigure_fails_closed_on_modified_outgoing_consultant_config(self) -> None:
        coordinator = self.bind_bootstrap_coordinator("modified-consultant-task")
        consultant = self.target / ".baton/agents/consultant-product-designer.toml"
        before = consultant.read_bytes() + b"# project-owned adjustment\n"
        consultant.write_bytes(before)
        team_before = (self.target / ".baton/state/team.json").read_bytes()
        memory_before = (self.target / ".baton/memory/memory.json").read_bytes()

        failed = baton(
            self.target,
            [
                "roster",
                "configure",
                "--preset",
                "game-development",
                "--consultant",
                "art-director",
                "--invocation-task-id",
                coordinator,
                "--yes",
                "--json",
            ],
            self.state_home,
            expected=1,
        )
        self.assertIn("modified generated role config", failed.stdout + failed.stderr)
        self.assertEqual(consultant.read_bytes(), before)
        self.assertEqual(
            (self.target / ".baton/state/team.json").read_bytes(), team_before
        )
        self.assertEqual(
            (self.target / ".baton/memory/memory.json").read_bytes(), memory_before
        )

    def test_preset_reconfigure_can_return_to_a_previously_selected_preset(self) -> None:
        coordinator = self.bind_bootstrap_coordinator("return-preset-task")

        def reconfigure(preset: str, consultant: str) -> None:
            json_output(
                baton(
                    self.target,
                    [
                        "roster",
                        "configure",
                        "--preset",
                        preset,
                        "--consultant",
                        consultant,
                        "--invocation-task-id",
                        coordinator,
                        "--yes",
                        "--json",
                    ],
                    self.state_home,
                )
            )

        reconfigure("game-development", "art-director")
        reconfigure("business-operations", "change-manager")
        reconfigure("game-development", "art-director")

        memory = json.loads(
            (self.target / ".baton/memory/memory.json").read_text(encoding="utf-8")
        )
        self.assertEqual(memory["revision"], 4)
        self.assertEqual(
            memory["bootstrap"]["provisionalProject"]["projectPreset"],
            "game-development",
        )
        self.assertEqual(
            memory["bootstrap"]["provisionalProject"]["consultantSeats"],
            ["art-director"],
        )
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_source_repository_preset_reconfigure_updates_exact_codex_registry(self) -> None:
        self.use_source_repository_topology()
        coordinator = self.bind_bootstrap_coordinator("source-preset-task")
        self.assertTrue((self.target / ".baton/lib").is_symlink())

        changed = json_output(
            baton(
                self.target,
                [
                    "roster",
                    "configure",
                    "--preset",
                    "game-development",
                    "--consultant",
                    "art-director",
                    "--invocation-task-id",
                    coordinator,
                    "--yes",
                    "--json",
                ],
                self.state_home,
            )
        )
        self.assertEqual(changed["preset"], "game-development")
        agents = semantic_toml(self.target / ".codex/config.toml")["agents"]
        self.assertIn("consultant_art_director", agents)
        self.assertNotIn("consultant_product_designer", agents)
        self.assertEqual(
            agents["consultant_art_director"]["description"],
            "Provide recurring visual direction and art production readiness and acceptance.",
        )
        self.assertEqual(
            agents["consultant_art_director"]["config_file"],
            "../.baton/agents/consultant-art-director.toml",
        )

    def test_source_repository_preset_reconfigure_preserves_modified_codex_config(self) -> None:
        self.use_source_repository_topology()
        coordinator = self.bind_bootstrap_coordinator("source-modified-config-task")
        config = self.target / ".codex/config.toml"
        before = (ROOT / ".codex/config.toml").read_bytes() + b"\n# project-owned\n"
        config.write_bytes(before)
        team_before = (self.target / ".baton/state/team.json").read_bytes()
        memory_before = (self.target / ".baton/memory/memory.json").read_bytes()

        failed = baton(
            self.target,
            [
                "roster",
                "configure",
                "--preset",
                "game-development",
                "--consultant",
                "art-director",
                "--invocation-task-id",
                coordinator,
                "--yes",
                "--json",
            ],
            self.state_home,
            expected=1,
        )
        self.assertIn("modified source Codex config", failed.stdout + failed.stderr)
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(
            (self.target / ".baton/state/team.json").read_bytes(), team_before
        )
        self.assertEqual(
            (self.target / ".baton/memory/memory.json").read_bytes(), memory_before
        )

    def test_dashboard_workload_is_neutral_and_mobile_memory_header_stacks(self) -> None:
        dashboard = (self.target / ".baton/views/dashboard.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("Assignments by person", dashboard)
        self.assertIn(
            "Counts describe current work only. They are not a performance score or ranking.",
            dashboard,
        )
        self.assertNotIn("Highest completion", dashboard)
        self.assertNotIn("Lowest completion", dashboard)
        self.assertNotIn("Completion by person", dashboard)
        self.assertNotIn("Assignment share", dashboard)
        self.assertNotIn("b.rate-a.rate", dashboard)
        self.assertIn(
            "@media(max-width:760px){.company-subheading{align-items:start;display:grid;grid-template-columns:1fr}",
            dashboard,
        )
        self.assertIn("@media(prefers-reduced-motion:reduce)", dashboard)
        self.assertIn("browserHistory=globalThis.history", dashboard)
        self.assertIn("workforceRoleKey=person=>['Management','Operations']", dashboard)

    def test_dashboard_projects_neutral_personnel_outcomes_and_source_provenance(self) -> None:
        records = {
            name: json.loads(
                (self.target / f".baton/state/{name}.json").read_text(encoding="utf-8")
            )
            for name in ("project", "goals", "tickets", "ownership", "reviews", "team")
        }
        projection = json.loads(
            (ROOT / "tests/fixtures/dashboard-personnel-projection.json").read_text(
                encoding="utf-8"
            )
        )
        for person in projection["personnel"]:
            for summary in person["performanceSummaries"]:
                self.assertTrue(summary["sourceClasses"])
                self.assertTrue(summary["evidencePaths"])
        dashboard = harness_state.render_dashboard(records, projection)
        for value in (
            "active",
            "awaiting-task",
            "former",
            "rehired",
            "assignmentTypes",
            "recentOutcomes",
            "performanceSummaries",
            "explicit-user",
            "management-assessment",
            "operational-evidence",
            "self-reflection",
            "Evidence links",
            "Self Reflection · Unverified",
        ):
            self.assertIn(value, dashboard)
        self.assertIn("summary.sourceClasses", dashboard)
        self.assertIn("evidenceLinks(summary.evidencePaths)", dashboard)
        self.assertNotIn("leaderboard", dashboard.casefold())

    def test_consultant_hire_and_fire_recover_process_death_between_memory_files(self) -> None:
        memory_path = self.target / ".baton/memory/memory.json"
        history_path = self.target / ".baton/memory/history.jsonl"
        memory_before = memory_path.read_bytes()
        history_before = history_path.read_bytes()

        baton(
            self.target,
            ["roster", "hire", "--consultant", "security-lead", "--yes", "--json"],
            self.state_home,
            expected=97,
            extra_env={
                "BATON_TEST_TEAM_EXIT_AFTER": ".baton/memory/history.jsonl",
            },
        )

        self.assertEqual(memory_path.read_bytes(), memory_before)
        self.assertNotEqual(history_path.read_bytes(), history_before)
        reports = list(self.state_home.rglob("team-report.json"))
        self.assertEqual(len(reports), 1)
        interrupted_report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(interrupted_report["result"], "prepared")
        self.assertTrue(Path(interrupted_report["backupPath"]).is_dir())
        self.assertEqual(
            interrupted_report["rollbackLocation"],
            interrupted_report["backupPath"],
        )

        recovered = json_output(
            baton(
                self.target,
                ["roster", "hire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )
        self.assertEqual(recovered["memoryRevision"], 1)
        recovered_report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(recovered_report["result"], "rolled-back-recovered")
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        history = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(memory["revision"], 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["revision"], 1)

        memory_before_fire = memory_path.read_bytes()
        history_before_fire = history_path.read_bytes()
        baton(
            self.target,
            ["roster", "fire", "--consultant", "security-lead", "--yes", "--json"],
            self.state_home,
            expected=97,
            extra_env={
                "BATON_TEST_TEAM_EXIT_AFTER": ".baton/memory/history.jsonl",
            },
        )
        self.assertEqual(memory_path.read_bytes(), memory_before_fire)
        self.assertNotEqual(history_path.read_bytes(), history_before_fire)
        prepared_reports = [
            path
            for path in self.state_home.rglob("team-report.json")
            if json.loads(path.read_text(encoding="utf-8"))["result"] == "prepared"
        ]
        self.assertEqual(len(prepared_reports), 1)

        fired = json_output(
            baton(
                self.target,
                ["roster", "fire", "--consultant", "security-lead", "--yes", "--json"],
                self.state_home,
            )
        )
        self.assertEqual(fired["memoryRevision"], 2)
        fire_report = json.loads(
            prepared_reports[0].read_text(encoding="utf-8")
        )
        self.assertEqual(fire_report["result"], "rolled-back-recovered")
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        history = [
            json.loads(line)
            for line in history_path.read_text(encoding="utf-8").splitlines()
        ]
        remembered = next(
            person
            for person in memory["personnel"]
            if person["role"] == "Consultant" and person["seat"] == "security-lead"
        )
        self.assertEqual(memory["revision"], 2)
        self.assertEqual(len(history), 2)
        self.assertEqual(remembered["employmentStatus"], "former")
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_memory_transaction_refreshes_generated_views_and_rolls_them_back_together(self) -> None:
        command = self.base / f"{self.target.name}-memory.json"
        command.write_text(
            json.dumps(
                {
                    "operation": "remember",
                    "actor": "User",
                    "actorId": "user",
                    "expectedRevision": 0,
                    "idempotencyKey": "state-team-memory-1",
                    "timestamp": "2026-07-15T13:00:00+00:00",
                    "category": "company",
                    "subject": "company",
                    "statement": "The company favors small, verifiable releases.",
                    "sourceClass": "explicit-user",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        applied = json_output(
            baton(
                self.target,
                ["boot", "record", command, "--json"],
                self.state_home,
            )
        )
        self.assertEqual(applied["revision"], 1)
        self.assertIn(".baton/views/dashboard.html", applied["generatedViews"])
        self.assertTrue(Path(applied["backupPath"], "dashboard.html").is_file())
        dashboard = (self.target / ".baton/views/dashboard.html").read_bytes()
        metadata = (self.target / ".baton/metadata.json").read_bytes()
        memory = (self.target / ".baton/memory/memory.json").read_bytes()
        history = (self.target / ".baton/memory/history.jsonl").read_bytes()
        self.assertIn(b"Company memory", dashboard)
        self.assertNotIn(b"small, verifiable releases", dashboard)
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

        failing = self.base / f"{self.target.name}-memory-failure.json"
        failing.write_text(
            json.dumps(
                {
                    "operation": "remember",
                    "actor": "User",
                    "actorId": "user",
                    "expectedRevision": 1,
                    "idempotencyKey": "state-team-memory-2",
                    "timestamp": "2026-07-15T13:01:00+00:00",
                    "category": "company",
                    "subject": "company",
                    "statement": "This transaction must roll back.",
                    "sourceClass": "explicit-user",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        failed = baton(
            self.target,
            ["boot", "record", failing, "--json"],
            self.state_home,
            expected=1,
            extra_env={"BATON_TEST_MEMORY_FAIL_AT": "after-generated"},
        )
        self.assertIn("rolled back", failed.stdout + failed.stderr)
        self.assertEqual((self.target / ".baton/views/dashboard.html").read_bytes(), dashboard)
        self.assertEqual((self.target / ".baton/metadata.json").read_bytes(), metadata)
        self.assertEqual((self.target / ".baton/memory/memory.json").read_bytes(), memory)
        self.assertEqual((self.target / ".baton/memory/history.jsonl").read_bytes(), history)
        self.assertEqual(
            baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode,
            0,
        )

    def test_codex_contract_accepts_exact_nested_agent_semantics(self) -> None:
        config = self.target / ".codex/config.toml"
        self.assertEqual(semantic_toml(config), expected_consumer_config())
        expected_names = [
            "management",
            "operations",
            "contractor",
            "internal_audit",
            "consultant_product_designer",
        ]
        contract_script = (
            "import sys; from pathlib import Path; "
            f"sys.path.insert(0, {str(self.target / '.baton/lib')!r}); "
            "from codex_config_contract import assert_codex_config; "
            f"assert_codex_config(Path({str(config)!r}), {expected_names!r})"
        )
        run([sys.executable, "-c", contract_script], cwd=self.target)

    def test_discovery_uses_individual_links_and_never_codex_skills_or_bytecode(self) -> None:
        self.assertFalse((self.target / ".codex/skills").exists())
        self.assertFalse((self.target / ".codex/skills").is_symlink())
        actual = {path.name for path in (self.target / ".agents/skills").iterdir()}
        self.assertEqual(actual, set(SKILLS))
        for name in SKILLS:
            link = self.target / ".agents/skills" / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (self.target / ".baton/skills" / name).resolve())
        self.assertEqual(baton(self.target, ["terminal", "status", "--json"], self.state_home).returncode, 0)
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)
        assert_no_python_cache(self.target)

    def test_cross_process_mutations_share_one_lock_without_lost_team_updates(self) -> None:
        environment = dict(os.environ)
        environment.update(
            {
                "BATON_PROJECT_ROOT": str(self.target),
                "HOME": str(self.base / "lock-home"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_STATE_HOME": str(self.state_home),
            }
        )
        first_environment = dict(environment)
        first_environment["BATON_TEST_HOLD_MUTATION_LOCK_MS"] = "700"
        command = [
            str(self.target / ".baton/bin/baton"),
            "roster",
            "hire",
            "--yes",
            "--json",
            "--consultant",
        ]
        first = subprocess.Popen(
            [*command, "security-lead"],
            cwd=str(self.target),
            env=first_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        project_id = hashlib.sha256(str(self.target.resolve()).encode("utf-8")).hexdigest()[:16]
        lock_path = Path("/tmp") / f"baton-{os.getuid()}" / project_id / "mutation.lock"
        deadline = time.monotonic() + 5
        acquired = False
        while time.monotonic() < deadline:
            try:
                record = json.loads(lock_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                time.sleep(0.02)
                continue
            if (
                record.get("operation") == "team-hire_consultant"
                and first.poll() is None
            ):
                acquired = True
                break
            time.sleep(0.02)
        self.assertTrue(acquired, "first process never acquired the shared mutation lock")

        second_started = time.monotonic()
        second = subprocess.Popen(
            [*command, "accessibility-lead"],
            cwd=str(self.target),
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        first_stdout, first_stderr = first.communicate(timeout=15)
        second_stdout, second_stderr = second.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
        self.assertEqual(second.returncode, 0, second_stdout + second_stderr)
        self.assertGreaterEqual(time.monotonic() - second_started, 0.35)

        team = json.loads((self.target / ".baton/state/team.json").read_text(encoding="utf-8"))
        active = [item["id"] for item in team["consultants"] if item["status"] == "active"]
        self.assertEqual(
            active,
            ["product-designer", "security-lead", "accessibility-lead"],
        )
        self.assertEqual(
            semantic_toml(self.target / ".codex/config.toml"),
            expected_consumer_config(tuple(active)),
        )
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)
        assert_no_python_cache(self.target)

    def test_full_goal_controls_do_not_revive_legacy_persistent_goal_onboarding(self) -> None:
        regression_fixture = {
            "availableGoalControls": ["create_goal", "get_goal", "update_goal"],
            "legacyOnboardingPrompt": (
                "Create a persistent goal for this permanent role and rely on automatic continuation."
            ),
            "automaticContinuation": True,
            "newTaskMessage": False,
            "expectedAction": "perform no work and report the legacy continuation",
        }
        self.assertEqual(
            regression_fixture["availableGoalControls"],
            ["create_goal", "get_goal", "update_goal"],
        )
        thread_registry = (self.target / ".baton/views/team-tasks.md").read_text(
            encoding="utf-8"
        )
        lifecycle_rule = (self.target / ".baton/rules/lifecycle.md").read_text(
            encoding="utf-8"
        )
        policy = (thread_registry + "\n" + lifecycle_rule).casefold()
        for expected in (
            "sole wake event",
            "persistent goals are not role identity or lifecycle",
            "never create, resume, recreate, inspect for control, or attach one",
            "automatic continuation without a new task message",
            "performs no work",
        ):
            self.assertIn(expected, policy)
        goals_path = self.target / ".baton/state/goals.json"
        goals_before = goals_path.read_bytes()
        self.assertEqual(json.loads(goals_before)["goals"], [])
        self.assertEqual(baton(self.target, ["terminal", "status", "--json"], self.state_home).returncode, 0)
        self.assertEqual(baton(self.target, ["doctor", "check", "--json"], self.state_home).returncode, 0)
        self.assertEqual(goals_path.read_bytes(), goals_before)
        self.assertEqual(
            regression_fixture["expectedAction"],
            "perform no work and report the legacy continuation",
        )


if __name__ == "__main__":
    unittest.main()
