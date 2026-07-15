#!/usr/bin/env python3
"""Small installed command surface for Baton projects."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

sys.dont_write_bytecode = True

from baton_lifecycle import LifecycleError, inspect_status


def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print("\nBaton status")
    print(f"  Version: {payload.get('batonVersion') or payload.get('legacyHarnessVersion') or 'not installed'}")
    print(f"  Installation: {payload.get('installationStatus')}")
    if payload.get("integrity"):
        print(f"  Modified managed files: {len(payload['integrity'].get('modified', []))}")
        print(f"  Missing managed files: {len(payload['integrity'].get('missing', []))}")
        print(f"  AGENTS.md block: {payload['integrity'].get('agentsBlock')}")
    print(f"  Pending integration actions: {len(payload.get('pendingIntegration', []))}")
    print(f"  Human-approved cleanup candidates: {len(payload.get('legacyCleanupCandidates', []))}")


def run_internal(root: Path, tool: str, arguments: list[str]) -> int:
    path = root / f".baton/lib/{tool}.py"
    command = [sys.executable, str(path), *arguments]
    if tool == "harness_team" and arguments and arguments[0] != "catalog" and "--project-root" not in arguments:
        command.extend(["--project-root", str(root)])
    environment = dict(os.environ)
    environment["BATON_PROJECT_ROOT"] = str(root)
    return subprocess.run(command, cwd=root, env=environment, check=False).returncode


def run_check(root: Path, as_json: bool) -> int:
    status = inspect_status(root)
    if status.get("installationStatus") == "Needs Integration":
        payload = {
            "ok": bool(status.get("ok")),
            "installationStatus": "Needs Integration",
            "quarantinedStarter": True,
            "errors": [] if status.get("ok") else ["Baton-managed adoption files differ from their baselines"],
        }
        if as_json:
            print(json.dumps(payload, indent=2))
        elif payload["ok"]:
            print("OK: Baton adoption files are valid; mature project state still needs reviewed activation")
        else:
            print("ERROR: " + payload["errors"][0], file=sys.stderr)
        return 0 if payload["ok"] else 1
    suffix = ["--json"] if as_json else []
    state = run_internal(root, "harness_state", ["check", *suffix])
    if state:
        return state
    return run_internal(root, "harness_team", ["check", *suffix])


def activate(root: Path, *, proposal: Path, assume_yes: bool, as_json: bool) -> int:
    command = [
        sys.executable,
        str(root / ".baton/lib/baton_lifecycle.py"),
        "activate",
        "--project-root",
        str(root),
        "--from",
        str(proposal.resolve()),
    ]
    if assume_yes:
        command.append("--yes")
    if as_json:
        command.append("--json")
    environment = dict(os.environ)
    environment["BATON_PROJECT_ROOT"] = str(root)
    return subprocess.run(command, cwd=root, env=environment, check=False).returncode


def update(root: Path, *, assume_yes: bool, as_json: bool) -> int:
    metadata = root / ".baton/metadata.json"
    if metadata.is_symlink():
        raise LifecycleError("Baton metadata may not be a symbolic link")
    if not metadata.is_file() and not (root / ".agent-harness.json").is_file():
        raise LifecycleError("this repository has no Baton or supported legacy installation")
    release_dir = os.environ.get("BATON_RELEASE_DIR")
    with tempfile.TemporaryDirectory(prefix="baton-update-bootstrap-") as raw:
        installer = Path(raw) / "install.sh"
        if release_dir:
            source = Path(release_dir).expanduser().resolve() / "install.sh"
            installer.write_bytes(source.read_bytes())
        else:
            repository = "FabienGreard/baton"
            if metadata.is_file():
                try:
                    value = json.loads(metadata.read_text(encoding="utf-8"))
                    configured = value.get("source", {}).get("repository")
                    if configured in {"FabienGreard/baton", "FabienGreard/agentic-project-harness"}:
                        repository = configured
                except (OSError, json.JSONDecodeError):
                    pass
            url = f"https://github.com/{repository}/releases/latest/download/install.sh"
            urllib.request.urlretrieve(url, installer)
        command = ["bash", str(installer), "--target", str(root)]
        if assume_yes:
            command.append("--yes")
        if as_json:
            command.append("--json")
        environment = dict(os.environ)
        if release_dir:
            environment["BATON_RELEASE_DIR"] = release_dir
        return subprocess.run(command, cwd=root, env=environment, check=False).returncode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog=".baton/bin/baton", description="Inspect or update this Baton installation.")
    commands = result.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="show installed version, provenance, and integrity")
    status.add_argument("--json", action="store_true")
    update_parser = commands.add_parser("update", help="run the same stable lifecycle used by the installer")
    update_parser.add_argument("--yes", action="store_true")
    update_parser.add_argument("--json", action="store_true")
    check = commands.add_parser("check", help="validate Baton-owned state and team records")
    check.add_argument("--json", action="store_true")
    state = commands.add_parser("_state", help=argparse.SUPPRESS)
    state.add_argument("arguments", nargs=argparse.REMAINDER)
    team = commands.add_parser("_team", help=argparse.SUPPRESS)
    team.add_argument("arguments", nargs=argparse.REMAINDER)
    memory = commands.add_parser("_memory", help=argparse.SUPPRESS)
    memory.add_argument("arguments", nargs=argparse.REMAINDER)
    activation = commands.add_parser("_activate", help=argparse.SUPPRESS)
    activation.add_argument("--from", dest="proposal", type=Path, required=True)
    activation.add_argument("--yes", action="store_true")
    activation.add_argument("--json", action="store_true")
    return result


def main(project_root: Path | None = None) -> int:
    root = (project_root or Path.cwd()).resolve()
    args = parser().parse_args()
    try:
        if args.command == "status":
            emit(inspect_status(root), args.json)
            return 0
        if args.command == "update":
            return update(root, assume_yes=args.yes, as_json=args.json)
        if args.command == "check":
            return run_check(root, args.json)
        if args.command == "_state":
            return run_internal(root, "harness_state", args.arguments)
        if args.command == "_memory":
            return run_internal(root, "baton_memory", args.arguments)
        if args.command == "_activate":
            return activate(root, proposal=args.proposal, assume_yes=args.yes, as_json=args.json)
        return run_internal(root, "harness_team", args.arguments)
    except (LifecycleError, OSError, subprocess.SubprocessError) as error:
        as_json = bool(getattr(args, "json", False))
        if as_json:
            print(json.dumps({"ok": False, "error": str(error)}))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
