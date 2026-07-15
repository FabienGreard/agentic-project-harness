#!/usr/bin/env python3
"""Dependency-free parser, renderer, and semantic contract for Codex config."""

from __future__ import annotations

from collections.abc import Iterable
import json
import re
from pathlib import Path
from typing import Any


EXPECTED_BASE: dict[str, Any] = {
    "approval_policy": "on-request",
    "approvals_reviewer": "auto_review",
    "sandbox_mode": "workspace-write",
    "agents": {
        "max_threads": 4,
        "max_depth": 1,
    },
    "sandbox_workspace_write": {
        "network_access": True,
    },
}
REQUIRED_AGENT_NAMES = ("management", "operations", "contractor", "internal_audit")


def _parse_value(raw: str) -> Any:
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?[0-9]+", raw):
        return int(raw)
    if raw.startswith('"') and raw.endswith('"'):
        value = json.loads(raw)
        if isinstance(value, str):
            return value
    raise ValueError(f"unsupported TOML value: {raw}")


def _table(root: dict[str, Any], dotted: str, number: int) -> dict[str, Any]:
    current = root
    parts = dotted.split(".")
    for index, part in enumerate(parts):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", part):
            raise ValueError(f"unsupported TOML table at line {number}: {dotted}")
        if part not in current:
            current[part] = {}
        value = current[part]
        if not isinstance(value, dict):
            raise ValueError(f"table conflicts with a scalar at line {number}: {dotted}")
        if index == len(parts) - 1 and value:
            raise ValueError(f"duplicate table at line {number}: {dotted}")
        current = value
    return current


def parse_codex_config(path: Path) -> dict[str, Any]:
    return parse_codex_config_text(path.read_text(encoding="utf-8"))


def parse_codex_config_text(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    current = parsed
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]", line)
        if section:
            current = _table(parsed, section.group(1), number)
            continue
        assignment = re.fullmatch(r"([A-Za-z0-9_-]+)\s*=\s*(.+)", line)
        if not assignment:
            raise ValueError(f"unsupported TOML syntax at line {number}: {raw_line}")
        key, raw_value = assignment.groups()
        if key in current:
            raise ValueError(f"duplicate key at line {number}: {key}")
        current[key] = _parse_value(raw_value.strip())
    return parsed


def agent_filename(name: str) -> str:
    if name.startswith("consultant_"):
        identifier = name.removeprefix("consultant_").replace("_", "-")
        return f"consultant-{identifier}.toml"
    return name.replace("_", "-") + ".toml"


def agent_description(name: str) -> str:
    fixed = {
        "management": "Own project outcomes, priority, scope, readiness, and release decisions.",
        "operations": "Own delivery, Contractor dispatch, integration, and verification.",
        "contractor": "Execute one bounded assignment for Operations.",
        "internal_audit": "Independently evaluate Baton behavior without joining the project team.",
    }
    if name in fixed:
        return fixed[name]
    if name.startswith("consultant_"):
        identifier = name.removeprefix("consultant_").replace("_", "-")
        return f"Recurring Consultant for the {identifier.replace('-', ' ')} domain."
    raise ValueError(f"unsupported Baton agent name: {name}")


def render_codex_config(agent_names: Iterable[str]) -> str:
    names = list(dict.fromkeys(agent_names))
    if not set(REQUIRED_AGENT_NAMES).issubset(names):
        raise ValueError("Baton Codex config lacks a required permanent or disposable role")
    lines = [
        'approval_policy = "on-request"',
        'approvals_reviewer = "auto_review"',
        'sandbox_mode = "workspace-write"',
        "",
        "[agents]",
        "max_threads = 4",
        "max_depth = 1",
        "",
        "[sandbox_workspace_write]",
        "network_access = true",
    ]
    for name in names:
        lines.extend(
            [
                "",
                f"[agents.{name}]",
                f"description = {json.dumps(agent_description(name))}",
                f"config_file = {json.dumps('../.baton/agents/' + agent_filename(name))}",
            ]
        )
    return "\n".join(lines) + "\n"


def base_semantics(config: dict[str, Any]) -> bool:
    if any(config.get(key) != EXPECTED_BASE[key] for key in ("approval_policy", "approvals_reviewer", "sandbox_mode", "sandbox_workspace_write")):
        return False
    agents = config.get("agents")
    return isinstance(agents, dict) and agents.get("max_threads") == 4 and agents.get("max_depth") == 1


def assert_codex_config(path: Path, expected_agent_names: Iterable[str] | None = None) -> None:
    actual = parse_codex_config(path)
    if not base_semantics(actual):
        raise AssertionError(f"Codex base config mismatch: expected {EXPECTED_BASE!r}, got {actual!r}")
    agents = actual.get("agents", {})
    actual_names = {name for name, value in agents.items() if isinstance(value, dict)}
    expected_names = set(expected_agent_names or REQUIRED_AGENT_NAMES)
    if actual_names != expected_names:
        raise AssertionError(f"Codex agent set mismatch: expected {sorted(expected_names)}, got {sorted(actual_names)}")
    for name in sorted(expected_names):
        record = agents[name]
        expected_path = "../.baton/agents/" + agent_filename(name)
        if (
            not isinstance(record.get("description"), str)
            or not record["description"].strip()
            or record.get("config_file") != expected_path
            or set(record) != {"description", "config_file"}
        ):
            raise AssertionError(f"Codex agent config mismatch for {name}: {record!r}")
