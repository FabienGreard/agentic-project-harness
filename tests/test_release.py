#!/usr/bin/env python3
"""Deterministic template-projection and dual-payload tests for Baton."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baton_testkit import (  # noqa: E402
    ARTIFACTS,
    RELEASE_TOOL,
    archive_names,
    build_bundle,
    git_commit,
    inferred_projection,
    make_candidate,
    manifest,
    projected_path,
    resign_manifest,
    run,
    sha256,
)


class ReleaseDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-release-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle"
        build_bundle(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_artifacts_and_archives_are_deterministic(self) -> None:
        repeated = self.base / "bundle-repeated"
        build_bundle(self.source, repeated)
        self.assertEqual({path.name for path in self.bundle.iterdir()}, ARTIFACTS)
        self.assertEqual(
            {path.name: sha256(path) for path in self.bundle.iterdir()},
            {path.name: sha256(path) for path in repeated.iterdir()},
        )
        validated = run([sys.executable, RELEASE_TOOL, "validate", "--bundle", self.bundle])
        self.assertTrue(json.loads(validated.stdout)["ok"])

    def test_consumer_projection_is_rooted_only_at_template_baton(self) -> None:
        tracked = sorted(
            item
            for item in run(["git", "ls-files", "-z"], cwd=self.source).stdout.split("\0")
            if item
        )
        template_paths = [path for path in tracked if path.startswith("template/")]
        self.assertTrue(template_paths)
        self.assertTrue(all(path.startswith("template/.baton/") for path in template_paths))
        self.assertEqual(inferred_projection("template/.baton/workflow.md"), "shared")
        self.assertEqual(inferred_projection("template/.baton/AGENTS.md"), "starter")
        self.assertEqual(inferred_projection("template/.baton/memory/memory.json"), "starter")
        self.assertEqual(inferred_projection("template/.baton/state/project.json"), "starter")
        self.assertEqual(inferred_projection("template/.baton/views/team-tasks.md"), "starter")
        self.assertEqual(inferred_projection("template/.baton/records/README.md"), "starter")
        self.assertEqual(
            inferred_projection("template/.baton/migration/README.md"),
            "adoption-only",
        )
        self.assertFalse((self.source / "scripts/source-classification.json").exists())

    def test_manifest_lists_exact_new_project_and_adoption_payloads(self) -> None:
        release_manifest = manifest(self.bundle)
        source_paths = [
            path
            for path in run(["git", "ls-files", "-z"], cwd=self.source).stdout.split("\0")
            if path.startswith("template/.baton/")
        ]
        self.assertEqual(set(release_manifest["payloads"]), {"new-project", "adoption"})
        for payload in ("new-project", "adoption"):
            expected = [
                {
                    "path": destination,
                    "sourcePath": source_path,
                    "projection": projection,
                }
                for source_path in source_paths
                for projection in [inferred_projection(source_path)]
                for destination in [projected_path(source_path, projection, payload)]
                if destination is not None
            ]
            expected.sort(key=lambda item: item["path"])
            actual = [
                {
                    "path": item["path"],
                    "sourcePath": item["sourcePath"],
                    "projection": item["projection"],
                }
                for item in release_manifest["payloads"][payload]["files"]
            ]
            self.assertEqual(actual, expected)
            self.assertEqual(archive_names(self.bundle, payload), [item["path"] for item in expected])

    def test_payloads_are_namespaced_and_adoption_state_is_quarantined(self) -> None:
        release_manifest = manifest(self.bundle)
        new_paths = {
            item["path"] for item in release_manifest["payloads"]["new-project"]["files"]
        }
        adoption_paths = {
            item["path"] for item in release_manifest["payloads"]["adoption"]["files"]
        }
        self.assertTrue(all(path.startswith(".baton/") for path in new_paths | adoption_paths))
        self.assertIn(".baton/state/project.json", new_paths)
        self.assertIn(".baton/AGENTS.md", new_paths)
        self.assertEqual(
            {path for path in new_paths if path.startswith(".baton/memory/")},
            {".baton/memory/history.jsonl", ".baton/memory/memory.json"},
        )
        self.assertNotIn(".baton/state/project.json", adoption_paths)
        self.assertNotIn(".baton/AGENTS.md", adoption_paths)
        self.assertIn(".baton/migration/starter/AGENTS.md", adoption_paths)
        self.assertIn(".baton/migration/starter/state/project.json", adoption_paths)
        self.assertEqual(
            {
                path
                for path in adoption_paths
                if path.startswith(".baton/migration/starter/memory/")
            },
            {
                ".baton/migration/starter/memory/history.jsonl",
                ".baton/migration/starter/memory/memory.json",
            },
        )
        self.assertFalse(any(path.startswith(".baton/memory/") for path in adoption_paths))
        self.assertIn(".baton/migration/README.md", adoption_paths)
        self.assertNotIn(".baton/migration/README.md", new_paths)
        self.assertFalse(any(path.startswith(".codex/skills") for path in new_paths | adoption_paths))
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in new_paths | adoption_paths))
        self.assertFalse(any(path.startswith(".baton/state/") for path in adoption_paths))

    def test_source_repository_growth_is_never_payload_eligible(self) -> None:
        drifted = self.base / "drifted"
        shutil.copytree(self.source, drifted, symlinks=True)
        (drifted / "new-source-file.txt").write_text("source repository only\n", encoding="utf-8")
        run(["git", "add", "new-source-file.txt"], cwd=drifted)
        run(["git", "commit", "-qm", "source repository growth"], cwd=drifted)
        bundle = self.base / "drifted-bundle"
        build_bundle(drifted, bundle)
        source_paths = {
            item["sourcePath"]
            for payload in manifest(bundle)["payloads"].values()
            for item in payload["files"]
        }
        self.assertNotIn("new-source-file.txt", source_paths)
        for payload in ("new-project", "adoption"):
            artifact = manifest(bundle)["payloads"][payload]["artifact"]
            self.assertEqual(sha256(bundle / artifact), sha256(self.bundle / artifact))

    def test_template_content_outside_baton_fails_closed(self) -> None:
        polluted = self.base / "polluted-template"
        shutil.copytree(self.source, polluted, symlinks=True)
        (polluted / "template/project-root.txt").write_text("must not ship\n", encoding="utf-8")
        run(["git", "add", "template/project-root.txt"], cwd=polluted)
        run(["git", "commit", "-qm", "polluted consumer template"], cwd=polluted)
        failed = build_bundle(polluted, self.base / "polluted-template-bundle", expected=1)
        self.assertIn("consumer source exists outside template/.baton", failed.stderr)

    def test_upgrade_origin_requires_both_full_commit_and_manifest_digest(self) -> None:
        failed = build_bundle(
            self.source,
            self.base / "origin-without-manifest-digest",
            origins=[("v0.5.0", "1" * 40, None)],
            expected=1,
        )
        self.assertIn("TAG=FULL_COMMIT,MANIFEST_SHA256", failed.stderr)

    def test_manifest_and_archive_tampering_is_rejected(self) -> None:
        tampered = self.base / "tampered"
        shutil.copytree(self.bundle, tampered)
        (tampered / "baton-adoption.tar.gz").write_bytes(b"tampered")
        failed = run(
            [sys.executable, RELEASE_TOOL, "validate", "--bundle", tampered],
            expected=1,
        )
        self.assertIn("checksum mismatch: baton-adoption.tar.gz", failed.stderr)

    def test_validator_rejects_false_projection_provenance(self) -> None:
        cases = {
            "source-outside-template": ("sourcePath", "README.md"),
            "projection-does-not-match-source": ("projection", "starter"),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name):
                tampered = self.base / f"false-provenance-{name}"
                shutil.copytree(self.bundle, tampered)
                document = manifest(tampered)
                record = next(
                    item
                    for item in document["payloads"]["adoption"]["files"]
                    if item["path"] == ".baton/workflow.md"
                )
                record[field] = value
                resign_manifest(tampered, document)
                failed = run(
                    [sys.executable, RELEASE_TOOL, "validate", "--bundle", tampered],
                    expected=1,
                )
                self.assertIn("payload projection provenance mismatch", failed.stderr)

    def test_validator_rejects_an_unexpected_sixth_asset(self) -> None:
        polluted = self.base / "polluted"
        shutil.copytree(self.bundle, polluted)
        (polluted / "source-repository.zip").write_bytes(b"must not ship")
        failed = run(
            [sys.executable, RELEASE_TOOL, "validate", "--bundle", polluted],
            expected=1,
        )
        self.assertIn("release bundle artifact set is not exact", failed.stderr)
        self.assertIn("source-repository.zip", failed.stderr)

    def test_manifest_provenance_and_origin_records_are_immutable(self) -> None:
        release_manifest = manifest(self.bundle)
        self.assertEqual(release_manifest["version"], "0.6.0")
        self.assertEqual(release_manifest["stableTag"], "v0.6.0")
        self.assertEqual(release_manifest["stateSchemaVersion"], 2)
        self.assertEqual(release_manifest["memorySchemaVersion"], 1)
        self.assertEqual(release_manifest["source"]["commit"], git_commit(self.source))
        self.assertRegex(release_manifest["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertNotIn("sourceClassificationSha256", release_manifest)

    def test_manifest_rejects_missing_or_invalid_memory_schema_version(self) -> None:
        for label, mutation in (
            ("missing", lambda document: document.pop("memorySchemaVersion")),
            ("zero", lambda document: document.__setitem__("memorySchemaVersion", 0)),
            ("boolean", lambda document: document.__setitem__("memorySchemaVersion", True)),
        ):
            with self.subTest(label=label):
                tampered = self.base / f"memory-schema-{label}"
                shutil.copytree(self.bundle, tampered)
                document = manifest(tampered)
                mutation(document)
                resign_manifest(tampered, document)
                failed = run(
                    [sys.executable, RELEASE_TOOL, "validate", "--bundle", tampered],
                    expected=1,
                )
                self.assertIn("manifest", failed.stderr)


if __name__ == "__main__":
    unittest.main()
