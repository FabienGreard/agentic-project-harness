#!/usr/bin/env python3
"""PTY acceptance coverage for Baton preset and custom installer flows."""

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
from typing import List, Optional, Tuple
import unittest


sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from baton_testkit import (  # noqa: E402
    assert_no_python_cache,
    build_bundle,
    expected_consumer_config,
    make_candidate,
    semantic_toml,
)


ENTER = b"\r"


class InteractiveInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="baton-interactive-tests-")
        cls.base = Path(cls.temporary.name).resolve()
        cls.source = make_candidate(cls.base, "0.6.0")
        cls.bundle = cls.base / "bundle"
        build_bundle(cls.source, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def run_pty(
        self,
        name: str,
        steps: List[Tuple[bytes, bytes]],
    ) -> Tuple[Path, bytes]:
        target = self.base / name
        target.mkdir()
        state_home = self.base / f"state-{name}"
        child, descriptor = pty.fork()
        if child == 0:
            os.chdir(target)
            environment = dict(os.environ)
            environment.update(
                {
                    "BATON_RELEASE_DIR": str(self.bundle),
                    "HOME": str(self.base / f"home-{name}"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "TERM": "xterm-256color",
                    "XDG_STATE_HOME": str(state_home),
                }
            )
            environment.pop("NO_COLOR", None)
            os.execve(
                "/bin/bash",
                ["bash", str(self.bundle / "install.sh")],
                environment,
            )

        transcript = bytearray()
        step_index = 0
        scan_from = 0
        deadline = time.monotonic() + 30
        status: Optional[int] = None
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([descriptor], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(descriptor, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            chunk = b""
                        else:
                            raise
                    transcript.extend(chunk)
                if step_index < len(steps):
                    prompt, response = steps[step_index]
                    location = transcript.find(prompt, scan_from)
                    if location >= 0:
                        os.write(descriptor, response)
                        scan_from = len(transcript)
                        step_index += 1
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
        self.assertEqual(
            step_index,
            len(steps),
            f"interactive flow stopped at step {step_index + 1}/{len(steps)}\n{rendered}",
        )
        self.assertTrue(os.WIFEXITED(status), rendered)
        self.assertEqual(os.WEXITSTATUS(status), 0, rendered)
        return target, bytes(transcript)

    def test_interactive_game_preset_uses_selected_defaults(self) -> None:
        target, transcript = self.run_pty(
            "game-preset",
            [
                (b"What are you building?", b"2"),
                (b"Project name", b"PTY Game" + ENTER),
                (b"Where should Baton be installed?", ENTER),
                (b"How much reasoning should the team use?", b"1"),
                (b"Hire your starting Consultants", ENTER),
            ],
        )
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["projectType"], "game-development")
        self.assertEqual(metadata["reasoningPreset"], "low")
        self.assertEqual(
            metadata["reasoning"],
            {
                "management": "medium",
                "operations": "medium",
                "consultants": "medium",
                "contractors": "low",
                "internalAudit": "high",
            },
        )
        team = json.loads((target / ".baton/state/team.json").read_text(encoding="utf-8"))
        self.assertEqual(team["management"]["title"], "Game Director")
        self.assertEqual(team["operations"]["title"], "Producer")
        self.assertEqual(
            [item["id"] for item in team["consultants"] if item["status"] == "active"],
            ["art-director"],
        )
        self.assertEqual(
            semantic_toml(target / ".codex/config.toml"),
            expected_consumer_config(("art-director",)),
        )
        self.assertIn(b"\x1b[", transcript)
        self.assertFalse((target / ".codex/skills").exists())
        assert_no_python_cache(target)

    def test_interactive_custom_reasoning_records_every_role_choice(self) -> None:
        target, _ = self.run_pty(
            "custom-reasoning",
            [
                (b"What are you building?", b"3"),
                (b"Project name", b"PTY Operations" + ENTER),
                (b"Where should Baton be installed?", ENTER),
                (b"How much reasoning should the team use?", b"4"),
                (b"Management reasoning", b"4"),
                (b"Operations reasoning", b"5"),
                (b"Consultants reasoning", b"6"),
                (b"Contractors reasoning", b"7"),
                (b"Internal Audit reasoning", b"8"),
                (b"Hire your starting Consultants", ENTER),
            ],
        )
        metadata = json.loads((target / ".baton/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["projectType"], "business-operations")
        self.assertEqual(metadata["reasoningPreset"], "custom")
        self.assertEqual(
            metadata["reasoning"],
            {
                "management": "low",
                "operations": "medium",
                "consultants": "high",
                "contractors": "xhigh",
                "internalAudit": "max",
            },
        )
        team = json.loads((target / ".baton/state/team.json").read_text(encoding="utf-8"))
        self.assertEqual(team["operations"]["title"], "Operations Manager")
        self.assertEqual(
            [item["id"] for item in team["consultants"] if item["status"] == "active"],
            ["change-manager"],
        )
        self.assertEqual(
            semantic_toml(target / ".codex/config.toml"),
            expected_consumer_config(("change-manager",)),
        )
        self.assertFalse((target / ".codex/skills").exists())
        assert_no_python_cache(target)


if __name__ == "__main__":
    unittest.main()
