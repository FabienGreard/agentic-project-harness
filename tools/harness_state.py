#!/usr/bin/env python3
"""Validate and transactionally update APH's canonical operational state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import date
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

from harness_team import load_catalog, validate_team
from harness_lock import MutationLockError, mutation_lock
from json_schema_contract import SchemaContractError, schema_errors

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "docs/state"
SCHEMA_DIR = ROOT / "docs/schemas"
DASHBOARD = ROOT / "docs/index.html"
RECORD_NAMES = ("project", "goals", "tickets", "ownership", "reviews", "team")
OPERATION_RECORD_NAMES = ("project", "goals", "tickets", "ownership", "reviews")
STATUS = {"Backlog", "Ready", "In Progress", "Blocked", "In Review", "Done", "Cancelled"}
GOAL_STATUS = {"Needs Definition", "Ready", "Active", "Review", "Done"}
ACTIVE_STATUS = {"Assigned", "Building", "Blocked", "Integrating", "Verifying", "Awaiting Review"}
OWNERSHIP_TICKET_STATUS = {
    "Assigned": "In Progress",
    "Building": "In Progress",
    "Blocked": "Blocked",
    "Integrating": "In Progress",
    "Verifying": "In Progress",
    "Awaiting Review": "In Review",
}
PRIORITY = {"P0", "P1", "P2", "P3", "P4"}
REVIEW_STATUS = {"Pending", "Approved", "Revision Requested", "Rejected"}
TEST_RIGOR = {"Lean", "Standard", "Thorough"}
HUMAN_REVIEW_STAGES = {"Readiness", "Acceptance", "Release"}
EXECUTABLE_STATUS = {"Ready", "In Progress", "Blocked", "In Review", "Done"}
READY_ARRAY_FIELDS = (
    "scope",
    "nonGoals",
    "affectedSystems",
    "acceptanceCriteria",
    "requiredVerification",
    "expectedEvidence",
    "risks",
)


def locked_state_mutation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            with mutation_lock(ROOT, "state-apply"):
                return function(*args, **kwargs)
        except MutationLockError as error:
            as_json = kwargs.get("as_json", args[1] if len(args) > 1 else False)
            emit(result(False, [str(error)]), as_json)
            return 1

    return wrapped


def read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path.relative_to(ROOT)}: {error}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path.relative_to(ROOT)}: expected an object")
        return None
    return data


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def iso_date(value: Any) -> bool:
    if not nonempty(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def repository_path(
    value: Any, location: str, errors: list[str]
) -> Path | None:
    if not nonempty(value) or "\\" in value:
        errors.append(f"{location}: expected a repository-relative path")
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{location}: path must stay inside the repository")
        return None
    candidate = ROOT.joinpath(*path.parts)
    parent = candidate.parent.resolve(strict=False)
    root = ROOT.resolve()
    if parent != root and root not in parent.parents:
        errors.append(f"{location}: path escapes the repository")
        return None
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        errors.append(f"{location}: path target escapes the repository")
        return None
    return candidate


def reject_extra_keys(
    value: dict[str, Any], allowed: set[str], location: str, errors: list[str]
) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        errors.append(f"{location}: unsupported keys: {', '.join(extra)}")


def dependency_cycle(items: list[Any]) -> list[str] | None:
    graph = {
        item.get("id"): [
            dependency
            for dependency in item.get("dependencies", [])
            if isinstance(dependency, str)
        ]
        for item in items
        if isinstance(item, dict) and nonempty(item.get("id"))
    }
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(identifier: str) -> list[str] | None:
        if identifier in visiting:
            start = visiting.index(identifier)
            return [*visiting[start:], identifier]
        if identifier in visited:
            return None
        visiting.append(identifier)
        for dependency in graph.get(identifier, []):
            if dependency not in graph:
                continue
            found = visit(dependency)
            if found:
                return found
        visiting.pop()
        visited.add(identifier)
        return None

    for identifier in graph:
        found = visit(identifier)
        if found:
            return found
    return None


def validate_schema_files(errors: list[str]) -> None:
    for name in (*RECORD_NAMES, "operation", "consultant"):
        schema = read_json(SCHEMA_DIR / f"{name}.schema.json", errors)
        if schema is None:
            continue
        required = schema.get("required")
        if name != "consultant" and (
            not isinstance(required, list) or "schemaVersion" not in required
        ):
            errors.append(f"docs/schemas/{name}.schema.json: missing schemaVersion requirement")
        if schema.get("type") != "object":
            errors.append(f"docs/schemas/{name}.schema.json: expected object schema")


def validate_record(name: str, data: dict[str, Any], errors: list[str]) -> None:
    prefix = f"docs/state/{name}.json"
    if not isinstance(data, dict):
        errors.append(f"{prefix}: expected an object")
        return
    try:
        structural_errors = schema_errors(data, SCHEMA_DIR / f"{name}.schema.json")
    except SchemaContractError as error:
        errors.append(f"docs/schemas/{name}.schema.json: {error}")
        return
    if structural_errors:
        errors.extend(f"{prefix} schema {error}" for error in structural_errors)
        return
    if type(data.get("schemaVersion")) is not int or data.get("schemaVersion") != 1 or data.get("recordType") != name:
        errors.append(f"{prefix}: expected schemaVersion 1 and recordType {name!r}")
    if name == "team":
        errors.extend(validate_team(data, load_catalog(ROOT)))
        return
    if name == "project":
        reject_extra_keys(data, {"schemaVersion", "recordType", "project", "baton"}, prefix, errors)
        project, baton = data.get("project"), data.get("baton")
        if not isinstance(project, dict) or not all(nonempty(project.get(key)) for key in ("name", "phase")) or not all(isinstance(project.get(key), str) for key in ("outcome", "currentGoal")) or project.get("agentProvider") != "codex" or not isinstance(project.get("templateMode"), bool) or not isinstance(project.get("lastVerified"), str):
            errors.append(f"{prefix}: invalid project payload")
        if not isinstance(baton, dict) or not all(nonempty(baton.get(key)) for key in ("owner", "action", "returnTrigger")):
            errors.append(f"{prefix}: invalid baton payload")
        if isinstance(project, dict):
            reject_extra_keys(project, {"name", "outcome", "currentGoal", "agentProvider", "phase", "templateMode", "lastVerified", "assuranceDefaults"}, f"{prefix}.project", errors)
            assurance_defaults = project.get("assuranceDefaults")
            if isinstance(assurance_defaults, dict):
                reject_extra_keys(
                    assurance_defaults,
                    {"testRigor", "humanReviewStages"},
                    f"{prefix}.project.assuranceDefaults",
                    errors,
                )
                if assurance_defaults.get("testRigor") not in TEST_RIGOR:
                    errors.append(f"{prefix}.project.assuranceDefaults: invalid testRigor")
                stages = assurance_defaults.get("humanReviewStages")
                if not isinstance(stages, list) or not set(stages).issubset(HUMAN_REVIEW_STAGES):
                    errors.append(
                        f"{prefix}.project.assuranceDefaults: invalid humanReviewStages"
                    )
        if isinstance(baton, dict):
            reject_extra_keys(baton, {"owner", "action", "returnTrigger"}, f"{prefix}.baton", errors)
        return
    record_keys = {"schemaVersion", "recordType", name}
    if name == "reviews":
        record_keys.add("consultantReviews")
    reject_extra_keys(data, record_keys, prefix, errors)
    items = data.get(name)
    if not isinstance(items, list):
        errors.append(f"{prefix}: {name} must be an array")
        return
    if name == "goals":
        for index, goal in enumerate(items):
            location = f"{prefix}.goals[{index}]"
            if not isinstance(goal, dict) or not all(
                nonempty(goal.get(key))
                for key in ("id", "title", "owner", "objective", "context")
            ):
                errors.append(
                    f"{location}: id, title, owner, objective, and context are required strings"
                )
                continue
            reject_extra_keys(
                goal,
                {
                    "id", "title", "status", "priority", "owner", "objective", "context",
                    "dependencies", "blockers", "blockerOwner", "resumeCondition",
                    "narrativePath", "decisionPaths", "evidencePaths",
                    "plannedStart", "plannedEnd", "resultSummary", "completedAt",
                },
                location,
                errors,
            )
            if re.fullmatch(r"[A-Z][A-Z0-9-]+", goal["id"]) is None:
                errors.append(f"{location}: invalid goal id")
            if goal.get("status") not in GOAL_STATUS:
                errors.append(f"{location}: invalid status")
            if goal.get("priority") not in PRIORITY:
                errors.append(f"{location}: invalid priority")
            for field in ("dependencies", "blockers", "decisionPaths", "evidencePaths"):
                value = goal.get(field)
                if not isinstance(value, list) or not all(nonempty(item) for item in value):
                    errors.append(f"{location}: {field} must be a string array")
            blockers = goal.get("blockers")
            if isinstance(blockers, list) and blockers:
                if not all(nonempty(goal.get(field)) for field in ("blockerOwner", "resumeCondition")):
                    errors.append(
                        f"{location}: blocked goals require blockerOwner and resumeCondition"
                    )
            for field in ("narrativePath", "plannedStart", "plannedEnd", "completedAt", "blockerOwner", "resumeCondition", "resultSummary"):
                if field in goal and not nonempty(goal[field]):
                    errors.append(f"{location}: {field} must be a non-empty string")
            for field in ("plannedStart", "plannedEnd", "completedAt"):
                if field in goal and not iso_date(goal[field]):
                    errors.append(f"{location}: {field} must be an ISO date")
            if ("plannedStart" in goal) != ("plannedEnd" in goal):
                errors.append(f"{location}: plannedStart and plannedEnd must be provided together")
            if (
                iso_date(goal.get("plannedStart"))
                and iso_date(goal.get("plannedEnd"))
                and goal["plannedEnd"] < goal["plannedStart"]
            ):
                errors.append(f"{location}: plannedEnd cannot be earlier than plannedStart")
            if "narrativePath" in goal:
                narrative = repository_path(
                    goal["narrativePath"], f"{location}.narrativePath", errors
                )
                if narrative is not None and (
                    narrative.is_symlink() or not narrative.is_file()
                ):
                    errors.append(f"{location}: narrativePath does not exist")
            for path_field in ("decisionPaths", "evidencePaths"):
                for linked_path in goal.get(path_field, []):
                    linked = repository_path(
                        linked_path, f"{location}.{path_field}", errors
                    )
                    if linked is not None and (
                        linked.is_symlink() or not linked.is_file()
                    ):
                        errors.append(
                            f"{location}: {path_field} entry does not exist: {linked_path}"
                        )
            if goal.get("status") == "Done":
                if not iso_date(goal.get("completedAt")):
                    errors.append(f"{location}: Done goals require completedAt")
                if not goal.get("evidencePaths"):
                    errors.append(f"{location}: Done goals require evidencePaths")
                if not nonempty(goal.get("resultSummary")):
                    errors.append(f"{location}: Done goals require resultSummary")
    elif name == "tickets":
        for index, ticket in enumerate(items):
            location = f"{prefix}.tickets[{index}]"
            if not isinstance(ticket, dict) or not all(nonempty(ticket.get(key)) for key in ("id", "title", "owner")):
                errors.append(f"{location}: id, title, and owner are required strings")
                continue
            reject_extra_keys(
                ticket,
                {
                    "id", "title", "status", "priority", "owner", "goal", "dependencies",
                    "objective", "scope", "nonGoals", "affectedSystems",
                    "acceptanceCriteria", "requiredVerification", "expectedEvidence",
                    "risks", "requiredConsultantIds", "assurance",
                    "blockers", "openDecisions", "narrativePath", "reportPath",
                },
                location,
                errors,
            )
            if re.fullmatch(r"[A-Z][A-Z0-9-]+", ticket["id"]) is None:
                errors.append(f"{location}: invalid ticket id")
            if ticket.get("status") not in STATUS:
                errors.append(f"{location}: invalid status")
            if ticket.get("priority") not in PRIORITY:
                errors.append(f"{location}: invalid priority")
            if not isinstance(ticket.get("dependencies"), list) or not all(nonempty(item) for item in ticket["dependencies"]):
                errors.append(f"{location}: dependencies must be strings")
            for field in (*READY_ARRAY_FIELDS, "blockers", "openDecisions"):
                value = ticket.get(field, [])
                if not isinstance(value, list) or not all(nonempty(item) for item in value):
                    errors.append(f"{location}: {field} must be a string array")
            required_consultants = ticket.get("requiredConsultantIds")
            if (
                not isinstance(required_consultants, list)
                or not all(nonempty(item) for item in required_consultants)
                or len(required_consultants) != len(set(required_consultants))
            ):
                errors.append(f"{location}: requiredConsultantIds must be a unique string array")
            assurance = ticket.get("assurance")
            if isinstance(assurance, dict):
                reject_extra_keys(
                    assurance,
                    {"testRigor", "humanReviewStages", "overrideReason"},
                    f"{location}.assurance",
                    errors,
                )
                if assurance.get("testRigor") not in TEST_RIGOR:
                    errors.append(f"{location}.assurance: invalid testRigor")
                stages = assurance.get("humanReviewStages")
                if not isinstance(stages, list) or not set(stages).issubset(HUMAN_REVIEW_STAGES):
                    errors.append(f"{location}.assurance: invalid humanReviewStages")
                if not isinstance(assurance.get("overrideReason"), str):
                    errors.append(f"{location}.assurance: overrideReason must be a string")
            if ticket.get("status") in EXECUTABLE_STATUS:
                if not nonempty(ticket.get("goal")):
                    errors.append(f"{location}: executable work requires goal")
                if not nonempty(ticket.get("objective")):
                    errors.append(f"{location}: executable work requires objective")
                for field in READY_ARRAY_FIELDS:
                    if not ticket.get(field):
                        errors.append(f"{location}: executable work requires {field}")
            for field in ("narrativePath", "reportPath"):
                if field in ticket and not nonempty(ticket[field]):
                    errors.append(f"{location}: {field} must be a non-empty string")
                elif field in ticket:
                    candidate = repository_path(
                        ticket[field], f"{location}.{field}", errors
                    )
                    if field == "narrativePath" and candidate is not None and (
                        candidate.is_symlink() or not candidate.is_file()
                    ):
                        errors.append(f"{location}: narrativePath does not exist")
    elif name == "ownership":
        for index, item in enumerate(items):
            location = f"{prefix}.ownership[{index}]"
            if not isinstance(item, dict) or not all(nonempty(item.get(key)) for key in ("ticket", "owner", "returnDestination")):
                errors.append(f"{location}: ticket, owner, and returnDestination are required strings")
                continue
            reject_extra_keys(item, {"ticket", "owner", "scopes", "status", "returnDestination"}, location, errors)
            if item.get("status") not in ACTIVE_STATUS:
                errors.append(f"{location}: invalid status")
            if not isinstance(item.get("scopes"), list) or not item["scopes"] or not all(nonempty(scope) for scope in item["scopes"]):
                errors.append(f"{location}: scopes must be a non-empty string array")
    else:
        for index, item in enumerate(items):
            location = f"{prefix}.reviews[{index}]"
            if not isinstance(item, dict) or not all(nonempty(item.get(key)) for key in ("id", "ticket", "stage", "path")):
                errors.append(f"{location}: id, ticket, stage, and path are required strings")
                continue
            reject_extra_keys(item, {"id", "ticket", "stage", "status", "path", "reviewer", "recordedAt"}, location, errors)
            if item.get("stage") not in HUMAN_REVIEW_STAGES:
                errors.append(f"{location}: invalid stage")
            if item.get("status") not in REVIEW_STATUS:
                errors.append(f"{location}: invalid status")
            review_path = repository_path(
                item.get("path"), f"{location}.path", errors
            )
            if (
                item.get("status") == "Approved"
                and review_path is not None
                and (review_path.is_symlink() or not review_path.is_file())
            ):
                errors.append(
                    f"{location}: Approved human review path does not exist or is not a regular file"
                )
            if item.get("status") == "Approved":
                if not nonempty(item.get("reviewer")) or not iso_date(
                    item.get("recordedAt")
                ):
                    errors.append(
                        f"{location}: Approved human review requires reviewer and ISO recordedAt"
                    )
                packet = PurePosixPath(str(item.get("path", "")))
                if (
                    packet.parts[:2] != ("docs", "review-packets")
                    or packet.name.lower() in {"readme.md", "template.md", "_template.md"}
                    or "templates" in {part.lower() for part in packet.parts}
                    or packet.suffix.lower() != ".md"
                ):
                    errors.append(
                        f"{location}: Approved human review requires a dedicated Markdown packet under docs/review-packets, not a README or template"
                    )
        consultant_reviews = data.get("consultantReviews")
        if not isinstance(consultant_reviews, list):
            errors.append(f"{prefix}: consultantReviews must be an array")
            return
        for index, item in enumerate(consultant_reviews):
            location = f"{prefix}.consultantReviews[{index}]"
            required = ("id", "ticket", "consultantId", "stage", "status")
            if not isinstance(item, dict) or not all(nonempty(item.get(key)) for key in required):
                errors.append(
                    f"{location}: id, ticket, consultantId, stage, and status are required strings"
                )
                continue
            reject_extra_keys(
                item,
                {
                    "id", "ticket", "consultantId", "stage", "status",
                    "evidencePaths", "reviewer", "recordedAt",
                },
                location,
                errors,
            )
            if item.get("stage") not in {"Readiness", "Acceptance"}:
                errors.append(f"{location}: invalid stage")
            if item.get("status") not in REVIEW_STATUS:
                errors.append(f"{location}: invalid status")
            evidence_paths = item.get("evidencePaths")
            if not isinstance(evidence_paths, list) or not all(
                nonempty(path) for path in evidence_paths
            ):
                errors.append(f"{location}: evidencePaths must be a string array")
                continue
            if item.get("status") == "Approved" and not evidence_paths:
                errors.append(f"{location}: Approved Consultant reviews require evidencePaths")
            for linked_path in evidence_paths:
                linked = repository_path(
                    linked_path, f"{location}.evidencePaths", errors
                )
                if linked is not None and (
                    linked.is_symlink() or not linked.is_file()
                ):
                    errors.append(f"{location}: evidencePath does not exist: {linked_path}")


def validate_consistency(records: dict[str, dict[str, Any]], errors: list[str]) -> None:
    project = records["project"].get("project", {})
    assurance_defaults = (
        project.get("assuranceDefaults", {}) if isinstance(project, dict) else {}
    )
    goals = records["goals"].get("goals", [])
    tickets = records["tickets"].get("tickets", [])
    ownership = records["ownership"].get("ownership", [])
    reviews = records["reviews"].get("reviews", [])
    consultant_reviews = records["reviews"].get("consultantReviews", [])
    consultants = records["team"].get("consultants", [])
    consultant_map = {
        item.get("id"): item for item in consultants if isinstance(item, dict)
    }
    active_consultants = {
        identifier
        for identifier, item in consultant_map.items()
        if item.get("status") == "active"
    }
    goal_ids = [goal.get("id") for goal in goals if isinstance(goal, dict)]
    duplicate_goals = [
        item for item, count in Counter(goal_ids).items() if count > 1
    ]
    if duplicate_goals:
        errors.append(
            "docs/state/goals.json: duplicate goal ids: "
            + ", ".join(sorted(duplicate_goals))
        )
    known_goals = set(goal_ids)
    goal_map = {
        goal.get("id"): goal for goal in goals if isinstance(goal, dict)
    }
    current_goal = project.get("currentGoal") if isinstance(project, dict) else ""
    if current_goal and current_goal not in known_goals:
        errors.append(f"docs/state/project.json: unknown currentGoal {current_goal!r}")
    elif current_goal and goal_map.get(current_goal, {}).get("status") == "Done":
        errors.append("docs/state/project.json: currentGoal cannot be Done")
    active_goal_ids = [
        goal.get("id")
        for goal in goals
        if isinstance(goal, dict) and goal.get("status") in {"Active", "Review"}
    ]
    if len(active_goal_ids) > 1:
        errors.append(
            "docs/state/goals.json: only one goal may be Active or Review"
        )
    if active_goal_ids and active_goal_ids[0] != current_goal:
        errors.append(
            "docs/state/project.json: currentGoal must identify the Active or Review goal"
        )
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        dependencies = goal.get("dependencies")
        if not isinstance(dependencies, list):
            continue
        unknown = set(dependencies) - known_goals
        if unknown:
            errors.append(
                f"docs/state/goals.json: {goal.get('id')} has unknown dependencies: "
                + ", ".join(sorted(unknown))
            )
        if goal.get("id") in dependencies:
            errors.append(f"docs/state/goals.json: {goal.get('id')} depends on itself")
        if goal.get("status") in {"Ready", "Active", "Review", "Done"}:
            incomplete = [
                dependency
                for dependency in dependencies
                if goal_map.get(dependency, {}).get("status") != "Done"
            ]
            if incomplete:
                errors.append(
                    f"docs/state/goals.json: {goal.get('status')} goal {goal.get('id')} has incomplete dependencies: "
                    + ", ".join(sorted(incomplete))
                )
    cycle = dependency_cycle(goals)
    if cycle:
        errors.append(
            "docs/state/goals.json: dependency cycle: " + " -> ".join(cycle)
        )
    ids = [ticket.get("id") for ticket in tickets if isinstance(ticket, dict)]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append("docs/state/tickets.json: duplicate ticket ids: " + ", ".join(sorted(duplicates)))
    known = set(ids)
    ticket_map = {
        ticket.get("id"): ticket for ticket in tickets if isinstance(ticket, dict)
    }
    ownership_ticket_ids = {
        item.get("ticket") for item in ownership if isinstance(item, dict)
    }
    human_reviews_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for review in reviews:
        if isinstance(review, dict):
            key = (review.get("ticket"), review.get("stage"))
            human_reviews_by_key.setdefault(key, []).append(review)
    consultant_reviews_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for review in consultant_reviews:
        if not isinstance(review, dict):
            continue
        key = (review.get("ticket"), review.get("consultantId"), review.get("stage"))
        consultant_reviews_by_key.setdefault(key, []).append(review)
    for (ticket_id, stage), grouped in human_reviews_by_key.items():
        if len(grouped) > 1:
            errors.append(
                "docs/state/reviews.json: multiple human review decisions for "
                f"{ticket_id} {stage}; replace the canonical decision transactionally"
            )
    for (ticket_id, consultant_id, stage), grouped in consultant_reviews_by_key.items():
        if len(grouped) > 1:
            errors.append(
                "docs/state/reviews.json: multiple Consultant review decisions for "
                f"{ticket_id} {consultant_id} {stage}; replace the canonical decision transactionally"
            )
    for goal in goals:
        if not isinstance(goal, dict) or goal.get("status") != "Done":
            continue
        linked_tickets = [
            ticket
            for ticket in tickets
            if isinstance(ticket, dict) and ticket.get("goal") == goal.get("id")
        ]
        active_linked = [
            ticket.get("id")
            for ticket in linked_tickets
            if ticket.get("status") not in {"Done", "Cancelled"}
        ]
        owned_linked = [
            ticket.get("id")
            for ticket in linked_tickets
            if ticket.get("id") in ownership_ticket_ids
        ]
        blocked_linked = [
            ticket.get("id")
            for ticket in linked_tickets
            if ticket.get("blockers") or ticket.get("openDecisions")
        ]
        if active_linked:
            errors.append(
                f"docs/state/goals.json: Done goal {goal.get('id')} has non-terminal tickets: "
                + ", ".join(sorted(active_linked))
            )
        if owned_linked:
            errors.append(
                f"docs/state/goals.json: Done goal {goal.get('id')} retains active ownership: "
                + ", ".join(sorted(owned_linked))
            )
        if goal.get("blockers") or blocked_linked:
            errors.append(
                f"docs/state/goals.json: Done goal {goal.get('id')} retains blockers or open decisions"
            )
    for ticket in tickets:
        if not isinstance(ticket, dict):
            continue
        assurance = ticket.get("assurance", {})
        if isinstance(assurance, dict) and isinstance(assurance_defaults, dict):
            differs_from_default = (
                assurance.get("testRigor") != assurance_defaults.get("testRigor")
                or assurance.get("humanReviewStages")
                != assurance_defaults.get("humanReviewStages")
            )
            if differs_from_default and not nonempty(assurance.get("overrideReason")):
                errors.append(
                    f"docs/state/tickets.json: {ticket.get('id')} assurance differs from project defaults without a human-authorized overrideReason"
                )
            required_human_stages = assurance.get("humanReviewStages", [])
            if not isinstance(required_human_stages, list):
                required_human_stages = []
            stage_gates = []
            if ticket.get("status") in EXECUTABLE_STATUS:
                stage_gates.append("Readiness")
            if ticket.get("status") == "Done":
                stage_gates.append("Acceptance")
            missing_human_stages = [
                stage
                for stage in stage_gates
                if stage in required_human_stages
                and not any(
                    review.get("status") == "Approved"
                    for review in human_reviews_by_key.get(
                        (ticket.get("id"), stage), []
                    )
                )
            ]
            if missing_human_stages:
                errors.append(
                    f"docs/state/tickets.json: {ticket.get('status')} ticket {ticket.get('id')} lacks approved human review for: "
                    + ", ".join(missing_human_stages)
                )
        if ticket.get("goal") and ticket.get("goal") not in known_goals:
            errors.append(
                f"docs/state/tickets.json: {ticket.get('id')} has unknown goal {ticket.get('goal')!r}"
            )
        required_consultants = ticket.get("requiredConsultantIds", [])
        if isinstance(required_consultants, list):
            unknown_consultants = set(required_consultants) - set(consultant_map)
            inactive_consultants = set(required_consultants) - active_consultants
            if unknown_consultants:
                errors.append(
                    f"docs/state/tickets.json: {ticket.get('id')} requires unknown Consultants: "
                    + ", ".join(sorted(unknown_consultants))
                )
            elif (
                inactive_consultants
                and ticket.get("status") in EXECUTABLE_STATUS
                and ticket.get("status") != "Done"
            ):
                errors.append(
                    f"docs/state/tickets.json: {ticket.get('id')} requires inactive Consultants: "
                    + ", ".join(sorted(inactive_consultants))
                )
            if ticket.get("status") in EXECUTABLE_STATUS:
                missing_readiness = [
                    identifier
                    for identifier in required_consultants
                    if not any(
                        review.get("status") == "Approved"
                        for review in consultant_reviews_by_key.get(
                            (ticket.get("id"), identifier, "Readiness"), []
                        )
                    )
                ]
                if missing_readiness:
                    errors.append(
                        f"docs/state/tickets.json: executable ticket {ticket.get('id')} lacks approved Consultant readiness for: "
                        + ", ".join(sorted(missing_readiness))
                    )
            if ticket.get("status") == "Done":
                missing_acceptance = [
                    identifier
                    for identifier in required_consultants
                    if not any(
                        review.get("status") == "Approved"
                        for review in consultant_reviews_by_key.get(
                            (ticket.get("id"), identifier, "Acceptance"), []
                        )
                    )
                ]
                if missing_acceptance:
                    errors.append(
                        f"docs/state/tickets.json: Done ticket {ticket.get('id')} lacks approved Consultant acceptance for: "
                        + ", ".join(sorted(missing_acceptance))
                    )
        dependencies = ticket.get("dependencies")
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            continue
        unknown = set(dependencies) - known
        if unknown:
            errors.append(f"docs/state/tickets.json: {ticket.get('id')} has unknown dependencies: {', '.join(sorted(unknown))}")
        if ticket.get("id") in dependencies:
            errors.append(f"docs/state/tickets.json: {ticket.get('id')} depends on itself")
        if ticket.get("status") == "Ready":
            incomplete = [
                dependency
                for dependency in dependencies
                if ticket_map.get(dependency, {}).get("status") != "Done"
            ]
            if incomplete:
                errors.append(
                    f"docs/state/tickets.json: Ready ticket {ticket.get('id')} has incomplete dependencies: "
                    + ", ".join(sorted(incomplete))
                )
        if ticket.get("status") == "Done":
            report_path = ticket.get("reportPath")
            report = repository_path(
                report_path,
                f"docs/state/tickets.json.{ticket.get('id')}.reportPath",
                errors,
            )
            if report is None or report.is_symlink() or not report.is_file():
                errors.append(
                    f"docs/state/tickets.json: Done ticket {ticket.get('id')} requires an existing reportPath"
                )
    scopes: list[tuple[str, str]] = []
    for item in ownership:
        if not isinstance(item, dict):
            continue
        if item.get("ticket") not in known:
            errors.append(f"docs/state/ownership.json: unknown ticket {item.get('ticket')!r}")
        elif ticket_map[item.get("ticket")].get("status") != OWNERSHIP_TICKET_STATUS.get(item.get("status")):
            errors.append(
                f"docs/state/ownership.json: {item.get('ticket')} status does not match its ticket"
            )
        item_scopes = item.get("scopes")
        if isinstance(item_scopes, list):
            for scope in item_scopes:
                if not isinstance(scope, str):
                    continue
                normalized = scope.rstrip("/")
                for previous, previous_ticket in scopes:
                    if (
                        normalized == previous
                        or normalized.startswith(previous + "/")
                        or previous.startswith(normalized + "/")
                    ):
                        errors.append(
                            "docs/state/ownership.json: overlapping scopes: "
                            f"{previous_ticket}:{previous} <> {item.get('ticket')}:{normalized}"
                        )
                scopes.append((normalized, str(item.get("ticket"))))
    for item in reviews:
        if isinstance(item, dict) and item.get("ticket") not in known:
            errors.append(f"docs/state/reviews.json: unknown ticket {item.get('ticket')!r}")
    review_ids = [
        item.get("id")
        for item in [*reviews, *consultant_reviews]
        if isinstance(item, dict)
    ]
    duplicate_review_ids = [
        item for item, count in Counter(review_ids).items() if count > 1
    ]
    if duplicate_review_ids:
        errors.append(
            "docs/state/reviews.json: duplicate review ids: "
            + ", ".join(sorted(duplicate_review_ids))
        )
    for item in consultant_reviews:
        if not isinstance(item, dict):
            continue
        if item.get("ticket") not in known:
            errors.append(
                f"docs/state/reviews.json: Consultant review has unknown ticket {item.get('ticket')!r}"
            )
        if item.get("consultantId") not in consultant_map:
            errors.append(
                f"docs/state/reviews.json: unknown Consultant {item.get('consultantId')!r}"
            )


def load_records(errors: list[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name in RECORD_NAMES:
        value = read_json(STATE_DIR / f"{name}.json", errors)
        if value is not None:
            records[name] = value
    return records


def validate_records(records: dict[str, dict[str, Any]], errors: list[str]) -> None:
    if set(records) != set(RECORD_NAMES):
        return
    before = len(errors)
    for name in RECORD_NAMES:
        validate_record(name, records[name], errors)
    if len(errors) == before:
        validate_consistency(records, errors)


def render_dashboard(records: dict[str, dict[str, Any]]) -> str:
    snapshot = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).replace("</", "<\\/")
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Project status</title>
<style>
:root{color-scheme:light;--ink:#0f172a;--muted:#64748b;--subtle:#94a3b8;--line:#e2e8f0;--line-strong:#cbd5e1;--paper:#fff;--canvas:#f8fafc;--accent:#2563eb;--accent-dark:#1d4ed8;--accent-soft:#eff6ff;--success:#047857;--success-soft:#ecfdf5;--warning:#a16207;--warning-soft:#fffbeb;--danger:#b42318;--danger-soft:#fef3f2;--shadow:0 16px 40px rgba(15,23,42,.08)}
*{box-sizing:border-box}
html{background:var(--canvas)}
body{background:var(--canvas);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:-.006em;margin:0}
button,input{font:inherit}
a{color:var(--accent-dark);text-decoration-thickness:1px;text-underline-offset:3px}
a:hover{color:#1e40af;text-decoration-thickness:2px}
:where(a,button,input,summary):focus-visible{outline:3px solid #60a5fa;outline-offset:3px}
.skip-link{background:var(--ink);border-radius:8px;color:#fff;left:1rem;padding:.65rem .9rem;position:absolute;top:-5rem;z-index:10}
.skip-link:focus{top:1rem}
.site-header{background:var(--paper);border-bottom:1px solid var(--line);padding:2.5rem max(1.25rem,calc((100vw - 980px)/2)) 2rem}
.site-header h1{font-size:clamp(1.8rem,4vw,2.55rem);letter-spacing:-.04em;line-height:1.08;margin:0;max-width:760px}
.site-header>p{color:var(--muted);font-size:1.03rem;margin:.65rem 0 0;max-width:760px}
.header-meta{align-items:center;color:var(--muted);display:flex;font-size:.82rem;gap:.55rem;margin-top:1rem}
.header-meta span+span:before{color:var(--line-strong);content:"•";margin-right:.55rem}
main{margin:0 auto;max-width:980px;padding:2rem 1.25rem 5rem}
#dashboard{display:grid;gap:2.5rem}
.preview-bar{align-items:center;background:var(--accent-soft);border:1px solid #bfdbfe;border-radius:12px;color:#1e3a8a;display:flex;gap:1rem;justify-content:space-between;padding:.8rem 1rem}
.preview-bar p{margin:0}.preview-bar a{font-weight:700;white-space:nowrap}
.section-heading{align-items:end;display:flex;gap:1rem;justify-content:space-between;margin-bottom:1.25rem}
.section-heading h2{font-size:1.3rem;letter-spacing:-.025em;line-height:1.2;margin:0}
.section-heading p{color:var(--muted);margin:.25rem 0 0}
.count{color:var(--muted);font-size:.82rem;white-space:nowrap}
.roadmap-scroll{border:1px solid var(--line);border-radius:16px;overflow-x:auto}
.roadmap{background:var(--paper);min-width:800px}
.roadmap-header,.roadmap-row{display:grid;grid-template-columns:minmax(260px,1.5fr) repeat(3,minmax(145px,1fr))}
.roadmap-header{background:#f1f5f9;border-bottom:1px solid var(--line);color:var(--muted);font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.roadmap-header span{padding:.7rem 1rem}.roadmap-header span+span{border-left:1px solid var(--line);text-align:center}
.roadmap-row{min-height:76px}.roadmap-row+.roadmap-row{border-top:1px solid var(--line)}
.roadmap-label{align-self:stretch;display:flex;flex-direction:column;justify-content:center;min-width:0;padding:.75rem 1rem}
.roadmap-label strong{font-size:.9rem;line-height:1.3}.roadmap-label span{color:var(--muted);font-size:.75rem;margin-top:.15rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.roadmap-cell{align-items:center;border-left:1px solid var(--line);display:flex;padding:.55rem}
.goal-bar{border:1px solid transparent;border-radius:9px;cursor:pointer;display:grid;font-size:.8rem;font-weight:750;gap:.15rem;min-height:44px;padding:.55rem .65rem;text-align:left;transition:box-shadow .15s,transform .15s,background .15s;width:100%}
.goal-bar small{font-size:.7rem;font-weight:600;opacity:.78}.goal-bar:hover{box-shadow:0 5px 14px rgba(15,23,42,.12);transform:translateY(-1px)}
.goal-bar[aria-pressed="true"]{box-shadow:0 0 0 3px var(--paper),0 0 0 6px #93c5fd}
.goal-bar-done{background:var(--success-soft);border-color:#a7f3d0;color:#065f46}.goal-bar-current{background:var(--accent);border-color:var(--accent);color:#fff}.goal-bar-upcoming{background:#f1f5f9;border-color:var(--line-strong);color:#334155}.goal-bar-upcoming:hover{background:#e2e8f0}
.goal-detail{margin-top:1.25rem}
.current-goal{background:var(--paper);border:1px solid #bfdbfe;border-radius:18px;box-shadow:var(--shadow);overflow:hidden}
.current-goal:not(.is-current){border-color:var(--line);box-shadow:0 10px 30px rgba(15,23,42,.06)}
.current-goal:not(.is-current) .current-label{color:var(--muted)}.current-goal:not(.is-current) .goal-brief-bar{background:var(--canvas);border-color:var(--line)}
.current-head{padding:1.5rem 1.5rem 1.2rem}
.current-label{color:var(--accent-dark);font-size:.72rem;font-weight:800;letter-spacing:.1em;margin:0 0 .55rem;text-transform:uppercase}
.current-title-row{align-items:start;display:flex;gap:1rem;justify-content:space-between}
.current-title-row h2{font-size:clamp(1.45rem,3vw,2rem);letter-spacing:-.035em;line-height:1.15;margin:0}
.current-head>.goal-objective{font-size:1.04rem;margin:.65rem 0 .25rem;max-width:760px}
.current-head>.goal-context{color:var(--muted);margin:.2rem 0 0;max-width:760px}
.status-pill{align-items:center;background:#f1f5f9;border-radius:999px;color:#475569;display:inline-flex;font-size:.76rem;font-weight:750;line-height:1;padding:.38rem .6rem;white-space:nowrap}
.status-active{background:var(--accent-soft);color:#1e40af}.status-success{background:var(--success-soft);color:var(--success)}.status-review{background:var(--warning-soft);color:var(--warning)}.status-danger{background:var(--danger-soft);color:var(--danger)}
.progress-wrap{align-items:center;display:grid;gap:.65rem;grid-template-columns:1fr auto;margin-top:1.25rem}
.progress-track{background:#e8eef7;border-radius:999px;height:8px;overflow:hidden}
.progress-bar{background:var(--accent);border-radius:inherit;height:100%;min-width:0}
.progress-label{color:var(--muted);font-size:.82rem;white-space:nowrap}
.goal-columns{border-top:1px solid var(--line);display:grid;grid-template-columns:1fr 1fr}
.goal-column{padding:1.35rem 1.5rem}
.goal-column+.goal-column{border-left:1px solid var(--line)}
.goal-column h3{font-size:.92rem;margin:0 0 .8rem}
.person-list,.remaining-list{display:grid;gap:.3rem}
.person-row,.remaining-row{align-items:center;border-radius:10px;display:grid;gap:.75rem;min-height:48px;padding:.55rem .6rem}
.person-row{grid-template-columns:34px minmax(0,1fr) auto}
.remaining-row{grid-template-columns:18px minmax(0,1fr) auto}
.person-row:hover,.remaining-row:hover{background:var(--canvas)}
.avatar{align-items:center;background:#e0e7ff;border-radius:999px;color:#3730a3;display:flex;font-size:.72rem;font-weight:800;height:34px;justify-content:center;width:34px}
.person-copy strong,.remaining-copy strong{display:block;font-size:.9rem;line-height:1.3}.person-copy span,.remaining-copy span{color:var(--muted);display:block;font-size:.78rem;margin-top:.1rem}
.todo-dot{border:2px solid var(--line-strong);border-radius:999px;height:16px;width:16px}
.empty-note{color:var(--muted);margin:.35rem 0}
.blocker{background:var(--danger-soft);border-top:1px solid #fecdca;color:#7a271a;padding:1rem 1.5rem}
.goal-brief-bar{align-items:center;background:var(--accent-soft);border-top:1px solid #dbeafe;display:flex;gap:1rem;justify-content:space-between;padding:.8rem 1.5rem}
.goal-brief-bar div{min-width:0}.goal-brief-bar strong{display:block;font-size:.82rem}.goal-brief-bar span{color:var(--muted);display:block;font-size:.8rem;margin-top:.1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.goal-brief-bar a{font-size:.84rem;font-weight:700;white-space:nowrap}
.goal-work-section{border-top:1px solid var(--line);padding:1.1rem 1.5rem 1.3rem}.goal-work-section h3{font-size:.9rem;margin:0 0 .6rem}
.ticket-list{display:grid}
.ticket-row{align-items:center;border-top:1px solid var(--line);display:grid;gap:.85rem;grid-template-columns:minmax(0,1fr) minmax(100px,140px) auto;padding:.65rem .25rem}
.ticket-row:first-child{border-top:0}.ticket-copy small{color:var(--muted);display:block;font-size:.7rem;font-weight:700}.ticket-copy strong{display:block;font-size:.88rem;line-height:1.3}.ticket-owner{color:var(--muted);font-size:.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.completed-work{border-top:1px solid var(--line);padding:0 1.5rem}
.completed-work summary{color:var(--accent-dark);cursor:pointer;font-size:.85rem;font-weight:700;list-style:none;padding:.9rem 0}.completed-work summary::-webkit-details-marker{display:none}.completed-work summary:after{content:"+";float:right;font-size:1.05rem}.completed-work[open] summary:after{content:"−"}
.completed-work summary:hover{text-decoration:underline;text-underline-offset:3px}.completed-work .ticket-list{padding-bottom:1rem}
.empty-goal{background:var(--paper);border:1px dashed var(--line-strong);border-radius:16px;padding:1.5rem}
.empty-goal h2{margin:0}.empty-goal p{color:var(--muted);margin:.5rem 0 0}
.empty-goal .preview-link{display:inline-block;font-weight:700;margin-top:1rem}
@media(max-width:700px){.site-header{padding:1.8rem 1rem 1.5rem}main{padding:1.5rem .85rem 4rem}#dashboard{gap:2rem}.goal-columns{grid-template-columns:1fr}.goal-column+.goal-column{border-left:0;border-top:1px solid var(--line)}.preview-bar,.goal-brief-bar{align-items:flex-start;flex-direction:column}.ticket-row{grid-template-columns:minmax(0,1fr) auto}.ticket-owner{display:none}}
@media(max-width:460px){.current-head,.goal-column,.goal-work-section{padding-left:1rem;padding-right:1rem}.current-title-row{display:block}.current-title-row .status-pill{margin-top:.75rem}.progress-wrap{grid-template-columns:1fr}.progress-label{white-space:normal}.ticket-row{gap:.5rem}.status-pill{font-size:.7rem}.header-meta{align-items:flex-start;flex-direction:column;gap:.15rem}.header-meta span+span:before{display:none}}
</style>
<style>
:root{--ui-deep:#19324F;--ui-dark:#325886;--ui-blue:#447AB9;--ui-light:#82A7D6;--ui-yellow:#FEF265;--ui-cream:#FCE8A4;--ui-paper:#FEEED4;--ink:#263f5e;--muted:#405B78;--subtle:#506983;--line:rgba(50,88,134,.22);--line-strong:rgba(50,88,134,.42);--paper:var(--ui-paper);--canvas:var(--ui-cream);--accent:var(--ui-blue);--accent-dark:var(--ui-dark);--accent-soft:rgba(130,167,214,.28);--success:var(--ui-deep);--success-soft:rgba(130,167,214,.38);--warning:var(--ui-deep);--warning-soft:var(--ui-yellow);--danger:var(--ui-deep);--danger-soft:var(--ui-cream);--shadow:0 14px 38px rgba(25,50,79,.2)}
html,body{background:var(--paper);max-width:100%;overflow-x:hidden}body{background:repeating-linear-gradient(0deg,rgba(50,88,134,.012) 0,rgba(50,88,134,.012) 1px,transparent 1px,transparent 4px),linear-gradient(180deg,var(--ui-paper) 0%,var(--ui-cream) 180%);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:15px;letter-spacing:0}body:after{background:radial-gradient(ellipse at center,transparent 68%,rgba(50,88,134,.035) 100%);content:"";inset:0;pointer-events:none;position:fixed;z-index:30}
.site-header{background-image:repeating-linear-gradient(0deg,rgba(254,238,212,.04) 0,rgba(254,238,212,.04) 1px,transparent 1px,transparent 4px),linear-gradient(105deg,var(--ui-deep) 0%,var(--ui-dark) 78%,#274b74 100%);border-bottom:4px solid var(--ui-yellow);color:var(--ui-paper);overflow:hidden;padding:2.35rem clamp(1rem,2.5vw,2.75rem) 0;position:relative}.site-header:before{color:var(--ui-yellow);content:"PROJECT CONTROL // TEAM NETWORK";display:block;font:650 .74rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;margin-bottom:.55rem}.site-header h1{color:var(--ui-paper);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:clamp(2rem,4vw,2.8rem);font-weight:750;letter-spacing:-.04em;max-width:none;text-shadow:0 0 18px rgba(254,242,101,.2);text-transform:uppercase}.site-header>p{color:var(--ui-paper);font-size:1rem;max-width:920px}.header-meta{color:var(--ui-paper);font:550 .8rem/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:.9rem}.header-meta span+span:before{color:var(--ui-yellow)}
.system-nav{align-items:stretch;background:rgba(25,50,79,.82);border-top:1px solid rgba(254,238,212,.42);display:flex;font:650 .76rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;gap:0;margin-top:1.35rem;min-height:44px;text-transform:uppercase}.system-nav a{align-items:center;border-right:1px solid rgba(254,238,212,.32);color:var(--ui-paper);display:flex;letter-spacing:.06em;padding:.85rem 1rem;text-decoration:none}.system-nav a:before{color:var(--ui-yellow);content:"[";margin-right:.42rem}.system-nav a:after{color:var(--ui-yellow);content:"]";margin-left:.42rem}.system-nav a:hover{background:var(--ui-yellow);color:var(--ui-deep)}.system-nav a:hover:before,.system-nav a:hover:after{color:var(--ui-deep)}.system-nav-status{align-items:center;color:var(--ui-paper);display:flex;letter-spacing:.08em;margin-left:auto;padding:.8rem 0 .8rem 1rem}.system-nav-status:before{background:var(--ui-yellow);box-shadow:0 0 8px rgba(254,242,101,.8);content:"";height:8px;margin-right:.55rem;width:8px}
main{margin:0;max-width:none;min-width:0;padding:1.35rem clamp(.75rem,2vw,2.5rem) 5rem;width:100%}#dashboard{gap:2.25rem;max-width:100%;min-width:0}#dashboard>*,#dashboard section{max-width:100%;min-width:0}
.preview-bar{background:var(--ui-yellow);border-left:3px solid var(--ui-dark);border-radius:3px;color:var(--ui-dark);padding:.65rem .8rem}.preview-bar a{color:var(--ui-dark)}
.section-heading{align-items:center;border-bottom:2px solid var(--ui-dark);margin-bottom:.8rem;padding-bottom:.55rem;position:relative}.section-heading:after{background:var(--ui-yellow);bottom:-2px;content:"";height:2px;position:absolute;right:0;width:clamp(46px,8vw,110px)}.section-heading h2{color:var(--ui-dark);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:1.05rem;font-weight:750;letter-spacing:.055em;text-transform:uppercase}.section-heading h2:before{content:"[ ";color:var(--ui-blue)}.section-heading h2:after{content:" ]";color:var(--ui-blue)}.section-heading p{font-size:.82rem;margin-top:.15rem}
.gantt-toolbar{align-items:center;display:flex;gap:.5rem}.gantt-toolbar .count,.ticket-tools .count{font:550 .76rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace}.notion-button{background:rgba(130,167,214,.24);border:1px solid var(--line-strong);border-radius:5px;color:var(--ui-deep);cursor:pointer;font-size:.8rem;font-weight:650;min-height:28px;padding:.38rem .55rem}.notion-button:hover{background:var(--accent-soft);border-color:var(--ui-dark)}
:where(a,button,input,summary):focus-visible{box-shadow:0 0 0 5px var(--ui-yellow);outline:3px solid var(--ui-deep);outline-offset:2px}
.gantt-viewport{background:var(--ui-paper);border:2px solid var(--ui-dark);border-left-width:6px;border-radius:0;box-shadow:inset 0 0 28px rgba(50,88,134,.08);display:block;max-height:410px;max-width:100%;min-width:0;overflow:auto;overscroll-behavior:contain;scrollbar-color:var(--ui-blue) var(--ui-cream);width:100%}
.gantt-grid{display:grid;grid-template-columns:190px var(--timeline-width);max-width:none;width:max-content}
.gantt-corner,.gantt-dates{background:var(--ui-dark);border-bottom:2px solid var(--ui-yellow);height:42px;position:sticky;top:0;z-index:4}
.gantt-corner{align-items:center;border-right:1px solid rgba(254,238,212,.3);color:var(--ui-paper);display:flex;font:650 .72rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;left:0;letter-spacing:.055em;padding:0 .8rem;text-transform:uppercase;z-index:6}
.gantt-dates{position:sticky;top:0}.date-tick{color:var(--ui-paper);font:600 .72rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;left:var(--left);padding-left:.45rem;position:absolute;top:14px;white-space:nowrap}.date-tick:before{background:rgba(254,238,212,.42);bottom:-18px;content:"";left:0;position:absolute;top:-14px;width:1px}
.today-head{background:var(--ui-yellow);color:var(--ui-deep);font:750 .7rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;left:var(--left);padding:.16rem .28rem;position:absolute;top:2px;transform:translateX(-50%);white-space:nowrap}
.gantt-label,.gantt-track{border-bottom:1px solid var(--line);height:66px}.gantt-label{align-items:center;background:var(--paper);border-right:1px solid var(--line);display:flex;left:0;padding:.4rem .45rem;position:sticky;z-index:3}.gantt-label:hover,.gantt-track:hover{background-color:rgba(130,167,214,.13)}
.gantt-goal-button{align-items:center;background:transparent;border:0;border-left:3px solid transparent;border-radius:0;color:var(--ink);cursor:pointer;display:grid;gap:.15rem;grid-template-columns:minmax(0,1fr) auto;padding:.4rem;text-align:left;width:100%}.gantt-goal-button:hover,.gantt-goal-button[aria-pressed="true"]{background:rgba(130,167,214,.24);border-left-color:var(--ui-dark)}.gantt-goal-button strong{font-size:.84rem;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gantt-goal-button small{color:var(--muted);font-size:.75rem;grid-column:1/-1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gantt-track{background-image:repeating-linear-gradient(to right,transparent 0,transparent calc(var(--week-width) - 1px),var(--line) calc(var(--week-width) - 1px),var(--line) var(--week-width));position:relative}
.today-line{background:var(--ui-blue);bottom:0;left:var(--left);pointer-events:none;position:absolute;top:0;width:2px;z-index:2}
.gantt-bar{align-items:center;border:1px solid var(--ui-deep);border-left-width:5px;border-radius:0;cursor:pointer;display:flex;font:650 .74rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;height:36px;left:var(--left);max-width:calc(100% - var(--left));overflow:hidden;padding:0 .55rem;position:absolute;text-align:left;text-overflow:ellipsis;top:15px;transition:filter .12s,box-shadow .12s;width:var(--width);white-space:nowrap;z-index:1}.gantt-bar:hover{filter:brightness(.94)}.gantt-bar[aria-pressed="true"]{box-shadow:inset 0 0 0 2px var(--ui-yellow),0 0 0 2px var(--ui-deep)}
.gantt-bar-done{background:var(--ui-light);color:var(--ui-deep)}.gantt-bar-current{background:var(--ui-deep);border-left-color:var(--ui-yellow);color:var(--ui-paper);text-shadow:0 0 7px rgba(254,238,212,.28)}.gantt-bar-upcoming{background:var(--ui-cream);color:var(--ui-deep)}.gantt-bar-blocked{background:var(--ui-yellow);color:var(--ui-deep)}.gantt-bar-unscheduled{background:repeating-linear-gradient(135deg,var(--ui-cream),var(--ui-cream) 6px,var(--ui-paper) 6px,var(--ui-paper) 12px);color:var(--ui-deep)}
.ticket-section{border-top:0;padding-top:1.35rem}.ticket-tools{align-items:center;display:flex;gap:1rem;justify-content:space-between;margin:.7rem 0}.ticket-search{max-width:320px;position:relative;width:100%}.ticket-search:before{color:var(--ui-dark);content:">";font:750 .85rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;left:.65rem;position:absolute;top:50%;transform:translateY(-50%);z-index:1}.ticket-search label{height:1px;overflow:hidden;position:absolute;width:1px;clip:rect(0 0 0 0)}.ticket-search input{background:var(--ui-paper);border:2px solid var(--ui-dark);border-radius:0;color:var(--ink);font:550 .8rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;min-height:36px;padding:.52rem .65rem .52rem 1.55rem;width:100%}.ticket-search input:hover{background:var(--ui-cream)}.ticket-search input:focus{border-color:var(--ui-deep)}.ticket-search input::placeholder{color:var(--subtle);opacity:1}.ticket-table{border:2px solid var(--ui-dark);max-width:100%;min-width:0}.ticket-table-head,.ticket-table-row{display:grid;gap:.8rem;grid-template-columns:minmax(240px,1.5fr) minmax(160px,1fr) minmax(110px,.7fr) 105px;padding:.58rem .65rem}.ticket-table-head{background:var(--ui-deep);color:var(--ui-paper);font:650 .72rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase}.ticket-table-row{align-items:center;background:rgba(254,238,212,.64);border:0;border-bottom:1px solid var(--line);border-left:4px solid transparent;color:var(--ink);cursor:pointer;min-height:48px;text-align:left;width:100%}.ticket-table-row:hover{background:var(--ui-yellow);border-left-color:var(--ui-dark)}.ticket-name{min-width:0}.ticket-name strong{display:block;font-size:.84rem;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ticket-name small,.ticket-table-row>span{color:var(--muted);font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ticket-empty{color:var(--muted);padding:1rem .6rem}
.team-grid{display:grid;gap:.75rem;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}.team-card{background:rgba(254,238,212,.7);border:2px solid var(--ui-dark);box-shadow:4px 4px 0 rgba(35,43,39,.15);padding:.85rem}.team-card small{color:var(--ui-deep);display:block;font:700 .72rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.07em;text-transform:uppercase}.team-card strong{display:block;font-size:.95rem;margin-top:.25rem}.team-card p{color:var(--muted);font-size:.8rem;margin:.35rem 0 0}.team-card-internal{background:rgba(225,222,209,.55);border-style:dashed}.team-tools{color:var(--muted);font-size:.8rem;margin:.8rem 0 0}
.sheet-backdrop{background:rgba(50,88,134,.32);inset:0;opacity:0;pointer-events:none;position:fixed;transition:opacity .18s;z-index:20}.sheet-backdrop.is-open{opacity:1;pointer-events:auto}
.side-sheet{background:var(--paper);border-left:5px solid var(--ui-dark);box-shadow:-12px 0 38px rgba(50,88,134,.24);height:100dvh;max-width:100%;overflow-y:auto;position:fixed;right:0;top:0;transform:translateX(102%);transition:transform .2s ease;width:520px;z-index:31}.side-sheet.is-open{transform:translateX(0)}
.sheet-top{align-items:center;background:var(--ui-deep);border-bottom:3px solid var(--ui-yellow);display:flex;justify-content:space-between;padding:.65rem .8rem;position:sticky;top:0;z-index:2}.sheet-top span{color:var(--ui-yellow);font:650 .74rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.09em;text-transform:uppercase}.sheet-close{align-items:center;background:transparent;border:1px solid var(--ui-paper);border-radius:0;color:var(--ui-paper);cursor:pointer;display:flex;font-size:1.2rem;height:32px;justify-content:center;width:32px}.sheet-close:hover{background:var(--ui-yellow);color:var(--ui-deep)}
.sheet-content{padding:2rem 2.2rem 3rem}.sheet-title-row{align-items:flex-start;display:flex;flex-wrap:wrap;gap:1rem;justify-content:space-between}.sheet-title-row h2{flex:1 1 260px;min-width:0}.sheet-title-row .status-pill{flex:0 0 auto;max-width:100%}.sheet-content h2{color:var(--ui-deep);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:1.5rem;letter-spacing:-.025em;line-height:1.2;margin:0;text-transform:uppercase}.sheet-objective{font-size:.98rem;margin:.85rem 0 .25rem}.sheet-context{color:var(--muted);margin:.25rem 0 1.25rem}.sheet-properties{border:2px solid var(--ui-deep);margin:1rem 0 1.5rem;padding:.3rem .75rem}.sheet-property{display:grid;gap:1rem;grid-template-columns:110px minmax(0,1fr);padding:.55rem 0}.sheet-property+.sheet-property{border-top:1px solid var(--line)}.sheet-property dt{color:var(--muted);font:650 .74rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.sheet-property dd{margin:0;min-width:0}.sheet-section{border-top:2px solid var(--ui-deep);padding-top:1rem;margin-top:1rem}.sheet-section h3{color:var(--ui-deep);font:700 .8rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.055em;margin:0 0 .55rem;text-transform:uppercase}.sheet-section h3:before{color:var(--ui-dark);content:"[ ";}.sheet-section h3:after{color:var(--ui-dark);content:" ]"}.sheet-section .ticket-row{padding:.65rem .2rem}.sheet-person{align-items:center;display:flex;gap:.55rem;padding:.35rem 0}.sheet-person .avatar{height:26px;width:26px}.sheet-person span{color:var(--muted);font-size:.8rem}.sheet-open{overflow:hidden}
.sheet-person{gap:.75rem;padding:.4rem 0}.sheet-person .avatar{color:var(--ui-deep);height:30px;width:30px}.sheet-person>div{min-width:0}.sheet-person strong,.sheet-person span{display:block}.sheet-person span{margin-top:.12rem}.avatar{background:var(--ui-light);color:var(--ui-deep)}.status-pill{border:1px solid currentColor;border-radius:0;font:650 .72rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.025em;padding:.32rem .44rem;text-transform:uppercase}.status-active{background:var(--ui-deep);color:var(--ui-paper)}.status-success{background:var(--ui-light);color:var(--ui-deep)}.status-review{background:var(--ui-yellow);color:var(--ui-deep)}.status-danger{background:var(--ui-deep);color:var(--ui-yellow)}.ticket-search input:focus-visible{box-shadow:0 0 0 5px var(--ui-yellow);outline:3px solid var(--ui-deep);outline-offset:2px}
@media(max-width:760px){.site-header{padding:2rem 1rem 0}.system-nav{margin-left:-1rem;margin-right:-1rem;padding-left:1rem}.system-nav a{padding:.8rem .65rem}.system-nav-status{display:none}main{padding:1rem .8rem 4rem}.section-heading{align-items:flex-start;display:grid}.gantt-toolbar{align-self:start}.ticket-tools{align-items:stretch;display:grid}.ticket-search{max-width:none}.ticket-table-head,.ticket-table-row{grid-template-columns:minmax(190px,1fr) 95px}.ticket-table-head span:nth-child(2),.ticket-table-head span:nth-child(3),.ticket-table-row>span:nth-child(2),.ticket-table-row>span:nth-child(3){display:none}.sheet-content{padding:1.5rem 1.2rem 2.5rem}}
@media print{body:after{display:none}}
</style>
<style>
:root{--screen:#07131c;--screen-raised:#0b1f2d;--screen-blue:#173a57;--phosphor:#fef265;--phosphor-soft:#fce8a4;--phosphor-muted:#e5d991;--alert:#ff9f43;--ink:var(--phosphor-soft);--muted:var(--phosphor-muted);--subtle:#c9bd79;--line:rgba(254,242,101,.3);--line-strong:rgba(254,242,101,.58);--paper:var(--screen);--canvas:var(--screen-raised);--accent:var(--phosphor);--accent-dark:var(--phosphor);--accent-soft:rgba(254,242,101,.12);--success:var(--phosphor);--success-soft:rgba(254,242,101,.12);--warning:var(--phosphor);--warning-soft:rgba(254,242,101,.14);--danger:var(--alert);--danger-soft:rgba(255,159,67,.14);--shadow:0 0 34px rgba(254,242,101,.1)}
html,body{background:var(--screen);color:var(--ink)}body{background-image:linear-gradient(rgba(7,19,28,.72),rgba(7,19,28,.92)),radial-gradient(circle at 72% -10%,rgba(68,122,185,.38),transparent 38%),linear-gradient(115deg,#102c40,var(--screen) 58%);background-attachment:fixed;color:var(--ink)}body:after{background:repeating-linear-gradient(0deg,rgba(254,242,101,.025) 0,rgba(254,242,101,.025) 1px,transparent 1px,transparent 4px),radial-gradient(ellipse at center,transparent 62%,rgba(0,0,0,.32) 100%);z-index:30}a{color:var(--phosphor);text-decoration-color:rgba(254,242,101,.55)}a:hover{color:#fff8b8}.skip-link{background:var(--phosphor);color:var(--screen)}
.site-header{background:linear-gradient(180deg,rgba(7,19,28,.98),rgba(7,19,28,.9));border-bottom:1px solid var(--line-strong);box-shadow:inset 0 -18px 36px rgba(68,122,185,.06),0 8px 30px rgba(0,0,0,.34);padding:1.35rem clamp(1rem,2.5vw,2.75rem) 0}.site-header:before{color:var(--phosphor-muted);content:"BATON-OS // PROJECT CONTROL";font-size:.72rem;letter-spacing:.18em}.site-header h1{color:var(--phosphor);font-size:clamp(1.65rem,3vw,2.25rem);letter-spacing:.015em;text-shadow:0 0 10px rgba(254,242,101,.42)}.site-header>p{color:var(--phosphor-soft);font-size:.96rem}.header-meta{color:var(--phosphor-muted);font-size:.76rem}.header-meta span+span:before{color:var(--phosphor)}
.system-nav{background:transparent;border-top:0;gap:.15rem;margin-left:clamp(-2.75rem,-2.5vw,-1rem);margin-right:clamp(-2.75rem,-2.5vw,-1rem);margin-top:1.1rem;min-height:48px;overflow:visible;padding-left:clamp(1rem,2.5vw,2.75rem);padding-right:clamp(1rem,2.5vw,2.75rem);position:relative}.system-nav:after{background:var(--phosphor);bottom:0;box-shadow:0 0 8px rgba(254,242,101,.42);content:"";height:2px;left:0;position:absolute;right:0}.system-nav a{border:0;color:var(--phosphor-muted);font-size:.82rem;letter-spacing:.09em;padding:.9rem 1.15rem 1rem;position:relative;z-index:1}.system-nav a:first-child{margin-left:-1.15rem}.system-nav a:before,.system-nav a:after{content:none}.system-nav a:hover,.system-nav a.is-active,.system-nav a[aria-current="page"]{background:transparent;color:var(--phosphor);text-shadow:0 0 8px rgba(254,242,101,.48)}.system-nav a.is-active:after,.system-nav a[aria-current="page"]:after{background:var(--screen);border:2px solid var(--phosphor);border-bottom:0;bottom:-2px;content:"";height:9px;left:.42rem;position:absolute;right:.42rem}.system-nav-status{color:var(--phosphor-muted);font-size:.7rem;padding-right:.25rem}.system-nav-status:before{background:var(--phosphor);box-shadow:0 0 10px var(--phosphor)}
main{padding-bottom:6.25rem}.preview-bar{background:rgba(23,58,87,.72);border:1px solid var(--phosphor);border-left-width:5px;border-radius:0;color:var(--phosphor-soft);box-shadow:inset 0 0 20px rgba(68,122,185,.13)}.preview-bar a,.preview-bar strong{color:var(--phosphor)}
.section-heading{border-bottom:2px solid var(--phosphor);padding-bottom:.45rem}.section-heading:after{background:var(--screen);border:2px solid var(--phosphor);border-bottom:0;bottom:-2px;height:8px;right:1rem;width:64px}.section-heading h2{color:var(--phosphor);font-size:1rem;text-shadow:0 0 8px rgba(254,242,101,.28)}.section-heading h2:before,.section-heading h2:after{color:var(--phosphor-muted)}.section-heading p,.count{color:var(--muted)}
.notion-button{background:transparent;border:1px solid var(--phosphor);border-radius:0;color:var(--phosphor);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.notion-button:before{content:"[ ";}.notion-button:after{content:" ]"}.notion-button:hover{background:var(--phosphor);border-color:var(--phosphor);color:var(--screen)}
:where(a,button,input,select,summary):focus-visible{box-shadow:0 0 0 6px #fff8d2;outline:3px solid var(--screen);outline-offset:2px}
.gantt-viewport{background:rgba(7,19,28,.82);border:1px solid var(--phosphor);border-left-width:3px;box-shadow:inset 0 0 36px rgba(68,122,185,.1),0 0 18px rgba(254,242,101,.06);scrollbar-color:var(--phosphor) var(--screen)}.gantt-corner,.gantt-dates{background:var(--screen);border-bottom:2px solid var(--phosphor)}.gantt-corner{border-right-color:var(--line);color:var(--phosphor)}.date-tick{color:var(--phosphor-muted)}.date-tick:before{background:var(--line)}.today-head{background:var(--phosphor);color:var(--screen);text-shadow:none}.gantt-label{background:var(--screen);border-right-color:var(--phosphor);box-shadow:3px 0 0 rgba(7,19,28,.96);isolation:isolate;overflow:hidden;pointer-events:auto;z-index:5}.gantt-label,.gantt-track{border-bottom-color:var(--line)}.gantt-label:hover{background:var(--screen-raised)}.gantt-track:hover{background-color:rgba(254,242,101,.055)}.gantt-goal-button{background:rgba(7,19,28,.94);border:1px solid var(--line-strong);border-left:3px solid var(--phosphor);color:var(--phosphor-soft)}.gantt-goal-button:hover,.gantt-goal-button:focus-visible,.gantt-goal-button[aria-pressed="true"]{background:rgba(254,242,101,.1);border-color:var(--phosphor);box-shadow:inset 0 0 18px rgba(254,242,101,.1)}.gantt-goal-button small{color:var(--muted)}.gantt-track{background-image:repeating-linear-gradient(to right,transparent 0,transparent calc(var(--week-width) - 1px),var(--line) calc(var(--week-width) - 1px),var(--line) var(--week-width))}.today-line{background:var(--phosphor);box-shadow:0 0 8px rgba(254,242,101,.7)}
.gantt-bar{background:rgba(254,242,101,.07);border-color:var(--phosphor);color:var(--phosphor-soft);text-shadow:none}.gantt-bar:hover{filter:none}.gantt-bar-done,.gantt-bar-current,.gantt-bar-upcoming{background:var(--phosphor);border-color:var(--phosphor);color:var(--screen);text-shadow:none}.gantt-bar-blocked{background:var(--alert);border-color:var(--alert);color:var(--screen)}.gantt-bar-unscheduled{background:repeating-linear-gradient(135deg,rgba(254,242,101,.14),rgba(254,242,101,.14) 6px,rgba(7,19,28,.9) 6px,rgba(7,19,28,.9) 12px);color:var(--phosphor-soft)}
.gantt-bar-done:hover,.gantt-bar-current:hover,.gantt-bar-upcoming:hover{background:#fff58a;box-shadow:0 0 14px rgba(254,242,101,.34);color:var(--screen)}.gantt-bar-blocked:hover{background:#ffb35f;box-shadow:0 0 14px rgba(255,159,67,.3);color:var(--screen)}.gantt-bar-unscheduled:hover{background:repeating-linear-gradient(135deg,rgba(254,242,101,.22),rgba(254,242,101,.22) 6px,rgba(7,19,28,.96) 6px,rgba(7,19,28,.96) 12px)}
.team-card{background:rgba(11,31,45,.76);border:1px solid var(--line-strong);box-shadow:none;color:var(--ink)}.team-card:hover{background:rgba(254,242,101,.07);border-color:var(--phosphor)}.team-card small,.team-card strong{color:var(--phosphor)}.team-card p,.team-tools{color:var(--muted)}.team-card-internal{background:rgba(23,58,87,.42);border-color:var(--line-strong)}code{color:var(--phosphor)}
.team-card{text-decoration:none}.team-card:hover strong{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px}
.workforce-summary{display:grid;gap:.75rem;grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:.8rem}.workforce-callout{background:rgba(254,242,101,.07);border:1px solid var(--phosphor);border-left-width:5px;padding:.8rem .9rem}.workforce-callout-attention{background:rgba(255,159,67,.09);border-color:var(--alert)}.workforce-callout small{color:var(--muted);display:block;font:650 .68rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.07em;text-transform:uppercase}.workforce-callout strong{color:var(--phosphor);display:block;font:700 .98rem/1.25 ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:.3rem}.workforce-callout-attention strong{color:#ffd08a}.workforce-callout span{color:var(--muted);display:block;font-size:.76rem;margin-top:.18rem}.workforce-layout{display:grid;gap:.8rem;grid-template-columns:minmax(0,1.55fr) minmax(280px,.75fr)}.workforce-panel{background:rgba(7,19,28,.76);border:1px solid var(--line-strong);padding:1rem}.workforce-panel h3{color:var(--phosphor);font:700 .78rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.07em;margin:0 0 .9rem;text-transform:uppercase}.workforce-panel h3:before{color:var(--phosphor-muted);content:"[ ";}.workforce-panel h3:after{color:var(--phosphor-muted);content:" ]"}.workforce-bars{display:grid;gap:.72rem;list-style:none;margin:0;padding:0}.workforce-row{align-items:center;display:grid;gap:.7rem;grid-template-columns:minmax(120px,180px) minmax(120px,1fr) 48px}.workforce-person{min-width:0}.workforce-person strong{color:var(--phosphor-soft);display:block;font-size:.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.workforce-person span{color:var(--muted);display:block;font-size:.7rem;margin-top:.12rem}.workforce-row>b{color:var(--phosphor);font:700 .74rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;text-align:right}.workforce-bar{border:1px solid var(--phosphor);height:18px;overflow:hidden}.workforce-bar i{background:var(--phosphor);box-shadow:0 0 8px rgba(254,242,101,.44);display:block;height:100%;width:var(--value)}.workforce-distribution{align-items:center;display:grid;grid-template-columns:minmax(150px,.9fr) minmax(140px,1fr)}.workforce-distribution h3{grid-column:1/-1;justify-self:start}.workforce-donut{align-items:center;aspect-ratio:1;background:var(--workforce-gradient);border:1px solid var(--phosphor);border-radius:50%;box-shadow:0 0 18px rgba(254,242,101,.12);display:flex;justify-content:center;max-width:190px;position:relative;width:100%}.workforce-donut:before{background:var(--screen);border:1px solid var(--line-strong);border-radius:50%;content:"";inset:25%;position:absolute}.workforce-donut>div{display:grid;position:relative;text-align:center;z-index:1}.workforce-donut strong{color:var(--phosphor);font:750 1.35rem/1 ui-monospace,SFMono-Regular,Menlo,monospace}.workforce-donut span{color:var(--muted);font:650 .62rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:.25rem;text-transform:uppercase}.workforce-legend{display:grid;gap:.42rem;list-style:none;margin:0;padding:0}.workforce-legend li{align-items:center;display:grid;gap:.45rem;grid-template-columns:10px minmax(0,1fr) auto}.workforce-legend i{background:var(--swatch);height:8px;width:8px}.workforce-legend span{color:var(--muted);font-size:.7rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.workforce-legend strong{color:var(--phosphor);font:650 .7rem/1 ui-monospace,SFMono-Regular,Menlo,monospace}.workforce-note{color:var(--muted);font-size:.7rem;margin:.7rem 0 0}
.workforce-callout{color:inherit}.workforce-person{background:transparent;color:inherit;min-width:0;text-align:left;width:100%}.workforce-legend li{display:block}.workforce-legend-entry{align-items:center;color:inherit;display:grid;gap:.45rem;grid-template-columns:10px minmax(0,1fr) auto;padding:.16rem 0;width:100%}.ticket-row{appearance:none;background:transparent;border:0;color:inherit;cursor:pointer;font-family:inherit;text-align:left;width:100%}.ticket-row:hover,.ticket-row:focus-visible{background:rgba(254,242,101,.09)}.ticket-row.is-linked,.ticket-table-row.is-linked{background:var(--phosphor);color:var(--screen)}.ticket-row.is-linked .ticket-copy small,.ticket-row.is-linked .ticket-copy strong,.ticket-row.is-linked .ticket-owner,.ticket-table-row.is-linked .ticket-name small,.ticket-table-row.is-linked>span{color:var(--screen)}.sheet-person .avatar{align-items:center;display:flex;flex:0 0 30px;justify-content:center;line-height:1;margin:0;text-align:center}.ticket-owner{min-width:0}
.ticket-control-group{display:flex;flex:1;gap:.6rem;min-width:0}.ticket-search:before{color:var(--phosphor)}.ticket-search input{background:rgba(7,19,28,.9);border-color:var(--phosphor);color:var(--phosphor-soft);caret-color:var(--phosphor)}.ticket-search input:hover{background:rgba(254,242,101,.06)}.ticket-search input:focus{border-color:var(--phosphor)}.ticket-search input::placeholder{color:var(--muted)}.ticket-filter{max-width:240px;position:relative;width:100%;z-index:20}.ticket-filter-label{height:1px;overflow:hidden;position:absolute;width:1px;clip:rect(0 0 0 0)}.ticket-filter-trigger{align-items:center;appearance:none;background:rgba(7,19,28,.9);border:2px solid var(--phosphor);border-radius:0;color:var(--phosphor-soft);cursor:pointer;display:flex;font:650 .76rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;gap:.65rem;justify-content:space-between;min-height:38px;padding:.38rem .65rem;width:100%}.ticket-filter-trigger:hover{background:rgba(254,242,101,.06);border-color:#fff8b8}.ticket-filter-trigger[aria-expanded="true"]{background:var(--screen-raised);border-color:#fff8d2}.ticket-filter-value{align-items:center;display:flex;min-width:0;text-align:left}.ticket-filter-value .status-pill{pointer-events:none}.ticket-filter-chevron{color:var(--phosphor);flex:0 0 auto}.ticket-filter-menu{background:var(--screen-raised);border:2px solid var(--phosphor);box-shadow:8px 8px 0 rgba(0,0,0,.32);display:grid;gap:2px;max-height:min(430px,65vh);min-width:100%;overflow-y:auto;padding:.35rem;position:absolute;right:0;top:calc(100% + 5px);width:max-content;z-index:50}.ticket-filter-menu[hidden]{display:none}.ticket-filter-option{align-items:center;appearance:none;background:transparent;border:1px solid transparent;color:var(--phosphor-soft);cursor:pointer;display:flex;font:650 .76rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;justify-content:flex-start;min-height:38px;padding:.35rem;text-align:left;width:100%}.ticket-filter-option:hover,.ticket-filter-option:focus-visible,.ticket-filter-option[aria-selected="true"]{background:rgba(254,242,101,.12);border-color:var(--phosphor);outline:0}.ticket-filter-option[aria-selected="true"]:before{color:var(--phosphor);content:">";margin-right:.45rem}.ticket-filter-option .status-pill{pointer-events:none}.ticket-filter-option-all{padding-left:.55rem}.ticket-table{border:1px solid var(--phosphor);overflow:hidden}.ticket-table-head{background:rgba(254,242,101,.09);border-bottom:1px solid var(--phosphor);color:var(--phosphor)}#ticket-rows{height:min(420px,48vh);min-height:250px;overflow-y:auto;overscroll-behavior:contain;scrollbar-color:var(--phosphor) var(--screen)}.ticket-table-row{background:rgba(7,19,28,.74);border-bottom-color:var(--line);color:var(--ink)}.ticket-table-row:hover,.ticket-table-row:focus-visible{background:var(--phosphor);border-left-color:var(--phosphor);color:var(--screen)}.ticket-table-row:hover .ticket-name small,.ticket-table-row:hover>span,.ticket-table-row:focus-visible .ticket-name small,.ticket-table-row:focus-visible>span{color:var(--screen)}.ticket-name strong{color:inherit}.ticket-name small,.ticket-table-row>span,.ticket-empty{color:var(--muted)}
.sheet-backdrop{background:rgba(0,0,0,.72)}.side-sheet{background:var(--screen);border-left:2px solid var(--phosphor);box-shadow:-10px 0 40px rgba(0,0,0,.6),-2px 0 14px rgba(254,242,101,.12)}.sheet-top{background:var(--screen);border-bottom-color:var(--phosphor)}.sheet-top span{color:var(--phosphor)}.sheet-close{border-color:var(--phosphor);color:var(--phosphor)}.sheet-close:hover{background:var(--phosphor);color:var(--screen)}.sheet-content h2,.sheet-section h3{color:var(--phosphor)}.sheet-objective{color:var(--phosphor-soft)}.sheet-context,.sheet-property dt,.sheet-person span{color:var(--muted)}.sheet-properties,.sheet-section{border-color:var(--phosphor)}.sheet-property+.sheet-property{border-color:var(--line)}.sheet-section h3:before,.sheet-section h3:after{color:var(--phosphor-muted)}.sheet-person .avatar,.avatar{background:rgba(254,242,101,.14);border:1px solid var(--phosphor);color:var(--phosphor)}
.status-pill{border-color:currentColor}.status-active{background:var(--phosphor);color:var(--screen)}.status-success{background:rgba(254,242,101,.12);color:var(--phosphor)}.status-review{background:rgba(255,159,67,.16);color:#ffd08a}.status-danger{background:var(--alert);color:var(--screen)}
.status-pill.status-neutral{background:#173a57;border-color:#a9c9ef;color:#d9eaff}.status-pill.status-ready{background:#82a7d6;border-color:#b8d2ef;color:#07131c}.status-pill.status-active{background:#fef265;border-color:#fef265;color:#07131c}.status-pill.status-review{background:#ff9f43;border-color:#ffd0a0;color:#07131c}.status-pill.status-success{background:#143b2a;border-color:#64d99a;color:#b9f6d2}.status-pill.status-danger{background:#8f2f2a;border-color:#ff8f7c;color:#fff3d6}.status-pill.status-abandoned{background:#303742;border-color:#8d98a8;color:#d2d8e1}.ticket-row.is-linked>.status-pill,.ticket-table-row:hover>.status-pill,.ticket-table-row:focus-visible>.status-pill,.ticket-table-row.is-linked>.status-pill{background:var(--screen);border-color:var(--screen);color:var(--phosphor)}
.pip-hud{align-items:stretch;background:rgba(7,19,28,.97);border-top:2px solid var(--phosphor);bottom:0;box-shadow:0 -8px 24px rgba(0,0,0,.44),0 -2px 12px rgba(254,242,101,.12);display:grid;grid-template-columns:minmax(130px,.65fr) minmax(280px,2fr) minmax(120px,.65fr) minmax(120px,.65fr);left:0;padding:0 clamp(.75rem,2vw,2.5rem);position:fixed;right:0;z-index:19}.hud-cell{border-right:1px solid var(--line);display:grid;gap:.2rem;min-width:0;padding:.58rem .8rem}.hud-cell:first-child{border-left:1px solid var(--line)}.hud-cell span{color:var(--phosphor-muted);font:650 .65rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;text-transform:uppercase}.hud-cell strong{color:var(--phosphor);font:700 .78rem/1.25 ui-monospace,SFMono-Regular,Menlo,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hud-progress-track{border:1px solid var(--phosphor);height:7px;margin-top:.15rem;overflow:hidden}.hud-progress-track i{background:var(--phosphor);box-shadow:0 0 8px rgba(254,242,101,.6);display:block;height:100%;width:var(--value)}
.pip-tooltip{background:rgba(7,19,28,.98);border:1px solid var(--phosphor);border-left-width:4px;box-shadow:0 0 18px rgba(254,242,101,.18),inset 0 0 14px rgba(68,122,185,.12);color:var(--phosphor-soft);font:650 .74rem/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em;max-width:min(360px,calc(100vw - 24px));padding:.5rem .65rem;pointer-events:none;position:fixed;white-space:normal;z-index:60}.pip-tooltip:before{color:var(--phosphor);content:"> ";font-weight:800}.pip-tooltip[hidden]{display:none}
@media(max-width:760px){.system-nav{margin-left:-1rem;margin-right:-1rem;overflow-x:auto;padding-left:1rem;padding-right:1rem}.system-nav a{font-size:.7rem;padding:.85rem .5rem 1rem;white-space:nowrap}.system-nav a:first-child{margin-left:-.5rem}.system-nav a.is-active:after,.system-nav a[aria-current="page"]:after{left:.2rem;right:.2rem}.workforce-summary,.workforce-layout{grid-template-columns:1fr}.workforce-row{grid-template-columns:minmax(105px,145px) minmax(90px,1fr) 42px}.ticket-control-group{display:grid;grid-template-columns:minmax(0,1fr) minmax(150px,.55fr)}.ticket-filter{max-width:none}.pip-hud{grid-template-columns:minmax(0,1fr) 110px}.hud-cell{padding:.55rem .65rem}.hud-phase,.hud-review{display:none}.hud-goal{border-left:1px solid var(--line)}}
@media(max-width:1100px){.workforce-distribution{align-content:start;grid-template-columns:1fr}.workforce-donut{justify-self:center;max-width:160px}.workforce-legend{margin-top:.8rem;min-width:0;width:100%}.workforce-legend-entry,.workforce-legend-entry span{min-width:0}}
@media(max-width:480px){.workforce-row{grid-template-columns:minmax(0,1fr) 44px}.workforce-bar{grid-column:1/-1;grid-row:2}.workforce-row>b{grid-column:2;grid-row:1}.ticket-control-group{grid-template-columns:1fr}}
.workforce-person span{color:#a9c9ef;font:650 .66rem/1.25 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.025em;text-transform:uppercase}.workforce-person small{color:var(--muted);display:block;font-size:.68rem;margin-top:.12rem}.workforce-callout em{color:#a9c9ef;display:block;font:650 .68rem/1.25 ui-monospace,SFMono-Regular,Menlo,monospace;font-style:normal;letter-spacing:.025em;margin-top:.16rem;text-transform:uppercase}.workforce-legend-entry span{display:grid}.workforce-legend-entry span small{color:#a9c9ef;font-size:.6rem;margin-top:.08rem;text-transform:uppercase}
.sheet-actions{align-items:center;display:flex;gap:.7rem;margin:0 0 1.1rem}.sheet-back-button{appearance:none;background:rgba(254,242,101,.07);border:1px solid var(--phosphor);color:var(--phosphor);cursor:pointer;flex:0 0 36px;height:36px;position:relative;width:36px}.sheet-back-button:before{border-bottom:2px solid currentColor;border-left:2px solid currentColor;content:"";height:8px;left:12px;position:absolute;top:50%;transform:translateY(-50%) rotate(45deg);width:8px}.sheet-back-button:after{background:currentColor;content:"";height:2px;left:11px;position:absolute;top:50%;transform:translateY(-50%);width:15px}.sheet-back-button:hover{background:var(--phosphor);color:var(--screen)}.sheet-list-action{appearance:none;background:transparent;border:0;border-bottom:1px solid transparent;color:var(--phosphor-muted);cursor:pointer;font:650 .7rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;padding:.4rem .1rem;text-align:left}.sheet-list-action:before{color:var(--phosphor);content:"> ";font-weight:800}.sheet-list-action:hover{border-bottom-color:var(--phosphor);color:var(--phosphor)}.sheet-record-button{appearance:none;background:rgba(254,242,101,.07);border:1px solid var(--phosphor);color:var(--phosphor);cursor:pointer;font:650 .7rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;padding:.45rem .6rem;text-align:left}.sheet-record-button:hover{background:var(--phosphor);color:var(--screen)}.sheet-record-button:before{content:"[ ";}.sheet-record-button:after{content:" ]"}.sheet-detail-list{display:grid;gap:.45rem;list-style:none;margin:.35rem 0 0;padding:0}.sheet-detail-list li{border-left:2px solid var(--line-strong);color:var(--phosphor-soft);font-size:.8rem;padding:.2rem 0 .2rem .6rem}.sheet-record-list{display:grid;gap:.4rem}.sheet-record-list .sheet-record-button{width:100%}.sheet-empty{color:var(--muted);font-size:.8rem;margin:.3rem 0}.ticket-sheet-id{color:var(--phosphor-muted);font:700 .72rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;margin:0 0 .45rem;text-transform:uppercase}
.sheet-property [data-sheet-goal]{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;width:100%}
.goal-brief{min-width:0}.goal-brief-text{color:var(--phosphor-soft);display:-webkit-box;font-size:.8rem;line-height:1.45;margin:0;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2;line-clamp:2}.goal-brief.is-expanded .goal-brief-text{display:block;overflow:visible;-webkit-line-clamp:unset;line-clamp:unset}.goal-brief-toggle{appearance:none;background:transparent;border:0;border-bottom:1px solid transparent;color:var(--phosphor);cursor:pointer;font:650 .68rem/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:.35rem;padding:.15rem 0}.goal-brief-toggle:before{content:"> ";font-weight:800}.goal-brief-toggle:hover{border-bottom-color:var(--phosphor)}.goal-brief-toggle[hidden]{display:none}
.ticket-search input{padding-right:2.7rem}.ticket-search input::-webkit-search-cancel-button{-webkit-appearance:none;appearance:none;display:none}.ticket-search-clear{align-items:center;appearance:none;background:transparent;border:1px solid transparent;color:var(--muted);cursor:pointer;display:flex;font:700 1rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;height:26px;justify-content:center;position:absolute;right:.45rem;top:50%;transform:translateY(-50%);width:26px;z-index:2}.ticket-search-clear[hidden]{display:none}.ticket-search-clear:hover{background:rgba(254,242,101,.12);border-color:var(--phosphor);color:var(--phosphor)}.ticket-search-clear:focus-visible{background:var(--phosphor);border-color:var(--phosphor);color:var(--screen);outline:2px solid #fff8d2;outline-offset:2px}.ticket-filter{z-index:18}.ticket-filter.opens-up .ticket-filter-menu{bottom:calc(100% + 5px);top:auto}
.status-pill{justify-self:start;max-width:100%;overflow:hidden;text-overflow:ellipsis;width:max-content}.ticket-table-head>span:last-child,.ticket-table-row>.status-pill{justify-self:end;text-align:right}
.ticket-search input,.ticket-filter-trigger{background:rgba(7,19,28,.9);border:2px solid var(--phosphor);color:var(--phosphor-soft);min-height:38px}.ticket-search input:hover,.ticket-filter-trigger:hover{background:rgba(254,242,101,.06);border-color:#fff8b8}.ticket-search input:focus,.ticket-filter-trigger:focus{background:var(--screen-raised);border-color:var(--phosphor)}.ticket-search input:focus-visible,.ticket-filter-trigger:focus-visible{background:var(--screen-raised);border-color:#fff8d2;box-shadow:0 0 0 2px var(--screen),0 0 0 5px var(--phosphor);outline:0}.ticket-search:focus-within:before,.ticket-filter-trigger:focus-visible .ticket-filter-chevron{color:#fff8d2;text-shadow:0 0 8px rgba(254,242,101,.7)}
.ticket-filter-trigger[aria-expanded="true"]{background:var(--screen-raised);border-color:#fff8d2;box-shadow:0 0 0 2px var(--screen),0 0 0 5px var(--phosphor);outline:0}.ticket-filter-trigger[aria-expanded="true"] .ticket-filter-chevron{color:#fff8d2;text-shadow:0 0 8px rgba(254,242,101,.7)}.ticket-filter-option:hover{background:rgba(254,242,101,.08);border-color:rgba(254,242,101,.5)}.ticket-filter-option:focus-visible{background:rgba(254,242,101,.13);border-color:#fff8d2;box-shadow:inset 0 0 0 1px var(--phosphor);outline:0}.ticket-filter-option[aria-selected="true"]{background:rgba(254,242,101,.18);border-color:var(--phosphor);box-shadow:inset 4px 0 0 var(--phosphor)}.ticket-filter-menu{box-sizing:border-box;left:0;min-width:0;right:auto;scrollbar-color:var(--phosphor) var(--screen);scrollbar-width:thin;top:calc(100% + 20px);width:100%}.ticket-filter.opens-up .ticket-filter-menu{bottom:calc(100% + 20px);top:auto}.ticket-filter-option{column-gap:.45rem;display:grid;grid-template-columns:1rem minmax(0,1fr);padding:.35rem .55rem}.ticket-filter-option:before{content:"";grid-column:1;margin:0}.ticket-filter-option[aria-selected="true"]:before{content:">";margin:0}.ticket-filter-option>span{grid-column:2;justify-self:start}.gantt-viewport::-webkit-scrollbar,.ticket-filter-menu::-webkit-scrollbar,#ticket-rows::-webkit-scrollbar,.org-chart::-webkit-scrollbar{height:10px;width:10px}.gantt-viewport::-webkit-scrollbar-track,.ticket-filter-menu::-webkit-scrollbar-track,#ticket-rows::-webkit-scrollbar-track,.org-chart::-webkit-scrollbar-track{background:var(--screen)}.gantt-viewport::-webkit-scrollbar-thumb,.ticket-filter-menu::-webkit-scrollbar-thumb,#ticket-rows::-webkit-scrollbar-thumb,.org-chart::-webkit-scrollbar-thumb{background:var(--phosphor);border:2px solid var(--screen);border-radius:0}.gantt-viewport::-webkit-scrollbar-thumb:hover,.ticket-filter-menu::-webkit-scrollbar-thumb:hover,#ticket-rows::-webkit-scrollbar-thumb:hover,.org-chart::-webkit-scrollbar-thumb:hover{background:#fff8b8}
.ticket-filter-trigger[aria-expanded="true"],.ticket-filter-trigger[aria-expanded="true"]:focus-visible{box-shadow:0 0 0 2px var(--screen),0 0 0 5px var(--phosphor)}.ticket-filter-menu{box-shadow:8px 8px 0 rgba(0,0,0,.32);top:calc(100% + 10px)}.ticket-filter.opens-up .ticket-filter-menu{bottom:calc(100% + 10px);top:auto}
html{scrollbar-color:var(--phosphor) var(--screen);scrollbar-width:thin}html::-webkit-scrollbar,body::-webkit-scrollbar{height:12px;width:12px}html::-webkit-scrollbar-track,body::-webkit-scrollbar-track{background:var(--screen);border-left:1px solid var(--line)}html::-webkit-scrollbar-thumb,body::-webkit-scrollbar-thumb{background:var(--phosphor);border:3px solid var(--screen);border-radius:0}html::-webkit-scrollbar-thumb:hover,body::-webkit-scrollbar-thumb:hover{background:#fff8b8}html::-webkit-scrollbar-corner,body::-webkit-scrollbar-corner{background:var(--screen)}
.team-card,.team-card:hover{background:rgba(11,31,45,.76);border-color:var(--line-strong);cursor:default}.team-card:hover strong{text-decoration:none}
@media(min-width:761px){.gantt-grid{grid-template-columns:260px var(--timeline-width)}.gantt-label,.gantt-track{height:82px}.gantt-goal-button{grid-template-rows:auto auto}.gantt-goal-button strong{grid-column:1/-1;line-height:1.25;overflow:visible;text-overflow:clip;white-space:normal}.gantt-goal-button .status-pill{grid-column:2;grid-row:2}.gantt-goal-button small{grid-column:1;grid-row:2}.gantt-bar{top:23px}.ticket-table-head,.ticket-table-row{grid-template-columns:minmax(240px,1.5fr) minmax(160px,1fr) minmax(110px,.7fr) minmax(165px,max-content)}}
@media(max-width:760px){.ticket-table-head,.ticket-table-row{grid-template-columns:minmax(0,1fr) minmax(165px,max-content)}}
@media(max-width:760px){.section-heading{gap:.65rem}.gantt-toolbar{justify-content:space-between;width:100%}.gantt-viewport{-webkit-overflow-scrolling:touch;max-height:none;overflow-x:auto;overflow-y:clip;overscroll-behavior-x:contain;overscroll-behavior-y:auto;scroll-snap-type:x proximity;touch-action:pan-x pan-y}.gantt-grid{grid-template-columns:var(--timeline-width);width:var(--timeline-width)}.gantt-corner{display:none}.gantt-dates{grid-column:1;width:var(--timeline-width)}.gantt-label,.gantt-track{grid-column:1}.gantt-label,.gantt-label:hover{background:transparent;border:0;box-shadow:none}.gantt-label{height:62px;left:0;overflow:visible;padding:0;pointer-events:none;position:sticky;width:min(calc(100vw - 2rem),420px);z-index:3}.gantt-goal-button{background:rgba(7,19,28,.94);border:1px solid var(--line-strong);border-left:3px solid var(--phosphor);margin:6px;min-height:50px;padding:.45rem .55rem;pointer-events:auto;width:calc(100% - 12px)}.gantt-goal-button strong{font-size:.8rem}.gantt-goal-button .status-pill{font-size:.62rem}.gantt-goal-button small{display:none}.gantt-track{height:108px;margin-top:-62px;scroll-snap-align:start}.gantt-bar{height:36px;min-width:72px;top:66px}#ticket-rows{height:min(360px,44vh);min-height:220px}}
.dashboard-view[hidden],.pip-hud[hidden]{display:none}.dashboard-view{min-width:0}.company-surface,.company-workforce{background:rgba(7,19,28,.48);border:1px solid var(--line-strong);padding:1rem}.company-surface>.section-heading{margin-top:0}.company-workforce{margin-top:1rem}.company-subheading{align-items:end;display:flex;gap:1rem;justify-content:space-between;margin-bottom:.8rem}.company-subheading h2{color:var(--phosphor);font:750 1rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em;margin:0;text-transform:uppercase}.company-subheading h2:before{color:var(--phosphor-muted);content:"[ ";}.company-subheading h2:after{color:var(--phosphor-muted);content:" ]"}.company-subheading p{color:var(--muted);font-size:.76rem;margin:.18rem 0 0}.org-chart{display:grid;justify-items:center;min-width:0;overflow-x:auto;padding:1rem .5rem .35rem}.org-level{display:flex;flex-wrap:wrap;gap:.75rem;justify-content:center;list-style:none;margin:0;padding:0;width:100%}.org-person{background:rgba(11,31,45,.9);border:1px solid var(--phosphor);min-width:min(220px,100%);padding:.7rem .85rem;text-align:center}.org-person small{color:#a9c9ef;display:block;font:650 .62rem/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.07em;text-transform:uppercase}.org-person strong{color:var(--phosphor);display:block;font-size:.88rem;margin-top:.22rem}.org-person span{color:var(--phosphor-soft);display:block;font-size:.72rem;margin-top:.16rem}.org-connector{background:var(--phosphor);box-shadow:0 0 7px rgba(254,242,101,.45);display:block;height:28px;width:2px}.workforce-person-static{cursor:default}.workforce-person-static:hover strong{text-decoration:none}.sheet-close{font-size:0;position:relative}.sheet-close:before,.sheet-close:after{background:currentColor;content:"";height:2px;left:50%;position:absolute;top:50%;width:15px}.sheet-close:before{transform:translate(-50%,-50%) rotate(45deg)}.sheet-close:after{transform:translate(-50%,-50%) rotate(-45deg)}
.workforce-donut{cursor:help}.workforce-donut:focus-visible{box-shadow:0 0 0 3px var(--screen),0 0 0 6px var(--phosphor);outline:0}
@media print{.pip-hud{display:none}}
</style></head>
<body><a class="skip-link" href="#content">Skip to project status</a><header class="site-header"><h1 id="project-name">Project status</h1><p id="project-summary" aria-live="polite"></p><div class="header-meta" id="project-meta"></div><nav class="system-nav" aria-label="Pip-Boy dashboard" role="tablist"><a href="?view=mission" data-dashboard-tab="project" role="tab" aria-controls="project-view" aria-selected="true">Mission</a><a href="?view=team" data-dashboard-tab="company" role="tab" aria-controls="company-view" aria-selected="false">Team</a><span class="system-nav-status">Team network // read only</span></nav></header><script id="view-bootstrap">(()=>{const params=new URLSearchParams(location.search),stored=params.get('view'),legacyTeamHashes=new Set(['#team','#roster','#team-title','#workforce-title']),view=['mission','team'].includes(stored)?stored:legacyTeamHashes.has(location.hash)?'team':'mission',urlFor=target=>{const url=new URL(location.href);url.searchParams.set('view',target);url.hash='';return url};document.querySelectorAll('[data-dashboard-tab]').forEach(link=>{link.href=urlFor(link.dataset.dashboardTab==='company'?'team':'mission')});const canonical=urlFor(view);if(canonical.href!==location.href)location.replace(canonical.href)})();</script><main id="content" tabindex="-1"><div id="dashboard"></div></main>
<script id="state-snapshot" type="application/json">__STATE_SNAPSHOT__</script><script>
const canonical=JSON.parse(document.getElementById('state-snapshot').textContent),q=document.getElementById('dashboard'),previewMode=new URLSearchParams(location.search).get('mock')==='1';
const mock={
  project:{project:{name:'Cedar Health — Online booking',outcome:'Let patients book and pay online without calling the clinic.',currentGoal:'BETA-LAUNCH',agentProvider:'codex',phase:'Pilot launch',templateMode:true,lastVerified:'14 July 2026',assuranceDefaults:{testRigor:'Standard',humanReviewStages:[]}},baton:{owner:'Operations',action:'Finish beta testing and prepare the release review',returnTrigger:'The full booking journey passes on mobile and desktop'}},
  goals:{goals:[
    {id:'DISCOVERY',title:'Understand why patients still call',status:'Done',priority:'P1',owner:'Product Lead',objective:'Find the biggest obstacles to online booking',context:'Clinic staff logged every booking call for two weeks',dependencies:[],blockers:[],decisionPaths:[],evidencePaths:['docs/implementation-reports/README.md'],narrativePath:'docs/prds/README.md',plannedStart:'2026-06-23',plannedEnd:'2026-07-02',resultSummary:'Payment confidence and unclear availability caused most calls',completedAt:'2026-07-02'},
    {id:'PROTOTYPE',title:'Test the booking prototype',status:'Done',priority:'P1',owner:'Product Lead',objective:'Confirm that patients can complete the proposed flow',context:'Eight patients tested the prototype on their own phones',dependencies:['DISCOVERY'],blockers:[],decisionPaths:[],evidencePaths:['docs/review-packets/README.md'],narrativePath:'docs/prds/README.md',plannedStart:'2026-07-03',plannedEnd:'2026-07-08',resultSummary:'Seven of eight patients completed a booking without help',completedAt:'2026-07-08'},
    {id:'BETA-LAUNCH',title:'Launch online booking to 20 pilot patients',status:'Active',priority:'P1',owner:'Operations',objective:'Allow pilot patients to choose a time, pay, and receive confirmation without staff help.',context:'The beta will run with one clinic and three practitioners before a wider release.',dependencies:['PROTOTYPE'],blockers:[],decisionPaths:['docs/decisions/README.md'],evidencePaths:[],narrativePath:'docs/prds/README.md',plannedStart:'2026-07-09',plannedEnd:'2026-07-22'},
    {id:'MEASURE',title:'Measure whether patients finish booking',status:'Ready',priority:'P1',owner:'Product Lead',objective:'Measure completion, drop-off, and support calls during the pilot',context:'The team needs real usage evidence before expanding access',dependencies:['BETA-LAUNCH'],blockers:[],decisionPaths:[],evidencePaths:[],narrativePath:'docs/prds/README.md',plannedStart:'2026-07-23',plannedEnd:'2026-08-05'},
    {id:'RESCHEDULE',title:'Let patients reschedule online',status:'Needs Definition',priority:'P2',owner:'Product Lead',objective:'Remove the most common call after booking',context:'Rescheduling is excluded from the first beta',dependencies:['MEASURE'],blockers:[],decisionPaths:[],evidencePaths:[],narrativePath:'docs/prds/README.md',plannedStart:'2026-08-06',plannedEnd:'2026-08-20'}
  ]},
  tickets:{tickets:[
    {id:'DISC-001',title:'Review two weeks of booking calls',status:'Done',priority:'P1',owner:'Noor Ahmed',goal:'DISCOVERY',dependencies:[],acceptanceCriteria:['The main reasons for calling are ranked'],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[]},
    {id:'PROTO-001',title:'Build a clickable booking prototype',status:'Done',priority:'P1',owner:'Maya Chen',goal:'PROTOTYPE',dependencies:[],acceptanceCriteria:['The full proposed flow can be tested'],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[]},
    {id:'PROTO-002',title:'Run patient usability sessions',status:'Done',priority:'P1',owner:'Noor Ahmed',goal:'PROTOTYPE',dependencies:['PROTO-001'],acceptanceCriteria:['Eight patients attempt the flow'],assurance:{testRigor:'Thorough',humanReviewStages:[],overrideReason:'User requested full usability evidence'},blockers:[]},
    {id:'MEASURE-001',title:'Track booking completion and drop-off',status:'Ready',priority:'P1',owner:'Maya Chen',goal:'MEASURE',dependencies:['BOOK-107'],acceptanceCriteria:['The pilot reports completion and drop-off'],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[]},
    {id:'FUTURE-001',title:'Offer a waitlist when no times are available',status:'Backlog',priority:'P3',owner:'Sarah Morgan',goal:'RESCHEDULE',dependencies:[],objective:'Explore whether a waitlist would reduce calls',scope:[],nonGoals:[],affectedSystems:[],acceptanceCriteria:[],requiredVerification:[],expectedEvidence:[],risks:[],requiredConsultantIds:[],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:[]},
    {id:'FAMILY-001',title:'Let families book linked appointments',status:'Backlog',priority:'P2',owner:'Sarah Morgan',goal:'RESCHEDULE',dependencies:[],objective:'Clarify how one person could book for several family members',scope:[],nonGoals:[],affectedSystems:[],acceptanceCriteria:[],requiredVerification:[],expectedEvidence:[],risks:[],requiredConsultantIds:['product-designer'],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:['Whether each patient needs a separate account']},
    {id:'RESCHEDULE-001',title:'Define the online rescheduling journey',status:'Backlog',priority:'P2',owner:'Noor Ahmed',goal:'RESCHEDULE',dependencies:[],objective:'Define how patients change an appointment without calling',scope:['Rescheduling journey definition'],nonGoals:['Recurring appointments'],affectedSystems:['Booking web app'],acceptanceCriteria:['The end-to-end journey and edge cases are explicit'],requiredVerification:['Product design review'],expectedEvidence:['Approved PRD'],risks:['Clinic rules differ by practitioner'],requiredConsultantIds:['product-designer'],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:['How late a patient may reschedule']},
    {id:'REMIND-001',title:'Send an appointment reminder',status:'Ready',priority:'P2',owner:'Leo Park',goal:'MEASURE',dependencies:['BOOK-104'],objective:'Reduce missed appointments during the pilot',scope:['One reminder before the appointment'],nonGoals:['Reminder preferences'],affectedSystems:['Email'],acceptanceCriteria:['Pilot patients receive the correct reminder'],requiredVerification:['Email preview and delivery test'],expectedEvidence:['Approved preview and passing delivery test'],risks:['Duplicate reminders'],requiredConsultantIds:[],assurance:{testRigor:'Lean',humanReviewStages:[],overrideReason:'User approved focused delivery proof for the pilot'},blockers:[],openDecisions:[]},
    {id:'BOOK-108',title:'Improve the mobile availability picker',status:'In Progress',priority:'P1',owner:'Maya Chen',goal:'BETA-LAUNCH',dependencies:['BOOK-101'],objective:'Make available times easier to scan on small screens',scope:['Mobile availability picker'],nonGoals:['Calendar redesign'],affectedSystems:['Booking web app'],acceptanceCriteria:['Patients can identify and select a time at the target mobile viewport'],requiredVerification:['Mobile interaction test'],expectedEvidence:['Passing viewport test'],risks:['Dense schedules may still require scrolling'],requiredConsultantIds:['product-designer'],assurance:{testRigor:'Lean',humanReviewStages:[],overrideReason:'User approved focused mobile interaction proof'},blockers:[],openDecisions:[]},
    {id:'CAL-001',title:'Sync practitioner calendar changes',status:'Blocked',priority:'P1',owner:'Leo Park',goal:'BETA-LAUNCH',dependencies:['BOOK-101'],objective:'Keep online availability aligned with the clinic calendar',scope:['Calendar change synchronization'],nonGoals:['Calendar migration'],affectedSystems:['Booking API','Clinic calendar'],acceptanceCriteria:['Changed clinic availability appears online without double booking'],requiredVerification:['Synchronization and conflict tests'],expectedEvidence:['Passing integration tests'],risks:['Clinic calendar access is not yet approved'],requiredConsultantIds:[],assurance:{testRigor:'Thorough',humanReviewStages:[],overrideReason:'User requested broader synchronization failure coverage'},blockers:['Waiting for clinic calendar API access'],openDecisions:[]},
    {id:'REPORT-001',title:'Connect booking events to pilot reporting',status:'In Progress',priority:'P1',owner:'Maya Chen',goal:'MEASURE',dependencies:['BOOK-101','BOOK-103','BOOK-104'],objective:'Combine booking, payment, and confirmation events into the pilot report',scope:['Pilot event integration'],nonGoals:['Long-term analytics warehouse'],affectedSystems:['Booking web app','Payments','Email','Pilot reporting'],acceptanceCriteria:['One booking is represented once across the complete event chain'],requiredVerification:['Integrated event replay'],expectedEvidence:['Passing replay report'],risks:['Duplicate events'],requiredConsultantIds:[],assurance:{testRigor:'Thorough',humanReviewStages:[],overrideReason:'User requested complete event-chain regression evidence'},blockers:[],openDecisions:[]},
    {id:'ACCOUNT-001',title:'Require an account before booking',status:'Cancelled',priority:'P4',owner:'Sarah Morgan',goal:'DISCOVERY',dependencies:[],objective:'Evaluate account creation before appointment selection',scope:['Account-first concept'],nonGoals:['Account implementation'],affectedSystems:['Booking web app'],acceptanceCriteria:['The concept is compared with guest booking'],requiredVerification:['Journey comparison'],expectedEvidence:['Recorded decision'],risks:['Account creation adds avoidable friction'],requiredConsultantIds:['product-designer'],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:[]},
    {id:'BOOK-101',title:'Choose a practitioner and time',status:'Done',priority:'P1',owner:'Maya Chen',goal:'BETA-LAUNCH',dependencies:[],objective:'Show real availability and reserve the selected slot',scope:['Availability and slot selection'],nonGoals:['Recurring appointments'],affectedSystems:['Booking web app'],acceptanceCriteria:['A patient can reserve an available slot'],requiredVerification:['Booking flow test'],expectedEvidence:['Passing test'],risks:[],requiredConsultantIds:[],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:[]},
    {id:'BOOK-102',title:'Collect patient details',status:'Done',priority:'P1',owner:'Maya Chen',goal:'BETA-LAUNCH',dependencies:['BOOK-101'],objective:'Collect only the information required by the clinic',scope:['Patient details form'],nonGoals:['Full patient account'],affectedSystems:['Booking web app'],acceptanceCriteria:['Required details are saved'],requiredVerification:['Form test'],expectedEvidence:['Passing test'],risks:[],requiredConsultantIds:[],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:[]},
    {id:'BOOK-103',title:'Take card payment',status:'Done',priority:'P1',owner:'Leo Park',goal:'BETA-LAUNCH',dependencies:['BOOK-102'],objective:'Collect payment before confirming the appointment',scope:['Card payment'],nonGoals:['Refunds'],affectedSystems:['Payments'],acceptanceCriteria:['Successful payments confirm the booking'],requiredVerification:['Payment test'],expectedEvidence:['Passing test'],risks:['Payment provider failure'],requiredConsultantIds:[],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:[]},
    {id:'BOOK-104',title:'Send booking confirmation',status:'Done',priority:'P1',owner:'Noor Ahmed',goal:'BETA-LAUNCH',dependencies:['BOOK-103'],objective:'Send the patient the appointment details immediately',scope:['Confirmation email'],nonGoals:['Reminder sequence'],affectedSystems:['Email'],acceptanceCriteria:['The patient receives the correct appointment details'],requiredVerification:['Email preview'],expectedEvidence:['Approved preview'],risks:[],requiredConsultantIds:[],assurance:{testRigor:'Standard',humanReviewStages:[],overrideReason:''},blockers:[],openDecisions:[]},
    {id:'BOOK-105',title:'Handle failed payments',status:'In Progress',priority:'P1',owner:'Leo Park',goal:'BETA-LAUNCH',dependencies:['BOOK-103'],objective:'Let patients safely retry without losing their chosen slot',scope:['Failed and cancelled payment states'],nonGoals:['Alternative payment methods'],affectedSystems:['Payments','Booking web app'],acceptanceCriteria:['A failed payment can be retried safely'],requiredVerification:['Failure-path tests'],expectedEvidence:['Passing tests'],risks:['Duplicate bookings'],requiredConsultantIds:[],assurance:{testRigor:'Thorough',humanReviewStages:[],overrideReason:'User requested broader payment failure evidence'},blockers:[],openDecisions:[]},
    {id:'BOOK-106',title:'Test the complete booking journey',status:'In Progress',priority:'P1',owner:'Maya Chen',goal:'BETA-LAUNCH',dependencies:['BOOK-101','BOOK-102','BOOK-103','BOOK-104'],objective:'Test the full journey on mobile and desktop',scope:['End-to-end beta flow'],nonGoals:['Load testing'],affectedSystems:['Booking web app','Payments','Email'],acceptanceCriteria:['A patient can complete the flow without staff help'],requiredVerification:['Mobile and desktop journey'],expectedEvidence:['Test report'],risks:['Browser-specific failures'],requiredConsultantIds:[],assurance:{testRigor:'Thorough',humanReviewStages:[],overrideReason:'User requested full end-to-end release evidence'},blockers:[],openDecisions:[]},
    {id:'BOOK-107',title:'Approve the beta release',status:'In Review',priority:'P1',owner:'Sarah Morgan',goal:'BETA-LAUNCH',dependencies:['BOOK-105','BOOK-106'],objective:'Confirm that the beta is safe to open to pilot patients',scope:['Release review'],nonGoals:['Public launch'],affectedSystems:['Pilot release'],acceptanceCriteria:['Clinic owner explicitly approves the beta'],requiredVerification:['Human review'],expectedEvidence:['Recorded approval'],risks:['Launching before failure paths are proven'],requiredConsultantIds:[],assurance:{testRigor:'Standard',humanReviewStages:['Release'],overrideReason:'User requires explicit clinic-owner release approval'},blockers:[],openDecisions:[]}
  ]},
  ownership:{ownership:[
    {ticket:'BOOK-105',owner:'Leo Park',scopes:['failed payment states'],status:'Building',returnDestination:'Operations'},
    {ticket:'BOOK-106',owner:'Maya Chen',scopes:['mobile and desktop journey testing'],status:'Verifying',returnDestination:'Operations'}
  ]},
  reviews:{reviews:[{id:'BOOK-107-approval',ticket:'BOOK-107',stage:'Release',status:'Pending',path:'docs/review-packets/README.md',reviewer:'Sarah Morgan'}]},
  workforceProfiles:{
    'Maya Chen':{name:'Maya Chen',category:'Contractor',title:'Product Engineer'},
    'Leo Park':{name:'Leo Park',category:'Contractor',title:'Payments Engineer'},
    'Noor Ahmed':{name:'Noor Ahmed',category:'Consultant',title:'Product Designer'},
    'Sarah Morgan':{name:'Sarah Morgan',category:'Management',title:'Product Manager'}
  }
};
const s=previewMode?mock:canonical;
const e=x=>String(x??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
const values=x=>Array.isArray(x)&&x.length?x.join(' · '):'None';
const pathLink=(path,label='Open record')=>path?`<a href="../${e(path)}">${e(label)}</a>`:'';
const pathLinks=(paths,label)=>paths?.length?paths.map((path,index)=>pathLink(path,paths.length===1?label:`${label} ${index+1}`)).join(' · '):'None';
const p=s.project.project,b=s.project.baton,g=s.goals.goals,t=s.tickets.tickets,o=s.ownership.ownership,r=s.reviews.reviews,team=s.team||canonical.team;
const priority={P0:0,P1:1,P2:2,P3:3,P4:4},goalMap=Object.fromEntries(g.map(x=>[x.id,x])),ticketMap=Object.fromEntries(t.map(x=>[x.id,x]));
const current=goalMap[p.currentGoal]||null,history=g.filter(x=>x.status==='Done').sort((a,b)=>String(a.completedAt).localeCompare(String(b.completedAt))),pipeline=g.filter(x=>x.id!==p.currentGoal&&x.status!=='Done').sort((a,b)=>(priority[a.priority]-priority[b.priority])||g.indexOf(a)-g.indexOf(b));
const currentTickets=current?t.filter(x=>x.goal===current.id):[],currentTicketIds=new Set(currentTickets.map(x=>x.id)),currentOwnership=o.filter(x=>currentTicketIds.has(x.ticket)),currentReviews=r.filter(x=>currentTicketIds.has(x.ticket));
const terminal=new Set(['Done','Cancelled']),doneTickets=currentTickets.filter(x=>terminal.has(x.status)),remainingTickets=currentTickets.filter(x=>!terminal.has(x.status)),progress=currentTickets.length?Math.round(doneTickets.length/currentTickets.length*100):0;
const simpleStatus=status=>status;
const statusDescriptions={Backlog:'The work is not ready to start yet.',Ready:'The work is defined, approved, and available to start.','In Progress':'The team is actively delivering or validating the work.',Blocked:'A named dependency or decision prevents progress.','In Review':'The completed work is waiting for acceptance.',Done:'The work and required evidence have been accepted.',Cancelled:'The work was intentionally stopped and will not continue.'};
const statusTone=status=>status==='Done'?'success':status==='Cancelled'?'abandoned':status==='Blocked'?'danger':status==='Ready'?'ready':status==='In Review'?'review':status==='In Progress'?'active':'neutral';
const statusPill=status=>{const label=simpleStatus(status),description=statusDescriptions[status]||`${label} status`;return `<span class="status-pill status-${statusTone(status)}" data-tooltip="${e(`${label} · ${description}`)}" data-tooltip-static="true" aria-label="${e(`${label}: ${description}`)}">${e(label)}</span>`};
const assuranceFor=ticket=>ticket.assurance||{testRigor:p.assuranceDefaults?.testRigor||'Standard',humanReviewStages:p.assuranceDefaults?.humanReviewStages||[],overrideReason:''};
const humanReviewSummary=ticket=>{const stages=assuranceFor(ticket).humanReviewStages||[];return stages.length?stages.map(stage=>{const review=r.find(item=>item.ticket===ticket.id&&item.stage===stage);return `${stage}: ${review?.status||'Required'}`}).join(' · '):'None'};
const assuranceSummary=ticket=>{const assurance=assuranceFor(ticket),stages=assurance.humanReviewStages||[];return `${assurance.testRigor} · Human ${stages.length?stages.join('/'):'none'}`};
const initials=name=>String(name||'?').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
document.getElementById('project-name').textContent=p.name;
document.getElementById('project-summary').textContent=p.outcome||'Define the result this project should create.';
document.getElementById('project-meta').innerHTML=`<span>${e(p.phase||'No phase set')}</span><span>Default assurance: ${e(p.assuranceDefaults?.testRigor||'Standard')} · Human ${e(p.assuranceDefaults?.humanReviewStages?.length?p.assuranceDefaults.humanReviewStages.join('/'):'none')}</span><span>Updated ${e(p.lastVerified||'not yet')}</span>`;
const goalBriefFor=goal=>goal?.context||goal?.objective||goal?.resultSummary||'No goal brief recorded.';
const ticketRow=x=>`<button type="button" class="ticket-row" data-ticket-id="${e(x.id)}" aria-label="Open ${e(x.id)} details"><div class="ticket-copy"><small>${e(x.id)} · ${e(assuranceSummary(x))}</small><strong>${e(x.title)}</strong></div><span class="ticket-owner">${e(x.owner)}</span>${statusPill(x.status)}</button>`;
const ticketsForGoal=goal=>t.filter(x=>x.goal===goal.id);
const ticketListFor=goal=>{const items=ticketsForGoal(goal);return items.length?`<div class="ticket-list">${items.map(ticketRow).join('')}</div>`:'<p class="empty-note">No tasks have been created for this goal yet.</p>'};
const DAY=86400000,DAY_WIDTH=24;
const utcDay=date=>new Date(Date.UTC(date.getFullYear(),date.getMonth(),date.getDate()));
const parseDay=value=>value?new Date(`${value}T00:00:00Z`):null;
const addDays=(date,days)=>new Date(date.getTime()+days*DAY);
const dayDiff=(later,earlier)=>Math.round((later-earlier)/DAY);
const today=utcDay(new Date()),scheduledDates=g.flatMap(goal=>[parseDay(goal.plannedStart),parseDay(goal.plannedEnd)].filter(Boolean));
const rangeStart=new Date(Math.min(addDays(today,-28).getTime(),...scheduledDates.map(date=>addDays(date,-7).getTime()))),rangeEnd=new Date(Math.max(addDays(today,42).getTime(),...scheduledDates.map(date=>addDays(date,7).getTime()))),dayCount=dayDiff(rangeEnd,rangeStart)+1,timelineWidth=dayCount*DAY_WIDTH,todayLeft=dayDiff(today,rangeStart)*DAY_WIDTH;
const dateLabel=date=>new Intl.DateTimeFormat(undefined,{day:'numeric',month:'short'}).format(date);
const fullDate=date=>new Intl.DateTimeFormat(undefined,{day:'numeric',month:'short',year:'numeric'}).format(date);
const goalProgress=goal=>{const items=ticketsForGoal(goal),done=items.filter(x=>terminal.has(x.status));return {items,done,percent:items.length?Math.round(done.length/items.length*100):0}};
const scheduleFor=(goal,index)=>{const plannedStart=parseDay(goal.plannedStart),plannedEnd=parseDay(goal.plannedEnd),unscheduled=!plannedStart||!plannedEnd,start=plannedStart||addDays(today,index*7),end=plannedEnd||addDays(start,6);return {start,end,unscheduled,left:Math.max(0,dayDiff(start,rangeStart)*DAY_WIDTH),width:Math.max(72,(dayDiff(end,start)+1)*DAY_WIDTH)}};
const laneFor=goal=>goal.blockers?.length?'blocked':goal.status==='Done'?'done':goal.id===p.currentGoal?'current':'upcoming';
const orderedGoals=[...g].sort((a,b)=>String(a.plannedStart||'9999').localeCompare(String(b.plannedStart||'9999'))||(priority[a.priority]-priority[b.priority]));
const ticks=Array.from({length:Math.ceil(dayCount/7)},(_,index)=>{const date=addDays(rangeStart,index*7);return `<span class="date-tick" style="--left:${index*7*DAY_WIDTH}px">${e(dateLabel(date))}</span>`}).join('');
const ganttRows=orderedGoals.map((goal,index)=>{const schedule=scheduleFor(goal,index),lane=laneFor(goal),stats=goalProgress(goal),barLabel=schedule.unscheduled?'Dates needed':goal.title,scheduleLabel=schedule.unscheduled?'Dates needed':`${fullDate(schedule.start)} – ${fullDate(schedule.end)}`,tooltip=`${goal.title} · ${scheduleLabel}`;return `<div class="gantt-label"><button type="button" class="gantt-goal-button" data-goal="${e(goal.id)}" aria-pressed="false"><strong>${e(goal.title)}</strong>${statusPill(goal.status)}<small>${e(goal.context||goal.objective)}</small></button></div><div class="gantt-track" style="--week-width:${7*DAY_WIDTH}px"><span class="today-line" style="--left:${todayLeft}px" aria-hidden="true"></span><button type="button" class="gantt-bar gantt-bar-${lane}${schedule.unscheduled?' gantt-bar-unscheduled':''}" style="--left:${schedule.left}px;--width:${schedule.width}px" data-goal="${e(goal.id)}" data-tooltip="${e(tooltip)}" data-tooltip-static="true" aria-label="${e(tooltip)}" aria-pressed="false">${e(barLabel)}${lane==='current'&&stats.items.length?` · ${stats.percent}%`:''}</button></div>`}).join('');
const gantt=orderedGoals.length?`<div class="gantt-viewport" id="gantt-viewport"><div class="gantt-grid" style="--timeline-width:${timelineWidth}px"><div class="gantt-corner">Goals and PRD extracts</div><div class="gantt-dates"><span class="today-head" style="--left:${todayLeft}px">Today</span>${ticks}</div>${ganttRows}</div></div>`:`<div class="empty-goal"><h2>No goals yet</h2><p>Choose the first meaningful project result before assigning work.</p><a class="preview-link" href="?mock=1">See an example project</a></div>`;
const ticketRowsMarkup=items=>items.length?items.map(ticket=>`<button type="button" class="ticket-table-row" data-ticket-id="${e(ticket.id)}" data-ticket-goal="${e(ticket.goal||'')}"><span class="ticket-name"><small>${e(ticket.id)} · ${e(assuranceSummary(ticket))}</small><strong>${e(ticket.title)}</strong></span><span>${e(goalMap[ticket.goal]?.title||ticket.goal||'No goal')}</span><span>${e(ticket.owner)}</span>${statusPill(ticket.status)}</button>`).join(''):'<p class="ticket-empty">No tasks match this search.</p>';
const ticketStatusOrder=['Backlog','Ready','In Progress','Blocked','In Review','Done','Cancelled'],ticketStatusLabels=[...new Set(t.map(ticket=>simpleStatus(ticket.status)))].sort((a,b)=>{const ai=ticketStatusOrder.indexOf(a),bi=ticketStatusOrder.indexOf(b);return (ai<0?99:ai)-(bi<0?99:bi)||a.localeCompare(b)}),ticketStatusOptions=ticketStatusLabels.map(status=>`<button type="button" class="ticket-filter-option" role="option" aria-selected="false" data-status="${e(status)}">${statusPill(status)}</button>`).join('');
const activeConsultants=(team?.consultants||[]).filter(item=>item.status==='active');
const identityKey=value=>String(value||'').trim().toLowerCase(),titleCase=value=>String(value||'').split(/[-_\s]+/).filter(Boolean).map(word=>word[0].toUpperCase()+word.slice(1)).join(' ');
function workforceProfileFor(owner){const explicit=s.workforceProfiles?.[owner];if(explicit)return {owner,...explicit};const key=identityKey(owner),management=team?.management,operations=team?.operations;if(management&&[management.commonName,management.title,'management'].some(value=>identityKey(value)===key))return {owner,name:management.commonName||'Management',category:'Management',title:management.title};if(operations&&[operations.commonName,operations.title,'operations'].some(value=>identityKey(value)===key))return {owner,name:operations.commonName||'Operations',category:'Operations',title:operations.title};const consultant=activeConsultants.find(item=>[item.id,item.title].some(value=>identityKey(value)===key));if(consultant)return {owner,name:consultant.title,category:'Consultant',title:consultant.domain||consultant.headline};const contractor=(team?.contractorBench||[]).find(item=>identityKey(item.id)===key);if(contractor)return {owner,name:titleCase(contractor.id),category:'Contractor',title:contractor.headline};const dispatched=o.some(item=>identityKey(item.owner)===key);return {owner,name:owner,category:dispatched?'Contractor':'Project team',title:dispatched?'Assigned specialist':'Assigned contributor'}}
const previewBanner=previewMode?'<div class="preview-bar"><p><strong>Example project</strong> · Illustrative data only</p><a href="./index.html">Return to your project</a></div>':'';
q.innerHTML=`${previewBanner}<section aria-labelledby="plan-title"><div class="section-heading"><div><h2 id="plan-title">Timeline</h2><p>Goals are scheduled around today. Scroll to explore the full plan.</p></div><div class="gantt-toolbar"><span class="count">${e(dateLabel(rangeStart))} – ${e(dateLabel(rangeEnd))}</span><button type="button" class="notion-button" id="today-button">Today</button></div></div>${gantt}</section><section aria-labelledby="team-title"><div class="section-heading"><h2 id="team-title">People</h2></div><div id="org-chart-root"></div></section><section class="ticket-section" aria-labelledby="tickets-title"><div class="section-heading"><div><h2 id="tickets-title">Tasks</h2><p>Every task across the project.</p></div></div><div class="ticket-tools"><div class="ticket-control-group"><div class="ticket-search"><label for="ticket-search">Search tasks</label><input id="ticket-search" type="search" placeholder="Search tasks"></div><div class="ticket-filter"><label for="ticket-status-filter">Filter tasks by status</label><select id="ticket-status-filter"><option value="">All statuses</option>${ticketStatusOptions}</select></div></div><span class="count" id="ticket-count" aria-live="polite"></span></div><div class="ticket-table"><div class="ticket-table-head"><span>Task</span><span>Goal</span><span>Owner</span><span>Status</span></div><div id="ticket-rows">${ticketRowsMarkup(t)}</div></div></section><div class="sheet-backdrop" id="sheet-backdrop"></div><aside class="side-sheet" id="goal-sheet" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="sheet-title"><div class="sheet-top"><span>Goal details</span><button type="button" class="sheet-close" id="sheet-close" aria-label="Close goal details">×</button></div><div class="sheet-content" id="sheet-content"></div></aside>`;
const ticketSearchHost=document.querySelector('.ticket-search'),ticketSearchInput=ticketSearchHost.querySelector('input');ticketSearchInput.type='text';ticketSearchInput.setAttribute('role','searchbox');ticketSearchHost.insertAdjacentHTML('beforeend','<button type="button" class="ticket-search-clear" id="ticket-search-clear" aria-label="Clear task search" hidden>×</button>');
const ticketFilterHost=document.querySelector('.ticket-filter');ticketFilterHost.innerHTML=`<span class="ticket-filter-label" id="ticket-status-label">Filter tasks by status</span><button type="button" class="ticket-filter-trigger" id="ticket-status-filter" aria-haspopup="listbox" aria-expanded="false" aria-labelledby="ticket-status-label ticket-status-value" data-value=""><span class="ticket-filter-value" id="ticket-status-value">All statuses</span><span class="ticket-filter-chevron" aria-hidden="true">▾</span></button><div class="ticket-filter-menu" id="ticket-status-menu" role="listbox" aria-labelledby="ticket-status-label" hidden><button type="button" class="ticket-filter-option ticket-filter-option-all" role="option" aria-selected="true" data-status=""><span>All statuses</span></button>${ticketStatusOptions}</div>`;
const workforceByOwner=new Map();t.forEach(ticket=>{const owner=String(ticket.owner||'').trim();if(!owner)return;const stats=workforceByOwner.get(owner)||{...workforceProfileFor(owner),total:0,done:0};stats.total+=1;if(ticket.status==='Done')stats.done+=1;workforceByOwner.set(owner,stats)});
const assignedPeople=[...workforceByOwner.values()].map(person=>({...person,rate:person.total?Math.round(person.done/person.total*100):0})).sort((a,b)=>b.rate-a.rate||b.done-a.done||b.total-a.total||a.name.localeCompare(b.name)),configuredPeople=[team?.management&&{owner:team.management.commonName||'Management',name:team.management.commonName||'Management',category:'Management',title:team.management.title,total:0,done:0,rate:0},team?.operations&&{owner:team.operations.commonName||'Operations',name:team.operations.commonName||'Operations',category:'Operations',title:team.operations.title,total:0,done:0,rate:0},...activeConsultants.map(item=>({owner:item.id,name:team?.commonNames?.consultants||'Consultant',category:'Consultant',title:item.title,total:0,done:0,rate:0}))].filter(Boolean),assignedRoleKeys=new Set(assignedPeople.map(person=>`${identityKey(person.category)}|${identityKey(person.title)}`)),unassignedConfiguredPeople=configuredPeople.filter(person=>!assignedRoleKeys.has(`${identityKey(person.category)}|${identityKey(person.title)}`));const workforceOrder={Management:0,Operations:1,Consultant:2,Contractor:3,'Project team':4},workforcePeople=[...unassignedConfiguredPeople,...assignedPeople].sort((a,b)=>(workforceOrder[a.category]??9)-(workforceOrder[b.category]??9)||a.name.localeCompare(b.name)),workforceTotal=assignedPeople.reduce((sum,person)=>sum+person.total,0),workforceColors=['#fef265','#82a7d6','#ff9f43','#447ab9','#fce8a4','#c9bd79'];let workforceCursor=0;
const orgPerson=person=>`<li><article class="org-person"><small>${e(person.category)}</small><strong>${e(person.name)}</strong><span>${e(person.title)}</span></article></li>`,orgGroups=[{label:'Management',people:workforcePeople.filter(person=>person.category==='Management')},{label:'Operations',people:workforcePeople.filter(person=>person.category==='Operations')},{label:'Specialists',people:workforcePeople.filter(person=>!['Management','Operations'].includes(person.category))}].filter(group=>group.people.length),orgChart=orgGroups.map((group,index)=>`${index?'<span class="org-connector" aria-hidden="true"></span>':''}<ol class="org-level" aria-label="${e(group.label)}">${group.people.map(orgPerson).join('')}</ol>`).join('');document.getElementById('org-chart-root').innerHTML=`<div class="org-chart" aria-label="Team organization">${orgChart||'<p class="empty-note">No people configured.</p>'}</div>`;
const workforceIdentity=person=>`${person.category} · ${person.title}`,workforceAria=person=>`${person.name}, ${person.category}, ${person.title}`,workforceSlices=assignedPeople.map((person,index)=>{const start=workforceCursor,end=workforceCursor+(person.total/workforceTotal*100),slice={person,start,end,color:workforceColors[index%workforceColors.length],percent:Math.round(person.total/workforceTotal*100)};workforceCursor=end;return slice}),workforceSegments=workforceSlices.map(slice=>`${slice.color} ${slice.start.toFixed(2)}% ${slice.end.toFixed(2)}%`).join(','),workforceSliceLabel=slice=>`${slice.person.name} · ${workforceIdentity(slice.person)} · ${slice.person.total} assignment${slice.person.total===1?'':'s'} · ${slice.percent}%`,workforceDistributionLabel=workforceSlices.map(workforceSliceLabel).join(' · '),workforceBest=assignedPeople[0],workforceWorst=assignedPeople.at(-1),workforceBars=workforcePeople.map(person=>`<li class="workforce-row"><div class="workforce-person"><strong>${e(person.name)}</strong><span>${e(workforceIdentity(person))}</span><small>${person.total?`${person.done} of ${person.total} completed`:'No assigned work'}</small></div><div class="workforce-bar" role="progressbar" aria-label="${e(workforceAria(person))} completion" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${person.rate}"><i style="--value:${person.rate}%"></i></div><b>${person.total?`${person.rate}%`:'—'}</b></li>`).join(''),workforceLegend=assignedPeople.map((person,index)=>`<li><div class="workforce-legend-entry"><i style="--swatch:${workforceColors[index%workforceColors.length]}"></i><span>${e(person.name)}<small>${e(workforceIdentity(person))}</small></span><strong>${person.total}</strong></div></li>`).join('');
const workforceSection=document.createElement('section');workforceSection.className='company-workforce';workforceSection.setAttribute('aria-labelledby','workforce-title');workforceSection.innerHTML=`<div class="company-subheading"><div><h2 id="workforce-title">Workload</h2><p>Assignments and completion across the team.</p></div><span class="count">${workforcePeople.length} people · ${workforceTotal} assignments</span></div>${workforceBest?`<div class="workforce-summary"><article class="workforce-callout"><small>Highest completion</small><strong>${e(workforceBest.name)}</strong><em>${e(workforceIdentity(workforceBest))}</em><span>${workforceBest.rate}% · ${workforceBest.done}/${workforceBest.total} completed</span></article>${assignedPeople.length>1?`<article class="workforce-callout workforce-callout-attention"><small>Lowest completion</small><strong>${e(workforceWorst.name)}</strong><em>${e(workforceIdentity(workforceWorst))}</em><span>${workforceWorst.rate}% · ${workforceWorst.done}/${workforceWorst.total} completed</span></article>`:''}</div>`:''}<div class="workforce-layout"><article class="workforce-panel"><h3>Completion by person</h3><ol class="workforce-bars">${workforceBars}</ol></article><article class="workforce-panel workforce-distribution"><h3>Assignment share</h3>${workforceTotal?`<div class="workforce-donut" style="--workforce-gradient:conic-gradient(${workforceSegments})" role="img" tabindex="0" data-workload-chart data-tooltip="${e(workforceDistributionLabel)}" data-tooltip-static="true" aria-label="${e(`Workload distribution across ${assignedPeople.length} assigned contributors. ${workforceDistributionLabel}`)}"><div><strong>${workforceTotal}</strong><span>assigned</span></div></div><ul class="workforce-legend">${workforceLegend}</ul>`:'<p class="empty-note">No work is assigned yet.</p>'}</article></div><p class="workforce-note">Completion is shown only for assigned work and does not normalize for workload difficulty, role, or time assigned.</p>`;
const planSection=document.getElementById('plan-title').closest('section'),teamSection=document.getElementById('team-title').closest('section'),ticketSection=document.querySelector('.ticket-section');teamSection.classList.add('company-surface');const projectView=document.createElement('div');projectView.id='project-view';projectView.className='dashboard-view';projectView.dataset.dashboardView='project';const companyView=document.createElement('div');companyView.id='company-view';companyView.className='dashboard-view';companyView.dataset.dashboardView='company';companyView.hidden=true;q.insertBefore(projectView,planSection);q.insertBefore(companyView,planSection);projectView.append(planSection,ticketSection);companyView.append(teamSection,workforceSection);
const hud=document.createElement('footer');hud.className='pip-hud';hud.setAttribute('aria-label','Project status summary');hud.innerHTML=`<div class="hud-cell hud-phase"><span>Phase</span><strong>${e(p.phase||'Not set')}</strong></div><div class="hud-cell hud-goal"><span>Active goal</span><strong>${e(current?.title||'No active goal')}</strong><div class="hud-progress-track" role="progressbar" aria-label="Active goal progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><i style="--value:${progress}%"></i></div></div><div class="hud-cell hud-work"><span>Tasks</span><strong>${remainingTickets.length} open</strong></div><div class="hud-cell hud-review"><span>Review</span><strong>${currentReviews.filter(item=>item.status==='Pending').length} pending</strong></div>`;document.body.appendChild(hud);
const pipTooltip=document.createElement('div');pipTooltip.id='pip-tooltip';pipTooltip.className='pip-tooltip';pipTooltip.setAttribute('role','tooltip');pipTooltip.hidden=true;document.body.appendChild(pipTooltip);let activeTooltipTarget=null;
const navLinks=[...document.querySelectorAll('[data-dashboard-tab]')],dashboardViews=[projectView,companyView],legacyTeamHashes=new Set(['#team','#roster','#team-title','#workforce-title']),viewParam=()=>new URLSearchParams(location.search).get('view'),validViewParam=()=>['mission','team'].includes(viewParam()),viewForLocation=()=>viewParam()==='team'||(!validViewParam()&&legacyTeamHashes.has(location.hash))?'company':'project',viewName=name=>name==='company'?'team':'mission';function dashboardUrl(name){const url=new URL(location.href);url.searchParams.set('view',viewName(name));url.hash='';return url}function syncDashboardLinks(){navLinks.forEach(link=>{link.href=dashboardUrl(link.dataset.dashboardTab)})}function updateDashboardUrl(name,replaceUrl){const url=dashboardUrl(name);history[replaceUrl?'replaceState':'pushState'](null,'',url);return false}function setDashboardView(name,updateUrl=false,replaceUrl=false){dashboardViews.forEach(view=>view.hidden=view.dataset.dashboardView!==name);navLinks.forEach(link=>{const selected=link.dataset.dashboardTab===name;link.classList.toggle('is-active',selected);link.setAttribute('aria-selected',String(selected))});hud.hidden=name==='company';if(updateUrl&&updateDashboardUrl(name,replaceUrl))return;syncDashboardLinks();requestAnimationFrame(()=>refreshOverflowTooltips())}navLinks.forEach(link=>link.addEventListener('click',event=>{if(location.protocol==='file:')return;event.preventDefault();setDashboardView(link.dataset.dashboardTab,true)}));window.addEventListener('popstate',()=>setDashboardView(viewForLocation()));const initialView=viewForLocation(),normalizeViewUrl=!validViewParam()||Boolean(location.hash);setDashboardView(initialView,location.protocol!=='file:'&&normalizeViewUrl,true);
navLinks.forEach((link,index)=>link.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();const offset=event.key==='ArrowRight'?1:-1,target=navLinks[(index+offset+navLinks.length)%navLinks.length];if(location.protocol==='file:'){location.assign(target.href);return}setDashboardView(target.dataset.dashboardTab,true);target.focus()}));
const sheet=document.getElementById('goal-sheet'),backdrop=document.getElementById('sheet-backdrop'),sheetContent=document.getElementById('sheet-content'),sheetKicker=document.querySelector('.sheet-top span'),closeButton=document.getElementById('sheet-close'),viewport=document.getElementById('gantt-viewport'),ticketSearch=document.getElementById('ticket-search'),ticketSearchClear=document.getElementById('ticket-search-clear'),ticketStatusFilter=document.getElementById('ticket-status-filter'),ticketStatusMenu=document.getElementById('ticket-status-menu'),ticketStatusValue=document.getElementById('ticket-status-value'),ticketCount=document.getElementById('ticket-count'),ticketRowsContainer=document.getElementById('ticket-rows');let lastFocused=null;sheet.inert=true;
const overflowTooltipSelector='.gantt-goal-button strong,.gantt-goal-button small,.ticket-name strong,.ticket-name small,.ticket-table-row>span,.status-pill,.ticket-copy strong,.ticket-owner,.workforce-person strong,.workforce-legend span,.hud-cell strong,.team-card strong,.team-card p,.sheet-property [data-sheet-goal]';
function positionPipTooltip(target,point){const anchor=target.getBoundingClientRect(),bubble=pipTooltip.getBoundingClientRect(),gap=9;let left=point?point.x+14:anchor.left+(anchor.width-bubble.width)/2,top=point?point.y+14:anchor.bottom+gap;left=Math.max(12,Math.min(left,innerWidth-bubble.width-12));if(top+bubble.height>innerHeight-12)top=Math.max(12,(point?.y??anchor.top)-bubble.height-gap);pipTooltip.style.left=`${Math.round(left)}px`;pipTooltip.style.top=`${Math.round(top)}px`;pipTooltip.style.visibility='visible'}
function showPipTooltip(target,point){const label=target?.dataset.tooltip;if(!label)return;if(activeTooltipTarget&&activeTooltipTarget!==target)activeTooltipTarget.removeAttribute('aria-describedby');activeTooltipTarget=target;pipTooltip.textContent=label;pipTooltip.style.visibility='hidden';pipTooltip.hidden=false;target.setAttribute('aria-describedby',pipTooltip.id);requestAnimationFrame(()=>positionPipTooltip(target,point))}
function hidePipTooltip(){if(activeTooltipTarget)activeTooltipTarget.removeAttribute('aria-describedby');activeTooltipTarget=null;pipTooltip.hidden=true;pipTooltip.style.visibility='hidden'}
const workloadChart=document.querySelector('[data-workload-chart]');function workloadSliceAt(event){if(!workloadChart)return null;const rect=workloadChart.getBoundingClientRect(),x=event.clientX-(rect.left+rect.width/2),y=event.clientY-(rect.top+rect.height/2),radius=Math.min(rect.width,rect.height)/2,distance=Math.hypot(x,y);if(distance<radius*.5||distance>radius)return null;const percent=((Math.atan2(y,x)*180/Math.PI+450)%360)/3.6;return workforceSlices.find(slice=>percent>=slice.start&&(percent<slice.end||slice.end>=100))}workloadChart?.addEventListener('pointermove',event=>{const slice=workloadSliceAt(event);if(!slice){if(activeTooltipTarget===workloadChart)hidePipTooltip();return}workloadChart.dataset.tooltip=workforceSliceLabel(slice);showPipTooltip(workloadChart,{x:event.clientX,y:event.clientY})});workloadChart?.addEventListener('pointerleave',()=>{workloadChart.dataset.tooltip=workforceDistributionLabel;if(activeTooltipTarget===workloadChart)hidePipTooltip()});workloadChart?.addEventListener('focus',()=>{workloadChart.dataset.tooltip=workforceDistributionLabel});
function refreshOverflowTooltips(root=document){root.querySelectorAll('[data-auto-tooltip]').forEach(host=>{delete host.dataset.tooltip;delete host.dataset.autoTooltip});const grouped=new Map();root.querySelectorAll(overflowTooltipSelector).forEach(element=>{const clipped=element.scrollWidth>element.clientWidth+1||element.scrollHeight>element.clientHeight+1;if(!clipped)return;const host=element.classList.contains('status-pill')?element:element.closest('button,a')||element;if(host.dataset.tooltipStatic)return;const labels=grouped.get(host)||[],label=element.textContent.trim();if(label&&!labels.includes(label))labels.push(label);grouped.set(host,labels)});grouped.forEach((labels,host)=>{host.dataset.tooltip=labels.join(' · ');host.dataset.autoTooltip='true'});if(activeTooltipTarget&&!activeTooltipTarget.dataset.tooltip)hidePipTooltip()}
const ticketFilterOptions=()=>[...ticketStatusMenu.querySelectorAll('[role="option"]')];
function setTicketFilterOpen(open,edge=0){ticketStatusMenu.hidden=!open;ticketStatusFilter.setAttribute('aria-expanded',String(open));if(!open)return;ticketFilterHost.classList.remove('opens-up');const menuGap=10,triggerRect=ticketStatusFilter.getBoundingClientRect(),footer=document.querySelector('.pip-hud:not([hidden])'),visibleBottom=footer?.getBoundingClientRect().top||innerHeight,availableBelow=Math.max(0,visibleBottom-triggerRect.bottom-menuGap),availableAbove=Math.max(0,triggerRect.top-menuGap),opensUp=availableAbove>availableBelow,available=opensUp?availableAbove:availableBelow;ticketFilterHost.classList.toggle('opens-up',opensUp);ticketStatusMenu.style.maxHeight=`${Math.max(96,Math.min(430,available))}px`;const options=ticketFilterOptions(),selected=options.find(option=>option.getAttribute('aria-selected')==='true'),target=edge<0?options.at(-1):edge>0?options[0]:selected||options[0];target?.focus()}
function setTicketFilterStatus(status,shouldRender=true){ticketStatusFilter.dataset.value=status;ticketStatusValue.innerHTML=status?statusPill(status):'All statuses';ticketFilterOptions().forEach(option=>option.setAttribute('aria-selected',String(option.dataset.status===status)));if(shouldRender)renderTicketSearch();refreshOverflowTooltips(ticketStatusFilter)}
function prepareSheet(){if(!sheet.classList.contains('is-open'))lastFocused=document.activeElement;sheet.inert=false}
function showTicket(ticket){if(!ticket)return;prepareSheet();openTicket(ticket)}
function syncGoalBrief(){const brief=sheetContent.querySelector('[data-goal-brief]');if(!brief)return;const text=brief.querySelector('[data-goal-brief-text]'),toggle=brief.querySelector('[data-goal-brief-toggle]');brief.classList.remove('is-expanded','is-overflowing');toggle.hidden=true;toggle.textContent='Show more';toggle.setAttribute('aria-expanded','false');requestAnimationFrame(()=>{const overflowing=text.scrollHeight>text.clientHeight+1;brief.classList.toggle('is-overflowing',overflowing);toggle.hidden=!overflowing})}
window.addEventListener('resize',syncGoalBrief);
sheetContent.addEventListener('click',event=>{const toggle=event.target.closest('[data-goal-brief-toggle]');if(!toggle)return;const brief=toggle.closest('[data-goal-brief]'),expanded=brief.classList.toggle('is-expanded');toggle.setAttribute('aria-expanded',String(expanded));toggle.textContent=expanded?'Show less':'Show more'});
sheetContent.addEventListener('click',event=>{const ticketControl=event.target.closest('[data-ticket-id]');if(ticketControl){showTicket(ticketMap[ticketControl.dataset.ticketId]);return}const goalControl=event.target.closest('[data-sheet-goal]');if(goalControl)showGoal(goalMap[goalControl.dataset.sheetGoal])});document.addEventListener('pointerover',event=>{const target=event.target.closest?.('[data-tooltip]');if(target)showPipTooltip(target)});document.addEventListener('pointerout',event=>{if(activeTooltipTarget&&!activeTooltipTarget.contains(event.relatedTarget))hidePipTooltip()});document.addEventListener('focusin',event=>{const target=event.target.closest?.('[data-tooltip]');if(target)showPipTooltip(target)});document.addEventListener('focusout',event=>{if(activeTooltipTarget&&!activeTooltipTarget.contains(event.relatedTarget))hidePipTooltip()});document.addEventListener('scroll',hidePipTooltip,true);new MutationObserver(()=>refreshOverflowTooltips(sheetContent)).observe(sheetContent,{childList:true,subtree:true});let tooltipFrame=0;window.addEventListener('resize',()=>{hidePipTooltip();cancelAnimationFrame(tooltipFrame);tooltipFrame=requestAnimationFrame(()=>refreshOverflowTooltips())});
function showGoal(goal){if(!goal)return;sheetKicker.textContent='Goal details';prepareSheet();openGoal(goal)}
const sheetList=(items,empty='Nothing recorded')=>items?.length?`<ul class="sheet-detail-list">${items.map(item=>`<li>${e(item)}</li>`).join('')}</ul>`:`<p class="sheet-empty">${e(empty)}</p>`;
const sheetSection=(title,items,empty)=>`<section class="sheet-section"><h3>${e(title)}</h3>${sheetList(items,empty)}</section>`;
function openTicket(ticket){const goal=goalMap[ticket.goal],profile=workforceProfileFor(ticket.owner),dependencies=(ticket.dependencies||[]).map(id=>ticketMap[id]).filter(Boolean),consultants=(ticket.requiredConsultantIds||[]).map(id=>(team?.consultants||[]).find(item=>item.id===id)).filter(Boolean),assurance=assuranceFor(ticket);sheetKicker.textContent='Task details';sheetContent.innerHTML=`${goal?`<div class="sheet-actions"><button type="button" class="sheet-back-button" data-sheet-goal="${e(goal.id)}" data-tooltip="${e(`Back to goal: ${goal.title}`)}" data-tooltip-static="true" aria-label="${e(`Back to goal: ${goal.title}`)}"></button></div>`:''}<p class="ticket-sheet-id">${e(ticket.id)} · ${e(ticket.priority||'No priority')}</p><div class="sheet-title-row"><h2 id="sheet-title">${e(ticket.title)}</h2>${statusPill(ticket.status)}</div><p class="sheet-objective">${e(ticket.objective||'No objective recorded.')}</p><dl class="sheet-properties"><div class="sheet-property"><dt>Owner</dt><dd>${e(profile.name)} · ${e(profile.category)} · ${e(profile.title)}</dd></div><div class="sheet-property"><dt>Goal</dt><dd>${goal?`<button type="button" class="sheet-record-button" data-sheet-goal="${e(goal.id)}">${e(goal.title)}</button>`:'No goal linked'}</dd></div><div class="sheet-property"><dt>Priority</dt><dd>${e(ticket.priority||'Not set')}</dd></div><div class="sheet-property"><dt>Test rigor</dt><dd>${e(assurance.testRigor)}</dd></div><div class="sheet-property"><dt>Human review</dt><dd>${e(humanReviewSummary(ticket))}</dd></div>${assurance.overrideReason?`<div class="sheet-property"><dt>Override</dt><dd>${e(assurance.overrideReason)}</dd></div>`:''}</dl>${sheetSection('Scope',ticket.scope,'No scope recorded')}${sheetSection('Acceptance criteria',ticket.acceptanceCriteria,'No acceptance criteria recorded')}${sheetSection('Required checks',ticket.requiredVerification,'No required checks recorded')}${ticket.nonGoals?.length?sheetSection('Not included',ticket.nonGoals):''}${dependencies.length?`<section class="sheet-section"><h3>Dependencies</h3><div class="sheet-record-list">${dependencies.map(item=>`<button type="button" class="sheet-record-button" data-ticket-id="${e(item.id)}">${e(item.id)} · ${e(item.title)}</button>`).join('')}</div></section>`:''}${consultants.length?sheetSection('Required consultants',consultants.map(item=>item.title)):''}${ticket.blockers?.length?sheetSection('Blockers',ticket.blockers):''}`;sheet.classList.add('is-open');backdrop.classList.add('is-open');sheet.setAttribute('aria-hidden','false');document.body.classList.add('sheet-open');q.querySelectorAll('[data-goal]').forEach(button=>button.setAttribute('aria-pressed','false'));closeButton.focus()}
function openGoal(goal){if(!goal)return;const stats=goalProgress(goal),scheduleStart=parseDay(goal.plannedStart),scheduleEnd=parseDay(goal.plannedEnd),goalOwnership=o.filter(item=>stats.items.some(ticket=>ticket.id===item.ticket)),people=goalOwnership.length?`<section class="sheet-section"><h3>Working now</h3>${goalOwnership.map(item=>{const ticket=ticketMap[item.ticket]||{};return `<div class="sheet-person"><span class="avatar">${e(initials(item.owner))}</span><div><strong>${e(item.owner)}</strong><span>${e(ticket.title||item.ticket)}</span></div></div>`}).join('')}</section>`:'',briefText=goalBriefFor(goal),result=goal.status==='Done'&&goal.resultSummary?`<p class="sheet-context">${e(goal.resultSummary)}</p>`:'';sheetContent.innerHTML=`<div class="sheet-title-row"><h2 id="sheet-title">${e(goal.title)}</h2>${statusPill(goal.status)}</div><p class="sheet-objective">${e(goal.objective)}</p>${result}<dl class="sheet-properties"><div class="sheet-property"><dt>Owner</dt><dd>${e(goal.owner)}</dd></div><div class="sheet-property"><dt>Schedule</dt><dd>${scheduleStart&&scheduleEnd?`${e(fullDate(scheduleStart))} – ${e(fullDate(scheduleEnd))}`:'Dates not set'}</dd></div><div class="sheet-property"><dt>Progress</dt><dd>${stats.items.length?`${stats.done.length} of ${stats.items.length} tasks done`:'No tasks yet'}</dd></div><div class="sheet-property"><dt>Goal brief</dt><dd><div class="goal-brief" data-goal-brief><p class="goal-brief-text" data-goal-brief-text>${e(briefText)}</p><button type="button" class="goal-brief-toggle" data-goal-brief-toggle aria-expanded="false" hidden>Show more</button></div></dd></div></dl>${people}<section class="sheet-section"><h3>Related tasks</h3>${ticketListFor(goal)}</section>`;sheet.classList.add('is-open');backdrop.classList.add('is-open');sheet.setAttribute('aria-hidden','false');document.body.classList.add('sheet-open');q.querySelectorAll('[data-goal]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.goal===goal.id)));closeButton.focus();syncGoalBrief()}
function closeGoal(){sheet.classList.remove('is-open');backdrop.classList.remove('is-open');sheet.setAttribute('aria-hidden','true');sheet.inert=true;document.body.classList.remove('sheet-open');q.querySelectorAll('[data-goal]').forEach(button=>button.setAttribute('aria-pressed','false'));if(lastFocused?.isConnected)lastFocused.focus()}
function centerToday(){if(viewport){const corner=document.querySelector('.gantt-corner'),stickyWidth=corner&&getComputedStyle(corner).display!=='none'?corner.getBoundingClientRect().width:0;viewport.scrollLeft=Math.max(0,todayLeft-(viewport.clientWidth-stickyWidth)/2)}}
function bindTicketRows(){ticketRowsContainer.querySelectorAll('[data-ticket-id]').forEach(button=>button.addEventListener('click',()=>showTicket(ticketMap[button.dataset.ticketId])))}
function renderTicketSearch(){ticketSearchClear.hidden=!ticketSearch.value;const term=ticketSearch.value.trim().toLowerCase(),status=ticketStatusFilter.dataset.value||'',items=t.filter(ticket=>(!term||`${ticket.id} ${ticket.title} ${ticket.owner} ${ticket.status} ${simpleStatus(ticket.status)} ${goalMap[ticket.goal]?.title||ticket.goal||''} ${assuranceSummary(ticket)}`.toLowerCase().includes(term))&&(!status||simpleStatus(ticket.status)===status));ticketRowsContainer.innerHTML=ticketRowsMarkup(items);ticketCount.textContent=items.length===t.length?`${t.length} task${t.length===1?'':'s'}`:`${items.length} of ${t.length} tasks`;bindTicketRows();refreshOverflowTooltips(ticketRowsContainer)}
document.addEventListener('keydown',event=>{if(!sheet.classList.contains('is-open')||event.key!=='Tab')return;const focusable=[...sheet.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(element=>!element.inert&&element.offsetParent!==null),first=focusable[0],last=focusable.at(-1);if(!first){event.preventDefault();closeButton.focus()}else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}});
ticketSearchClear.addEventListener('click',()=>{ticketSearch.value='';renderTicketSearch();ticketSearch.focus()});ticketSearch.addEventListener('keydown',event=>{if(event.key==='Escape'&&ticketSearch.value){event.preventDefault();ticketSearch.value='';renderTicketSearch()}});
q.querySelectorAll('[data-goal]').forEach(button=>button.addEventListener('click',()=>showGoal(goalMap[button.dataset.goal])));ticketSearch.addEventListener('input',renderTicketSearch);ticketStatusFilter.addEventListener('click',()=>setTicketFilterOpen(ticketStatusMenu.hidden));ticketStatusFilter.addEventListener('keydown',event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();setTicketFilterOpen(true,event.key==='ArrowDown'?1:-1)}else if(event.key==='Escape'){setTicketFilterOpen(false);ticketStatusFilter.focus()}});ticketStatusMenu.addEventListener('click',event=>{const option=event.target.closest('[data-status]');if(!option)return;setTicketFilterStatus(option.dataset.status);setTicketFilterOpen(false);ticketStatusFilter.focus()});ticketStatusMenu.addEventListener('keydown',event=>{const options=ticketFilterOptions(),index=options.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?options.length-1:event.key==='ArrowDown'?(index+1)%options.length:(index-1+options.length)%options.length;options[next]?.focus()}else if(event.key==='Escape'){event.preventDefault();setTicketFilterOpen(false);ticketStatusFilter.focus()}else if(event.key==='Tab')setTicketFilterOpen(false)});document.addEventListener('pointerdown',event=>{if(!ticketFilterHost.contains(event.target))setTicketFilterOpen(false)});closeButton.addEventListener('click',closeGoal);backdrop.addEventListener('click',closeGoal);document.addEventListener('keydown',event=>{if(event.key==='Escape'&&sheet.classList.contains('is-open'))closeGoal()});document.getElementById('today-button').addEventListener('click',centerToday);renderTicketSearch();requestAnimationFrame(()=>{centerToday();refreshOverflowTooltips()});
</script></body></html>
'''
    return template.replace("__STATE_SNAPSHOT__", snapshot)


def write_transaction(files: dict[Path, str]) -> None:
    staged: dict[Path, Path] = {}
    backups: dict[Path, bytes | None] = {}
    try:
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            staged[path] = Path(temporary)
        for path in files:
            backups[path] = path.read_bytes() if path.exists() else None
        for path, temporary in staged.items():
            os.replace(temporary, path)
    except Exception:
        for path, previous in backups.items():
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def result(ok: bool, errors: list[str], changed: list[str] | None = None) -> dict[str, Any]:
    return {"ok": ok, "errors": errors, "changed": changed or []}


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    elif payload["ok"]:
        print("OK: canonical state and dashboard are valid")
    else:
        print("ERROR: " + "\nERROR: ".join(payload["errors"]), file=sys.stderr)


def command_check(as_json: bool) -> int:
    errors: list[str] = []
    validate_schema_files(errors)
    records = load_records(errors)
    validate_records(records, errors)
    if not errors and (not DASHBOARD.is_file() or DASHBOARD.read_text(encoding="utf-8") != render_dashboard(records)):
        errors.append("docs/index.html: dashboard drift; run apply with a valid operation")
    emit(result(not errors, errors), as_json)
    return 0 if not errors else 1


@locked_state_mutation
def command_apply(operation_path: Path, as_json: bool) -> int:
    errors: list[str] = []
    validate_schema_files(errors)
    operation = read_json(operation_path, errors)
    current = load_records(errors)
    if operation is None or set(current) != set(RECORD_NAMES):
        emit(result(False, errors), as_json)
        return 1
    try:
        operation_schema_errors = schema_errors(
            operation, SCHEMA_DIR / "operation.schema.json"
        )
    except SchemaContractError as error:
        errors.append(f"docs/schemas/operation.schema.json: {error}")
    else:
        errors.extend(f"operation schema {error}" for error in operation_schema_errors)
    if type(operation.get("schemaVersion")) is not int or operation.get("schemaVersion") != 1 or operation.get("operation") != "replace-records" or not isinstance(operation.get("records"), dict):
        errors.append("operation: expected schemaVersion 1, operation replace-records, and records object")
    if isinstance(operation, dict):
        reject_extra_keys(operation, {"schemaVersion", "operation", "records"}, "operation", errors)
    changes = operation.get("records", {}) if isinstance(operation, dict) else {}
    if not changes or not set(changes).issubset(OPERATION_RECORD_NAMES):
        errors.append(
            "operation: records must contain one or more operational record names; team changes require $hire-consultant or $fire-consultant"
        )
    proposed = dict(current)
    if isinstance(changes, dict):
        proposed.update(changes)
    validate_records(proposed, errors)
    if errors:
        emit(result(False, errors), as_json)
        return 1
    changed = [name for name in RECORD_NAMES if proposed[name] != current[name]]
    files = {STATE_DIR / f"{name}.json": json.dumps(proposed[name], indent=2, ensure_ascii=False) + "\n" for name in changed}
    dashboard = render_dashboard(proposed)
    files[DASHBOARD] = dashboard
    metadata_path = ROOT / ".agent-harness.json"
    if metadata_path.is_file():
        metadata = read_json(metadata_path, errors)
        managed = metadata.get("managedFiles") if isinstance(metadata, dict) else None
        dashboard_record = managed.get("docs/index.html") if isinstance(managed, dict) else None
        if dashboard_record is not None:
            if (
                not isinstance(dashboard_record, dict)
                or dashboard_record.get("ownership") != "generated-config"
            ):
                errors.append(
                    ".agent-harness.json: docs/index.html baseline must be generated-config"
                )
            else:
                dashboard_record["baselineSha256"] = hashlib.sha256(
                    dashboard.encode("utf-8")
                ).hexdigest()
                files[metadata_path] = json.dumps(
                    metadata, indent=2, ensure_ascii=False
                ) + "\n"
    for path in files:
        current = path
        while current != ROOT:
            if current.is_symlink():
                errors.append(
                    f"{path.relative_to(ROOT)}: transactional write path uses a symbolic link"
                )
                break
            current = current.parent
    if errors:
        emit(result(False, errors), as_json)
        return 1
    try:
        write_transaction(files)
    except OSError as error:
        errors.append(f"apply transaction failed: {error}")
        emit(result(False, errors), as_json)
        return 1
    emit(result(True, [], changed), as_json)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="validate canonical records and dashboard")
    check.add_argument("--json", action="store_true", dest="command_json")
    apply = subparsers.add_parser("apply", help="apply one canonical operation transactionally")
    apply.add_argument("operation", type=Path)
    apply.add_argument("--json", action="store_true", dest="command_json")
    args = parser.parse_args()
    as_json = args.json or getattr(args, "command_json", False)
    return command_check(as_json) if args.command == "check" else command_apply(args.operation, as_json)


if __name__ == "__main__":
    raise SystemExit(main())
