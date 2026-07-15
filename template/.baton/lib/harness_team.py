#!/usr/bin/env python3
"""Preset-driven team configuration and transactional Consultant lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Iterable
import uuid

sys.dont_write_bytecode = True

from harness_lock import MutationLockError, mutation_lock
from codex_config_contract import assert_codex_config, render_codex_config

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9-3.10 compatibility
    tomllib = None


ROOT = Path(
    os.environ.get("BATON_PROJECT_ROOT", Path(__file__).resolve().parents[2])
).expanduser().resolve()
CATALOG_NAME = ".baton/team-presets.json"
TEAM_NAME = ".baton/state/team.json"
METADATA_NAME = ".baton/metadata.json"
AGENTS_DIR = ".baton/agents"
REASONING_LEVELS = {
    "inherit", "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"
}
REASONING_KEYS = {
    "management", "operations", "consultants", "contractors", "internalAudit"
}
CONSULTANT_FIELDS = {
    "id", "title", "headline", "domain", "readinessRequirements",
    "evidenceRequirements", "acceptanceAuthority",
}
ROLE_CONFIGS = {
    "management.toml",
    "operations.toml",
    "contractor.toml",
    "internal-audit.toml",
}


class TeamError(RuntimeError):
    """A team operation could not continue safely."""


def locked_team_mutation(function):
    @wraps(function)
    def wrapped(*, project_root: Path, **kwargs):
        with mutation_lock(project_root, f"team-{function.__name__}"):
            return function(project_root=project_root, **kwargs)

    return wrapped


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def entry_digest(path: Path) -> str | None:
    if path.is_symlink():
        return sha256_bytes(os.readlink(path).encode("utf-8"))
    if path.is_file():
        return sha256_file(path)
    return None


def safe_relative(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\0" in raw:
        raise TeamError(f"unsafe project path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise TeamError(f"unsafe project path: {raw!r}")
    return path.as_posix()


def inside(root: Path, relative: str) -> Path:
    relative = safe_relative(relative)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise TeamError(f"team path passes through a symbolic link: {relative}")
    resolved_root = root.resolve()
    resolved_parent = candidate.parent.resolve(strict=False)
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise TeamError(f"team path escapes the project: {relative}")
    return candidate


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TeamError(f"required JSON file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise TeamError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise TeamError(f"expected an object in {path}")
    return value


def read_project_record(root: Path, relative: str) -> dict[str, Any]:
    path = inside(root, relative)
    if path.is_symlink() or not path.is_file():
        raise TeamError(f"required Baton project record is missing or unsafe: {relative}")
    return read_json(path)


def write_json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TeamError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if "\0" in normalized or '"""' in normalized:
        raise TeamError(f"{field} contains unsupported characters")
    return normalized


def text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise TeamError(f"{field} must be a non-empty array")
    return [nonempty_text(item, f"{field}[]") for item in value]


def validate_identifier(value: Any, field: str = "id") -> str:
    value = nonempty_text(value, field)
    if re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", value) is None:
        raise TeamError(f"{field} must use lowercase hyphen-case")
    return value


def normalize_consultant(
    raw: dict[str, Any], *, source: str, non_authorities: list[str]
) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != CONSULTANT_FIELDS:
        missing = sorted(CONSULTANT_FIELDS - set(raw if isinstance(raw, dict) else {}))
        extra = sorted(set(raw if isinstance(raw, dict) else {}) - CONSULTANT_FIELDS)
        raise TeamError(
            "consultant definition must use the standard template"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; unsupported: {', '.join(extra)}" if extra else "")
        )
    return {
        "id": validate_identifier(raw["id"]),
        "title": nonempty_text(raw["title"], "title"),
        "headline": nonempty_text(raw["headline"], "headline"),
        "domain": nonempty_text(raw["domain"], "domain"),
        "readinessRequirements": text_list(raw["readinessRequirements"], "readinessRequirements"),
        "evidenceRequirements": text_list(raw["evidenceRequirements"], "evidenceRequirements"),
        "acceptanceAuthority": nonempty_text(raw["acceptanceAuthority"], "acceptanceAuthority"),
        "nonAuthorities": list(non_authorities),
        "source": source,
    }


def load_catalog(root: Path = ROOT) -> dict[str, Any]:
    catalog = read_json(inside(root, CATALOG_NAME))
    if type(catalog.get("schemaVersion")) is not int or catalog.get("schemaVersion") != 1:
        raise TeamError("unsupported team preset schema")
    common = catalog.get("commonNames")
    expected_common = {"management", "operations", "consultants", "contractors", "internalAudit"}
    if not isinstance(common, dict) or set(common) != expected_common:
        raise TeamError("team catalog common names are incomplete")
    for key in expected_common:
        nonempty_text(common[key], f"commonNames.{key}")
    non_authorities = text_list(catalog.get("consultantNonAuthorities"), "consultantNonAuthorities")
    if set(non_authorities) != {
        "overall priority", "Contractor dispatch", "technical integration", "publication"
    }:
        raise TeamError("Consultant non-authorities do not match the governance contract")
    audit = catalog.get("internalAudit")
    if (
        not isinstance(audit, dict)
        or set(audit) != {"title", "headline", "projectTeamMember"}
        or audit.get("projectTeamMember") is not False
    ):
        raise TeamError("Internal Audit must remain outside the project team")
    nonempty_text(audit["title"], "internalAudit.title")
    nonempty_text(audit["headline"], "internalAudit.headline")
    presets = catalog.get("presets")
    if not isinstance(presets, dict) or not presets:
        raise TeamError("team catalog has no presets")
    for preset_id, preset in presets.items():
        validate_identifier(preset_id, "preset id")
        if not isinstance(preset, dict):
            raise TeamError(f"preset {preset_id} must be an object")
        expected = {
            "label", "headline", "management", "operations", "defaultConsultants",
            "consultants", "contractorBench",
        }
        if set(preset) != expected:
            raise TeamError(f"preset {preset_id} does not match the standard template")
        nonempty_text(preset["label"], f"{preset_id}.label")
        nonempty_text(preset["headline"], f"{preset_id}.headline")
        for role in ("management", "operations"):
            definition = preset[role]
            if not isinstance(definition, dict) or set(definition) != {"title", "headline"}:
                raise TeamError(f"preset {preset_id} {role} is invalid")
            nonempty_text(definition["title"], f"{preset_id}.{role}.title")
            nonempty_text(definition["headline"], f"{preset_id}.{role}.headline")
        if not isinstance(preset["consultants"], list):
            raise TeamError(f"preset {preset_id} consultants must be an array")
        normalized = [
            normalize_consultant(item, source="preset", non_authorities=non_authorities)
            for item in preset["consultants"]
        ]
        ids = [item["id"] for item in normalized]
        titles = [item["title"].casefold() for item in normalized]
        if len(ids) != len(set(ids)) or len(titles) != len(set(titles)):
            raise TeamError(f"preset {preset_id} has duplicate Consultant identities")
        defaults = preset["defaultConsultants"]
        if not isinstance(defaults, list) or len(defaults) != len(set(defaults)):
            raise TeamError(f"preset {preset_id} defaults are invalid")
        if not set(defaults).issubset(ids):
            raise TeamError(f"preset {preset_id} defaults reference unknown Consultants")
        if not isinstance(preset["contractorBench"], list) or not preset["contractorBench"]:
            raise TeamError(f"preset {preset_id} has no Contractor bench")
        bench_ids: set[str] = set()
        for capability in preset["contractorBench"]:
            if not isinstance(capability, dict) or set(capability) != {"id", "headline"}:
                raise TeamError(f"preset {preset_id} Contractor capability is invalid")
            identifier = validate_identifier(capability["id"], "contractor id")
            nonempty_text(capability["headline"], "contractor headline")
            if identifier in bench_ids:
                raise TeamError(f"preset {preset_id} has duplicate Contractor capabilities")
            bench_ids.add(identifier)
    return catalog


def preset_definition(catalog: dict[str, Any], preset_id: str) -> dict[str, Any]:
    presets = catalog["presets"]
    if preset_id not in presets:
        raise TeamError(
            f"unknown project preset {preset_id!r}; choose one of: {', '.join(presets)}"
        )
    return presets[preset_id]


def normalized_reasoning(reasoning: dict[str, Any]) -> dict[str, str]:
    if not isinstance(reasoning, dict):
        raise TeamError("reasoning must be an object")
    if set(reasoning) == REASONING_KEYS:
        normalized = dict(reasoning)
    elif set(reasoning) == {
        "projectDirector", "deliveryLead", "specialistLead", "executionWorker", "harnessEvaluator"
    }:
        normalized = {
            "management": reasoning["projectDirector"],
            "operations": reasoning["deliveryLead"],
            "consultants": reasoning["specialistLead"],
            "contractors": reasoning["executionWorker"],
            "internalAudit": reasoning["harnessEvaluator"],
        }
    else:
        raise TeamError("reasoning must define every common harness role")
    if any(level not in REASONING_LEVELS for level in normalized.values()):
        raise TeamError("reasoning contains an unsupported level")
    return normalized


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def role_config(
    *, name: str, description: str, reasoning: str, instructions: str, read_only: bool = False
) -> str:
    lines = [f"name = {toml_string(name)}", f"description = {toml_string(description)}"]
    if reasoning != "inherit":
        lines.append(f"model_reasoning_effort = {toml_string(reasoning)}")
    if read_only:
        lines.append('sandbox_mode = "read-only"')
    lines.append(f"developer_instructions = {toml_string(instructions.strip())}")
    return "\n".join(lines) + "\n"


def parse_role_config(content: str, filename: str) -> dict[str, Any]:
    """Parse and validate generated role TOML on every supported Python version."""
    if tomllib is not None:
        try:
            parsed = tomllib.loads(content)
        except tomllib.TOMLDecodeError as error:
            raise TeamError(f"generated agent config is invalid TOML ({filename}): {error}") from error
    else:
        parsed: dict[str, Any] = {}
        for line in content.splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r"([a-z_]+)\s*=\s*(.+)", line)
            if match is None or match.group(1) in parsed:
                raise TeamError(f"generated agent config has invalid syntax ({filename})")
            try:
                parsed[match.group(1)] = json.loads(match.group(2))
            except json.JSONDecodeError as error:
                raise TeamError(
                    f"generated agent config has invalid quoted value ({filename})"
                ) from error
    required = {"name", "description", "developer_instructions"}
    allowed = {*required, "model_reasoning_effort", "sandbox_mode"}
    if not required.issubset(parsed) or not set(parsed).issubset(allowed):
        raise TeamError(f"generated agent config has an invalid field set ({filename})")
    if not all(isinstance(parsed[key], str) and parsed[key].strip() for key in required):
        raise TeamError(f"generated agent config has empty required values ({filename})")
    return parsed


def validate_role_config(content: str, filename: str) -> None:
    """Validate generated role TOML before any config reaches a transaction."""
    parse_role_config(content, filename)


def consultant_config(consultant: dict[str, Any], reasoning: str) -> str:
    readiness = " ".join(consultant["readinessRequirements"])
    evidence = " ".join(consultant["evidenceRequirements"])
    non_authorities = ", ".join(consultant["nonAuthorities"])
    return role_config(
        name=f"consultant_{consultant['id'].replace('-', '_')}",
        description=f"Consultant / {consultant['title']} — {consultant['headline']}",
        reasoning=reasoning,
        instructions=f"""
You are a Consultant serving as {consultant['title']} for the configured {consultant['domain']} domain.
Read AGENTS.md, every applicable .baton/rules/ file, .baton/state/team.json, and .baton/roles/consultant.md completely before acting.
Define readiness and accept or reject evidence only inside this approved domain. Readiness: {readiness} Evidence: {evidence} Authority: {consultant['acceptanceAuthority']}
You do not own {non_authorities}. Return execution requirements and revisions to Operations; never dispatch or steer Contractors directly.
This is a permanent top-level task with an event-driven run-to-idle lifecycle. Only a new message to this exact task is a wake; never create, resume, recreate, or attach a persistent goal. A legacy automatic continuation is a non-wake event: do no work and report it for removal. If .baton/state/team.json marks this Consultant inactive, perform no project work and report the stale task or config for cleanup.
""",
    )


def fixed_configs(
    *, preset: dict[str, Any], reasoning: dict[str, str]
) -> dict[str, str]:
    management = preset["management"]
    operations = preset["operations"]
    bench = "; ".join(
        f"{item['id']}: {item['headline']}" for item in preset["contractorBench"]
    )
    return {
        "management.toml": role_config(
            name="management",
            description=f"Management / {management['title']} — {management['headline']}",
            reasoning=reasoning["management"],
            instructions=f"""
You are Management, serving as {management['title']}. {management['headline']}
Read AGENTS.md, every applicable .baton/rules/ file, .baton/state/team.json, and .baton/roles/management.md completely before acting.
Own outcomes, priority, scope, readiness, durable decisions, publication, and human-review gates. Commission active Consultants for their configured domains and route executable work to Operations. Never dispatch or steer Contractors directly.
This is a permanent top-level task with an event-driven run-to-idle lifecycle. Only a new message to this exact task is a wake; never create, resume, recreate, or attach a persistent goal. A legacy automatic continuation is a non-wake event: do no work and report it for removal.
""",
        ),
        "operations.toml": role_config(
            name="operations",
            description=f"Operations / {operations['title']} — {operations['headline']}",
            reasoning=reasoning["operations"],
            instructions=f"""
You are Operations, serving as {operations['title']}. {operations['headline']}
Read AGENTS.md, every applicable .baton/rules/ file, .baton/state/team.json, and .baton/roles/operations.md completely before acting.
Own executable planning, exclusive ownership, Contractor dispatch, integration, verification, and completion evidence. Route missing outcome intent to Management and missing expert requirements to the active Consultant for that domain.
This is a permanent top-level task with an event-driven run-to-idle lifecycle. Only a new message to this exact task is a wake; never create, resume, recreate, or attach a persistent goal. A legacy automatic continuation is a non-wake event: do no work and report it for removal.
""",
        ),
        "contractor.toml": role_config(
            name="contractor",
            description="Disposable Contractor selected by Operations for one bounded capability and assignment.",
            reasoning=reasoning["contractors"],
            instructions=f"""
You are a disposable Contractor selected by Operations for one bounded assignment. The available preset capabilities are: {bench}
Read AGENTS.md, every applicable .baton/rules/ file, .baton/state/team.json, .baton/roles/contractor.md, and the complete assignment before acting.
Stay inside exclusive scope, do not invent intent or acceptance, verify proportionally, return exact evidence to Operations, and stop. The capability labels are routing hints, not job titles you must perform in conversation.
""",
        ),
        "internal-audit.toml": role_config(
            name="internal_audit",
            description="Hidden disposable read-only Baton evaluator; not a project team member or QA Consultant.",
            reasoning=reasoning["internalAudit"],
            read_only=True,
            instructions="""
You are Internal Audit, a disposable independent evaluator of Baton rather than a member of the project team.
Read AGENTS.md, applicable .baton/rules/ files, .baton/state/team.json, .baton/roles/internal-audit.md, and the exact evaluation contract.
Audit only the bounded orchestration evidence. Do not perform project QA, mutate state, fix findings, message permanent roles, dispatch, accept project work, or publish. Return the report and stop.
""",
        ),
    }


def consultant_from_preset(
    catalog: dict[str, Any], preset_id: str, consultant_id: str
) -> dict[str, Any]:
    preset = preset_definition(catalog, preset_id)
    for raw in preset["consultants"]:
        if raw["id"] == consultant_id:
            return normalize_consultant(
                raw,
                source="preset",
                non_authorities=catalog["consultantNonAuthorities"],
            )
    raise TeamError(f"Consultant {consultant_id!r} is not available for {preset['label']}")


def team_record(
    *, catalog: dict[str, Any], preset_id: str, selected: Iterable[str], reasoning: dict[str, str]
) -> dict[str, Any]:
    preset = preset_definition(catalog, preset_id)
    selected_ids = list(dict.fromkeys(selected))
    consultants = []
    now = utc_now()
    for identifier in selected_ids:
        consultant = consultant_from_preset(catalog, preset_id, identifier)
        consultant.update(
            {
                "status": "active",
                "configPath": f"{AGENTS_DIR}/consultant-{identifier}.toml",
                "configBaselineSha256": "",
                "hiredAt": now,
                "firedAt": "",
                "preservedConfig": False,
                "manualAction": "",
            }
        )
        consultants.append(consultant)
    return {
        "schemaVersion": 1,
        "recordType": "team",
        "preset": preset_id,
        "presetLabel": preset["label"],
        "commonNames": dict(catalog["commonNames"]),
        "management": {
            "commonName": catalog["commonNames"]["management"],
            "title": preset["management"]["title"],
            "headline": preset["management"]["headline"],
            "configPath": f"{AGENTS_DIR}/management.toml",
        },
        "operations": {
            "commonName": catalog["commonNames"]["operations"],
            "title": preset["operations"]["title"],
            "headline": preset["operations"]["headline"],
            "configPath": f"{AGENTS_DIR}/operations.toml",
        },
        "consultants": consultants,
        "contractorBench": [dict(item) for item in preset["contractorBench"]],
        "internalAudit": dict(catalog["internalAudit"]),
        "reasoning": dict(reasoning),
        "updatedAt": now,
    }


def validate_team(team: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "schemaVersion", "recordType", "preset", "presetLabel", "commonNames",
        "management", "operations", "consultants", "contractorBench", "internalAudit",
        "reasoning", "updatedAt",
    }
    if set(team) != expected:
        errors.append(".baton/state/team.json does not match the team record contract")
        return errors
    if type(team.get("schemaVersion")) is not int or team.get("schemaVersion") != 1 or team.get("recordType") != "team":
        errors.append(".baton/state/team.json has an unsupported schema")
    try:
        preset = preset_definition(catalog, team.get("preset"))
        reasoning = normalized_reasoning(team.get("reasoning"))
    except TeamError as error:
        errors.append(str(error))
        return errors
    if team.get("presetLabel") != preset["label"]:
        errors.append(".baton/state/team.json preset label drift")
    if team.get("commonNames") != catalog["commonNames"]:
        errors.append(".baton/state/team.json common-name drift")
    for role in ("management", "operations"):
        current = team.get(role)
        definition = preset[role]
        if not isinstance(current, dict) or current.get("title") != definition["title"]:
            errors.append(f".baton/state/team.json {role} persona drift")
    if team.get("contractorBench") != preset["contractorBench"]:
        errors.append(".baton/state/team.json Contractor bench drift")
    if team.get("internalAudit") != catalog["internalAudit"]:
        errors.append(".baton/state/team.json Internal Audit drift")
    consultants = team.get("consultants")
    if not isinstance(consultants, list):
        errors.append(".baton/state/team.json Consultants must be an array")
        return errors
    ids: set[str] = set()
    titles: set[str] = set()
    for index, raw in enumerate(consultants):
        if not isinstance(raw, dict):
            errors.append(f".baton/state/team.json consultant {index} must be an object")
            continue
        try:
            normalized = normalize_consultant(
                {key: raw.get(key) for key in CONSULTANT_FIELDS},
                source=raw.get("source"),
                non_authorities=catalog["consultantNonAuthorities"],
            )
        except TeamError as error:
            errors.append(f".baton/state/team.json consultant {index}: {error}")
            continue
        identifier = normalized["id"]
        title = normalized["title"].casefold()
        if raw.get("source") not in {"preset", "custom"}:
            errors.append(
                f".baton/state/team.json Consultant {identifier} has invalid source"
            )
        if identifier in ids or title in titles:
            errors.append(".baton/state/team.json has duplicate Consultant identities")
        ids.add(identifier)
        titles.add(title)
        if raw.get("nonAuthorities") != catalog["consultantNonAuthorities"]:
            errors.append(f".baton/state/team.json Consultant {identifier} has authority drift")
        if raw.get("status") not in {"active", "inactive"}:
            errors.append(f".baton/state/team.json Consultant {identifier} has invalid status")
        expected_path = f"{AGENTS_DIR}/consultant-{identifier}.toml"
        if raw.get("configPath") != expected_path:
            errors.append(f".baton/state/team.json Consultant {identifier} has invalid configPath")
        baseline = raw.get("configBaselineSha256")
        if raw.get("status") == "active" and not (
            isinstance(baseline, str) and re.fullmatch(r"[0-9a-f]{64}", baseline)
        ):
            errors.append(f".baton/state/team.json Consultant {identifier} lacks a config baseline")
        for field in ("hiredAt", "firedAt", "manualAction"):
            if not isinstance(raw.get(field), str):
                errors.append(f".baton/state/team.json Consultant {identifier} has invalid {field}")
        if not isinstance(raw.get("preservedConfig"), bool):
            errors.append(f".baton/state/team.json Consultant {identifier} has invalid preservedConfig")
    if team.get("reasoning") != reasoning:
        errors.append(".baton/state/team.json reasoning is not normalized")
    return errors


def render_team_configs(
    *, team: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, str]:
    preset = preset_definition(catalog, team["preset"])
    reasoning = normalized_reasoning(team["reasoning"])
    configs = fixed_configs(preset=preset, reasoning=reasoning)
    for consultant in team["consultants"]:
        if consultant["status"] == "active":
            configs[f"consultant-{consultant['id']}.toml"] = consultant_config(
                consultant, reasoning["consultants"]
            )
    for filename, content in configs.items():
        validate_role_config(content, filename)
    return configs


def codex_agent_names(team: dict[str, Any]) -> list[str]:
    names = ["management", "operations", "contractor", "internal_audit"]
    names.extend(
        f"consultant_{item['id'].replace('-', '_')}"
        for item in team["consultants"]
        if item["status"] == "active"
    )
    return names


def reconcile_codex_config(
    *, root: Path, team: dict[str, Any], metadata: dict[str, Any], transaction_id: str
) -> tuple[dict[str, bytes], dict[str, Any], list[str]]:
    updated = json.loads(json.dumps(metadata))
    managed = updated.get("managedFiles")
    if not isinstance(managed, dict):
        raise TeamError("installed Baton metadata has no managed-file map")
    desired = render_codex_config(codex_agent_names(team)).encode("utf-8")
    digest = sha256_bytes(desired)
    writes: dict[str, bytes] = {}
    manual: list[str] = []

    def preserve(relative: str) -> None:
        managed.pop(relative, None)
        owned = updated.setdefault("projectOwnedFiles", [])
        if relative not in owned:
            owned.append(relative)
            owned.sort()

    root_path = ".codex/config.toml"
    root_record = managed.get(root_path)
    if isinstance(root_record, dict):
        actual = entry_digest(inside(root, root_path))
        if actual == root_record.get("baselineSha256"):
            writes[root_path] = desired
            root_record["ownership"] = "integration-link"
            root_record["baselineSha256"] = digest
            return writes, updated, manual
        preserve(root_path)
        manual.append(
            "Preserved the modified .codex/config.toml as project-owned; merge the generated Baton proposal to register the current Consultant team."
        )

    integration_path = ".baton/integration/codex-config.toml"
    integration_record = managed.get(integration_path)
    integration = inside(root, integration_path)
    actual = entry_digest(integration)
    if isinstance(integration_record, dict) and actual == integration_record.get("baselineSha256"):
        writes[integration_path] = desired
        integration_record["ownership"] = "generated-config"
        integration_record["baselineSha256"] = digest
    elif integration_record is None and actual in {None, digest}:
        if actual is None:
            writes[integration_path] = desired
        managed[integration_path] = {
            "ownership": "generated-config",
            "baselineSha256": digest,
        }
    else:
        if integration_record is not None:
            preserve(integration_path)
        proposed = f".baton/integration/codex-config.{transaction_id}.toml"
        writes[proposed] = desired
        managed[proposed] = {
            "ownership": "generated-config",
            "baselineSha256": digest,
        }
        manual.append(
            f"Preserved the modified {integration_path}; merge {proposed} manually to register the current Consultant team."
        )
    return writes, updated, manual


def initialize_team(
    *, project_root: Path, preset_id: str, selected: Iterable[str], reasoning: dict[str, Any]
) -> dict[str, Any]:
    root = project_root.resolve()
    catalog = load_catalog(root)
    normalized = normalized_reasoning(reasoning)
    team = team_record(
        catalog=catalog, preset_id=preset_id, selected=selected, reasoning=normalized
    )
    agents = inside(root, AGENTS_DIR)
    agents.mkdir(parents=True, exist_ok=True)
    for path in agents.glob("*.toml"):
        if path.is_symlink() or not path.is_file():
            raise TeamError(f"agent config cannot be safely replaced: {path}")
        path.unlink()
    configs = render_team_configs(team=team, catalog=catalog)
    for filename, content in configs.items():
        (agents / filename).write_text(content, encoding="utf-8")
    for consultant in team["consultants"]:
        config = inside(root, consultant["configPath"])
        consultant["configBaselineSha256"] = sha256_file(config)
    inside(root, TEAM_NAME).write_text(write_json_text(team), encoding="utf-8")
    return team


def configure_existing_team(
    *, project_root: Path, team: dict[str, Any], reasoning: dict[str, Any]
) -> dict[str, Any]:
    root = project_root.resolve()
    catalog = load_catalog(root)
    normalized = normalized_reasoning(reasoning)
    configured = json.loads(json.dumps(team))
    configured["reasoning"] = normalized
    configured["updatedAt"] = utc_now()
    errors = validate_team(configured, catalog)
    if errors:
        raise TeamError("; ".join(errors))
    agents = inside(root, AGENTS_DIR)
    agents.mkdir(parents=True, exist_ok=True)
    for path in agents.glob("*.toml"):
        path.unlink()
    configs = render_team_configs(team=configured, catalog=catalog)
    for filename, content in configs.items():
        (agents / filename).write_text(content, encoding="utf-8")
    for consultant in configured["consultants"]:
        if consultant["status"] == "active":
            consultant["configBaselineSha256"] = sha256_file(
                inside(root, consultant["configPath"])
            )
    inside(root, TEAM_NAME).write_text(write_json_text(configured), encoding="utf-8")
    return configured


def transaction_directory(root: Path, transaction_id: str) -> Path:
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", transaction_id) is None:
        raise TeamError("invalid team transaction id")
    state_home = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).expanduser()
    project_id = sha256_bytes(str(root.resolve()).encode("utf-8"))[:16]
    transaction = (
        state_home / "baton" / project_id / "team" / transaction_id
    ).resolve(strict=False)
    project = root.resolve()
    if transaction == project or project in transaction.parents:
        raise TeamError("team transaction data must be outside the working tree")
    return transaction


def load_dashboard_module(root: Path):
    path = inside(root, ".baton/lib/harness_state.py")
    spec = importlib.util.spec_from_file_location("aph_project_harness_state", path)
    if spec is None or spec.loader is None:
        raise TeamError("could not load the project state renderer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dashboard_for(root: Path, team: dict[str, Any]) -> str:
    module = load_dashboard_module(root)
    errors: list[str] = []
    records = module.load_records(errors)
    records["team"] = team
    module.validate_records(records, errors)
    if errors:
        raise TeamError("team state would invalidate the project dashboard: " + "; ".join(errors))
    return module.render_dashboard(records)


def transaction_write(
    *, root: Path, writes: dict[str, bytes], removes: list[str], report: dict[str, Any]
) -> Path:
    transaction_id = report["transactionId"]
    transaction = transaction_directory(root, transaction_id)
    backup = transaction / "backup"
    transaction.mkdir(parents=True, exist_ok=False)
    affected = sorted(set(writes) | set(removes))
    previous: dict[str, bytes | None] = {}
    for relative in affected:
        path = inside(root, relative)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise TeamError(f"team transaction cannot safely modify {relative}")
        previous[relative] = path.read_bytes() if path.is_file() else None
        if path.is_file():
            target = backup.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    staged: dict[str, Path] = {}
    try:
        for relative, content in writes.items():
            path = inside(root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            staged[relative] = Path(raw_temp)
        for relative in removes:
            inside(root, relative).unlink(missing_ok=True)
        for relative, temporary in staged.items():
            os.replace(temporary, inside(root, relative))
        report["backupPath"] = str(backup)
        report["reportPath"] = str(transaction / "team-report.json")
        (transaction / "team-report.json").write_text(write_json_text(report), encoding="utf-8")
    except BaseException as error:
        for relative, content in previous.items():
            path = inside(root, relative)
            path.unlink(missing_ok=True)
            if content is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        rollback = dict(report)
        rollback.update({"result": "rolled-back", "error": str(error), "backupPath": str(backup)})
        (transaction / "team-report.json").write_text(write_json_text(rollback), encoding="utf-8")
        raise TeamError(f"team transaction failed and was rolled back: {error}") from error
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    return transaction


def metadata_with_team_change(
    *, metadata: dict[str, Any], add: dict[str, str] | None = None, remove: str | None = None,
    preserve: dict[str, str] | None = None, refresh: dict[str, str] | None = None,
    transaction_id: str,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(metadata))
    managed = updated.get("managedFiles")
    if not isinstance(managed, dict):
        raise TeamError("installed Baton metadata has no managed-file map")
    if add:
        managed[add["path"]] = {
            "ownership": "generated-config",
            "baselineSha256": add["sha256"],
        }
    if remove:
        managed.pop(remove, None)
    if preserve:
        managed.pop(preserve["path"], None)
        project_owned = updated.setdefault("projectOwnedFiles", [])
        if preserve["path"] not in project_owned:
            project_owned.append(preserve["path"])
            project_owned.sort()
    if refresh:
        managed[refresh["path"]] = {
            "ownership": "generated-config",
            "baselineSha256": refresh["sha256"],
        }
    updated["updatedAt"] = utc_now()
    updated["lastTransactionId"] = transaction_id
    updated["lastTeamTransactionId"] = transaction_id
    return updated


@locked_team_mutation
def hire_consultant(
    *, project_root: Path, consultant_id: str | None, custom_path: Path | None
) -> dict[str, Any]:
    root = project_root.resolve()
    catalog = load_catalog(root)
    team = read_project_record(root, TEAM_NAME)
    metadata = read_project_record(root, METADATA_NAME)
    errors = validate_team(team, catalog)
    if errors:
        raise TeamError("; ".join(errors))
    if (consultant_id is None) == (custom_path is None):
        raise TeamError("choose exactly one curated Consultant or one custom definition")
    if consultant_id:
        consultant = consultant_from_preset(catalog, team["preset"], consultant_id)
    else:
        raw = read_json(custom_path.resolve())
        consultant = normalize_consultant(
            raw,
            source="custom",
            non_authorities=catalog["consultantNonAuthorities"],
        )
    identifier = consultant["id"]
    active = [item for item in team["consultants"] if item["status"] == "active"]
    if any(item["id"] == identifier for item in active):
        raise TeamError(f"Consultant {identifier} is already active")
    if any(item["title"].casefold() == consultant["title"].casefold() for item in active):
        raise TeamError(f"an active Consultant already uses the title {consultant['title']!r}")
    existing = next((item for item in team["consultants"] if item["id"] == identifier), None)
    now = utc_now()
    consultant.update(
        {
            "status": "active",
            "configPath": f"{AGENTS_DIR}/consultant-{identifier}.toml",
            "configBaselineSha256": "",
            "hiredAt": now,
            "firedAt": "",
            "preservedConfig": False,
            "manualAction": "",
        }
    )
    updated_team = json.loads(json.dumps(team))
    if existing is None:
        updated_team["consultants"].append(consultant)
    else:
        index = next(i for i, item in enumerate(updated_team["consultants"]) if item["id"] == identifier)
        updated_team["consultants"][index] = consultant
    updated_team["updatedAt"] = now
    config = consultant_config(consultant, updated_team["reasoning"]["consultants"])
    consultant["configBaselineSha256"] = sha256_bytes(config.encode("utf-8"))
    target_record = next(item for item in updated_team["consultants"] if item["id"] == identifier)
    target_record["configBaselineSha256"] = consultant["configBaselineSha256"]
    config_path = consultant["configPath"]
    destination = inside(root, config_path)
    if destination.exists() or destination.is_symlink():
        raise TeamError(f"Consultant config path is already occupied: {config_path}")
    transaction_id = f"hire-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    dashboard = dashboard_for(root, updated_team)
    updated_metadata = metadata_with_team_change(
        metadata=metadata,
        add={"path": config_path, "sha256": consultant["configBaselineSha256"]},
        refresh={
            "path": ".baton/dashboard/index.html",
            "sha256": sha256_bytes(dashboard.encode("utf-8")),
        },
        transaction_id=transaction_id,
    )
    codex_writes, updated_metadata, codex_actions = reconcile_codex_config(
        root=root,
        team=updated_team,
        metadata=updated_metadata,
        transaction_id=transaction_id,
    )
    report = {
        "result": "applied",
        "action": "hire",
        "transactionId": transaction_id,
        "consultant": {"id": identifier, "title": consultant["title"], "source": consultant["source"]},
        "writes": [config_path, TEAM_NAME, ".baton/dashboard/index.html", METADATA_NAME, *codex_writes],
        "removes": [],
        "manualActions": codex_actions,
    }
    writes = {
        config_path: config.encode("utf-8"),
        TEAM_NAME: write_json_text(updated_team).encode("utf-8"),
        ".baton/dashboard/index.html": dashboard.encode("utf-8"),
        METADATA_NAME: write_json_text(updated_metadata).encode("utf-8"),
        **codex_writes,
    }
    transaction = transaction_write(
        root=root,
        writes=writes,
        removes=[],
        report=report,
    )
    return {
        "ok": True,
        "action": "hire",
        "consultant": report["consultant"],
        "manualActions": codex_actions,
        "transactionId": transaction_id,
        "backupPath": str(transaction / "backup"),
        "reportPath": str(transaction / "team-report.json"),
    }


@locked_team_mutation
def fire_consultant(*, project_root: Path, consultant_id: str) -> dict[str, Any]:
    root = project_root.resolve()
    catalog = load_catalog(root)
    team = read_project_record(root, TEAM_NAME)
    metadata = read_project_record(root, METADATA_NAME)
    errors = validate_team(team, catalog)
    if errors:
        raise TeamError("; ".join(errors))
    consultant = next(
        (item for item in team["consultants"] if item["id"] == consultant_id and item["status"] == "active"),
        None,
    )
    if consultant is None:
        raise TeamError(f"Consultant {consultant_id!r} is not active")
    config_path = consultant["configPath"]
    config = inside(root, config_path)
    if config.is_symlink() or (config.exists() and not config.is_file()):
        raise TeamError(
            f"Consultant config is not a safe regular file; no changes made: {config_path}"
        )
    config_missing = not config.exists()
    current_digest = sha256_file(config) if config.is_file() else None
    baseline = consultant["configBaselineSha256"]
    unchanged = current_digest == baseline
    updated_team = json.loads(json.dumps(team))
    record = next(item for item in updated_team["consultants"] if item["id"] == consultant_id)
    record["status"] = "inactive"
    record["firedAt"] = utc_now()
    record["preservedConfig"] = not config_missing and not unchanged
    record["manualAction"] = (
        "Review and manually archive or remove the preserved modified Codex agent config after explicit human approval."
        if record["preservedConfig"]
        else ""
    )
    updated_team["updatedAt"] = record["firedAt"]
    transaction_id = f"fire-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    dashboard = dashboard_for(root, updated_team)
    updated_metadata = metadata_with_team_change(
        metadata=metadata,
        remove=config_path if unchanged or config_missing else None,
        preserve=(
            {"path": config_path, "sha256": current_digest}
            if record["preservedConfig"] and current_digest is not None
            else None
        ),
        refresh={
            "path": ".baton/dashboard/index.html",
            "sha256": sha256_bytes(dashboard.encode("utf-8")),
        },
        transaction_id=transaction_id,
    )
    codex_writes, updated_metadata, codex_actions = reconcile_codex_config(
        root=root,
        team=updated_team,
        metadata=updated_metadata,
        transaction_id=transaction_id,
    )
    removes = [config_path] if unchanged else []
    manual_actions = [record["manualAction"]] if record["manualAction"] else []
    manual_actions.extend(codex_actions)
    report = {
        "result": "applied-needs-manual-cleanup" if manual_actions else "applied",
        "action": "fire",
        "transactionId": transaction_id,
        "consultant": {"id": consultant_id, "title": consultant["title"], "source": consultant["source"]},
        "writes": [TEAM_NAME, ".baton/dashboard/index.html", METADATA_NAME, *codex_writes],
        "removes": removes,
        "reconciledMissingFiles": [config_path] if config_missing else [],
        "preservedFiles": [config_path] if record["preservedConfig"] else [],
        "manualActions": manual_actions,
    }
    transaction = transaction_write(
        root=root,
        writes={
            TEAM_NAME: write_json_text(updated_team).encode("utf-8"),
            ".baton/dashboard/index.html": dashboard.encode("utf-8"),
            METADATA_NAME: write_json_text(updated_metadata).encode("utf-8"),
            **codex_writes,
        },
        removes=removes,
        report=report,
    )
    return {
        "ok": True,
        "action": "fire",
        "consultant": report["consultant"],
        "manualCleanupRequired": bool(manual_actions),
        "preservedFiles": report["preservedFiles"],
        "reconciledMissingFiles": report["reconciledMissingFiles"],
        "manualActions": manual_actions,
        "transactionId": transaction_id,
        "backupPath": str(transaction / "backup"),
        "reportPath": str(transaction / "team-report.json"),
    }


def confirm(action: str, title: str, assume_yes: bool) -> None:
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise TeamError(f"{action} requires a terminal or --yes")
    answer = input(f"{action} {title}? [y/N] ").strip().casefold()
    if answer not in {"y", "yes"}:
        raise TeamError("no changes made")


def choose(items: list[tuple[str, str, str]], prompt: str) -> str:
    if not sys.stdin.isatty():
        raise TeamError("interactive selection requires a terminal")
    print(f"\n╭─ {prompt}")
    for index, (_, title, headline) in enumerate(items, start=1):
        print(f"│  {index}. {title} — {headline}")
    print("╰─ Enter a number")
    while True:
        answer = input("› ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1][0]
        print("Choose one of the listed numbers.")


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if not payload.get("ok"):
        print(f"Error: {payload.get('error', 'operation failed')}", file=sys.stderr)
        return
    if payload.get("action") == "hire":
        consultant = payload["consultant"]
        print(f"\nWELCOME ABOARD // {consultant['title']}")
        print(f"  Consultant ID: {consultant['id']}")
        print(f"  Transaction: {payload['transactionId']}")
    elif payload.get("action") == "fire":
        consultant = payload["consultant"]
        print(f"\nEXIT INTERVIEW COMPLETE // {consultant['title']}")
        print(f"  Consultant ID: {consultant['id']}")
        print(f"  Transaction: {payload['transactionId']}")
        if payload["manualCleanupRequired"]:
            print("  Manual cleanup required; the modified config was preserved.")
            print(f"  Report: {payload['reportPath']}")
    else:
        print("OK: team catalog and state are valid")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    catalog = sub.add_parser("catalog", help="inspect the canonical preset catalog")
    catalog.add_argument("--preset")
    catalog.add_argument("--field", choices=("presets", "consultants", "defaults"), default="presets")
    catalog.add_argument("--json", action="store_true")
    check = sub.add_parser("check", help="validate team state and generated configs")
    check.add_argument("--project-root", type=Path, default=ROOT)
    check.add_argument("--json", action="store_true")
    hire = sub.add_parser("hire", help="hire a curated or custom Consultant")
    hire.add_argument("--project-root", type=Path, default=ROOT)
    hire.add_argument("--consultant")
    hire.add_argument("--custom", type=Path)
    hire.add_argument("--yes", action="store_true")
    hire.add_argument("--json", action="store_true")
    fire = sub.add_parser("fire", help="fire an active Consultant safely")
    fire.add_argument("--project-root", type=Path, default=ROOT)
    fire.add_argument("--consultant")
    fire.add_argument("--yes", action="store_true")
    fire.add_argument("--json", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "catalog":
            catalog = load_catalog(ROOT)
            if args.field == "presets":
                payload: Any = [
                    {"id": identifier, "label": preset["label"], "headline": preset["headline"]}
                    for identifier, preset in catalog["presets"].items()
                ]
            else:
                if not args.preset:
                    raise TeamError("--preset is required for Consultant catalog fields")
                preset = preset_definition(catalog, args.preset)
                payload = (
                    preset["defaultConsultants"]
                    if args.field == "defaults"
                    else preset["consultants"]
                )
            if args.json:
                print(json.dumps(payload, ensure_ascii=False))
            else:
                for item in payload:
                    if isinstance(item, str):
                        print(item)
                    else:
                        print("\t".join((item["id"], item.get("label", item.get("title", "")), item["headline"])))
            return 0
        root = args.project_root.resolve()
        if args.command == "check":
            catalog = load_catalog(root)
            team = read_project_record(root, TEAM_NAME)
            metadata = read_project_record(root, METADATA_NAME)
            errors = validate_team(team, catalog)
            if metadata.get("projectType") != team.get("preset"):
                errors.append("Baton metadata projectType differs from team preset")
            try:
                metadata_reasoning = normalized_reasoning(metadata.get("reasoning"))
            except TeamError as error:
                errors.append(f"Baton metadata reasoning is invalid: {error}")
            else:
                if metadata_reasoning != team.get("reasoning"):
                    errors.append("Baton metadata reasoning differs from team reasoning")
            if not errors:
                configs = render_team_configs(team=team, catalog=catalog)
                allowed_preserved = {
                    Path(item["configPath"]).name
                    for item in team["consultants"]
                    if item["status"] == "inactive" and item["preservedConfig"]
                }
                agents = inside(root, AGENTS_DIR)
                for path in agents.glob("consultant-*.toml"):
                    if path.is_symlink() or not path.is_file():
                        errors.append(
                            f"Consultant agent config is not a regular file: {path.relative_to(root)}"
                        )
                    elif path.name not in configs and path.name not in allowed_preserved:
                        errors.append(
                            f"unexpected Consultant agent config: {path.relative_to(root)}"
                        )
                for filename, expected in configs.items():
                    path = inside(root, f"{AGENTS_DIR}/{filename}")
                    if path.is_symlink() or not path.is_file():
                        errors.append(f"missing active agent config: {path.relative_to(root)}")
                    elif path.read_text(encoding="utf-8") != expected:
                        errors.append(f"generated agent config differs from team definition: {filename}")
                    if filename.startswith("consultant-") and path.is_file():
                        identifier = filename.removeprefix("consultant-").removesuffix(".toml")
                        consultant = next(item for item in team["consultants"] if item["id"] == identifier)
                        if sha256_bytes(expected.encode("utf-8")) != consultant["configBaselineSha256"]:
                            errors.append(f"active Consultant baseline differs from team definition: {filename}")
                if metadata.get("installationStatus") == "Installed":
                    managed = metadata.get("managedFiles")
                    if not isinstance(managed, dict):
                        errors.append("installed Baton metadata lacks managedFiles")
                    else:
                        for filename in configs:
                            relative = f"{AGENTS_DIR}/{filename}"
                            record = managed.get(relative)
                            if not isinstance(record, dict) or record.get("ownership") != "generated-config":
                                errors.append(f"installed agent config lacks generated ownership: {relative}")
                        for consultant in team["consultants"]:
                            if consultant["status"] != "inactive" or not consultant["preservedConfig"]:
                                continue
                            project_owned = metadata.get("projectOwnedFiles", [])
                            if consultant["configPath"] not in project_owned:
                                errors.append(
                                    f"preserved Consultant config lacks project ownership: {consultant['configPath']}"
                                )
                        codex_targets = [
                            relative
                            for relative in (
                                ".codex/config.toml",
                                ".baton/integration/codex-config.toml",
                            )
                            if isinstance(managed.get(relative), dict)
                        ]
                        if len(codex_targets) != 1:
                            errors.append("installed Baton state must own exactly one current Codex config or integration proposal")
                        else:
                            target = inside(root, codex_targets[0])
                            if target.is_symlink() or not target.is_file():
                                errors.append(f"managed Codex config is not a regular file: {codex_targets[0]}")
                            else:
                                try:
                                    assert_codex_config(target, codex_agent_names(team))
                                except (AssertionError, OSError, ValueError) as error:
                                    errors.append(f"managed Codex config differs from active team: {error}")
            payload = {"ok": not errors, "errors": errors}
            emit(payload, args.json)
            return 0 if not errors else 1
        if args.command == "hire":
            if args.consultant is None and args.custom is None:
                catalog = load_catalog(root)
                team = read_project_record(root, TEAM_NAME)
                active = {item["id"] for item in team["consultants"] if item["status"] == "active"}
                options = [
                    (item["id"], item["title"], item["headline"])
                    for item in preset_definition(catalog, team["preset"])["consultants"]
                    if item["id"] not in active
                ]
                if not options:
                    raise TeamError("every curated Consultant for this preset is already active; use --custom FILE")
                args.consultant = choose(options, "OPEN CONSULTANT REQUISITION")
            title = args.consultant or args.custom.name
            confirm("Hire", title, args.yes)
            payload = hire_consultant(
                project_root=root, consultant_id=args.consultant, custom_path=args.custom
            )
            emit(payload, args.json)
            return 0
        if args.consultant is None:
            team = read_project_record(root, TEAM_NAME)
            options = [
                (item["id"], item["title"], item["headline"])
                for item in team["consultants"] if item["status"] == "active"
            ]
            if not options:
                raise TeamError("there are no active Consultants to fire")
            args.consultant = choose(options, "SELECT CONSULTANT FOR OFFBOARDING")
        team = read_project_record(root, TEAM_NAME)
        title = next(
            (item["title"] for item in team["consultants"] if item["id"] == args.consultant),
            args.consultant,
        )
        confirm("Fire", title, args.yes)
        payload = fire_consultant(project_root=root, consultant_id=args.consultant)
        emit(payload, args.json)
        return 0
    except (MutationLockError, TeamError, OSError, json.JSONDecodeError) as error:
        payload = {"ok": False, "error": str(error)}
        emit(payload, getattr(args, "json", False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
