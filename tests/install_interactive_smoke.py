#!/usr/bin/env python3
"""PTY smoke coverage for the keyboard-first installer flow."""

from __future__ import annotations

import atexit
import errno
import json
import os
import pty
import select
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(sys.argv[1]).resolve()
INSTALLER = ROOT / "install.sh"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tools"))
from codex_config_contract import assert_codex_config

ARROW_DOWN = b"\x1b[B"
ENTER = b"\r"
TEMP_TARGETS: list[Path] = []


@atexit.register
def cleanup_targets() -> None:
    for target in TEMP_TARGETS:
        shutil.rmtree(target, ignore_errors=True)


def run_interactive(
    steps: list[tuple[bytes, bytes]],
    *,
    prepopulate: bool = False,
    extra_args: list[str] | None = None,
) -> tuple[Path, bytes]:
    target = Path(tempfile.mkdtemp(prefix="agentic-harness-interactive-"))
    TEMP_TARGETS.append(target)
    if prepopulate:
        (target / "keep-me.txt").write_text("preserve me\n", encoding="utf-8")
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(target)
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env.pop("NO_COLOR", None)
        os.execve("/bin/bash", ["bash", str(INSTALLER), "--no-git", *(extra_args or [])], env)

    transcript = bytearray()
    step_index = 0
    scan_from = 0
    deadline = time.monotonic() + 20
    status: int | None = None

    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                try:
                    chunk = os.read(fd, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        chunk = b""
                    else:
                        raise
                if chunk:
                    transcript.extend(chunk)

            if step_index < len(steps):
                needle, response = steps[step_index]
                location = transcript.find(needle, scan_from)
                if location >= 0:
                    os.write(fd, response)
                    scan_from = len(transcript)
                    step_index += 1

            waited_pid, waited_status = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                status = waited_status
                break
    finally:
        if status is None:
            os.kill(pid, signal.SIGTERM)
            _, status = os.waitpid(pid, 0)
        os.close(fd)

    if step_index != len(steps):
        raise AssertionError(
            f"interactive flow stopped at step {step_index + 1}/{len(steps)}\n"
            + transcript.decode("utf-8", errors="replace")
        )
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        raise AssertionError(transcript.decode("utf-8", errors="replace"))
    return target, bytes(transcript)


def metadata(target: Path) -> dict:
    return json.loads((target / ".agent-harness.json").read_text(encoding="utf-8"))


def assert_concurrency_config(target: Path) -> None:
    assert_codex_config(target / ".codex/config.toml")


preset_target, preset_output = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ENTER),
    ],
    extra_args=["--project-type", "game-development", "--reasoning-preset", "deep"],
)
preset = metadata(preset_target)
assert preset["projectType"] == "game-development"
assert preset["reasoningPreset"] == "deep"
assert preset["reasoning"] == {
    "projectDirector": "xhigh",
    "deliveryLead": "xhigh",
    "specialistLead": "xhigh",
    "executionWorker": "high",
    "harnessEvaluator": "xhigh",
}
assert preset_target.name in (preset_target / "README.md").read_text(encoding="utf-8")
assert b"\x1b[" in preset_output
assert (preset_target / ".codex/skills").is_symlink()
assert (preset_target / ".codex/skills").resolve() == (preset_target / ".agents/skills").resolve()
assert_concurrency_config(preset_target)

custom_target, _ = run_interactive(
    [
        (b"What are you building?", ARROW_DOWN + ARROW_DOWN + ENTER),
        (b"Project name", b"Ops Pilot" + ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ARROW_DOWN + ARROW_DOWN + ENTER),
        (b"Project Director reasoning", ENTER),
        (b"Delivery Lead reasoning", ENTER),
        (b"Specialist Lead reasoning", ENTER),
        (b"Execution worker reasoning", ENTER),
        (b"Harness Evaluator reasoning", ENTER),
    ]
)
custom = metadata(custom_target)
assert custom["projectType"] == "business-operations"
assert custom["reasoningPreset"] == "custom"
assert custom["reasoning"]["specialistLead"] == "high"
assert (custom_target / ".codex/agents/specialist-lead.toml").is_file()
custom_readme = (custom_target / "README.md").read_text(encoding="utf-8")
assert "## First project prompt" in custom_readme
assert "Bootstrap Ops Pilot using the repository harness." in custom_readme
assert not (custom_target / "BOOTSTRAP_PROMPT.md").exists()
assert (custom_target / ".codex/skills").is_symlink()
assert (custom_target / ".codex/skills").resolve() == (custom_target / ".agents/skills").resolve()
assert_concurrency_config(custom_target)

nonempty_target, nonempty_output = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"Choose a new empty directory", b"nested" + ENTER),
        (b"How much reasoning should the team use?", ENTER),
    ],
    prepopulate=True,
)
assert (nonempty_target / "keep-me.txt").read_text(encoding="utf-8") == "preserve me\n"
assert (nonempty_target / "nested/.agent-harness.json").is_file()
assert b"That location is not empty" in nonempty_output
assert_concurrency_config(nonempty_target / "nested")

print("PASS: interactive keyboard installer smoke completed")
