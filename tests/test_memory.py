#!/usr/bin/env python3
"""Focused behavior tests for Baton's project-local memory module."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "template/.baton/lib"
sys.path.insert(0, str(LIB))

import baton_memory  # noqa: E402
import harness_team  # noqa: E402


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="baton-memory-tests-")
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        (self.project / ".baton").mkdir(parents=True)
        shutil.copytree(ROOT / "template/.baton/memory", self.project / ".baton/memory")
        shutil.copytree(ROOT / "template/.baton/schemas", self.project / ".baton/schemas")
        shutil.copytree(ROOT / "template/.baton/state", self.project / ".baton/state")
        views = self.project / ".baton/views"
        views.mkdir()
        (views / "dashboard.html").write_text("<!doctype html><title>Baton</title>\n", encoding="utf-8")
        shutil.copy2(
            ROOT / "template/.baton/views/team-tasks.md",
            views / "team-tasks.md",
        )
        shutil.copy2(
            ROOT / "template/.baton/team-presets.json",
            self.project / ".baton/team-presets.json",
        )
        harness_team.initialize_team(
            project_root=self.project,
            preset_id="software-product",
            selected=[],
            reasoning={
                "management": "inherit",
                "operations": "inherit",
                "consultants": "inherit",
                "contractors": "inherit",
                "internalAudit": "inherit",
            },
        )
        self.state_home = self.base / "state"
        self.environment = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.state_home)}, clear=False)
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def command(self, operation: str, revision: int, **values):
        result = {
            "operation": operation,
            "actor": "User",
            "actorId": "user",
            "expectedRevision": revision,
            "idempotencyKey": "%s-%s" % (operation, revision),
            "timestamp": "2026-07-15T12:%02d:00+00:00" % revision,
        }
        result.update(values)
        return result

    def snapshot(self):
        return json.loads((self.project / ".baton/memory/memory.json").read_text(encoding="utf-8"))

    def history(self):
        return [json.loads(line) for line in (self.project / ".baton/memory/history.jsonl").read_text(encoding="utf-8").splitlines()]

    def remember(self, revision=0, **values):
        defaults = {
            "category": "company",
            "subject": "company",
            "statement": "The company builds dependable tools.",
            "sourceClass": "explicit-user",
        }
        defaults.update(values)
        return baton_memory.transact(self.project, self.command("remember", revision, **defaults))

    def person(self, revision=0, **values):
        defaults = {"action": "ensure", "role": "Management", "seat": "Management", "specialty": "", "seed": "project-seed:management"}
        defaults.update(values)
        return baton_memory.transact(self.project, self.command("personnel", revision, **defaults))

    def confirm_project_intent(
        self,
        revision=0,
        *,
        seed="project-seed",
        preset="software-product",
        consultant_seats=None,
        identity="Baton",
    ):
        consultant_seats = list(consultant_seats or [])
        baton_memory.transact(
            self.project,
            self.command("bootstrap", revision, action="start", seed=seed),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                revision + 1,
                action="project-preset",
                preset=preset,
                consultantSeats=consultant_seats,
                userApproved=True,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                revision + 2,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                revision + 3,
                action="provisional",
                project={
                    "identity": identity,
                    "purpose": "Create a dependable project.",
                    "users": "The intended users.",
                    "outcome": "A useful maintained result.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                revision + 4,
                action="confirm",
                userApproved=True,
            ),
        )
        return revision + 5

    def test_starter_records_validate_with_revision_zero_and_empty_history(self):
        result = baton_memory.inspect(self.project)
        self.assertEqual(result["revision"], 0)
        self.assertEqual(result["confirmed"], [])
        snapshot = self.snapshot()
        self.assertEqual(snapshot["historyHead"]["sha256"], hashlib.sha256(b"").hexdigest())
        self.assertEqual((self.project / ".baton/memory/history.jsonl").read_bytes(), b"")

    def test_explicit_initialization_is_atomic_collision_safe_and_preserves_existing_memory(self):
        memory_path = self.project / ".baton/memory/memory.json"
        history_path = self.project / ".baton/memory/history.jsonl"
        metadata_path = self.project / ".baton/metadata.json"
        metadata_path.write_text(
            json.dumps({"managedFiles": {}, "projectOwnedFiles": []}) + "\n",
            encoding="utf-8",
        )
        memory_path.unlink()
        history_path.unlink()

        initialized = baton_memory.initialize(self.project)
        self.assertTrue(initialized["changed"])
        self.assertEqual(self.snapshot()["revision"], 0)
        self.assertEqual(history_path.read_bytes(), b"")
        self.assertTrue(Path(initialized["reportPath"]).is_file())
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(
            metadata["projectOwnedFiles"],
            [".baton/memory/history.jsonl", ".baton/memory/memory.json"],
        )
        self.assertFalse(
            set(metadata["projectOwnedFiles"]).intersection(metadata["managedFiles"])
        )

        replay = baton_memory.initialize(self.project)
        self.assertFalse(replay["changed"])
        remembered = self.remember()
        memory_before = memory_path.read_bytes()
        history_before = history_path.read_bytes()
        preserved = baton_memory.initialize(self.project)
        self.assertFalse(preserved["changed"])
        self.assertEqual(memory_path.read_bytes(), memory_before)
        self.assertEqual(history_path.read_bytes(), history_before)
        self.assertEqual(preserved["revision"], remembered["revision"])

        history_path.unlink()
        with self.assertRaisesRegex(baton_memory.MemoryError, "collision"):
            baton_memory.initialize(self.project)
        self.assertEqual(memory_path.read_bytes(), memory_before)

    def test_source_repository_initialization_accepts_only_exact_schema_projection(self):
        memory_path = self.project / ".baton/memory/memory.json"
        history_path = self.project / ".baton/memory/history.jsonl"
        metadata_path = self.project / ".baton/metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "installationStatus": "Source Repository",
                    "managedFiles": {},
                    "projectOwnedFiles": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        projected = self.project / "template/.baton/schemas"
        projected.parent.mkdir(parents=True)
        shutil.move(self.project / ".baton/schemas", projected)
        (self.project / ".baton/schemas").symlink_to("../template/.baton/schemas")
        memory_path.unlink()
        history_path.unlink()

        initialized = baton_memory.initialize(self.project)
        self.assertTrue(initialized["changed"])
        self.assertEqual(self.snapshot()["revision"], 0)

        memory_path.unlink()
        history_path.unlink()
        (self.project / ".baton/schemas").unlink()
        alternate = self.project / "alternate-schemas"
        shutil.copytree(projected, alternate)
        (self.project / ".baton/schemas").symlink_to("../alternate-schemas")
        with self.assertRaisesRegex(
            baton_memory.MemoryError,
            "requires installed memory schemas",
        ):
            baton_memory.initialize(self.project)
        self.assertFalse(memory_path.exists())
        self.assertFalse(history_path.exists())

    def test_failed_explicit_initialization_removes_partial_files(self):
        memory_path = self.project / ".baton/memory/memory.json"
        history_path = self.project / ".baton/memory/history.jsonl"
        metadata_path = self.project / ".baton/metadata.json"
        metadata_before = (
            json.dumps({"managedFiles": {}, "projectOwnedFiles": []}, indent=2) + "\n"
        ).encode("utf-8")
        metadata_path.write_bytes(metadata_before)
        memory_path.unlink()
        history_path.unlink()
        with mock.patch.dict(os.environ, {"BATON_TEST_MEMORY_INIT_FAIL_AT": "after-history"}, clear=False):
            with self.assertRaisesRegex(baton_memory.MemoryError, "rolled back"):
                baton_memory.initialize(self.project)
        self.assertFalse(memory_path.exists())
        self.assertFalse(history_path.exists())
        self.assertEqual(metadata_path.read_bytes(), metadata_before)

    def test_explicit_initialization_recovers_process_death_at_commit_boundary(self):
        memory_path = self.project / ".baton/memory/memory.json"
        history_path = self.project / ".baton/memory/history.jsonl"
        metadata_path = self.project / ".baton/metadata.json"
        metadata_path.write_text(
            json.dumps({"managedFiles": {}, "projectOwnedFiles": []}) + "\n",
            encoding="utf-8",
        )
        memory_path.unlink()
        history_path.unlink()
        environment = dict(os.environ)
        environment.update(
            {
                "BATON_PROJECT_ROOT": str(self.project),
                "BATON_TEST_MEMORY_INIT_EXIT_AFTER": "after-history",
                "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_STATE_HOME": str(self.state_home),
            }
        )
        interrupted = subprocess.run(
            [
                sys.executable,
                str(ROOT / "template/.baton/lib/baton_memory.py"),
                "initialize",
                "--json",
            ],
            cwd=self.project,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(interrupted.returncode, 98)
        self.assertFalse(memory_path.exists())
        self.assertTrue(history_path.is_file())
        recovered = baton_memory.initialize(self.project)
        self.assertTrue(recovered["changed"])
        reports = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.state_home.rglob("memory-report.json")
        ]
        self.assertIn("rolled-back-recovered", {report["result"] for report in reports})
        self.assertEqual(
            set(json.loads(metadata_path.read_text(encoding="utf-8"))["projectOwnedFiles"]),
            {".baton/memory/memory.json", ".baton/memory/history.jsonl"},
        )

        memory_path.unlink()
        history_path.unlink()
        metadata_path.write_text(
            json.dumps({"managedFiles": {}, "projectOwnedFiles": []}) + "\n",
            encoding="utf-8",
        )
        environment["BATON_TEST_MEMORY_INIT_EXIT_AFTER"] = "after-memory"
        interrupted = subprocess.run(
            [
                sys.executable,
                str(ROOT / "template/.baton/lib/baton_memory.py"),
                "initialize",
                "--json",
            ],
            cwd=self.project,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(interrupted.returncode, 98)
        self.assertTrue(memory_path.is_file())
        self.assertTrue(history_path.is_file())
        recovered = baton_memory.initialize(self.project)
        self.assertFalse(recovered["changed"])
        reports = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.state_home.rglob("memory-report.json")
        ]
        self.assertIn("committed-recovered", {report["result"] for report in reports})
        self.assertEqual(
            set(json.loads(metadata_path.read_text(encoding="utf-8"))["projectOwnedFiles"]),
            {".baton/memory/memory.json", ".baton/memory/history.jsonl"},
        )

    def test_cli_explicitly_initializes_absent_memory(self):
        (self.project / ".baton/memory/memory.json").unlink()
        (self.project / ".baton/memory/history.jsonl").unlink()
        environment = dict(os.environ)
        environment.update(
            {
                "BATON_PROJECT_ROOT": str(self.project),
                "PYTHONDONTWRITEBYTECODE": "1",
                "XDG_STATE_HOME": str(self.state_home),
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "template/.baton/lib/baton_memory.py"),
                "initialize",
                "--json",
            ],
            cwd=self.project,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["changed"])
        self.assertEqual(self.snapshot()["revision"], 0)

    def test_remember_commits_history_first_contract_and_is_idempotent(self):
        command = self.command(
            "remember",
            0,
            category="company",
            subject="purpose",
            statement="Build a generic project control plane.",
            sourceClass="explicit-user",
        )
        result = baton_memory.transact(self.project, command)
        self.assertEqual(result["revision"], 1)
        self.assertTrue(Path(result["reportPath"]).is_file())
        self.assertTrue(Path(result["backupPath"], "memory.json").is_file())
        duplicate = baton_memory.transact(self.project, command)
        self.assertTrue(duplicate["idempotent"])
        self.assertFalse(duplicate["changed"])
        self.assertEqual(self.snapshot()["revision"], 1)
        event = self.history()[0]
        self.assertNotIn("Build a generic", json.dumps(event))
        self.assertEqual(self.snapshot()["historyHead"]["sha256"], hashlib.sha256(baton_memory._line_bytes(event)).hexdigest())

    def test_idempotency_key_is_bound_to_request_semantics(self):
        command = self.command(
            "remember",
            0,
            category="company",
            subject="purpose",
            statement="Build a generic project control plane.",
            sourceClass="explicit-user",
            roleRelevance=["Operations", "Management"],
            assignmentTypes=["verification", "delivery"],
            references=["docs/evidence-b.md", "docs/evidence-a.md"],
        )
        first = baton_memory.transact(self.project, command)
        replay = dict(command)
        replay.update(
            {
                "expectedRevision": 999,
                "timestamp": "2026-07-16T09:00:00+00:00",
                "roleRelevance": ["Management", "Operations"],
                "assignmentTypes": ["delivery", "verification"],
                "references": ["docs/evidence-a.md", "docs/evidence-b.md"],
            }
        )
        self.assertTrue(baton_memory.transact(self.project, replay)["idempotent"])
        mismatch = dict(replay)
        mismatch["statement"] = "Reuse the key for different behavior."
        with self.assertRaisesRegex(baton_memory.MemoryError, "different request semantics"):
            baton_memory.transact(self.project, mismatch)
        self.assertEqual(self.snapshot()["revision"], first["revision"])

    def test_idempotency_normalizes_initial_claim_defaults(self):
        command = self.command(
            "remember",
            0,
            category="company",
            subject="purpose",
            statement="Keep semantic retries stable.",
            sourceClass="explicit-user",
        )
        baton_memory.transact(self.project, command)
        replay = dict(command)
        replay.update(
            {
                "expectedRevision": 99,
                "timestamp": "2026-07-16T09:00:00+00:00",
                "roleRelevance": list(reversed(baton_memory.ROLES)),
                "assignmentTypes": [],
                "importance": 3,
                "reference": "",
                "references": [],
            }
        )
        self.assertTrue(baton_memory.transact(self.project, replay)["idempotent"])

    def test_expected_revision_rejects_lost_update_without_changes(self):
        self.remember()
        before = (self.project / ".baton/memory/memory.json").read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "expected revision"):
            self.remember(0, statement="A stale write.", idempotencyKey="stale")
        self.assertEqual((self.project / ".baton/memory/memory.json").read_bytes(), before)

    def test_personal_inference_stays_pending_until_user_confirmation(self):
        candidate = baton_memory.transact(
            self.project,
            {
                **self.command("remember", 0),
                "actor": "Contractor",
                "actorId": "person-1",
                "category": "preference",
                "subject": "user",
                "statement": "The user may prefer concise updates.",
                "sourceClass": "personal-inference",
            },
        )
        claim_id = candidate["claimIds"][0]
        self.assertEqual(self.snapshot()["claims"][0]["status"], "pending-confirmation")
        context = baton_memory.select_context(self.project, {"role": "Operations"})
        self.assertEqual(context["claimIds"], [])
        confirmed = baton_memory.transact(self.project, self.command("confirm", 1, claimId=claim_id))
        self.assertEqual(confirmed["result"], "confirmed")
        self.assertEqual(self.snapshot()["claims"][0]["status"], "confirmed")

    def test_internal_audit_is_read_only_and_contractor_cannot_confirm(self):
        command = self.command("candidate", 0, category="company", subject="x", statement="An observation.", sourceClass="self-reflection")
        command.update({"actor": "Internal Audit", "actorId": "audit"})
        with self.assertRaisesRegex(baton_memory.MemoryError, "read-only"):
            baton_memory.transact(self.project, command)
        command.update({"actor": "Contractor", "actorId": "contractor"})
        candidate = baton_memory.transact(self.project, command)
        confirm = self.command("confirm", 1, claimId=candidate["claimIds"][0])
        confirm.update({"actor": "Contractor", "actorId": "contractor"})
        with self.assertRaisesRegex(baton_memory.MemoryError, "confirmation requires"):
            baton_memory.transact(self.project, confirm)

    def test_secret_and_sensitive_rejection_never_echoes_or_writes(self):
        secret = "password=do-not-repeat-this"
        before_memory = (self.project / ".baton/memory/memory.json").read_bytes()
        before_history = (self.project / ".baton/memory/history.jsonl").read_bytes()
        with self.assertRaises(baton_memory.MemoryError) as caught:
            self.remember(statement=secret)
        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual((self.project / ".baton/memory/memory.json").read_bytes(), before_memory)
        self.assertEqual((self.project / ".baton/memory/history.jsonl").read_bytes(), before_history)
        self.assertFalse(self.state_home.exists())

    def test_correct_supersedes_without_duplicate_active_claim(self):
        first = self.remember()
        corrected = baton_memory.transact(
            self.project,
            self.command("correct", 1, claimId=first["claimIds"][0], statement="The company builds safe tools."),
        )
        self.assertEqual(corrected["result"], "corrected")
        claims = self.snapshot()["claims"]
        self.assertEqual([item["status"] for item in claims], ["superseded", "confirmed"])
        self.assertEqual(claims[1]["supersedesClaimId"], claims[0]["id"])

    def test_forget_removes_claim_redacts_history_and_warns_about_git(self):
        first = self.remember(statement="A value to remove everywhere.")
        history_path = self.project / ".baton/memory/history.jsonl"
        event = self.history()[0]
        event["references"] = ["A value to remove everywhere."]
        history_path.write_bytes(baton_memory._line_bytes(event))
        snapshot = self.snapshot()
        snapshot["historyHead"]["sha256"] = hashlib.sha256(history_path.read_bytes()).hexdigest()
        (self.project / ".baton/memory/memory.json").write_bytes(baton_memory._json_bytes(snapshot))
        result = baton_memory.transact(self.project, self.command("forget", 1, claimIds=first["claimIds"]))
        self.assertEqual(self.snapshot()["claims"], [])
        self.assertNotIn("A value to remove", history_path.read_text(encoding="utf-8"))
        self.assertIn("Git commits may retain", result["warning"])
        self.assertIn("[redacted]", history_path.read_text(encoding="utf-8"))

    def test_personnel_identity_name_and_style_are_stable_from_seed(self):
        first = self.person()
        person = self.snapshot()["personnel"][0]
        self.confirm_project_intent(1, seed="project-seed")
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            {"list": True, "create": True, "stableIdentity": True, "read": True, "message": True, "title": True, "archive": True},
            {
                "seed": "project-seed",
                "seats": [{"role": "Management", "seat": "Management"}],
                "liveTasks": [],
            },
        )
        self.assertEqual(plan["plan"][0]["personnelId"], first["personnelIds"][0])
        self.assertEqual(plan["plan"][0]["name"], person["name"])
        self.assertEqual(plan["plan"][0]["workingStyle"], person["workingStyle"])
        self.assertEqual(plan["plan"][0]["taskAction"], "create")

    def test_confirmed_native_bootstrap_persists_ordered_roster_before_creation(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        self.confirm_project_intent(seed="native-project")
        live_tasks = []
        observations = {
            "seed": "native-project",
            "actor": "Operations",
            "actorId": "different-caller-must-not-change-bootstrap-semantics",
            "seats": [
                {"role": "Operations", "seat": "Operations"},
                {"role": "Management", "seat": "Management"},
            ],
            "liveTasks": live_tasks,
        }
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            observations,
        )
        self.assertEqual(
            [item["role"] for item in plan["plan"]],
            ["Management", "Operations"],
        )
        self.assertEqual(
            [item["taskAction"] for item in plan["plan"]],
            ["create", "wait-for-prior"],
        )
        snapshot = self.snapshot()
        self.assertEqual(snapshot["revision"], 6)
        self.assertEqual(
            snapshot["bootstrap"]["roster"],
            [item["personnelId"] for item in plan["plan"]],
        )
        self.assertEqual(
            [person["role"] for person in snapshot["personnel"]],
            ["Management", "Operations"],
        )
        memory_before_direct_register = (
            self.project / ".baton/memory/memory.json"
        ).read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "created checkpoint"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    6,
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=plan["plan"][0]["personnelId"],
                    taskId="management-task",
                    wakePath="message:management-task",
                    observedTitle=plan["plan"][0]["taskTitle"],
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            memory_before_direct_register,
        )
        live_tasks.append(
            {
                "taskId": "management-task",
                "wakePath": "message:management-task",
                "title": plan["plan"][0]["taskTitle"],
                "attemptId": plan["plan"][0]["attemptId"],
            }
        )
        created_management = baton_memory.transact(
            self.project,
            self.command(
                "task",
                6,
                actor="Operations",
                actorId="ops",
                action="created",
                personnelId=plan["plan"][0]["personnelId"],
                attemptId=plan["plan"][0]["attemptId"],
                taskId="management-task",
                wakePath="message:management-task",
            ),
        )
        with self.assertRaisesRegex(baton_memory.MemoryError, "verified title"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    created_management["revision"],
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=plan["plan"][0]["personnelId"],
                    taskId="management-task",
                    wakePath="message:management-task",
                    observedTitle="wrong title",
                ),
            )
        registered_management = baton_memory.transact(
            self.project,
            self.command(
                "task",
                created_management["revision"],
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=plan["plan"][0]["personnelId"],
                taskId="management-task",
                wakePath="message:management-task",
                observedTitle=plan["plan"][0]["taskTitle"],
            ),
        )
        waiting_for_wake = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            observations,
        )
        self.assertEqual(
            [item["taskAction"] for item in waiting_for_wake["plan"]],
            ["wake", "wait-for-prior"],
        )
        self.assertFalse(waiting_for_wake["deliveryReady"])
        online_management = baton_memory.transact(
            self.project,
            self.command(
                "task",
                registered_management["revision"],
                actor="Operations",
                actorId="ops",
                action="online",
                personnelId=plan["plan"][0]["personnelId"],
            ),
        )
        after_management = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        operations = after_management["plan"][1]
        self.assertEqual(operations["taskAction"], "create")
        live_tasks.append(
            {
                "taskId": "operations-task",
                "wakePath": "message:operations-task",
                "title": operations["taskTitle"],
                "attemptId": operations["attemptId"],
            }
        )
        created_operations = baton_memory.transact(
            self.project,
            self.command(
                "task",
                online_management["revision"],
                actor="Operations",
                actorId="ops",
                action="created",
                personnelId=operations["personnelId"],
                attemptId=operations["attemptId"],
                taskId="operations-task",
                wakePath="message:operations-task",
            ),
        )
        registered_operations = baton_memory.transact(
            self.project,
            self.command(
                "task",
                created_operations["revision"],
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=operations["personnelId"],
                taskId="operations-task",
                wakePath="message:operations-task",
                observedTitle=operations["taskTitle"],
            ),
        )
        online_operations = baton_memory.transact(
            self.project,
            self.command(
                "task",
                registered_operations["revision"],
                actor="Operations",
                actorId="ops",
                action="online",
                personnelId=operations["personnelId"],
            ),
        )
        replay = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            observations,
        )
        self.assertEqual(
            [item["taskAction"] for item in replay["plan"]],
            ["reuse", "reuse"],
        )
        self.assertTrue(replay["deliveryReady"])
        self.assertEqual(replay["revision"], online_operations["revision"])

    def test_interrupted_native_create_recovers_or_cleans_up_before_retry(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        seats = [{"role": "Management", "seat": "Management"}]
        self.confirm_project_intent(seed="recover-create", identity="Recovery Project")
        observations = {
            "seed": "recover-create",
            "seats": seats,
            "liveTasks": [],
        }
        initial = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        planned = initial["plan"][0]
        self.assertEqual(planned["taskAction"], "create")
        self.assertTrue(planned["attemptId"])

        duplicate_inventory = dict(
            observations,
            liveTasks=[
                {
                    "taskId": "duplicate-a",
                    "wakePath": "message:duplicate-a",
                    "title": "Provisioning task",
                    "attemptId": planned["attemptId"],
                },
                {
                    "taskId": "duplicate-b",
                    "wakePath": "message:duplicate-b",
                    "title": "Provisioning task",
                    "attemptId": planned["attemptId"],
                },
            ],
        )
        self.assertEqual(
            baton_memory.reconcile_bootstrap(
                self.project, capabilities, duplicate_inventory
            )["plan"][0]["taskAction"],
            "resolve-duplicate",
        )

        observations["liveTasks"] = [
            {
                "taskId": "recovered-task",
                "wakePath": "message:recovered-task",
                "title": "Provisioning task",
                "attemptId": planned["attemptId"],
            }
        ]
        recovered = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        self.assertEqual(recovered["plan"][0]["taskAction"], "recover-created")
        self.assertEqual(
            recovered["plan"][0]["recoveredTaskId"], "recovered-task"
        )
        created = baton_memory.transact(
            self.project,
            self.command(
                "task",
                recovered["revision"],
                actor="Operations",
                actorId="ops",
                action="created",
                personnelId=planned["personnelId"],
                attemptId=planned["attemptId"],
                taskId="recovered-task",
                wakePath="message:recovered-task",
            ),
        )
        missing_inventory = dict(observations, liveTasks=[])
        inspected = baton_memory.reconcile_bootstrap(
            self.project, capabilities, missing_inventory
        )
        self.assertEqual(inspected["plan"][0]["taskAction"], "inspect-created")
        cleanup = baton_memory.transact(
            self.project,
            self.command(
                "task",
                created["revision"],
                actor="Operations",
                actorId="ops",
                action="cleanup-required",
                personnelId=planned["personnelId"],
                reason="title update failed",
            ),
        )
        blocked = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        self.assertEqual(blocked["plan"][0]["taskAction"], "archive")
        self.assertEqual(
            baton_memory.reconcile_bootstrap(
                self.project, capabilities, observations
            )["plan"][0]["taskAction"],
            "archive",
        )
        archived = baton_memory.transact(
            self.project,
            self.command(
                "task",
                cleanup["revision"],
                actor="Operations",
                actorId="ops",
                action="archived",
                personnelId=planned["personnelId"],
                archiveConfirmed=True,
            ),
        )
        retry = baton_memory.reconcile_bootstrap(
            self.project, capabilities, missing_inventory
        )
        self.assertEqual(retry["revision"], archived["revision"])
        self.assertEqual(retry["plan"][0]["taskAction"], "create")
        self.assertNotEqual(retry["plan"][0]["attemptId"], planned["attemptId"])

    def test_bound_onboarding_rejects_every_wrong_task_mutation(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        bound = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "bound-project",
                "invocationTaskId": "task-A",
                "seats": [],
            },
        )
        memory_before = (self.project / ".baton/memory/memory.json").read_bytes()
        wrong_commands = [
            self.command(
                "bootstrap",
                bound["revision"],
                action="project-preset",
                invocationTaskId="task-B",
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
            self.command(
                "remember",
                bound["revision"],
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
                invocationTaskId="task-B",
            ),
            self.command(
                "bootstrap",
                bound["revision"],
                action="provisional",
                invocationTaskId="task-B",
                project={"identity": "Wrong task"},
            ),
            self.command(
                "bootstrap",
                bound["revision"],
                action="confirm",
                invocationTaskId="task-B",
                userApproved=True,
            ),
        ]
        for command in wrong_commands:
            with self.assertRaisesRegex(
                baton_memory.MemoryError, "original invoking task"
            ):
                baton_memory.transact(self.project, command)
            self.assertEqual(
                (self.project / ".baton/memory/memory.json").read_bytes(),
                memory_before,
            )

    def test_native_assembly_requires_created_order_and_provider_inventory(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        seats = [
            {"role": "Management", "seat": "Management"},
            {"role": "Operations", "seat": "Operations"},
        ]
        observations = {
            "seed": "ordered-provider-project",
            "seats": seats,
            "liveTasks": [],
        }
        self.confirm_project_intent(seed="ordered-provider-project")
        plan = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        management, operations = plan["plan"]
        self.assertEqual(
            [person["task"]["status"] for person in self.snapshot()["personnel"]],
            ["create-pending", "unregistered"],
        )

        memory_before = (self.project / ".baton/memory/memory.json").read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "created checkpoint"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    plan["revision"],
                    action="register",
                    personnelId=management["personnelId"],
                    taskId="management-task",
                    wakePath="message:management-task",
                    observedTitle=management["taskTitle"],
                ),
            )
        with self.assertRaisesRegex(baton_memory.MemoryError, "reserved"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    plan["revision"],
                    action="created",
                    personnelId=operations["personnelId"],
                    attemptId="unreserved-operations-attempt",
                    taskId="operations-task",
                    wakePath="message:operations-task",
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            memory_before,
        )

        provider_task = {
            "taskId": "management-task",
            "wakePath": "message:management-task",
            "title": management["taskTitle"],
            "attemptId": management["attemptId"],
        }
        created = baton_memory.transact(
            self.project,
            self.command(
                "task",
                plan["revision"],
                action="created",
                personnelId=management["personnelId"],
                attemptId=management["attemptId"],
                taskId=provider_task["taskId"],
                wakePath=provider_task["wakePath"],
            ),
        )
        registered = baton_memory.transact(
            self.project,
            self.command(
                "task",
                created["revision"],
                action="register",
                personnelId=management["personnelId"],
                taskId=provider_task["taskId"],
                wakePath=provider_task["wakePath"],
                observedTitle=provider_task["title"],
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                registered["revision"],
                action="online",
                personnelId=management["personnelId"],
            ),
        )

        missing = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        self.assertEqual(
            [item["taskAction"] for item in missing["plan"]],
            ["inspect-recorded", "wait-for-prior"],
        )
        self.assertFalse(missing["deliveryReady"])
        observations["liveTasks"] = [provider_task]
        verified = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        self.assertEqual(
            [item["taskAction"] for item in verified["plan"]],
            ["reuse", "create"],
        )

    def test_post_confirmation_task_mutations_remain_bound_to_invoking_task(self):
        coordinator = "bound-assembly-task"
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        observations = {
            "seed": "bound-assembly-project",
            "invocationTaskId": coordinator,
            "seats": [{"role": "Management", "seat": "Management"}],
            "liveTasks": [],
        }
        started = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                started["revision"],
                action="project-preset",
                invocationTaskId=coordinator,
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                2,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
                invocationTaskId=coordinator,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                3,
                action="provisional",
                invocationTaskId=coordinator,
                project={
                    "identity": "Bound Assembly Project",
                    "purpose": "Prove one-task assembly ownership.",
                    "users": "Project owners.",
                    "outcome": "A safely assembled team.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                4,
                action="confirm",
                invocationTaskId=coordinator,
                userApproved=True,
            ),
        )
        plan = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        management = plan["plan"][0]

        def reject_wrong_task(action, revision, **values):
            before = (self.project / ".baton/memory/memory.json").read_bytes()
            with self.assertRaisesRegex(
                baton_memory.MemoryError, "original invoking task"
            ):
                baton_memory.transact(
                    self.project,
                    self.command(
                        "task",
                        revision,
                        action=action,
                        invocationTaskId="different-task",
                        personnelId=management["personnelId"],
                        **values,
                    ),
                )
            self.assertEqual(
                (self.project / ".baton/memory/memory.json").read_bytes(), before
            )

        task_values = {
            "attemptId": management["attemptId"],
            "taskId": "bound-management-task",
            "wakePath": "message:bound-management-task",
        }
        reject_wrong_task("created", plan["revision"], **task_values)
        created = baton_memory.transact(
            self.project,
            self.command(
                "task",
                plan["revision"],
                action="created",
                invocationTaskId=coordinator,
                personnelId=management["personnelId"],
                **task_values,
            ),
        )
        reject_wrong_task(
            "register",
            created["revision"],
            taskId=task_values["taskId"],
            wakePath=task_values["wakePath"],
            observedTitle=management["taskTitle"],
        )
        registered = baton_memory.transact(
            self.project,
            self.command(
                "task",
                created["revision"],
                action="register",
                invocationTaskId=coordinator,
                personnelId=management["personnelId"],
                taskId=task_values["taskId"],
                wakePath=task_values["wakePath"],
                observedTitle=management["taskTitle"],
            ),
        )
        reject_wrong_task("online", registered["revision"])
        reject_wrong_task(
            "cleanup-required",
            registered["revision"],
            reason="provider wake failed",
        )

    def test_provisional_answers_cannot_overwrite_bootstrap_control_metadata(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        started = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "metadata-bound-project",
                "invocationTaskId": "metadata-task",
                "seats": [],
            },
        )
        before = (self.project / ".baton/memory/memory.json").read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "control metadata"):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    started["revision"],
                    action="provisional",
                    invocationTaskId="metadata-task",
                    project={
                        "identity": "Injected Project",
                        "coordinatorTaskId": "attacker-task",
                        "projectPresetConfirmed": True,
                    },
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(), before
        )

    def test_reset_allows_confirmed_incomplete_assembly_but_rejects_complete_team(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        seats = [{"role": "Management", "seat": "Management"}]
        self.confirm_project_intent(seed="confirmed-incomplete")
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {"seed": "confirmed-incomplete", "seats": seats, "liveTasks": []},
        )
        management = plan["plan"][0]
        created = baton_memory.transact(
            self.project,
            self.command(
                "task",
                plan["revision"],
                action="created",
                personnelId=management["personnelId"],
                attemptId=management["attemptId"],
                taskId="incomplete-management-task",
                wakePath="message:incomplete-management-task",
            ),
        )
        reset = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                created["revision"],
                action="reset-onboarding",
                userApproved=True,
                sourceClass="explicit-user",
            ),
        )
        self.assertEqual(reset["result"], "updated")
        self.assertEqual(
            self.snapshot()["bootstrap"]["cleanupTasks"][0]["taskId"],
            "incomplete-management-task",
        )

        complete_project = self.base / "complete-project"
        (complete_project / ".baton").mkdir(parents=True)
        shutil.copytree(
            ROOT / "template/.baton/memory", complete_project / ".baton/memory"
        )
        shutil.copytree(
            ROOT / "template/.baton/schemas", complete_project / ".baton/schemas"
        )
        shutil.copytree(
            ROOT / "template/.baton/state", complete_project / ".baton/state"
        )
        shutil.copytree(
            ROOT / "template/.baton/views", complete_project / ".baton/views"
        )
        (complete_project / ".baton/views/dashboard.html").write_text(
            "<!doctype html><title>Baton</title>\n", encoding="utf-8"
        )
        shutil.copy2(
            ROOT / "template/.baton/team-presets.json",
            complete_project / ".baton/team-presets.json",
        )
        harness_team.initialize_team(
            project_root=complete_project,
            preset_id="software-product",
            selected=[],
            reasoning={
                "management": "inherit",
                "operations": "inherit",
                "consultants": "inherit",
                "contractors": "inherit",
                "internalAudit": "inherit",
            },
        )
        commands = [
            self.command("bootstrap", 0, action="start", seed="complete-project"),
            self.command(
                "bootstrap",
                1,
                action="project-preset",
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
            self.command(
                "remember",
                2,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
            ),
            self.command(
                "bootstrap",
                3,
                action="provisional",
                project={
                    "identity": "Complete Project",
                    "purpose": "Prove complete onboarding cannot be reset here.",
                    "users": "Project owners.",
                    "outcome": "An online team.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
            self.command(
                "bootstrap", 4, action="confirm", userApproved=True
            ),
        ]
        for command in commands:
            baton_memory.transact(complete_project, command)
        fallback = baton_memory.reconcile_bootstrap(
            complete_project,
            {},
            {"seed": "complete-project", "seats": seats},
        )
        complete_management = fallback["plan"][0]
        registered = baton_memory.transact(
            complete_project,
            self.command(
                "task",
                fallback["revision"],
                action="register",
                personnelId=complete_management["personnelId"],
                taskId="complete-management-task",
                wakePath="message:complete-management-task",
                observedTitle=complete_management["taskTitle"],
            ),
        )
        online = baton_memory.transact(
            complete_project,
            self.command(
                "task",
                registered["revision"],
                action="online",
                personnelId=complete_management["personnelId"],
            ),
        )
        before_complete_reset = (
            complete_project / ".baton/memory/memory.json"
        ).read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "complete onboarding"):
            baton_memory.transact(
                complete_project,
                self.command(
                    "bootstrap",
                    online["revision"],
                    action="reset-onboarding",
                    userApproved=True,
                    sourceClass="explicit-user",
                ),
            )
        self.assertEqual(
            (complete_project / ".baton/memory/memory.json").read_bytes(),
            before_complete_reset,
        )

    def test_incomplete_intent_and_legacy_unbound_resume_fail_closed(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        bound = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "intent-project",
                "invocationTaskId": "intent-task",
                "seats": [],
            },
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                bound["revision"],
                action="project-preset",
                invocationTaskId="intent-task",
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
        )
        before = (self.project / ".baton/memory/memory.json").read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "project intent requires"):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    2,
                    action="provisional",
                    invocationTaskId="intent-task",
                    project={"identity": "Only a name"},
                    ready=True,
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(), before
        )

        other = self.base / "legacy-project"
        (other / ".baton").mkdir(parents=True)
        shutil.copytree(ROOT / "template/.baton/memory", other / ".baton/memory")
        shutil.copytree(ROOT / "template/.baton/schemas", other / ".baton/schemas")
        shutil.copy2(
            ROOT / "template/.baton/team-presets.json",
            other / ".baton/team-presets.json",
        )
        baton_memory.transact(
            other,
            self.command("bootstrap", 0, action="start", seed="legacy-partial"),
        )
        baton_memory.transact(
            other,
            self.command(
                "bootstrap",
                1,
                action="project-preset",
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
        )
        with self.assertRaisesRegex(baton_memory.MemoryError, "explicit reset"):
            baton_memory.reconcile_bootstrap(
                other,
                capabilities,
                {
                    "seed": "legacy-partial",
                    "invocationTaskId": "new-task",
                    "seats": [],
                },
            )

    def test_preset_selection_does_not_reactivate_a_legacy_consultant_task(self):
        consultant = self.person(
            role="Consultant",
            seat="product-designer",
            specialty="product and interaction design",
            seed="legacy-preset:Consultant:product-designer:product and interaction design",
        )
        consultant_id = consultant["personnelIds"][0]
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                1,
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=consultant_id,
                taskId="legacy-consultant-task",
                wakePath="message:legacy-consultant-task",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "personnel",
                2,
                action="fire",
                personnelId=consultant_id,
                userApproved=True,
            ),
        )
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        bound = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "legacy-preset",
                "invocationTaskId": "legacy-bootstrap-task",
                "seats": [],
            },
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                bound["revision"],
                action="project-preset",
                invocationTaskId="legacy-bootstrap-task",
                preset="software-product",
                consultantSeats=["product-designer"],
                userApproved=True,
            ),
        )
        person = self.snapshot()["personnel"][0]
        self.assertEqual(person["employmentStatus"], "former")
        self.assertEqual(person["task"]["status"], "inactive")
        self.assertEqual(
            baton_memory.inspect(self.project, {"section": "personnel"})[
                "personnel"
            ][0]["taskStatus"],
            "inactive",
        )

    def test_profile_mismatch_recommendation_is_durable_and_rejection_suppresses_repeats(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        coordinator = "profile-bootstrap-task"
        bound = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "profile-project",
                "invocationTaskId": coordinator,
                "seats": [],
            },
        )
        preset = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                bound["revision"],
                action="project-preset",
                invocationTaskId=coordinator,
                preset="software-product",
                consultantSeats=["product-designer"],
                userApproved=True,
            ),
        )
        evidence = [
            "The project is explicitly described as a cooperative game.",
            "The repository direction defines player-facing survival systems.",
        ]
        with self.assertRaisesRegex(
            baton_memory.MemoryError, "one to four concise evidence statements"
        ):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    preset["revision"],
                    idempotencyKey="profile-mismatch-too-little-project-evidence",
                    action="profile-mismatch",
                    invocationTaskId=coordinator,
                    recommendedPreset="game-development",
                    evidenceBasis="discoverable-project-facts",
                    evidence=evidence[:1],
                ),
            )
        with self.assertRaisesRegex(
            baton_memory.MemoryError, "listed recommended preset"
        ):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    preset["revision"],
                    idempotencyKey="profile-mismatch-unlisted",
                    action="profile-mismatch",
                    invocationTaskId=coordinator,
                    recommendedPreset="imaginary-project-profile",
                    evidenceBasis="discoverable-project-facts",
                    evidence=evidence,
                ),
            )
        proposed = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                preset["revision"],
                idempotencyKey="profile-mismatch-proposed",
                action="profile-mismatch",
                invocationTaskId=coordinator,
                recommendedPreset="game-development",
                evidenceBasis="discoverable-project-facts",
                evidence=evidence,
            ),
        )
        mismatch = self.snapshot()["bootstrap"]["provisionalProject"][
            "profileMismatch"
        ]
        self.assertEqual(mismatch["configuredPreset"], "software-product")
        self.assertEqual(mismatch["recommendedPreset"], "game-development")
        self.assertEqual(mismatch["evidenceBasis"], "discoverable-project-facts")
        self.assertEqual(mismatch["status"], "proposed")
        self.assertEqual(mismatch["evidence"], evidence)
        self.assertTrue(mismatch["evidenceFingerprint"])
        with self.assertRaisesRegex(
            baton_memory.MemoryError, "active profile recommendation"
        ):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    proposed["revision"],
                    idempotencyKey="profile-mismatch-active-overwrite",
                    action="profile-mismatch",
                    invocationTaskId=coordinator,
                    recommendedPreset="game-development",
                    evidenceBasis="discoverable-project-facts",
                    evidence=evidence
                    + ["Another repository fact appeared before the user answered."],
                ),
            )

        rejected = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                proposed["revision"],
                idempotencyKey="profile-mismatch-rejected",
                action="profile-mismatch",
                invocationTaskId=coordinator,
                recommendedPreset="game-development",
                recommendationStatus="rejected",
                userApproved=True,
            ),
        )
        self.assertEqual(
            self.snapshot()["bootstrap"]["provisionalProject"][
                "profileMismatch"
            ]["status"],
            "rejected",
        )
        rejected_fingerprint = self.snapshot()["bootstrap"][
            "provisionalProject"
        ]["profileMismatch"]["evidenceFingerprint"]
        self.assertIn(
            rejected_fingerprint,
            self.snapshot()["bootstrap"]["provisionalProject"][
                "rejectedProfileMismatchFingerprints"
            ],
        )
        before_repeat = (self.project / ".baton/memory/memory.json").read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "already rejected"):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    rejected["revision"],
                    idempotencyKey="profile-mismatch-repeated",
                    action="profile-mismatch",
                    invocationTaskId=coordinator,
                    recommendedPreset="game-development",
                    evidenceBasis="discoverable-project-facts",
                    evidence=evidence,
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            before_repeat,
        )
        with self.assertRaisesRegex(baton_memory.MemoryError, "already rejected"):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    rejected["revision"],
                    idempotencyKey="profile-mismatch-reordered",
                    action="profile-mismatch",
                    invocationTaskId=coordinator,
                    recommendedPreset="game-development",
                    evidenceBasis="discoverable-project-facts",
                    evidence=list(reversed(evidence)),
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            before_repeat,
        )

        alternate = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                rejected["revision"],
                idempotencyKey="profile-mismatch-alternate-proposed",
                action="profile-mismatch",
                invocationTaskId=coordinator,
                recommendedPreset="research",
                evidenceBasis="discoverable-project-facts",
                evidence=evidence,
            ),
        )
        alternate_rejected = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                alternate["revision"],
                idempotencyKey="profile-mismatch-alternate-rejected",
                action="profile-mismatch",
                invocationTaskId=coordinator,
                recommendedPreset="research",
                recommendationStatus="rejected",
                userApproved=True,
            ),
        )
        before_cross_repeat = (
            self.project / ".baton/memory/memory.json"
        ).read_bytes()
        with self.assertRaisesRegex(baton_memory.MemoryError, "already rejected"):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    alternate_rejected["revision"],
                    idempotencyKey="profile-mismatch-cross-repeat",
                    action="profile-mismatch",
                    invocationTaskId=coordinator,
                    recommendedPreset="game-development",
                    evidenceBasis="discoverable-project-facts",
                    evidence=evidence,
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            before_cross_repeat,
        )

        materially_changed = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                alternate_rejected["revision"],
                idempotencyKey="profile-mismatch-new-evidence",
                action="profile-mismatch",
                invocationTaskId=coordinator,
                recommendedPreset="game-development",
                evidenceBasis="discoverable-project-facts",
                evidence=evidence
                + ["The user confirmed that the intended outcome is playable."],
            ),
        )
        accepted = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                materially_changed["revision"],
                idempotencyKey="profile-mismatch-accepted",
                action="project-preset",
                invocationTaskId=coordinator,
                preset="game-development",
                consultantSeats=["art-director"],
                userApproved=True,
            ),
        )
        self.assertEqual(accepted["revision"], materially_changed["revision"] + 1)
        provisional = self.snapshot()["bootstrap"]["provisionalProject"]
        self.assertEqual(provisional["projectPreset"], "game-development")
        self.assertEqual(provisional["profileMismatch"]["status"], "accepted")
        self.assertTrue(provisional["profileMismatch"]["resolvedAt"])
        explicit = baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                accepted["revision"],
                idempotencyKey="profile-mismatch-explicit-user",
                action="profile-mismatch",
                invocationTaskId=coordinator,
                recommendedPreset="software-product",
                evidenceBasis="explicit-user",
                evidence=["The user explicitly says this is a software product."],
            ),
        )
        self.assertEqual(explicit["revision"], accepted["revision"] + 1)
        self.assertEqual(
            self.snapshot()["bootstrap"]["provisionalProject"]["profileMismatch"][
                "evidenceBasis"
            ],
            "explicit-user",
        )

    def test_project_preset_catalog_allows_only_the_contained_source_projection_symlink(self):
        source = self.base / "source-project"
        (source / ".baton").mkdir(parents=True)
        shutil.copytree(ROOT / "template/.baton/memory", source / ".baton/memory")
        shutil.copytree(ROOT / "template/.baton/schemas", source / ".baton/schemas")
        (source / "template/.baton").mkdir(parents=True)
        shutil.copy2(
            ROOT / "template/.baton/team-presets.json",
            source / "template/.baton/team-presets.json",
        )
        (source / ".baton/team-presets.json").symlink_to(
            "../template/.baton/team-presets.json"
        )
        (source / ".baton/metadata.json").write_text(
            json.dumps({"installationStatus": "Source Repository"}) + "\n",
            encoding="utf-8",
        )

        started = baton_memory.transact(
            source,
            self.command("bootstrap", 0, action="start", seed="source-project"),
        )
        selected = baton_memory.transact(
            source,
            self.command(
                "bootstrap",
                started["revision"],
                action="project-preset",
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
        )
        self.assertEqual(selected["revision"], 2)

        unexpected_catalog = source / "unexpected-team-presets.json"
        shutil.copy2(
            ROOT / "template/.baton/team-presets.json", unexpected_catalog
        )
        (source / ".baton/team-presets.json").unlink()
        (source / ".baton/team-presets.json").symlink_to(unexpected_catalog)
        with self.assertRaisesRegex(baton_memory.MemoryError, "safe project preset catalog"):
            baton_memory.transact(
                source,
                self.command(
                    "bootstrap",
                    selected["revision"],
                    action="profile-mismatch",
                    recommendedPreset="game-development",
                    evidenceBasis="explicit-user",
                    evidence=["The user explicitly says this is a game."],
                ),
            )

    def test_bootstrap_keeps_one_conversation_until_confirmed_then_titles_the_team(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        seats = [
            {"role": "Management", "seat": "Management"},
            {"role": "Operations", "seat": "Operations"},
            {
                "role": "Consultant",
                "seat": "product-designer",
                "id": "product-designer",
                "title": "Product Designer",
                "domain": "product and interaction design",
                "configPath": ".baton/agents/consultant-product-designer.toml",
                "acceptanceAuthority": "Accepts product-design work.",
                "status": "active",
            },
        ]
        conversation = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "quiet-project",
                "presetLabel": "Software Product",
                "invocationTaskId": "bootstrap-task-1",
                "seats": seats,
                "liveTasks": [],
            },
        )
        self.assertEqual(conversation["nextStep"], "confirm-project-preset")
        self.assertEqual(conversation["coordinatorTaskId"], "bootstrap-task-1")
        self.assertEqual(conversation["plan"], [])
        self.assertEqual(self.snapshot()["personnel"], [])
        self.assertEqual(
            conversation["publicStatus"]["question"],
            "Keep Software Product, or change it before I assemble the team?",
        )
        public = json.dumps(conversation["publicStatus"])
        self.assertNotIn("transaction", public.casefold())
        self.assertNotIn("backup", public.casefold())
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                1,
                action="project-preset",
                invocationTaskId="bootstrap-task-1",
                preset="software-product",
                consultantSeats=["product-designer"],
                userApproved=True,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                2,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
                invocationTaskId="bootstrap-task-1",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                3,
                action="provisional",
                invocationTaskId="bootstrap-task-1",
                project={
                    "identity": "X Hero Siege v2",
                    "purpose": "Build a cooperative action game.",
                    "users": "Players who enjoy team survival games.",
                    "outcome": "A playable and maintainable release.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Full Certification",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
        )
        before_confirmation = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "quiet-project",
                "presetLabel": "Software Product",
                "invocationTaskId": "bootstrap-task-1",
                "seats": seats,
            },
        )
        self.assertEqual(before_confirmation["nextStep"], "confirm-project-intent")
        self.assertEqual(
            before_confirmation["coordinatorTaskId"], "bootstrap-task-1"
        )
        self.assertEqual(before_confirmation["plan"], [])
        self.assertEqual(self.snapshot()["personnel"], [])
        with self.assertRaisesRegex(
            baton_memory.MemoryError, "original invoking task"
        ):
            baton_memory.reconcile_bootstrap(
                self.project,
                capabilities,
                {
                    "seed": "quiet-project",
                    "presetLabel": "Software Product",
                    "invocationTaskId": "different-bootstrap-task",
                    "seats": seats,
                    "liveTasks": [],
                },
            )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                before_confirmation["revision"],
                action="confirm",
                invocationTaskId="bootstrap-task-1",
                userApproved=True,
            ),
        )
        project = json.loads(
            (self.project / ".baton/state/project.json").read_text(encoding="utf-8")
        )["project"]
        self.assertEqual(project["name"], "X Hero Siege v2")
        self.assertEqual(project["purpose"], "Build a cooperative action game.")
        self.assertEqual(project["users"], ["Players who enjoy team survival games."])
        self.assertEqual(project["outcome"], "A playable and maintainable release.")
        self.assertEqual(project["constraints"], [])
        self.assertEqual(project["openQuestions"], [])
        self.assertEqual(
            project["assuranceDefaults"],
            {
                "readinessProtocol": "Full Certification",
                "clearanceProtocol": "Release Clearance",
            },
        )
        self.assertFalse(project["templateMode"])
        provisional = self.snapshot()["bootstrap"]["provisionalProject"]
        for field in (
            "identity",
            "purpose",
            "users",
            "outcome",
            "constraints",
            "unresolved",
            "readinessProtocol",
            "clearanceProtocol",
        ):
            self.assertNotIn(field, provisional)

        assembled = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "quiet-project",
                "presetLabel": "Software Product",
                "invocationTaskId": "bootstrap-task-1",
                "seats": seats,
                "liveTasks": [],
            },
        )
        self.assertEqual(assembled["nextStep"], "assemble-team")
        self.assertEqual(
            [item["taskTitle"] for item in assembled["plan"]],
            [
                "(X Hero Siege v2) - Management - %s" % assembled["plan"][0]["name"],
                "(X Hero Siege v2) - Operations - %s" % assembled["plan"][1]["name"],
                "(X Hero Siege v2) - Product Designer Consultant - %s"
                % assembled["plan"][2]["name"],
            ],
        )

    def test_one_conversation_trace_keeps_the_invoking_task_through_confirmation(self):
        task_id = "single-bootstrap-task"
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        seats = [
            {"role": "Management", "seat": "Management"},
            {"role": "Operations", "seat": "Operations"},
            {
                "role": "Consultant",
                "seat": "product-designer",
                "id": "product-designer",
                "title": "Product Designer",
                "domain": "product and interaction design",
                "configPath": ".baton/agents/consultant-product-designer.toml",
                "acceptanceAuthority": "Accepts product-design work.",
                "status": "active",
            },
        ]
        observations = {
            "seed": "trace-project",
            "presetLabel": "Software Product",
            "invocationTaskId": task_id,
            "seats": seats,
            "liveTasks": [],
        }
        trace = []

        step = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        trace.append((task_id, step["nextStep"], len(step["plan"])))
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                step["revision"],
                action="project-preset",
                invocationTaskId=task_id,
                preset="software-product",
                consultantSeats=["product-designer"],
                userApproved=True,
            ),
        )
        step = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        trace.append((task_id, step["nextStep"], len(step["plan"])))
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                step["revision"],
                actor="Management",
                actorId=task_id,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
                invocationTaskId=task_id,
                userApproved=True,
            ),
        )
        step = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        trace.append((task_id, step["nextStep"], len(step["plan"])))
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                step["revision"],
                actor="Management",
                actorId=task_id,
                action="provisional",
                invocationTaskId=task_id,
                project={
                    "identity": "Trace Project",
                    "purpose": "Prove one continuous onboarding conversation.",
                    "users": "Project owners.",
                    "outcome": "A confirmed project ready for team assembly.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
        )
        step = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        trace.append((task_id, step["nextStep"], len(step["plan"])))
        self.assertEqual(self.snapshot()["personnel"], [])
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                step["revision"],
                actor="Management",
                actorId=task_id,
                action="confirm",
                invocationTaskId=task_id,
                userApproved=True,
            ),
        )
        assembled = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        trace.append((task_id, assembled["nextStep"], len(assembled["plan"])))

        self.assertEqual(
            trace,
            [
                (task_id, "confirm-project-preset", 0),
                (task_id, "ask-preferred-name", 0),
                (task_id, "discover-project", 0),
                (task_id, "confirm-project-intent", 0),
                (task_id, "assemble-team", 3),
            ],
        )
        self.assertTrue(
            all(item[0] == assembled["coordinatorTaskId"] for item in trace)
        )
        self.assertEqual(
            [item["taskAction"] for item in assembled["plan"]],
            ["create", "wait-for-prior", "wait-for-prior"],
        )

        current = assembled
        for index, _ in enumerate(assembled["plan"]):
            planned = current["plan"][index]
            self.assertEqual(current["plan"][index]["taskAction"], "create")
            task_identity = "trace-task-%d" % index
            created = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    current["revision"],
                    actor="Operations",
                    actorId="bootstrap-operations",
                    action="created",
                    invocationTaskId=task_id,
                    personnelId=planned["personnelId"],
                    attemptId=planned["attemptId"],
                    taskId=task_identity,
                    wakePath="message:" + task_identity,
                ),
            )
            observations["liveTasks"].append(
                {
                    "taskId": task_identity,
                    "wakePath": "message:" + task_identity,
                    "title": planned["taskTitle"],
                    "attemptId": planned["attemptId"],
                }
            )
            current = baton_memory.reconcile_bootstrap(
                self.project, capabilities, observations
            )
            self.assertEqual(current["plan"][index]["taskAction"], "register")
            registered = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    created["revision"],
                    actor="Operations",
                    actorId="bootstrap-operations",
                    action="register",
                    invocationTaskId=task_id,
                    personnelId=planned["personnelId"],
                    taskId=task_identity,
                    wakePath="message:" + task_identity,
                    observedTitle=planned["taskTitle"],
                ),
            )
            current = baton_memory.reconcile_bootstrap(
                self.project, capabilities, observations
            )
            self.assertEqual(current["plan"][index]["taskAction"], "wake")
            failed_wake_retry = baton_memory.reconcile_bootstrap(
                self.project, capabilities, observations
            )
            self.assertEqual(failed_wake_retry["revision"], registered["revision"])
            self.assertEqual(
                failed_wake_retry["plan"][index]["taskAction"], "wake"
            )
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    registered["revision"],
                    actor="Operations",
                    actorId="bootstrap-operations",
                    action="online",
                    invocationTaskId=task_id,
                    personnelId=planned["personnelId"],
                ),
            )
            current = baton_memory.reconcile_bootstrap(
                self.project, capabilities, observations
            )
            self.assertEqual(current["plan"][index]["taskAction"], "reuse")

        self.assertEqual(current["nextStep"], "complete")
        self.assertTrue(current["deliveryReady"])
        self.assertEqual(
            [person["task"]["status"] for person in self.snapshot()["personnel"]],
            ["online", "online", "online"],
        )

    def test_confirmed_project_preset_keeps_discovery_in_one_task_without_mutating_legacy_consultants(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "resume-project",
                "presetLabel": "Software Product",
                "invocationTaskId": "resume-bootstrap-task",
                "seats": [],
            },
        )
        baton_memory.transact(
            self.project,
            self.command(
                "personnel",
                1,
                action="ensure",
                role="Consultant",
                seat="product-designer",
                specialty="product and interaction design",
                seed="resume-project:Consultant:product-designer:product and interaction design",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                2,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
                invocationTaskId="resume-bootstrap-task",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                3,
                action="project-preset",
                invocationTaskId="resume-bootstrap-task",
                preset="game-development",
                consultantSeats=["art-director"],
                userApproved=True,
            ),
        )
        snapshot = self.snapshot()
        self.assertEqual(
            snapshot["bootstrap"]["provisionalProject"]["projectPreset"],
            "game-development",
        )
        self.assertTrue(
            snapshot["bootstrap"]["provisionalProject"]["projectPresetConfirmed"]
        )
        self.assertEqual(snapshot["bootstrap"]["roster"], [])
        old_consultant = next(
            person for person in snapshot["personnel"] if person["seat"] == "product-designer"
        )
        self.assertEqual(old_consultant["employmentStatus"], "active")
        self.assertEqual(old_consultant["task"]["status"], "unregistered")
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                4,
                action="provisional",
                invocationTaskId="resume-bootstrap-task",
                project={
                    "identity": "A New Game",
                    "purpose": "Create a game.",
                    "users": "Players.",
                    "outcome": "A playable game.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
        )
        resumed = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "resume-project",
                "presetLabel": "Game Development",
                "invocationTaskId": "resume-bootstrap-task",
                "seats": [],
            },
        )
        self.assertEqual(resumed["nextStep"], "confirm-project-intent")
        self.assertEqual(resumed["plan"], [])
        self.assertEqual(
            [person["seat"] for person in self.snapshot()["personnel"]],
            ["product-designer"],
        )

    def test_interrupted_post_confirmation_assembly_reconciles_and_registers_the_complete_team(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        seats = [
            {"role": "Management", "seat": "Management"},
            {"role": "Operations", "seat": "Operations"},
            {
                "role": "Consultant",
                "seat": "product-designer",
                "id": "product-designer",
                "title": "Product Designer",
                "domain": "product and interaction design",
                "configPath": ".baton/agents/consultant-product-designer.toml",
                "acceptanceAuthority": "Accepts product-design work.",
                "status": "active",
            },
        ]
        self.confirm_project_intent(
            seed="interrupted-project",
            consultant_seats=["product-designer"],
            identity="A Continuous Project",
        )
        live_tasks = []
        observations = {
            "seed": "interrupted-project",
            "presetLabel": "Software Product",
            "seats": seats,
            "liveTasks": live_tasks,
        }
        initial = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            observations,
        )
        management, operations, consultant = initial["plan"]
        live_tasks.append(
            {
                "taskId": "management-task",
                "wakePath": "message:management-task",
                "title": management["taskTitle"],
                "attemptId": management["attemptId"],
            }
        )
        created_management = baton_memory.transact(
            self.project,
            self.command(
                "task",
                6,
                actor="Operations",
                actorId="bootstrap-operations",
                action="created",
                personnelId=management["personnelId"],
                attemptId=management["attemptId"],
                taskId="management-task",
                wakePath="message:management-task",
            ),
        )
        registered_management = baton_memory.transact(
            self.project,
            self.command(
                "task",
                created_management["revision"],
                actor="Operations",
                actorId="bootstrap-operations",
                action="register",
                personnelId=management["personnelId"],
                taskId="management-task",
                wakePath="message:management-task",
                observedTitle=management["taskTitle"],
            ),
        )
        online_management = baton_memory.transact(
            self.project,
            self.command(
                "task",
                registered_management["revision"],
                actor="Operations",
                actorId="bootstrap-operations",
                action="online",
                personnelId=management["personnelId"],
            ),
        )
        assembled = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            observations,
        )
        self.assertEqual(
            [item["taskAction"] for item in assembled["plan"]],
            ["reuse", "create", "wait-for-prior"],
        )
        self.assertEqual(
            self.snapshot()["bootstrap"]["roster"],
            [item["personnelId"] for item in assembled["plan"]],
        )
        self.assertEqual(assembled["nextStep"], "assemble-team")

        revision = online_management["revision"]
        for person, task_id in (
            (operations, "operations-task"),
            (consultant, "consultant-task"),
        ):
            current = baton_memory.reconcile_bootstrap(
                self.project, capabilities, observations
            )
            current_person = next(
                item
                for item in current["plan"]
                if item["personnelId"] == person["personnelId"]
            )
            self.assertEqual(current_person["taskAction"], "create")
            live_tasks.append(
                {
                    "taskId": task_id,
                    "wakePath": "message:" + task_id,
                    "title": current_person["taskTitle"],
                    "attemptId": current_person["attemptId"],
                }
            )
            created = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    revision,
                    actor="Management",
                    actorId=management["personnelId"],
                    action="created",
                    personnelId=person["personnelId"],
                    attemptId=current_person["attemptId"],
                    taskId=task_id,
                    wakePath="message:" + task_id,
                    userApproved=True,
                ),
            )
            registered = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    created["revision"],
                    actor="Management",
                    actorId=management["personnelId"],
                    action="register",
                    personnelId=person["personnelId"],
                    taskId=task_id,
                    wakePath="message:" + task_id,
                    observedTitle=current_person["taskTitle"],
                    userApproved=True,
                ),
            )
            online = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    registered["revision"],
                    actor="Management",
                    actorId=management["personnelId"],
                    action="online",
                    personnelId=person["personnelId"],
                    userApproved=True,
                ),
            )
            revision = online["revision"]

        completed = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            observations,
        )
        self.assertEqual(
            [item["taskAction"] for item in completed["plan"]],
            ["reuse", "reuse", "reuse"],
        )
        self.assertTrue(completed["deliveryReady"])
        self.assertEqual(completed["nextStep"], "complete")
        self.assertEqual(completed["revision"], revision)
        snapshot = self.snapshot()
        self.assertEqual(len(snapshot["personnel"]), 3)
        self.assertTrue(
            all(person["task"]["status"] == "online" for person in snapshot["personnel"])
        )

    def test_user_can_reset_incomplete_onboarding_without_erasing_company_memory(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
            "title": True,
            "archive": True,
        }
        observations = {
            "seed": "resettable-project",
            "presetLabel": "Software Product",
            "invocationTaskId": "reset-bootstrap-task",
            "seats": [{"role": "Management", "seat": "Management"}],
        }
        baton_memory.transact(
            self.project,
            self.command("bootstrap", 0, action="start", seed="resettable-project"),
        )
        manager = baton_memory.transact(
            self.project,
            self.command(
                "personnel",
                1,
                action="ensure",
                role="Management",
                seat="Management",
                seed="resettable-project:Management:Management:",
            ),
        )
        manager_id = manager["personnelIds"][0]
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                2,
                actor="Operations",
                actorId="bootstrap-operations",
                action="register",
                personnelId=manager_id,
                taskId="old-management-task",
                wakePath="message:old-management-task",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command("bootstrap", 3, action="roster", personnelIds=[manager_id]),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                4,
                actor="Management",
                actorId=manager_id,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
                userApproved=True,
            ),
        )
        company = baton_memory.transact(
            self.project,
            self.command(
                "remember",
                5,
                statement="The company builds durable tools.",
                category="company",
                subject="company",
                sourceClass="explicit-user",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                6,
                action="project-preset",
                preset="software-product",
                consultantSeats=["product-designer"],
                userApproved=True,
            ),
        )
        memory_before_denial = (
            self.project / ".baton/memory/memory.json"
        ).read_bytes()
        history_before_denial = (
            self.project / ".baton/memory/history.jsonl"
        ).read_bytes()
        with self.assertRaisesRegex(
            baton_memory.MemoryError, "explicit user authorization"
        ):
            baton_memory.transact(
                self.project,
                self.command(
                    "bootstrap",
                    7,
                    actor="Management",
                    actorId=manager_id,
                    action="reset-onboarding",
                    userApproved=True,
                ),
            )
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            memory_before_denial,
        )
        self.assertEqual(
            (self.project / ".baton/memory/history.jsonl").read_bytes(),
            history_before_denial,
        )
        reset_command = self.command(
            "bootstrap",
            7,
            action="reset-onboarding",
            userApproved=True,
            sourceClass="explicit-user",
            references=["BATON-006"],
        )
        reset = baton_memory.transact(self.project, reset_command)

        snapshot = self.snapshot()
        self.assertEqual(reset["personnelIds"], [manager_id])
        self.assertEqual(snapshot["revision"], 8)
        self.assertEqual(
            snapshot["bootstrap"],
            {
                "status": "not-started",
                "seed": "resettable-project",
                "roster": [],
                "provisionalProject": {"onboardingEpoch": 1},
                "confirmedAt": "",
                "cleanupTasks": [
                    {
                        "personnelId": manager_id,
                        "taskId": "old-management-task",
                        "wakePath": "message:old-management-task",
                        "title": "",
                        "status": "archive-required",
                    }
                ],
            },
        )
        self.assertEqual(snapshot["personnel"], [])
        self.assertEqual(
            [claim["id"] for claim in snapshot["claims"]], company["claimIds"]
        )
        replay = baton_memory.transact(self.project, reset_command)
        self.assertEqual(replay["revision"], 8)

        cleanup = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        self.assertEqual(cleanup["nextStep"], "cleanup-team")
        self.assertEqual(
            [item["taskId"] for item in cleanup["cleanupPlan"]],
            ["old-management-task"],
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                8,
                action="cleanup-complete",
                taskId="old-management-task",
                archiveConfirmed=True,
                userApproved=True,
            ),
        )

        restarted = baton_memory.reconcile_bootstrap(
            self.project, capabilities, observations
        )
        self.assertEqual(restarted["revision"], 10)
        self.assertEqual(restarted["nextStep"], "confirm-project-preset")
        self.assertEqual(restarted["plan"], [])
        self.assertEqual(self.snapshot()["personnel"], [])

    def test_bootstrap_management_registers_only_reconciled_private_roster_tasks(self):
        self.confirm_project_intent(seed="bounded-registration")
        plan = baton_memory.reconcile_bootstrap(
            self.project,
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
                "seed": "bounded-registration",
                "seats": [{"role": "Management", "seat": "Management"}],
                "liveTasks": [],
            },
        )
        management = plan["plan"][0]
        consultant = baton_memory.transact(
            self.project,
            self.command(
                "personnel",
                6,
                action="ensure",
                role="Consultant",
                seat="product-designer",
                specialty="product design",
                seed="bounded-registration:consultant",
            ),
        )["personnelIds"][0]
        with self.assertRaisesRegex(baton_memory.MemoryError, "private-roster"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    7,
                    actor="Management",
                    actorId=management["personnelId"],
                    action="register",
                    personnelId=consultant,
                    taskId="consultant-task",
                    wakePath="message:consultant-task",
                    userApproved=True,
                ),
            )

    def test_task_surface_without_exact_title_support_falls_back_to_copy_ready_prompt(self):
        self.confirm_project_intent(seed="fallback-project")
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            {
                "list": True,
                "create": True,
                "stableIdentity": True,
                "read": True,
                "message": True,
                "title": False,
                "archive": True,
            },
            {
                "seed": "fallback-project",
                "seats": [
                    {"role": "Management", "seat": "Management"},
                    {"role": "Operations", "seat": "Operations"},
                ],
            },
        )
        self.assertEqual(plan["capability"], "fallback")
        self.assertFalse(plan["deliveryReady"])
        self.assertEqual(
            [item["taskAction"] for item in plan["plan"]],
            ["copy-prompt", "wait-for-prior"],
        )
        for item in plan["plan"]:
            self.assertIn("permanent top-level task", item["copyPrompt"])
            self.assertIn(item["taskTitle"], item["copyPrompt"])
            self.assertIn("sole wake mechanism", item["copyPrompt"])
            self.assertIn(item["personnelId"], item["registrationInstruction"])
            self.assertNotIn("persistent goal for this role", item["copyPrompt"])
        snapshot = self.snapshot()
        self.assertEqual(snapshot["revision"], 6)
        self.assertEqual(len(snapshot["bootstrap"]["roster"]), 2)
        self.assertEqual(
            [person["task"]["status"] for person in snapshot["personnel"]],
            ["awaiting-task", "awaiting-task"],
        )

    def test_task_registration_and_bootstrap_reject_disposable_or_inactive_seats(self):
        contractor_id = self.person(
            role="Contractor",
            seat="verification",
            specialty="verification",
            seed="contractor-task",
        )["personnelIds"][0]
        with self.assertRaisesRegex(baton_memory.MemoryError, "permanent task"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    1,
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=contractor_id,
                    taskId="contractor-task",
                    wakePath="message:contractor-task",
                ),
            )
        consultant_id = self.person(
            1,
            role="Consultant",
            seat="security",
            specialty="security",
            seed="inactive-consultant",
        )["personnelIds"][0]
        baton_memory.transact(
            self.project,
            self.command(
                "personnel",
                2,
                action="fire",
                personnelId=consultant_id,
                userApproved=True,
            ),
        )
        with self.assertRaisesRegex(baton_memory.MemoryError, "active Consultant"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    3,
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=consultant_id,
                    taskId="inactive-consultant-task",
                    wakePath="message:inactive-consultant-task",
                ),
            )
        with self.assertRaisesRegex(baton_memory.MemoryError, "permanent bootstrap seat"):
            baton_memory.reconcile_bootstrap(
                self.project,
                {},
                {
                    "seed": "invalid-roster",
                    "seats": [{"role": "Contractor", "seat": "verification"}],
                },
            )
        with self.assertRaisesRegex(baton_memory.MemoryError, "active Consultant"):
            baton_memory.reconcile_bootstrap(
                self.project,
                {},
                {
                    "seed": "invalid-consultant",
                    "seats": [
                        {
                            "role": "Consultant",
                            "seat": "security",
                            "id": "security",
                            "title": "Security Lead",
                            "domain": "security",
                            "configPath": ".baton/agents/consultant-security.toml",
                            "acceptanceAuthority": "Accepts security work.",
                            "status": "inactive",
                        }
                    ],
                },
            )

    def test_fallback_reconciliation_persists_mixed_roster_and_resumes_to_complete(self):
        manager_id = self.person(seed="mixed-seed:Management:Management:")["personnelIds"][0]
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                1,
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=manager_id,
                taskId="manager-task",
                wakePath="message:manager-task",
            ),
        )
        seats = [
            {"role": "Management", "seat": "Management"},
            {"role": "Operations", "seat": "Operations"},
            {
                "role": "Consultant",
                "seat": "security",
                "id": "security",
                "title": "Security Lead",
                "domain": "application security",
                "configPath": ".baton/agents/consultant-security.toml",
                "acceptanceAuthority": "Accepts or rejects security work inside the approved security boundary.",
                "status": "active",
            },
        ]
        self.confirm_project_intent(
            2,
            seed="mixed-seed",
            consultant_seats=["security"],
            identity="Mixed Capability Project",
        )
        capabilities = {"list": True, "create": True, "stableIdentity": True, "read": True, "message": False}
        first = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {"seed": "mixed-seed", "seats": seats},
        )
        self.assertEqual(
            [item["taskAction"] for item in first["plan"]],
            ["manual-title", "wait-for-prior", "wait-for-prior"],
        )
        snapshot = self.snapshot()
        self.assertEqual(len(snapshot["bootstrap"]["roster"]), 3)
        self.assertEqual(
            [person["task"]["status"] for person in snapshot["personnel"]],
            ["online", "awaiting-task", "awaiting-task"],
        )

        resumed = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {"seed": "mixed-seed", "seats": seats},
        )
        self.assertEqual(
            [item["taskAction"] for item in resumed["plan"]],
            ["manual-title", "wait-for-prior", "wait-for-prior"],
        )
        management = resumed["plan"][0]
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                8,
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=management["personnelId"],
                taskId="manager-task",
                wakePath="message:manager-task",
                observedTitle=management["taskTitle"],
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                9,
                actor="Operations",
                actorId="ops",
                action="online",
                personnelId=management["personnelId"],
            ),
        )
        awaiting = [person for person in self.snapshot()["personnel"] if person["task"]["status"] == "awaiting-task"]
        current_revision = self.snapshot()["revision"]
        for index, person in enumerate(awaiting):
            plan_item = resumed["plan"][index + 1]
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    current_revision + index * 2,
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=person["id"],
                    taskId="task-%d" % index,
                    wakePath="message:task-%d" % index,
                    observedTitle=plan_item["taskTitle"],
                ),
            )
            result = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    current_revision + index * 2 + 1,
                    actor="Operations",
                    actorId="ops",
                    action="online",
                    personnelId=person["id"],
                ),
            )
        self.assertEqual(result["projection"]["bootstrap"]["status"], "complete")

    def test_fallback_reconciliation_rolls_back_roster_and_personnel_together(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": False,
        }
        self.confirm_project_intent(seed="atomic-fallback")
        memory_before = (self.project / ".baton/memory/memory.json").read_bytes()
        history_before = (self.project / ".baton/memory/history.jsonl").read_bytes()
        with mock.patch.dict(
            os.environ,
            {"BATON_TEST_MEMORY_FAIL_AT": "after-history"},
            clear=False,
        ):
            with self.assertRaisesRegex(baton_memory.MemoryError, "rolled back"):
                baton_memory.reconcile_bootstrap(
                    self.project,
                    capabilities,
                    {
                        "seed": "atomic-fallback",
                        "seats": [
                            {"role": "Management", "seat": "Management"},
                            {"role": "Operations", "seat": "Operations"},
                        ],
                    },
                )
        snapshot = self.snapshot()
        self.assertEqual(snapshot["revision"], 5)
        self.assertEqual(snapshot["personnel"], [])
        self.assertEqual(snapshot["bootstrap"]["roster"], [])
        self.assertEqual(
            (self.project / ".baton/memory/memory.json").read_bytes(),
            memory_before,
        )
        self.assertEqual(
            (self.project / ".baton/memory/history.jsonl").read_bytes(),
            history_before,
        )

    def test_fallback_prompts_distinguish_two_consultants_with_acceptance_boundaries(self):
        consultants = [
            {
                "role": "Consultant",
                "seat": "security",
                "id": "security",
                "title": "Security Lead",
                "domain": "application security",
                "configPath": ".baton/agents/consultant-security.toml",
                "acceptanceAuthority": "Accepts security work inside the approved security boundary.",
                "status": "active",
            },
            {
                "role": "Consultant",
                "seat": "research",
                "id": "research",
                "title": "Research Lead",
                "domain": "user research",
                "configPath": ".baton/agents/consultant-research.toml",
                "acceptanceAuthority": "Accepts research work inside the approved research boundary.",
                "status": "active",
            },
        ]
        self.confirm_project_intent(
            seed="two-consultants",
            consultant_seats=["security", "research"],
            identity="Two Consultant Project",
        )
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            {},
            {"seed": "two-consultants", "seats": consultants},
        )
        for item, consultant in zip(plan["plan"], consultants):
            prompt = item["copyPrompt"]
            self.assertIn(consultant["id"], prompt)
            self.assertIn(consultant["title"], prompt)
            self.assertIn(consultant["domain"], prompt)
            self.assertIn(consultant["configPath"], prompt)
            self.assertIn(consultant["acceptanceAuthority"], prompt)
        self.assertNotEqual(plan["plan"][0]["copyPrompt"], plan["plan"][1]["copyPrompt"])

    def test_candidate_rejection_removes_pending_claim_without_exposing_it_to_context(self):
        candidate = baton_memory.transact(
            self.project,
            self.command("candidate", 0, category="preference", subject="user", statement="A tentative preference.", sourceClass="personal-inference"),
        )
        rejected = baton_memory.transact(
            self.project,
            self.command("candidate", 1, action="reject", claimId=candidate["claimIds"][0]),
        )
        self.assertEqual(rejected["result"], "rejected")
        self.assertEqual(self.snapshot()["claims"], [])

    def test_task_registration_reuses_personnel_but_requires_legacy_title_verification(self):
        first = self.person()
        manager_id = first["personnelIds"][0]
        baton_memory.transact(self.project, self.command("task", 1, actor="Operations", actorId="ops", action="register", personnelId=manager_id, taskId="task-1", wakePath="message:task-1"))
        second = self.person(2, role="Operations", seat="Operations", seed="project-seed:operations")
        with self.assertRaisesRegex(baton_memory.MemoryError, "already registered"):
            baton_memory.transact(self.project, self.command("task", 3, actor="Operations", actorId="ops", action="register", personnelId=second["personnelIds"][0], taskId="task-1", wakePath="message:task-1"))
        self.confirm_project_intent(3, seed="project-seed")
        plan = baton_memory.reconcile_bootstrap(self.project, {}, {"seed": "project-seed", "seats": [{"role": "Management", "seat": "Management"}]})
        self.assertEqual(plan["plan"][0]["taskAction"], "manual-title")
        self.assertFalse(plan["deliveryReady"])

    def test_direct_bootstrap_roster_rejects_disposable_and_inactive_seats(self):
        manager = self.person()["personnelIds"][0]
        contractor = self.person(
            1,
            role="Contractor",
            seat="verification",
            specialty="verification",
            seed="project-seed:contractor",
        )["personnelIds"][0]
        with self.assertRaisesRegex(baton_memory.MemoryError, "active Management"):
            baton_memory.transact(
                self.project,
                self.command("bootstrap", 2, action="roster", personnelIds=[contractor]),
            )
        consultant = self.person(
            2,
            role="Consultant",
            seat="product-designer",
            specialty="product design",
            seed="project-seed:consultant",
        )["personnelIds"][0]
        baton_memory.transact(
            self.project,
            self.command(
                "personnel",
                3,
                action="fire",
                personnelId=consultant,
                userApproved=True,
            ),
        )
        with self.assertRaisesRegex(baton_memory.MemoryError, "active Management"):
            baton_memory.transact(
                self.project,
                self.command("bootstrap", 4, action="roster", personnelIds=[consultant]),
            )
        accepted = baton_memory.transact(
            self.project,
            self.command("bootstrap", 4, action="roster", personnelIds=[manager]),
        )
        self.assertEqual(accepted["personnelIds"], [manager])

    def test_permanent_replacement_requires_user_approval_but_contractor_does_not(self):
        manager = self.person()["personnelIds"][0]
        command = self.command("personnel", 1, actor="Operations", actorId="ops", action="replace", personnelId=manager)
        with self.assertRaisesRegex(baton_memory.MemoryError, "explicit user approval"):
            baton_memory.transact(self.project, command)
        contractor = self.person(1, role="Contractor", seat="platform-and-data", specialty="platform", seed="contractor-seed")["personnelIds"][0]
        result = baton_memory.transact(self.project, self.command("personnel", 2, actor="Operations", actorId="ops", action="replace", personnelId=contractor))
        self.assertTrue(result["ok"])

    def test_reviews_preserve_sources_and_require_repeated_evidence_for_summary(self):
        person_id = self.person(role="Contractor", seat="verification", seed="reviewer-seed")["personnelIds"][0]
        first = baton_memory.transact(
            self.project,
            self.command("review", 1, actor="Operations", actorId="ops", personnelId=person_id, sourceClass="operational-evidence", assignmentType="verification", outcome="Passed focused checks", revisionCause="", verificationQuality="focused and reproducible", workingStyleImpact="narrow exploration helped", reviewers=["Operations"], evidencePaths=["tests/report-1.json"]),
        )
        first_review = self.snapshot()["personnel"][0]["reviews"][0]["id"]
        second_command = self.command("review", 2, actor="Management", actorId="management", personnelId=person_id, sourceClass="management-assessment", assignmentType="verification", outcome="Repeated reliable result", revisionCause="", verificationQuality="independently checked", workingStyleImpact="", reviewers=["Management"], evidencePaths=["tests/report-2.json"])
        second_command["performanceSummary"] = {"assignmentType": "verification", "observation": "Repeated evidence supports verification work.", "reviewIds": [first_review, baton_memory._stable_id("review", second_command["idempotencyKey"], person_id, "verification")]}
        baton_memory.transact(self.project, second_command)
        person = self.snapshot()["personnel"][0]
        self.assertEqual(len(person["reviews"]), 2)
        self.assertEqual(len(person["performanceSummaries"]), 1)
        projected = baton_memory.inspect(
            self.project, {"section": "projection"}
        )["personnel"][0]["performanceSummaries"][0]
        self.assertEqual(
            projected["sourceClasses"],
            ["management-assessment", "operational-evidence"],
        )
        self.assertEqual(
            projected["evidencePaths"],
            ["tests/report-1.json", "tests/report-2.json"],
        )
        self.assertNotIn("score", json.dumps(person).lower())
        self.assertTrue(first["ok"])

    def test_context_is_role_specific_confirmed_and_within_exact_utf8_cap(self):
        revision = 0
        for index in range(12):
            role = baton_memory.ROLES[index % len(baton_memory.ROLES)]
            self.remember(
                revision,
                subject="context-%02d" % index,
                statement=("évidence %02d " % index) + ("x" * 180),
                roleRelevance=[role],
                assignmentTypes=[role.casefold()],
                importance=(index % 5) + 1,
                idempotencyKey="context-%02d" % index,
            )
            revision += 1
        selected = {claim["id"]: claim for claim in self.snapshot()["claims"]}
        for role in baton_memory.ROLES:
            packet = baton_memory.select_context(
                self.project,
                {"role": role, "assignmentType": role.casefold()},
            )
            self.assertGreater(packet["claimCount"], 0, role)
            self.assertLessEqual(packet["claimCount"], 10, role)
            self.assertLessEqual(packet["utf8Bytes"], 1800, role)
            self.assertLessEqual(packet["estimatedTokens"], 600, role)
            self.assertEqual(
                packet["estimatedTokens"],
                (len(packet["content"].encode("utf-8")) + 2) // 3,
                role,
            )
            self.assertTrue(
                all(role in selected[claim_id]["roleRelevance"] for claim_id in packet["claimIds"]),
                role,
            )
        on_demand = baton_memory.select_context(self.project, {"role": "Operations", "mode": "on-demand", "query": "context-00"})
        self.assertEqual(on_demand["mode"], "on-demand")
        self.assertEqual(on_demand["claimCount"], 0)
        matching = baton_memory.select_context(
            self.project,
            {"role": "Management", "mode": "on-demand", "query": "context-00"},
        )
        self.assertEqual(matching["claimCount"], 1)
        audit = baton_memory.select_context(
            self.project,
            {
                "role": "Internal Audit",
                "assignmentType": "harness-evaluation",
                "assignment": "Evaluate the bounded BATON-002 candidate.",
                "evaluationBoundary": "BATON-002 candidate, rubric, and supplied evidence",
            },
        )
        self.assertEqual(audit["authority"], "read-only-evaluation")
        self.assertEqual(audit["evaluationBoundary"], "BATON-002 candidate, rubric, and supplied evidence")
        self.assertGreater(audit["claimCount"], 0)
        self.assertLessEqual(audit["utf8Bytes"], 1800)
        audit_demand = baton_memory.select_context(
            self.project,
            {
                "role": "Internal Audit",
                "mode": "on-demand",
                "query": "context-00",
                "evaluationBoundary": "BATON-002 candidate, rubric, and supplied evidence",
            },
        )
        self.assertEqual(audit_demand["claimCount"], 1)
        with self.assertRaisesRegex(baton_memory.MemoryError, "evaluation boundary"):
            baton_memory.select_context(
                self.project,
                {"role": "Internal Audit"},
            )

    def test_bootstrap_states_are_idempotently_planned_and_confirmation_is_gated(self):
        baton_memory.transact(self.project, self.command("bootstrap", 0, actor="Management", actorId="management", action="start", seed="bootstrap-seed"))
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                1,
                actor="Management",
                actorId="management",
                action="provisional",
                project={
                    "identity": "Baton",
                    "purpose": "Coordinate a project.",
                    "users": "Project owners.",
                    "outcome": "A confirmed project.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=False,
            ),
        )
        denied = self.command("bootstrap", 2, actor="Management", actorId="management", action="confirm")
        with self.assertRaisesRegex(baton_memory.MemoryError, "user confirmation"):
            baton_memory.transact(self.project, denied)
        with self.assertRaisesRegex(baton_memory.MemoryError, "project preset"):
            baton_memory.transact(self.project, self.command("bootstrap", 2, action="confirm"))

    def test_gamification_and_project_management_authority_are_rejected(self):
        with self.assertRaisesRegex(baton_memory.MemoryError, "scoring"):
            baton_memory.transact(self.project, self.command("personnel", 0, action="ensure", role="Contractor", seat="x", seed="x", score=10))
        with self.assertRaisesRegex(baton_memory.MemoryError, "duplicate"):
            baton_memory.transact(self.project, self.command("remember", 0, category="company", subject="ticket", statement="A status", sourceClass="explicit-user", ticketStatus="Done"))

    def test_fault_injection_rolls_back_both_files_and_keeps_external_report(self):
        memory_before = (self.project / ".baton/memory/memory.json").read_bytes()
        history_before = (self.project / ".baton/memory/history.jsonl").read_bytes()
        with mock.patch.dict(os.environ, {"BATON_TEST_MEMORY_FAIL_AT": "after-history"}, clear=False):
            with self.assertRaisesRegex(baton_memory.MemoryError, "rolled back"):
                self.remember()
        self.assertEqual((self.project / ".baton/memory/memory.json").read_bytes(), memory_before)
        self.assertEqual((self.project / ".baton/memory/history.jsonl").read_bytes(), history_before)
        reports = list(self.state_home.rglob("memory-report.json"))
        self.assertEqual(len(reports), 1)
        self.assertEqual(json.loads(reports[0].read_text())["result"], "rolled-back")
        self.assertFalse(str(reports[0].resolve()).startswith(str(self.project.resolve())))

    def test_project_confirmation_rolls_back_memory_state_and_views_together(self):
        baton_memory.transact(
            self.project,
            self.command("bootstrap", 0, action="start", seed="atomic-direction"),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                1,
                action="project-preset",
                preset="software-product",
                consultantSeats=[],
                userApproved=True,
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "remember",
                2,
                category="preference",
                subject="user",
                statement="The user’s preferred name is Captain.",
                sourceClass="explicit-user",
                assignmentTypes=["bootstrap"],
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                3,
                action="provisional",
                project={
                    "identity": "Atomic project",
                    "purpose": "Preserve one confirmed direction.",
                    "users": "Project owners.",
                    "outcome": "One canonical project record.",
                    "constraints": [],
                    "unresolved": [],
                    "readinessProtocol": "Standard Protocol",
                    "clearanceProtocol": "Release Clearance",
                },
                ready=True,
            ),
        )
        paths = (
            ".baton/memory/memory.json",
            ".baton/memory/history.jsonl",
            ".baton/state/project.json",
            ".baton/views/dashboard.html",
        )
        before = {relative: (self.project / relative).read_bytes() for relative in paths}
        with mock.patch.dict(
            os.environ, {"BATON_TEST_MEMORY_FAIL_AT": "after-generated"}, clear=False
        ):
            with self.assertRaisesRegex(baton_memory.MemoryError, "rolled back"):
                baton_memory.transact(
                    self.project,
                    self.command(
                        "bootstrap", 4, action="confirm", userApproved=True
                    ),
                )
        self.assertEqual(
            {relative: (self.project / relative).read_bytes() for relative in paths},
            before,
        )

    def test_every_jsonl_line_and_cross_file_head_are_checked(self):
        self.remember()
        history_path = self.project / ".baton/memory/history.jsonl"
        history_path.write_text(history_path.read_text() + "{}\n", encoding="utf-8")
        with self.assertRaisesRegex(baton_memory.MemoryError, "schema validation"):
            baton_memory.inspect(self.project)
        shutil.copy2(ROOT / "template/.baton/memory/history.jsonl", history_path)
        snapshot = self.snapshot()
        snapshot["revision"] = 0
        snapshot["historyHead"] = {"revision": 0, "eventId": "wrong", "sha256": hashlib.sha256(b"").hexdigest()}
        (self.project / ".baton/memory/memory.json").write_bytes(baton_memory._json_bytes(snapshot))
        with self.assertRaisesRegex(baton_memory.MemoryError, "head"):
            baton_memory.inspect(self.project)

    def test_cli_main_supports_hidden_json_forwarding(self):
        environment = dict(os.environ)
        environment.update({"BATON_PROJECT_ROOT": str(self.project), "PYTHONDONTWRITEBYTECODE": "1"})
        result = subprocess.run(
            [sys.executable, str(ROOT / "template/.baton/lib/baton_memory.py"), "check", "--json"],
            cwd=self.project,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"historyEvents": 0, "ok": True, "revision": 0})


if __name__ == "__main__":
    unittest.main()
