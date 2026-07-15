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


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="baton-memory-tests-")
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        (self.project / ".baton").mkdir(parents=True)
        shutil.copytree(ROOT / "template/.baton/memory", self.project / ".baton/memory")
        shutil.copytree(ROOT / "template/.baton/schemas", self.project / ".baton/schemas")
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
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            {"list": True, "create": True, "stableIdentity": True, "read": True, "message": True},
            {"seed": "project-seed", "seats": [{"role": "Management", "seat": "Management"}]},
        )
        self.assertEqual(plan["plan"][0]["personnelId"], first["personnelIds"][0])
        self.assertEqual(plan["plan"][0]["name"], person["name"])
        self.assertEqual(plan["plan"][0]["workingStyle"], person["workingStyle"])
        self.assertEqual(plan["plan"][0]["taskAction"], "create")

    def test_fresh_native_bootstrap_persists_management_first_roster_before_creation(self):
        capabilities = {
            "list": True,
            "create": True,
            "stableIdentity": True,
            "read": True,
            "message": True,
        }
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "native-project",
                "seats": [
                    {"role": "Operations", "seat": "Operations"},
                    {"role": "Management", "seat": "Management"},
                ],
            },
        )
        self.assertEqual(
            [item["role"] for item in plan["plan"]],
            ["Management", "Operations"],
        )
        self.assertEqual(
            [item["taskAction"] for item in plan["plan"]],
            ["create", "create"],
        )
        snapshot = self.snapshot()
        self.assertEqual(snapshot["revision"], 1)
        self.assertEqual(
            snapshot["bootstrap"]["roster"],
            [item["personnelId"] for item in plan["plan"]],
        )
        self.assertEqual(
            [person["role"] for person in snapshot["personnel"]],
            ["Management", "Operations"],
        )
        with self.assertRaisesRegex(baton_memory.MemoryError, "Management task"):
            baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    1,
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=plan["plan"][1]["personnelId"],
                    taskId="operations-task",
                    wakePath="message:operations-task",
                ),
            )
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                1,
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=plan["plan"][0]["personnelId"],
                taskId="management-task",
                wakePath="message:management-task",
            ),
        )
        baton_memory.transact(
            self.project,
            self.command(
                "task",
                2,
                actor="Operations",
                actorId="ops",
                action="register",
                personnelId=plan["plan"][1]["personnelId"],
                taskId="operations-task",
                wakePath="message:operations-task",
            ),
        )
        replay = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {
                "seed": "native-project",
                "seats": [
                    {"role": "Operations", "seat": "Operations"},
                    {"role": "Management", "seat": "Management"},
                ],
            },
        )
        self.assertEqual(
            [item["taskAction"] for item in replay["plan"]],
            ["reuse", "reuse"],
        )
        self.assertTrue(replay["deliveryReady"])
        self.assertEqual(replay["revision"], 3)

    def test_partial_task_surface_falls_back_to_copy_ready_prompt(self):
        plan = baton_memory.reconcile_bootstrap(
            self.project,
            {
                "list": True,
                "create": True,
                "stableIdentity": True,
                "read": True,
                "message": False,
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
            ["copy-prompt", "copy-prompt"],
        )
        for item in plan["plan"]:
            self.assertIn("permanent top-level Codex task", item["copyPrompt"])
            self.assertIn("sole wake mechanism", item["copyPrompt"])
            self.assertIn(item["personnelId"], item["registrationInstruction"])
            self.assertNotIn("persistent goal for this role", item["copyPrompt"])
        snapshot = self.snapshot()
        self.assertEqual(snapshot["revision"], 1)
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
        capabilities = {"list": True, "create": True, "stableIdentity": True, "read": True, "message": False}
        first = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {"seed": "mixed-seed", "seats": seats},
        )
        self.assertEqual([item["taskAction"] for item in first["plan"]], ["reuse", "copy-prompt", "copy-prompt"])
        snapshot = self.snapshot()
        self.assertEqual(len(snapshot["bootstrap"]["roster"]), 3)
        self.assertEqual(
            [person["task"]["status"] for person in snapshot["personnel"]],
            ["online", "awaiting-task", "awaiting-task"],
        )

        revision = snapshot["revision"]
        baton_memory.transact(
            self.project,
            self.command(
                "bootstrap",
                revision,
                actor="Management",
                actorId="management",
                action="provisional",
                project={"identity": "Baton"},
                ready=True,
            ),
        )
        confirmed = baton_memory.transact(
            self.project,
            self.command("bootstrap", revision + 1, action="confirm"),
        )
        self.assertEqual(confirmed["projection"]["bootstrap"]["status"], "in-progress")
        self.assertTrue(self.snapshot()["bootstrap"]["confirmedAt"])

        resumed = baton_memory.reconcile_bootstrap(
            self.project,
            capabilities,
            {"seed": "mixed-seed", "seats": seats},
        )
        self.assertEqual([item["taskAction"] for item in resumed["plan"]], ["reuse", "copy-prompt", "copy-prompt"])
        awaiting = [person for person in self.snapshot()["personnel"] if person["task"]["status"] == "awaiting-task"]
        current_revision = self.snapshot()["revision"]
        for index, person in enumerate(awaiting):
            result = baton_memory.transact(
                self.project,
                self.command(
                    "task",
                    current_revision + index,
                    actor="Operations",
                    actorId="ops",
                    action="register",
                    personnelId=person["id"],
                    taskId="task-%d" % index,
                    wakePath="message:task-%d" % index,
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
        self.assertEqual(snapshot["revision"], 0)
        self.assertEqual(snapshot["personnel"], [])
        self.assertEqual(snapshot["bootstrap"]["roster"], [])
        self.assertEqual(self.history(), [])

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

    def test_task_registration_reuses_personnel_and_rejects_duplicate_task(self):
        first = self.person()
        manager_id = first["personnelIds"][0]
        baton_memory.transact(self.project, self.command("task", 1, actor="Operations", actorId="ops", action="register", personnelId=manager_id, taskId="task-1", wakePath="message:task-1"))
        second = self.person(2, role="Operations", seat="Operations", seed="project-seed:operations")
        with self.assertRaisesRegex(baton_memory.MemoryError, "already registered"):
            baton_memory.transact(self.project, self.command("task", 3, actor="Operations", actorId="ops", action="register", personnelId=second["personnelIds"][0], taskId="task-1", wakePath="message:task-1"))
        plan = baton_memory.reconcile_bootstrap(self.project, {}, {"seed": "project-seed", "seats": [{"role": "Management", "seat": "Management"}]})
        self.assertEqual(plan["plan"][0]["taskAction"], "reuse")
        self.assertTrue(plan["deliveryReady"])

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
        baton_memory.transact(self.project, self.command("bootstrap", 1, actor="Management", actorId="management", action="provisional", project={"identity": "Baton"}, ready=True))
        denied = self.command("bootstrap", 2, actor="Management", actorId="management", action="confirm")
        with self.assertRaisesRegex(baton_memory.MemoryError, "user confirmation"):
            baton_memory.transact(self.project, denied)
        with self.assertRaisesRegex(baton_memory.MemoryError, "roster"):
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
