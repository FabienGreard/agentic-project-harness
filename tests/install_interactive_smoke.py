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
    expected_exit: int = 0,
) -> tuple[Path, bytes]:
    target = Path(tempfile.mkdtemp(prefix="agentic-harness-interactive-"))
    TEMP_TARGETS.append(target)
    state_home = target.parent / f"{target.name}-external-state"
    TEMP_TARGETS.append(state_home)
    if prepopulate:
        (target / "keep-me.txt").write_text("preserve me\n", encoding="utf-8")
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(target)
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["XDG_STATE_HOME"] = str(state_home)
        env.pop("NO_COLOR", None)
        os.execve("/bin/bash", ["bash", str(INSTALLER)], env)

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
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != expected_exit:
        raise AssertionError(transcript.decode("utf-8", errors="replace"))
    return target, bytes(transcript)


def metadata(target: Path) -> dict:
    return json.loads((target / ".agent-harness.json").read_text(encoding="utf-8"))


def assert_concurrency_config(target: Path) -> None:
    assert_codex_config(target / ".codex/config.toml")


def team(target: Path) -> dict:
    return json.loads((target / "docs/state/team.json").read_text(encoding="utf-8"))


def assert_assurance_defaults(target: Path) -> None:
    project = json.loads(
        (target / "docs/state/project.json").read_text(encoding="utf-8")
    )["project"]
    assert project["assuranceDefaults"] == {
        "testRigor": "Standard",
        "humanReviewStages": [],
    }


medium_target, medium_output = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ENTER),
        (b"Hire your starting Consultants", ENTER),
    ]
)
medium = metadata(medium_target)
assert medium["projectType"] == "software-product"
assert medium["reasoningPreset"] == "medium"
assert medium["reasoning"] == {
    "management": "high",
    "operations": "high",
    "consultants": "high",
    "contractors": "medium",
    "internalAudit": "xhigh",
}
assert medium_target.name in (medium_target / "README.md").read_text(encoding="utf-8")
assert b"\x1b[" in medium_output
assert (medium_target / ".codex/skills").is_symlink()
assert (medium_target / ".codex/skills").resolve() == (medium_target / ".agents/skills").resolve()
assert_concurrency_config(medium_target)
assert_assurance_defaults(medium_target)
assert team(medium_target)["management"]["title"] == "Product Manager"
assert [item["id"] for item in team(medium_target)["consultants"] if item["status"] == "active"] == ["product-designer"]

low_target, _ = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", b"1"),
        (b"Hire your starting Consultants", ENTER),
    ]
)
low = metadata(low_target)
assert low["reasoningPreset"] == "low"
assert low["reasoning"] == {
    "management": "medium",
    "operations": "medium",
    "consultants": "medium",
    "contractors": "low",
    "internalAudit": "high",
}
assert_concurrency_config(low_target)
assert_assurance_defaults(low_target)

custom_target, _ = run_interactive(
    [
        (b"What are you building?", ARROW_DOWN + ARROW_DOWN + ENTER),
        (b"Project name", b"Ops Pilot" + ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ARROW_DOWN + ARROW_DOWN + ENTER),
        (b"Management reasoning", ENTER),
        (b"Operations reasoning", ENTER),
        (b"Consultants reasoning", ENTER),
        (b"Contractors reasoning", ENTER),
        (b"Internal Audit reasoning", ENTER),
        (b"Hire your starting Consultants", ENTER),
    ]
)
custom = metadata(custom_target)
assert custom["projectType"] == "business-operations"
assert custom["reasoningPreset"] == "custom"
assert custom["reasoning"]["consultants"] == "high"
assert (custom_target / ".codex/agents/consultant-change-manager.toml").is_file()
custom_readme = (custom_target / "README.md").read_text(encoding="utf-8")
assert "## First project prompt" in custom_readme
assert "Bootstrap Ops Pilot using the installed Agentic Project Harness." in custom_readme
assert "event-driven run-to-idle lifecycles" in custom_readme
assert "Confirm the generated `Standard` test-rigor default" in custom_readme
assert "per-ticket human-review timing" in custom_readme
assert not (custom_target / "BOOTSTRAP_PROMPT.md").exists()
assert (custom_target / ".codex/skills").is_symlink()
assert (custom_target / ".codex/skills").resolve() == (custom_target / ".agents/skills").resolve()
assert_concurrency_config(custom_target)
assert_assurance_defaults(custom_target)
assert team(custom_target)["operations"]["title"] == "Operations Manager"

no_consultant_target, _ = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ENTER),
        (b"Hire your starting Consultants", b" " + ENTER),
    ]
)
assert [
    item for item in team(no_consultant_target)["consultants"]
    if item["status"] == "active"
] == []
assert not list((no_consultant_target / ".codex/agents").glob("consultant-*.toml"))
assert_concurrency_config(no_consultant_target)

game_target, _ = run_interactive(
    [
        (b"What are you building?", ARROW_DOWN + ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ENTER),
        (b"Hire your starting Consultants", ENTER),
    ]
)
assert team(game_target)["management"]["title"] == "Game Director"
assert team(game_target)["operations"]["title"] == "Producer"
assert [item["id"] for item in team(game_target)["consultants"] if item["status"] == "active"] == ["art-director"]

research_target, _ = run_interactive(
    [
        (b"What are you building?", ARROW_DOWN * 3 + ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ENTER),
        (b"Hire your starting Consultants", ENTER),
    ]
)
assert team(research_target)["management"]["title"] == "Principal Investigator"
assert team(research_target)["operations"]["title"] == "Research Program Manager"
assert [item["id"] for item in team(research_target)["consultants"] if item["status"] == "active"] == ["research-methodologist"]

high_target, _ = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ARROW_DOWN + ENTER),
        (b"Hire your starting Consultants", ENTER),
    ]
)
high = metadata(high_target)
assert high["reasoningPreset"] == "high"
assert high["reasoning"] == {
    "management": "xhigh",
    "operations": "xhigh",
    "consultants": "xhigh",
    "contractors": "high",
    "internalAudit": "xhigh",
}
assert_concurrency_config(high_target)

nonempty_target, nonempty_output = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", ENTER),
        (b"How much reasoning should the team use?", ENTER),
        (b"Hire your starting Consultants", ENTER),
    ],
    prepopulate=True,
)
assert (nonempty_target / "keep-me.txt").read_text(encoding="utf-8") == "preserve me\n"
assert (nonempty_target / ".agent-harness.json").is_file()
assert metadata(nonempty_target)["installationStatus"] == "Installed"
assert b"Mode: adoption" in nonempty_output
assert_concurrency_config(nonempty_target)

unsafe_target, unsafe_output = run_interactive(
    [
        (b"What are you building?", ENTER),
        (b"Project name", ENTER),
        (b"Where should the harness be installed?", b"subdir/../escape" + ENTER),
        (b"How much reasoning should the team use?", ENTER),
        (b"Hire your starting Consultants", ENTER),
    ],
    expected_exit=1,
)
assert b"must not contain a '..' segment" in unsafe_output
assert not (unsafe_target / "subdir").exists()
assert not (unsafe_target / "escape").exists()

print("PASS: interactive keyboard installer smoke completed")
