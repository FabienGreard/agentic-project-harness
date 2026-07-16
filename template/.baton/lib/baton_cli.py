#!/usr/bin/env python3
"""Small installed command surface for Baton projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser

sys.dont_write_bytecode = True

from baton_lifecycle import LifecycleError, inspect_status
from baton_scrap import (
    apply_plan as apply_scrap_plan,
    create_plan as create_scrap_plan,
    write_plan as write_scrap_plan,
)


READINESS_PROTOCOLS = ("Waived", "Field Check", "Standard Protocol", "Full Certification")
CLEARANCE_PROTOCOLS = ("Autonomous", "Release Clearance", "Completion Clearance", "Continuous Clearance")


def human_output(
    surface: str,
    outcome: str,
    *,
    details: list[tuple[str, object]] | None = None,
    next_action: str = "",
    stream: object = None,
) -> None:
    destination = stream or sys.stdout
    print(f"\nBaton / {surface}", file=destination)
    print(outcome, file=destination)
    for label, value in details or []:
        if value is not None and value != "":
            print(f"  {label}: {value}", file=destination)
    if next_action:
        print(f"Next: {next_action}", file=destination)


def emit(payload: dict, as_json: bool, *, surface: str = "status") -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    installation = payload.get("installationStatus")
    if not payload.get("ok"):
        outcome = "Attention required: installed Baton files do not match their recorded state."
    elif installation == "Needs Integration":
        outcome = "Mature-repository adoption is staged for reviewed activation."
    elif installation == "Source Repository":
        outcome = "The local Baton source control plane is ready."
    else:
        outcome = "The Baton control plane is ready."
    details: list[tuple[str, object]] = [
        ("Version", payload.get("batonVersion") or payload.get("legacyHarnessVersion") or "not installed"),
        ("Installation", installation),
    ]
    if payload.get("integrity"):
        details.extend(
            [
                ("Modified managed files", len(payload["integrity"].get("modified", []))),
                ("Missing managed files", len(payload["integrity"].get("missing", []))),
                ("AGENTS.md block", payload["integrity"].get("agentsBlock")),
            ]
        )
    details.extend(
        [
            ("Pending integration actions", len(payload.get("pendingIntegration", []))),
            ("Cleanup candidates", len(payload.get("legacyCleanupCandidates", []))),
        ]
    )
    next_action = (
        "review and activate the mature-repository proposal through `$boot`."
        if installation == "Needs Integration"
        else "invoke `$boot` to continue onboarding."
        if surface == "boot"
        else "run `.baton/bin/baton doctor check` if you need full validation."
    )
    human_output(surface, outcome, details=details, next_action=next_action)


def run_internal(root: Path, tool: str, arguments: list[str]) -> int:
    path = root / f".baton/lib/{tool}.py"
    command = [sys.executable, str(path), *arguments]
    if tool == "harness_team" and arguments and arguments[0] != "catalog" and "--project-root" not in arguments:
        command.extend(["--project-root", str(root)])
    environment = dict(os.environ)
    environment["BATON_PROJECT_ROOT"] = str(root)
    return subprocess.run(command, cwd=root, env=environment, check=False).returncode


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise LifecycleError(f"required Baton file is missing or unsafe: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"invalid Baton JSON at {path}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"expected a JSON object at {path}")
    return value


def capture_internal(root: Path, tool: str, arguments: list[str]) -> dict:
    path = root / f".baton/lib/{tool}.py"
    command = [sys.executable, str(path), *arguments]
    if "--json" not in command:
        command.append("--json")
    if tool == "harness_team" and arguments and arguments[0] != "catalog" and "--project-root" not in arguments:
        command.extend(["--project-root", str(root)])
    environment = dict(os.environ)
    environment["BATON_PROJECT_ROOT"] = str(root)
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise LifecycleError(f"{tool} returned invalid JSON: {detail}") from error
    if not isinstance(payload, dict):
        raise LifecycleError(f"{tool} returned a non-object JSON result")
    if completed.returncode:
        detail = (
            payload.get("error")
            or payload.get("errors")
            or completed.stderr.strip()
            or f"{tool} failed"
        )
        raise LifecycleError(str(detail))
    return payload


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
            print(
                "OK: Baton adoption files are valid; mature-repository Project State "
                "still needs reviewed activation"
            )
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


def control_show(root: Path, as_json: bool) -> int:
    payload = read_json(root / ".baton/state/project.json")
    if as_json:
        print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))
    else:
        project = payload.get("project", {})
        human_output(
            "control",
            "Project controls loaded.",
            details=[
                ("Project", project.get("name", "Unknown")),
                ("Phase", project.get("phase", "Unknown")),
                ("Readiness", project.get("assuranceDefaults", {}).get("readinessProtocol", "Unknown")),
                ("Clearance", project.get("assuranceDefaults", {}).get("clearanceProtocol", "Unknown")),
            ],
            next_action="use `$control` to propose a bounded change.",
        )
    return 0


def control_protocols(root: Path, readiness: str | None, clearance: str | None, as_json: bool) -> int:
    document = read_json(root / ".baton/state/project.json")
    project = document.get("project")
    if not isinstance(project, dict):
        raise LifecycleError("canonical Project State is invalid")
    defaults = project.get("assuranceDefaults")
    if not isinstance(defaults, dict):
        raise LifecycleError("canonical Project protocol defaults are invalid")
    before = dict(defaults)
    if readiness is not None:
        defaults["readinessProtocol"] = readiness
    if clearance is not None:
        defaults["clearanceProtocol"] = clearance
    if defaults == before:
        payload = {"ok": True, "changed": [], "assuranceDefaults": defaults}
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            human_output(
                "control",
                "Project protocols already match.",
                details=[
                    ("Readiness", defaults["readinessProtocol"]),
                    ("Clearance", defaults["clearanceProtocol"]),
                ],
                next_action="return to the Project task.",
            )
        return 0
    goals = read_json(root / ".baton/state/goals.json")
    tickets = read_json(root / ".baton/state/tickets.json")
    for goal in goals.get("goals", []):
        assurance = goal.get("assurance", {}) if isinstance(goal, dict) else {}
        if (
            clearance is not None
            and isinstance(assurance, dict)
            and assurance.get("clearanceProtocol") == before.get("clearanceProtocol")
            and not assurance.get("overrideReason")
        ):
            assurance["clearanceProtocol"] = clearance
    for ticket in tickets.get("tickets", []):
        assurance = ticket.get("assurance", {}) if isinstance(ticket, dict) else {}
        if not isinstance(assurance, dict) or assurance.get("overrideReason"):
            continue
        if readiness is not None and assurance.get("readinessProtocol") == before.get("readinessProtocol"):
            assurance["readinessProtocol"] = readiness
        if clearance is not None and assurance.get("clearanceProtocol") == before.get("clearanceProtocol"):
            assurance["clearanceProtocol"] = clearance
    operation = {
        "schemaVersion": 1,
        "operation": "replace-records",
        "records": {"project": document, "goals": goals, "tickets": tickets},
    }
    with tempfile.TemporaryDirectory(prefix="baton-control-") as raw:
        path = Path(raw) / "operation.json"
        path.write_text(json.dumps(operation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = capture_internal(root, "harness_state", ["apply", str(path)])
    payload = {
        "ok": True,
        "changed": result.get("changed", []),
        "assuranceDefaults": defaults,
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        human_output(
            "control",
            "Project protocols changed.",
            details=[
                ("Readiness", defaults["readinessProtocol"]),
                ("Clearance", defaults["clearanceProtocol"]),
                ("Changed records", len(payload["changed"])),
            ],
            next_action="run `.baton/bin/baton control check`.",
        )
    return 0


def terminal_view(root: Path, *, open_view: bool, as_json: bool) -> int:
    dashboard = root / ".baton/views/dashboard.html"
    if dashboard.is_symlink() or not dashboard.is_file():
        raise LifecycleError(
            "the generated Baton dashboard is missing or unsafe; "
            "run `.baton/bin/baton doctor check`"
        )
    opened = False
    if open_view:
        opened = bool(webbrowser.open(dashboard.resolve().as_uri()))
    payload = {
        "ok": True,
        "path": str(dashboard.resolve()),
        "sha256": hashlib.sha256(dashboard.read_bytes()).hexdigest(),
        "opened": opened,
    }
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        outcome = (
            "The generated control room is ready."
            if not open_view or opened
            else "The control room path is valid, but it could not be opened automatically."
        )
        human_output(
            "terminal",
            outcome,
            details=[
                ("Path", dashboard.resolve()),
                ("SHA-256", payload["sha256"]),
                ("Opened", "yes" if opened else "no"),
            ],
            next_action="open the verified HTML path." if not opened else "return to the Project task.",
        )
    return 0


def roster_list(root: Path, as_json: bool) -> int:
    team = read_json(root / ".baton/state/team.json")
    payload = {
        "ok": True,
        "preset": team.get("preset"),
        "management": team.get("management"),
        "operations": team.get("operations"),
        "consultants": team.get("consultants", []),
        "contractorBench": team.get("contractorBench", []),
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        seats: list[tuple[str, object]] = []
        for key in ("management", "operations"):
            seat = payload.get(key) or {}
            seats.append((seat.get("commonName", key.title()), seat.get("title", "Unconfigured")))
        for consultant in payload["consultants"]:
            seats.append(
                (
                    "Consultant",
                    f"{consultant.get('title')} [{consultant.get('status')}]",
                )
            )
        human_output(
            "roster",
            f"{len(seats)} permanent seats are configured.",
            details=seats,
            next_action="use `$roster` to propose one team change.",
        )
    return 0


def doctor(root: Path, *, recover: bool, as_json: bool) -> int:
    recovery: dict[str, dict] = {}
    if recover:
        recovery["team"] = capture_internal(root, "harness_team", ["recover"])
        memory = root / ".baton/memory/memory.json"
        history = root / ".baton/memory/history.jsonl"
        if memory.exists() or history.exists():
            recovery["memory"] = capture_internal(root, "baton_memory", ["recover"])

    status = inspect_status(root)
    if status.get("installationStatus") == "Needs Integration":
        payload = {
            "ok": bool(status.get("ok")),
            "mode": "recover" if recover else "check",
            "installation": status,
            "installationStatus": "Needs Integration",
            "quarantinedStarter": True,
            "checks": {"adoption": {"ok": bool(status.get("ok"))}},
        }
        if recover:
            payload["recovery"] = recovery
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        elif payload["ok"]:
            human_output(
                "doctor",
                "Baton adoption files are valid; reviewed activation is still required.",
                details=[("Recovered transactions", sum(item.get("recoveredCount", 0) for item in recovery.values()))],
                next_action="continue mature-repository adoption through `$boot`.",
            )
        else:
            human_output(
                "doctor",
                "Attention required: Baton adoption diagnosis failed.",
                next_action="inspect the reported adoption evidence.",
                stream=sys.stderr,
            )
        return 0 if payload["ok"] else 1
    checks: dict[str, dict] = {}
    checks["state"] = capture_internal(root, "harness_state", ["check"])
    checks["roster"] = capture_internal(root, "harness_team", ["check"])
    memory = root / ".baton/memory/memory.json"
    history = root / ".baton/memory/history.jsonl"
    if memory.exists() or history.exists():
        checks["memory"] = capture_internal(root, "baton_memory", ["check"])
    payload = {
        "ok": bool(status.get("ok")) and all(bool(item.get("ok")) for item in checks.values()),
        "mode": "recover" if recover else "check",
        "installation": status,
        "checks": checks,
    }
    if recover:
        payload["recovery"] = recovery
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif payload["ok"]:
        recovered_count = sum(item.get("recoveredCount", 0) for item in recovery.values())
        human_output(
            "doctor",
            (
                f"Recovered {recovered_count} interrupted "
                f"transaction{'s' if recovered_count != 1 else ''}; Baton is healthy."
                if recover
                else "Baton installation, State, roster, and Memory are healthy."
            ),
            details=[("Recovered transactions", recovered_count)] if recover else [],
            next_action="return to the Project task.",
        )
    else:
        human_output(
            "doctor",
            "Attention required: Baton diagnosis failed.",
            next_action="inspect the failing check and its external recovery evidence.",
            stream=sys.stderr,
        )
    return 0 if payload["ok"] else 1


def parser() -> argparse.ArgumentParser:
    def command_parser(
        subparsers: argparse._SubParsersAction,
        name: str,
        help_text: str,
        *examples: str,
    ) -> argparse.ArgumentParser:
        epilog = ""
        if examples:
            epilog = "Examples:\n" + "\n".join(f"  {example}" for example in examples)
        return subparsers.add_parser(
            name,
            help=help_text,
            description=help_text[0].upper() + help_text[1:] + ".",
            epilog=epilog or None,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

    def json_flag(child: argparse.ArgumentParser) -> None:
        child.add_argument(
            "--json",
            action="store_true",
            help="emit one machine-readable JSON value",
        )

    result = argparse.ArgumentParser(
        prog=".baton/bin/baton",
        description="Inspect and manage this Baton control plane.",
        epilog=(
            "Examples:\n"
            "  .baton/bin/baton terminal status\n"
            "  .baton/bin/baton doctor check --json\n"
            "  .baton/bin/baton --help"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = result.add_subparsers(dest="command", required=True)

    boot = command_parser(
        commands,
        "boot",
        "onboard a Project or activate mature-repository adoption",
        ".baton/bin/baton boot status --json",
        ".baton/bin/baton boot catalog --field presets --json",
    )
    boot_commands = boot.add_subparsers(dest="boot_command", required=True)
    boot_status = command_parser(
        boot_commands,
        "status",
        "inspect installation and adoption status",
        ".baton/bin/baton boot status",
        ".baton/bin/baton boot status --json",
    )
    json_flag(boot_status)
    boot_inspect = command_parser(
        boot_commands,
        "inspect",
        "inspect privacy-filtered onboarding state",
        ".baton/bin/baton boot inspect --section summary --json",
    )
    boot_inspect.add_argument(
        "--section",
        default="summary",
        help="onboarding section to inspect (default: summary)",
    )
    json_flag(boot_inspect)
    boot_initialize = command_parser(
        boot_commands,
        "initialize",
        "initialize absent internal onboarding State",
        ".baton/bin/baton boot initialize --json",
    )
    json_flag(boot_initialize)
    for name, help_text, example in (
        (
            "record",
            "record one validated onboarding transaction from a file or stdin",
            ".baton/bin/baton boot record /tmp/onboarding-operation.json --json",
        ),
        (
            "next",
            "resolve the next onboarding action from a file or stdin",
            ".baton/bin/baton boot next /tmp/onboarding-context.json --json",
        ),
    ):
        child = command_parser(boot_commands, name, help_text, example)
        child.add_argument(
            "input",
            nargs="?",
            default="-",
            help="path to a validated JSON input, or - for stdin (default: -)",
        )
        json_flag(child)
    boot_activate = command_parser(
        boot_commands,
        "activate",
        "activate reviewed mature-repository Project State",
        ".baton/bin/baton boot activate --from /tmp/reviewed-proposal --yes --json",
    )
    boot_activate.add_argument(
        "--from",
        dest="proposal",
        type=Path,
        required=True,
        help="directory containing all six reviewed canonical State records",
    )
    boot_activate.add_argument(
        "--yes",
        action="store_true",
        help="confirm the exact reviewed activation without prompting",
    )
    json_flag(boot_activate)
    boot_catalog = command_parser(
        boot_commands,
        "catalog",
        "inspect onboarding presets or Consultants",
        ".baton/bin/baton boot catalog --field presets --json",
        ".baton/bin/baton boot catalog --preset software-product --field consultants --json",
    )
    boot_catalog.add_argument("--preset", help="preset identifier for Consultant fields")
    boot_catalog.add_argument(
        "--field",
        choices=("presets", "consultants", "defaults"),
        default="presets",
        help="catalog field to return (default: presets)",
    )
    json_flag(boot_catalog)
    boot_configure = command_parser(
        boot_commands,
        "configure",
        "set the unconfirmed onboarding preset",
        ".baton/bin/baton boot configure --preset software-product "
        "--consultant product-designer --invocation-task-id TASK_ID --yes --json",
    )
    boot_configure.add_argument("--preset", required=True, help="selected preset identifier")
    boot_configure.add_argument(
        "--consultant",
        action="append",
        dest="consultants",
        help="selected Consultant identifier; repeat for multiple seats",
    )
    boot_configure.add_argument(
        "--no-consultants",
        action="store_true",
        help="select no recurring Consultants",
    )
    boot_configure.add_argument(
        "--invocation-task-id",
        help="stable ID of the task that owns the onboarding conversation",
    )
    boot_configure.add_argument(
        "--yes",
        action="store_true",
        help="confirm the exact preset selection without prompting",
    )
    json_flag(boot_configure)

    control = command_parser(
        commands,
        "control",
        "inspect or change canonical Project controls",
        ".baton/bin/baton control show",
        ".baton/bin/baton control check --json",
    )
    control_commands = control.add_subparsers(dest="control_command", required=True)
    control_show_parser = command_parser(
        control_commands,
        "show",
        "show canonical Project controls",
        ".baton/bin/baton control show",
    )
    json_flag(control_show_parser)
    control_check = command_parser(
        control_commands,
        "check",
        "validate canonical State",
        ".baton/bin/baton control check --json",
    )
    json_flag(control_check)
    control_apply = command_parser(
        control_commands,
        "apply",
        "apply one validated canonical State operation",
        ".baton/bin/baton control apply /tmp/replace-records.json --json",
    )
    control_apply.add_argument("operation", type=Path, help="validated State operation JSON file")
    json_flag(control_apply)
    protocols = command_parser(
        control_commands,
        "protocols",
        "set Project Readiness and Clearance defaults",
        '.baton/bin/baton control protocols --readiness "Field Check" --clearance "Release Clearance" --json',
    )
    protocols.add_argument("--readiness", choices=READINESS_PROTOCOLS, help="new Project Readiness default")
    protocols.add_argument("--clearance", choices=CLEARANCE_PROTOCOLS, help="new Project Clearance default")
    json_flag(protocols)
    control_memory = command_parser(
        control_commands,
        "memory",
        "use advanced privacy-filtered Memory access",
        ".baton/bin/baton control memory inspect --section summary --json",
    )
    control_memory_commands = control_memory.add_subparsers(dest="control_memory_command", required=True)
    control_memory_inspect = command_parser(
        control_memory_commands,
        "inspect",
        "inspect privacy-filtered Memory",
        ".baton/bin/baton control memory inspect --section summary --json",
    )
    control_memory_inspect.add_argument(
        "--section",
        default="summary",
        help="privacy-filtered section to inspect (default: summary)",
    )
    json_flag(control_memory_inspect)
    control_memory_transact = command_parser(
        control_memory_commands,
        "transact",
        "apply one authority-checked Memory transaction from a file or stdin",
        ".baton/bin/baton control memory transact /tmp/memory-operation.json --json",
    )
    control_memory_transact.add_argument(
        "input",
        nargs="?",
        default="-",
        help="path to a validated JSON input, or - for stdin (default: -)",
    )
    json_flag(control_memory_transact)

    roster = command_parser(
        commands,
        "roster",
        "list, hire, offboard, or reconfigure the permanent team",
        ".baton/bin/baton roster list",
        ".baton/bin/baton roster check --json",
    )
    roster_commands = roster.add_subparsers(dest="roster_command", required=True)
    roster_list_parser = command_parser(
        roster_commands,
        "list",
        "show the permanent team and Contractor bench",
        ".baton/bin/baton roster list",
    )
    json_flag(roster_list_parser)
    roster_check = command_parser(
        roster_commands,
        "check",
        "validate team State and generated configs",
        ".baton/bin/baton roster check --json",
    )
    json_flag(roster_check)
    roster_catalog = command_parser(
        roster_commands,
        "catalog",
        "inspect presets or Consultants",
        ".baton/bin/baton roster catalog --preset software-product --field consultants --json",
    )
    roster_catalog.add_argument("--preset", help="preset identifier for Consultant fields")
    roster_catalog.add_argument(
        "--field",
        choices=("presets", "consultants", "defaults"),
        default="presets",
        help="catalog field to return (default: presets)",
    )
    json_flag(roster_catalog)
    roster_hire = command_parser(
        roster_commands,
        "hire",
        "hire a recurring Consultant",
        ".baton/bin/baton roster hire --consultant security-lead --yes --json",
        ".baton/bin/baton roster hire --custom /tmp/consultant.json --yes --json",
    )
    roster_hire.add_argument("--consultant", help="curated Consultant identifier")
    roster_hire.add_argument("--custom", type=Path, help="schema-valid custom Consultant JSON file")
    roster_hire.add_argument("--yes", action="store_true", help="confirm the exact hire without prompting")
    json_flag(roster_hire)
    roster_fire = command_parser(
        roster_commands,
        "fire",
        "offboard an active Consultant while preserving history",
        ".baton/bin/baton roster fire --consultant security-lead --yes --json",
    )
    roster_fire.add_argument("--consultant", help="active Consultant identifier")
    roster_fire.add_argument("--yes", action="store_true", help="confirm the exact offboarding without prompting")
    json_flag(roster_fire)
    roster_configure = command_parser(
        roster_commands,
        "configure",
        "change the unconfirmed Project preset",
        ".baton/bin/baton roster configure --preset research --no-consultants "
        "--invocation-task-id TASK_ID --yes --json",
    )
    roster_configure.add_argument("--preset", required=True, help="selected preset identifier")
    roster_configure.add_argument(
        "--consultant",
        action="append",
        dest="consultants",
        help="selected Consultant identifier; repeat for multiple seats",
    )
    roster_configure.add_argument("--no-consultants", action="store_true", help="select no recurring Consultants")
    roster_configure.add_argument("--invocation-task-id", help="stable ID of the onboarding task")
    roster_configure.add_argument("--yes", action="store_true", help="confirm the exact roster without prompting")
    json_flag(roster_configure)

    terminal = command_parser(
        commands,
        "terminal",
        "inspect Baton status or show its HTML control room",
        ".baton/bin/baton terminal status",
        ".baton/bin/baton terminal view --open",
    )
    terminal_commands = terminal.add_subparsers(dest="terminal_command", required=True)
    terminal_status = command_parser(
        terminal_commands,
        "status",
        "show version, provenance, and integrity",
        ".baton/bin/baton terminal status --json",
    )
    json_flag(terminal_status)
    terminal_view_parser = command_parser(
        terminal_commands,
        "view",
        "locate or open the generated HTML control room",
        ".baton/bin/baton terminal view --json",
        ".baton/bin/baton terminal view --open",
    )
    terminal_view_parser.add_argument("--open", action="store_true", help="open the verified HTML view")
    json_flag(terminal_view_parser)

    upgrade_parser = command_parser(
        commands,
        "upgrade",
        "inspect or install a supported stable Baton release",
        ".baton/bin/baton upgrade status --json",
        ".baton/bin/baton upgrade apply --yes --json",
    )
    upgrade_commands = upgrade_parser.add_subparsers(dest="upgrade_command", required=True)
    upgrade_status = command_parser(
        upgrade_commands,
        "status",
        "show the current Baton release and provenance",
        ".baton/bin/baton upgrade status --json",
    )
    json_flag(upgrade_status)
    upgrade_apply = command_parser(
        upgrade_commands,
        "apply",
        "install the latest supported stable release",
        ".baton/bin/baton upgrade apply --yes --json",
    )
    upgrade_apply.add_argument("--yes", action="store_true", help="confirm the verified stable upgrade")
    json_flag(upgrade_apply)

    doctor_parser = command_parser(
        commands,
        "doctor",
        "diagnose Baton or recover interrupted internal transactions",
        ".baton/bin/baton doctor check --json",
        ".baton/bin/baton doctor recover --json",
    )
    doctor_commands = doctor_parser.add_subparsers(dest="doctor_command", required=True)
    doctor_check = command_parser(
        doctor_commands,
        "check",
        "diagnose installation, State, roster, and Memory without recovery",
        ".baton/bin/baton doctor check --json",
    )
    json_flag(doctor_check)
    doctor_recover = command_parser(
        doctor_commands,
        "recover",
        "recover fully recognized interrupted team or Memory transactions, then validate",
        ".baton/bin/baton doctor recover --json",
    )
    json_flag(doctor_recover)

    scrap = command_parser(
        commands,
        "scrap",
        "preview or apply safe Baton removal",
        ".baton/bin/baton scrap plan --output /tmp/baton-scrap-plan.json --json",
    )
    scrap_commands = scrap.add_subparsers(dest="scrap_command", required=True)
    scrap_plan = command_parser(
        scrap_commands,
        "plan",
        "preview the exact removal boundary without changing the Repository",
        ".baton/bin/baton scrap plan --output /tmp/baton-scrap-plan.json --json",
    )
    scrap_plan.add_argument("--output", type=Path, help="write the immutable plan outside .baton")
    json_flag(scrap_plan)
    scrap_apply = command_parser(
        scrap_commands,
        "apply",
        "apply a previously reviewed removal plan",
        ".baton/bin/baton scrap apply --plan /tmp/baton-scrap-plan.json --yes --json",
    )
    scrap_apply.add_argument("--plan", type=Path, required=True, help="exact reviewed plan file")
    scrap_apply.add_argument("--yes", action="store_true", help="approve this exact unchanged plan")
    json_flag(scrap_apply)

    return result


def main(project_root: Path | None = None) -> int:
    root = (project_root or Path.cwd()).resolve()
    args = parser().parse_args()
    try:
        if args.command == "boot":
            if args.boot_command == "status":
                emit(inspect_status(root), args.json, surface="boot")
                return 0
            if args.boot_command == "inspect":
                return run_internal(root, "baton_memory", ["inspect", "--section", args.section, "--json"])
            if args.boot_command == "initialize":
                return run_internal(root, "baton_memory", ["initialize", "--json"])
            if args.boot_command == "record":
                return run_internal(root, "baton_memory", ["transact", args.input, "--json"])
            if args.boot_command == "next":
                return run_internal(root, "baton_memory", ["reconcile-bootstrap", args.input, "--json"])
            if args.boot_command == "activate":
                return activate(root, proposal=args.proposal, assume_yes=args.yes, as_json=args.json)
            if args.boot_command == "catalog":
                arguments = ["catalog", "--field", args.field]
                if args.preset:
                    arguments.extend(["--preset", args.preset])
                if args.json:
                    arguments.append("--json")
                return run_internal(root, "harness_team", arguments)
            arguments = ["reconfigure", "--preset", args.preset]
            for consultant in args.consultants or []:
                arguments.extend(["--consultant", consultant])
            if args.no_consultants:
                arguments.append("--no-consultants")
            if args.invocation_task_id:
                arguments.extend(["--invocation-task-id", args.invocation_task_id])
            if args.yes:
                arguments.append("--yes")
            if args.json:
                arguments.append("--json")
            return run_internal(root, "harness_team", arguments)
        if args.command == "control":
            if args.control_command == "show":
                return control_show(root, args.json)
            if args.control_command == "check":
                return run_internal(root, "harness_state", ["check", "--json"] if args.json else ["check"])
            if args.control_command == "apply":
                suffix = ["apply", str(args.operation)] + (["--json"] if args.json else [])
                return run_internal(root, "harness_state", suffix)
            if args.control_command == "memory":
                if args.control_memory_command == "inspect":
                    arguments = ["inspect", "--section", args.section]
                else:
                    arguments = ["transact", args.input]
                if args.json:
                    arguments.append("--json")
                return run_internal(root, "baton_memory", arguments)
            if args.readiness is None and args.clearance is None:
                raise LifecycleError("control protocols requires --readiness, --clearance, or both")
            return control_protocols(root, args.readiness, args.clearance, args.json)
        if args.command == "roster":
            if args.roster_command == "list":
                return roster_list(root, args.json)
            if args.roster_command == "check":
                arguments = ["check", "--json"] if args.json else ["check"]
            elif args.roster_command == "catalog":
                arguments = ["catalog", "--field", args.field]
                if args.preset:
                    arguments.extend(["--preset", args.preset])
                if args.json:
                    arguments.append("--json")
            elif args.roster_command == "hire":
                arguments = ["hire"]
                if args.consultant:
                    arguments.extend(["--consultant", args.consultant])
                if args.custom:
                    arguments.extend(["--custom", str(args.custom)])
                if args.yes:
                    arguments.append("--yes")
                if args.json:
                    arguments.append("--json")
            elif args.roster_command == "fire":
                arguments = ["fire"]
                if args.consultant:
                    arguments.extend(["--consultant", args.consultant])
                if args.yes:
                    arguments.append("--yes")
                if args.json:
                    arguments.append("--json")
            else:
                arguments = ["reconfigure", "--preset", args.preset]
                for consultant in args.consultants or []:
                    arguments.extend(["--consultant", consultant])
                if args.no_consultants:
                    arguments.append("--no-consultants")
                if args.invocation_task_id:
                    arguments.extend(["--invocation-task-id", args.invocation_task_id])
                if args.yes:
                    arguments.append("--yes")
                if args.json:
                    arguments.append("--json")
            return run_internal(root, "harness_team", arguments)
        if args.command == "terminal":
            if args.terminal_command == "status":
                emit(inspect_status(root), args.json, surface="terminal")
                return 0
            return terminal_view(root, open_view=args.open, as_json=args.json)
        if args.command == "upgrade":
            if args.upgrade_command == "status":
                emit(inspect_status(root), args.json, surface="upgrade")
                return 0
            return update(root, assume_yes=args.yes, as_json=args.json)
        if args.command == "doctor":
            return doctor(root, recover=args.doctor_command == "recover", as_json=args.json)
        if args.command == "scrap":
            if args.scrap_command == "plan":
                payload = create_scrap_plan(root)
                if args.output:
                    write_scrap_plan(payload, args.output, root)
                    payload = {**payload, "planPath": str(args.output.expanduser().resolve(strict=False))}
                if args.json:
                    print(json.dumps(payload, indent=2, ensure_ascii=False))
                else:
                    human_output(
                        "removal plan",
                        "The exact removal boundary is ready for review. No changes were made.",
                        details=[
                            ("Plan digest", payload["planDigest"]),
                            ("Automatic actions", len(payload["actions"]) + 1),
                            ("Preserved or manual actions", len(payload["manualActions"])),
                            ("Plan file", payload.get("planPath")),
                        ],
                        next_action="review this exact plan before approving removal.",
                    )
                return 0
            payload = apply_scrap_plan(root, args.plan, assume_yes=args.yes)
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                human_output(
                    "removed",
                    "Baton was removed from the Repository.",
                    details=[
                        ("Backup", payload["backupPath"]),
                        ("Report", payload["reportPath"]),
                    ],
                    next_action="retain the external backup.",
                )
            return 0
        raise LifecycleError(f"unknown Baton command: {args.command}")
    except (LifecycleError, OSError, subprocess.SubprocessError) as error:
        as_json = bool(getattr(args, "json", False))
        if as_json:
            print(json.dumps({"ok": False, "error": str(error)}))
        else:
            human_output(
                getattr(args, "command", "attention"),
                f"Attention required: {error}",
                next_action="correct the reported boundary and retry once.",
                stream=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
