#!/usr/bin/env python3
"""PTY coverage for the acquisition-only installer."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import pty
import select
import signal
import sys
import tempfile
import time
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from baton_testkit import assert_no_python_cache, build_bundle, make_candidate  # noqa: E402


class InstallerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-installer-boundary-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle"
        build_bundle(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_installer_acquires_defaults_without_project_questions(self) -> None:
        target = self.base / "repository"
        target.mkdir()
        child, descriptor = pty.fork()
        if child == 0:
            os.chdir(target)
            environment = dict(os.environ)
            environment.update(
                {
                    "BATON_RELEASE_DIR": str(self.bundle),
                    "HOME": str(self.base / "home"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "TERM": "xterm-256color",
                    "XDG_STATE_HOME": str(self.base / "state"),
                }
            )
            os.execve("/bin/bash", ["bash", str(self.bundle / "install.sh")], environment)

        transcript = bytearray()
        status = None
        deadline = time.monotonic() + 30
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([descriptor], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(descriptor, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        chunk = b""
                    transcript.extend(chunk)
                waited, waited_status = os.waitpid(child, os.WNOHANG)
                if waited == child:
                    status = waited_status
                    break
        finally:
            if status is None:
                os.kill(child, signal.SIGTERM)
                _, status = os.waitpid(child, 0)
            os.close(descriptor)

        rendered = transcript.decode("utf-8", errors="replace")
        self.assertTrue(os.WIFEXITED(status), rendered)
        self.assertEqual(os.WEXITSTATUS(status), 0, rendered)
        for retired_prompt in (
            "What are you building?",
            "Project name",
            "How much reasoning",
            "SELECT READINESS PROTOCOL",
            "SELECT CLEARANCE PROTOCOL",
            "Hire your starting Consultants",
        ):
            self.assertNotIn(retired_prompt, rendered)

        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["projectType"], "software-product")
        self.assertEqual(metadata["reasoningPreset"], "medium")
        project = json.loads((target / ".baton/state/project.json").read_text(encoding="utf-8"))["project"]
        self.assertEqual(
            project["assuranceDefaults"],
            {"readinessProtocol": "Standard Protocol", "clearanceProtocol": "Release Clearance"},
        )
        self.assertTrue((target / ".agents/skills/boot").is_symlink())
        self.assertFalse((target / ".codex/skills").exists())
        assert_no_python_cache(target)


if __name__ == "__main__":
    unittest.main()
