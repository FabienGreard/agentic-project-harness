#!/usr/bin/env python3
"""Deterministic release-classification and dual-payload tests for Baton."""

from __future__ import annotations

import hashlib
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
    inferred_class,
    make_candidate,
    manifest,
    projected_path,
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

    def test_every_source_path_has_the_exact_release_class(self) -> None:
        document = json.loads(
            (self.source / "release/source-classification.json").read_text(encoding="utf-8")
        )
        tracked = set(
            item
            for item in run(["git", "ls-files", "-z"], cwd=self.source).stdout.split("\0")
            if item
        )
        self.assertEqual(document["schema"], "baton.source-classification/v1")
        self.assertEqual(set(document["files"]), tracked)
        self.assertEqual(
            document["files"],
            {path: inferred_class(path) for path in sorted(tracked)},
        )
        self.assertEqual(document["files"][".baton/AGENTS.md"], "source-only")
        self.assertEqual(document["files"]["packages/consumer/.baton/guide.md"], "shared")
        self.assertEqual(
            document["files"]["packages/consumer/.baton/state/project.json"],
            "template-only",
        )
        self.assertEqual(
            document["files"]["packages/consumer/.baton/integration/README.md"],
            "adoption-runtime",
        )

    def test_manifest_lists_exact_new_project_and_adoption_payloads(self) -> None:
        release_manifest = manifest(self.bundle)
        classifications = json.loads(
            (self.source / "release/source-classification.json").read_text(encoding="utf-8")
        )["files"]
        self.assertEqual(set(release_manifest["payloads"]), {"new-project", "adoption"})
        for payload in ("new-project", "adoption"):
            expected = [
                {
                    "path": destination,
                    "sourcePath": source_path,
                    "classification": classification,
                }
                for source_path, classification in classifications.items()
                for destination in [projected_path(source_path, classification, payload)]
                if destination is not None
            ]
            expected.sort(key=lambda item: item["path"])
            actual = [
                {
                    "path": item["path"],
                    "sourcePath": item["sourcePath"],
                    "classification": item["classification"],
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
        self.assertNotIn(".baton/state/project.json", adoption_paths)
        self.assertIn(".baton/integration/starter/state/project.json", adoption_paths)
        self.assertIn(".baton/integration/README.md", adoption_paths)
        self.assertNotIn(".baton/integration/README.md", new_paths)
        self.assertFalse(any(path.startswith(".codex/skills") for path in new_paths | adoption_paths))
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in new_paths | adoption_paths))
        self.assertFalse(any(path.startswith(".baton/state/") for path in adoption_paths))

    def test_unclassified_source_change_fails_closed(self) -> None:
        drifted = self.base / "drifted"
        shutil.copytree(self.source, drifted, symlinks=True)
        (drifted / "new-source-file.txt").write_text("unclassified\n", encoding="utf-8")
        run(["git", "add", "new-source-file.txt"], cwd=drifted)
        run(["git", "commit", "-qm", "unclassified source"], cwd=drifted)
        failed = build_bundle(drifted, self.base / "drifted-bundle", expected=1)
        self.assertIn("source classification drift", failed.stderr)

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
        self.assertEqual(release_manifest["source"]["commit"], git_commit(self.source))
        self.assertRegex(release_manifest["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(release_manifest["sourceClassificationSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            release_manifest["sourceClassificationSha256"],
            hashlib.sha256(
                (self.source / "release/source-classification.json").read_bytes()
            ).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
