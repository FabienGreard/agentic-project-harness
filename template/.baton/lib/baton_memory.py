#!/usr/bin/env python3
"""Project-local company memory, personnel, bootstrap, and bounded recall."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple
import uuid

sys.dont_write_bytecode = True

from harness_lock import MutationLockError, mutation_lock
from json_schema_contract import SchemaContractError, schema_errors


SCHEMA_VERSION = 1
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
ROLES = ("Management", "Operations", "Consultant", "Contractor")
CONTEXT_ROLES = ROLES + ("Internal Audit",)
ACTORS = ("User",) + ROLES + ("Internal Audit",)
READINESS_PROTOCOLS = {
    "Waived",
    "Field Check",
    "Standard Protocol",
    "Full Certification",
}
CLEARANCE_PROTOCOLS = {
    "Autonomous",
    "Release Clearance",
    "Completion Clearance",
    "Continuous Clearance",
}
SOURCE_CLASSES = {
    "explicit-user",
    "personal-inference",
    "verified-company",
    "verified-personnel",
    "management-assessment",
    "operational-evidence",
    "consultant-observation",
    "self-reflection",
    "system",
}
OPERATIONS = {
    "remember",
    "candidate",
    "confirm",
    "correct",
    "forget",
    "personnel",
    "task",
    "review",
    "bootstrap",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:password|passwd|secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\s*[:=]", re.I),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.I),
)
SENSITIVE_TERMS = re.compile(
    r"\b(?:medical|diagnosis|disability|religion|ethnicity|race|sexual orientation|biometric|"
    r"social security|passport number|government id|bank account|credit card)\b",
    re.I,
)
FORBIDDEN_GAMIFICATION_KEYS = {
    "score",
    "rating",
    "rank",
    "leaderboard",
    "rotation",
    "rotationPolicy",
    "noveltyQuota",
    "explorationQuota",
}
FORBIDDEN_PM_KEYS = {"ticketStatus", "priority", "approval", "decision", "readiness"}
FIRST_NAMES = (
    "Alex",
    "Avery",
    "Camille",
    "Casey",
    "Drew",
    "Emery",
    "Jordan",
    "Morgan",
    "Quinn",
    "Riley",
    "Robin",
    "Taylor",
)
LAST_NAMES = (
    "Bennett",
    "Chen",
    "Dubois",
    "Ellis",
    "Garcia",
    "Ito",
    "Khan",
    "Martin",
    "Nielsen",
    "Okafor",
    "Patel",
    "Silva",
)


class MemoryError(RuntimeError):
    """A memory operation was unsafe, unauthorized, or inconsistent."""


def _paths(root: Path) -> Tuple[Path, Path, Path, Path]:
    project = root.expanduser().resolve()
    baton = project / ".baton"
    return (
        project,
        baton / "memory/memory.json",
        baton / "memory/history.jsonl",
        baton / "schemas",
    )


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _line_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    material = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return "%s-%s" % (prefix, hashlib.sha256(material).hexdigest()[:24])


def _request_semantics(command: Dict[str, Any]) -> str:
    """Return a stable digest for the logical mutation behind an idempotency key."""
    semantic = {
        key: value
        for key, value in command.items()
        if key not in {"expectedRevision", "idempotencyKey", "timestamp"}
    }
    operation = semantic.get("operation")
    semantic.setdefault("references", [])
    if operation in {"remember", "candidate"} and semantic.get("action") != "reject":
        semantic.setdefault("roleRelevance", list(ROLES))
        semantic.setdefault("assignmentTypes", [])
        semantic.setdefault("importance", 3)
        semantic.setdefault("reference", "")
    for key in (
        "assignmentTypes",
        "claimIds",
        "evidencePaths",
        "references",
        "reviewers",
        "roleRelevance",
    ):
        value = semantic.get(key)
        if isinstance(value, list):
            semantic[key] = sorted(set(value))
    summary = semantic.get("performanceSummary")
    if isinstance(summary, dict) and isinstance(summary.get("reviewIds"), list):
        summary = copy.deepcopy(summary)
        summary["reviewIds"] = sorted(set(summary["reviewIds"]))
        semantic["performanceSummary"] = summary
    return _sha256(
        json.dumps(
            semantic,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _idempotency_binding(key: str, command: Dict[str, Any]) -> str:
    return "v1:%s:%s" % (
        _sha256(key.encode("utf-8")),
        _request_semantics(command),
    )


def _timestamp(command: Dict[str, Any]) -> str:
    supplied = command.get("timestamp")
    if supplied is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not isinstance(supplied, str):
        raise MemoryError("timestamp must be an ISO date-time")
    try:
        datetime.fromisoformat(supplied.removesuffix("Z") + ("+00:00" if supplied.endswith("Z") else ""))
    except ValueError as error:
        raise MemoryError("timestamp must be an ISO date-time") from error
    return supplied


def _safe_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _safe_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _safe_strings(item)


def _reject_sensitive(command: Dict[str, Any]) -> None:
    if command.get("allowSensitive") is True:
        raise MemoryError("sensitive memory is disabled by project policy")
    for value in _safe_strings(command):
        if SENSITIVE_TERMS.search(value) or any(pattern.search(value) for pattern in SECRET_PATTERNS):
            raise MemoryError("secret or sensitive content was rejected; nothing was stored")


def _reject_forbidden_authorities(command: Dict[str, Any]) -> None:
    keys = set(command)
    if keys & FORBIDDEN_GAMIFICATION_KEYS:
        raise MemoryError("universal scoring, ranking, and forced rotation are not memory capabilities")
    if keys & FORBIDDEN_PM_KEYS:
        raise MemoryError("memory may reference canonical project records but cannot duplicate their authority")
    if command.get("operation") in {"import", "sync", "global-sync"}:
        raise MemoryError("memory import and global synchronization are not supported")


def _read_snapshot(path: Path) -> Dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise MemoryError("authoritative memory.json is missing or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MemoryError("authoritative memory.json is invalid") from error
    if not isinstance(value, dict):
        raise MemoryError("authoritative memory.json must contain an object")
    return value


def _read_history(path: Path) -> Tuple[List[Dict[str, Any]], bytes]:
    if path.is_symlink() or not path.is_file():
        raise MemoryError("subordinate history.jsonl is missing or unsafe")
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise MemoryError("subordinate history.jsonl is invalid") from error
    events = []
    for index, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise MemoryError("history.jsonl line %d is empty" % index)
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise MemoryError("history.jsonl line %d is invalid JSON" % index) from error
        if not isinstance(value, dict):
            raise MemoryError("history.jsonl line %d must contain an object" % index)
        events.append(value)
    return events, raw


def _validate(snapshot: Dict[str, Any], events: List[Dict[str, Any]], history_raw: bytes, schemas: Path) -> None:
    try:
        errors = schema_errors(snapshot, schemas / "memory.schema.json")
        for index, event in enumerate(events, 1):
            errors.extend(
                "history line %d %s" % (index, error)
                for error in schema_errors(event, schemas / "memory-event.schema.json")
            )
    except SchemaContractError as error:
        raise MemoryError("memory schema contract is unavailable: %s" % error) from error
    if errors:
        raise MemoryError("memory schema validation failed: " + "; ".join(errors))
    revision = snapshot.get("revision")
    head = snapshot.get("historyHead", {})
    if revision != len(events) or head.get("revision") != revision:
        raise MemoryError("memory revision and history length/head do not agree")
    previous = ""
    for expected, event in enumerate(events, 1):
        if event.get("revision") != expected or event.get("previousEventId") != previous:
            raise MemoryError("history event revision or chain is inconsistent")
        previous = event["eventId"]
    expected_id = events[-1]["eventId"] if events else ""
    expected_sha = _sha256(_line_bytes(events[-1])) if events else EMPTY_SHA256
    if head.get("eventId") != expected_id or head.get("sha256") != expected_sha:
        raise MemoryError("memory history head does not match history.jsonl")
    if events and history_raw != b"".join(_line_bytes(event) for event in events):
        raise MemoryError("history.jsonl must use canonical whole-file JSONL encoding")
    claim_ids = [claim.get("id") for claim in snapshot.get("claims", [])]
    person_ids = [person.get("id") for person in snapshot.get("personnel", [])]
    if len(claim_ids) != len(set(claim_ids)) or len(person_ids) != len(set(person_ids)):
        raise MemoryError("claim and personnel identities must be unique")
    review_ids = [review.get("id") for person in snapshot.get("personnel", []) for review in person.get("reviews", [])]
    if len(review_ids) != len(set(review_ids)):
        raise MemoryError("review identities must be unique")
    recorded_tasks = [
        person["task"]["taskId"]
        for person in snapshot.get("personnel", [])
        if person.get("task", {}).get("taskId")
    ]
    cleanup_tasks = [
        item.get("taskId")
        for item in snapshot.get("bootstrap", {}).get("cleanupTasks", [])
    ]
    if len(recorded_tasks) != len(set(recorded_tasks)) or len(cleanup_tasks) != len(
        set(cleanup_tasks)
    ) or set(recorded_tasks) & set(cleanup_tasks):
        raise MemoryError("recorded task identities must be unique")
    known_reviews = set(review_ids)
    for person in snapshot.get("personnel", []):
        for summary in person.get("performanceSummaries", []):
            if not set(summary.get("reviewIds", [])).issubset(known_reviews):
                raise MemoryError("performance summaries must reference known reviews")


def _load(root: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bytes, Path, Path, Path]:
    project, memory_path, history_path, schemas = _paths(root)
    snapshot = _read_snapshot(memory_path)
    events, history_raw = _read_history(history_path)
    _validate(snapshot, events, history_raw, schemas)
    return snapshot, events, history_raw, project, memory_path, history_path


def _projection(snapshot: Dict[str, Any], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    personnel = []
    for person in snapshot["personnel"]:
        personnel.append(
            {
                "id": person["id"],
                "name": person["name"],
                "role": person["role"],
                "seat": person["seat"],
                "specialty": person["specialty"],
                "employmentStatus": person["employmentStatus"],
                "taskStatus": person["task"]["status"],
                "workingStyle": copy.deepcopy(person["workingStyle"]),
                "assignmentTypes": sorted(
                    {review["assignmentType"] for review in person["reviews"]}
                ),
                "performanceSummaries": [
                    {
                        **copy.deepcopy(summary),
                        "sourceClasses": sorted(
                            {
                                review["sourceClass"]
                                for review in person["reviews"]
                                if review["id"] in summary["reviewIds"]
                            }
                        ),
                        "evidencePaths": sorted(
                            {
                                path
                                for review in person["reviews"]
                                if review["id"] in summary["reviewIds"]
                                for path in review["evidencePaths"]
                            }
                        ),
                    }
                    for summary in person["performanceSummaries"]
                ],
                "recentOutcomes": [
                    {
                        "reviewId": review["id"],
                        "assignmentType": review["assignmentType"],
                        "outcome": review["outcome"],
                        "verificationQuality": review["verificationQuality"],
                        "sourceClass": review["sourceClass"],
                        "evidencePaths": list(review["evidencePaths"]),
                        "recordedAt": review["recordedAt"],
                    }
                    for review in person["reviews"][-3:]
                ],
            }
        )
    chronology = [
        {
            "eventId": event["eventId"],
            "revision": event["revision"],
            "operation": event["operation"],
            "actor": event["actor"],
            "timestamp": event["timestamp"],
            "personnelIds": list(event["personnelIds"]),
            "references": list(event["references"]),
            "result": event["details"]["result"],
            "sourceClass": event["details"]["sourceClass"],
            "redacted": event["details"]["redacted"],
        }
        for event in events
    ]
    return {
        "schemaVersion": 1,
        "revision": snapshot["revision"],
        "bootstrap": {
            "status": snapshot["bootstrap"]["status"],
            "roster": list(snapshot["bootstrap"]["roster"]),
        },
        "personnel": personnel,
        "chronology": chronology,
        "privacy": "allowlisted; claims, candidates, task identities, and history values excluded",
    }


def render_team_tasks(snapshot: Dict[str, Any], team: Dict[str, Any]) -> str:
    """Render permanent task routing without exposing task prompts."""
    people = snapshot.get("personnel", [])

    def person_for(role: str, seat: str) -> Optional[Dict[str, Any]]:
        eligible = [
            person
            for person in people
            if person.get("role") == role
            and person.get("seat") == seat
            and person.get("employmentStatus") not in {"former", "retired", "replaced"}
        ]
        return eligible[0] if eligible else None

    def row(role: str, seat: str, persona: str, instructions: str) -> str:
        person = person_for(role, seat)
        name = person.get("name") if person else persona
        task = person.get("task", {}) if person else {}
        status = task.get("status", "unregistered")
        task_id = task.get("taskId", "") if status == "online" else ""
        identity = task_id or ("<awaiting task>" if status == "awaiting-task" else "<not registered>")
        return "| %s (`%s`) | `%s` | [%s](%s) |" % (
            role,
            name,
            identity,
            role,
            instructions,
        )

    management = team.get("management", {})
    operations = team.get("operations", {})
    rows = [
        row(
            "Management",
            "Management",
            management.get("title", "configured persona"),
            "../roles/management.md",
        ),
        row(
            "Operations",
            "Operations",
            operations.get("title", "configured persona"),
            "../roles/operations.md",
        ),
    ]
    for consultant in team.get("consultants", []):
        if consultant.get("status") != "active":
            continue
        rows.append(
            row(
                "Consultant",
                str(consultant.get("id", "")),
                consultant.get("title", "configured Consultant"),
                "../roles/consultant.md",
            )
        )
    return """# Permanent tasks

Generated from team and Memory State. Use `$boot` for initial assembly or `$roster` for later changes; do not edit. Keep private task links and credentials unversioned.

| Role | Task ID | Contract |
| --- | --- | --- |
%s

Only Management, Operations, and active Consultants are permanent. Wake and idle behavior is defined in [the lifecycle rule](../rules/lifecycle.md).
""" % "\n".join(rows)


def _generated_views(
    project: Path,
    snapshot: Dict[str, Any],
    events: List[Dict[str, Any]],
    project_after: Optional[bytes] = None,
    metadata_after: Optional[bytes] = None,
) -> Dict[str, bytes]:
    """Return generated view bytes when the installed control plane is active."""
    state = project / ".baton/state"
    if not state.exists():
        return {}
    required = ("project", "goals", "tickets", "ownership", "reviews", "team")
    paths = {name: state / (name + ".json") for name in required}
    if not all(path.is_file() and not path.is_symlink() for path in paths.values()):
        raise MemoryError("active Baton state is incomplete; generated memory views were not changed")
    try:
        records = {
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in paths.items()
        }
        if project_after is not None:
            records["project"] = json.loads(project_after.decode("utf-8"))
        from harness_state import render_dashboard

        dashboard = render_dashboard(records, _projection(snapshot, events)).encode("utf-8")
    except (OSError, json.JSONDecodeError, ImportError, TypeError, ValueError) as error:
        raise MemoryError("could not render generated memory views") from error
    views = {".baton/views/dashboard.html": dashboard}
    metadata_path = project / ".baton/metadata.json"
    try:
        if metadata_after is not None:
            metadata = json.loads(metadata_after.decode("utf-8"))
        elif metadata_path.is_file() and not metadata_path.is_symlink():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            return views
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MemoryError("installed Baton metadata is unreadable") from error
    managed = metadata.get("managedFiles")
    if not isinstance(managed, dict):
        raise MemoryError("installed Baton metadata has no managed-file map")
    dashboard_record = managed.get(".baton/views/dashboard.html")
    if dashboard_record is not None:
        if not isinstance(dashboard_record, dict) or dashboard_record.get("ownership") != "generated-config":
            raise MemoryError("dashboard baseline is not a generated Baton view")
        dashboard_record["baselineSha256"] = _sha256(dashboard)
    registry_record = managed.get(".baton/views/team-tasks.md")
    if registry_record is not None:
        if not isinstance(registry_record, dict) or registry_record.get("ownership") != "generated-config":
            raise MemoryError("team task baseline is not a generated Baton view")
        registry = render_team_tasks(snapshot, records["team"]).encode("utf-8")
        views[".baton/views/team-tasks.md"] = registry
        registry_record["baselineSha256"] = _sha256(registry)
    if dashboard_record is not None or registry_record is not None:
        views[".baton/metadata.json"] = _json_bytes(metadata)
    return views


def inspect(root: Path, query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a privacy-filtered readable view or allowlisted Operations projection."""
    snapshot, events, _, _, _, _ = _load(Path(root))
    query = query or {}
    section = query.get("section", "summary")
    if section == "projection":
        return _projection(snapshot, events)
    result = {
        "ok": True,
        "revision": snapshot["revision"],
        "filtered": True,
        "section": section,
    }
    if section in {"summary", "confirmed"}:
        result["confirmed"] = [
            {
                "id": claim["id"],
                "category": claim["category"],
                "subject": claim["subject"],
                "statement": claim["statement"],
                "status": claim["status"],
                "sourceClass": claim["source"]["class"],
                "sourceActor": claim["source"]["actor"],
                "sourceReference": claim["source"]["reference"],
                "createdAt": claim["createdAt"],
                "updatedAt": claim["updatedAt"],
            }
            for claim in snapshot["claims"]
            if claim["status"] == "confirmed"
        ]
    if section in {"summary", "candidates"}:
        result["candidates"] = [
            {
                "id": claim["id"],
                "category": claim["category"],
                "subject": claim["subject"],
                "statement": claim["statement"],
                "status": claim["status"],
                "sourceClass": claim["source"]["class"],
                "sourceActor": claim["source"]["actor"],
                "sourceReference": claim["source"]["reference"],
                "createdAt": claim["createdAt"],
                "updatedAt": claim["updatedAt"],
            }
            for claim in snapshot["claims"]
            if claim["status"] == "pending-confirmation"
        ]
    if section in {"summary", "personnel"}:
        result["personnel"] = _projection(snapshot, events)["personnel"]
    if section == "history":
        result["history"] = _projection(snapshot, events)["chronology"]
    if section not in {"summary", "confirmed", "candidates", "personnel", "history"}:
        raise MemoryError("unknown privacy-filtered inspection section")
    return result


def _authority(command: Dict[str, Any], snapshot: Dict[str, Any]) -> Tuple[str, str, str]:
    actor = command.get("actor")
    actor_id = command.get("actorId", "")
    operation = command.get("operation")
    if actor not in ACTORS or not isinstance(actor_id, str):
        raise MemoryError("a recognized actor and actorId are required")
    if operation not in OPERATIONS:
        raise MemoryError("unsupported memory operation")
    if actor == "Internal Audit":
        raise MemoryError("Internal Audit has read-only memory authority")
    if operation == "task" and actor not in {"User", "Operations"}:
        management_bootstrap = (
            actor == "Management"
            and command.get("userApproved") is True
            and snapshot.get("bootstrap", {}).get("status")
            in {"in-progress", "ready-for-confirmation"}
        )
        if management_bootstrap and command.get("personnelId") not in snapshot.get(
            "bootstrap", {}
        ).get("roster", []):
            raise MemoryError(
                "bootstrap Management may register only a reconciled private-roster task"
            )
        if not management_bootstrap:
            raise MemoryError(
                "only the user, Operations, or explicitly authorized bootstrap Management may register tasks"
            )
    if operation == "personnel" and actor not in {"User", "Management", "Operations"}:
        raise MemoryError("personnel mutations require user, Management, or Operations authority")
    if operation == "bootstrap" and actor not in {"User", "Management", "Operations"}:
        raise MemoryError("bootstrap mutations require user, Management, or Operations authority")
    if operation == "review":
        source_class = command.get("sourceClass")
        allowed = {
            "User": {"explicit-user"},
            "Management": {"management-assessment"},
            "Operations": {"operational-evidence"},
            "Consultant": {"consultant-observation", "self-reflection"},
            "Contractor": {"self-reflection"},
        }
        if source_class not in allowed.get(actor, set()):
            raise MemoryError("the review source exceeds the actor's authority")
    return actor, actor_id, operation


def _claim(snapshot: Dict[str, Any], claim_id: str) -> Dict[str, Any]:
    for claim in snapshot["claims"]:
        if claim["id"] == claim_id:
            return claim
    raise MemoryError("the requested claim does not exist")


def _person(snapshot: Dict[str, Any], person_id: str) -> Dict[str, Any]:
    for person in snapshot["personnel"]:
        if person["id"] == person_id:
            return person
    raise MemoryError("the requested personnel record does not exist")


def _claim_authority(actor: str, source_class: str, category: str, confirmed: bool, user_approved: bool) -> None:
    personal = category in {"user", "preference"}
    if personal and source_class == "personal-inference" and confirmed:
        raise MemoryError("personal inference must remain pending until user confirmation")
    if actor == "User":
        return
    if actor == "Management":
        if personal and not user_approved:
            raise MemoryError("personal memory requires explicit user approval")
        if source_class not in {"explicit-user", "verified-company", "verified-personnel", "management-assessment"}:
            raise MemoryError("Management source class is not authorized")
        return
    if actor == "Operations":
        if personal or source_class not in {"verified-company", "verified-personnel", "operational-evidence"}:
            raise MemoryError("Operations cannot confirm personal facts or this source class")
        return
    if confirmed:
        raise MemoryError("Consultants and Contractors may submit candidates only")
    allowed = {"consultant-observation", "self-reflection", "personal-inference"}
    if source_class not in allowed:
        raise MemoryError("the candidate source exceeds the actor's authority")


def _new_claim(snapshot: Dict[str, Any], command: Dict[str, Any], actor: str, actor_id: str, now: str, pending: bool) -> Dict[str, Any]:
    category = command.get("category")
    subject = command.get("subject")
    statement = command.get("statement")
    source_class = command.get("sourceClass")
    if category not in {"company", "user", "personnel", "working-style", "preference"}:
        raise MemoryError("a supported claim category is required")
    if not isinstance(subject, str) or not subject.strip() or not isinstance(statement, str) or not statement.strip():
        raise MemoryError("claim subject and statement are required")
    if source_class not in SOURCE_CLASSES:
        raise MemoryError("a supported sourceClass is required")
    if source_class == "personal-inference":
        pending = True
    confirmed = not pending
    _claim_authority(actor, source_class, category, confirmed, command.get("userApproved") is True)
    key = command.get("idempotencyKey", "")
    claim_id = command.get("claimId") or _stable_id("claim", key or snapshot["revision"] + 1, category, subject, statement)
    if not isinstance(claim_id, str) or re.fullmatch(r"claim-[a-f0-9]{24}", claim_id) is None:
        raise MemoryError("claimId must be a stable Baton claim identity")
    if any(item["id"] == claim_id for item in snapshot["claims"]):
        raise MemoryError("claim identity already exists; use correct or an idempotency key")
    relevance = command.get("roleRelevance", list(ROLES))
    assignments = command.get("assignmentTypes", [])
    if not isinstance(relevance, list) or not set(relevance).issubset(set(ROLES)):
        raise MemoryError("roleRelevance contains an unsupported role")
    if not isinstance(assignments, list) or not all(isinstance(item, str) and item for item in assignments):
        raise MemoryError("assignmentTypes must contain non-empty strings")
    importance = command.get("importance", 3)
    if type(importance) is not int or not 1 <= importance <= 5:
        raise MemoryError("importance must be an integer from 1 through 5")
    return {
        "id": claim_id,
        "category": category,
        "subject": subject.strip(),
        "statement": statement.strip(),
        "status": "pending-confirmation" if pending else "confirmed",
        "source": {
            "class": source_class,
            "actor": actor,
            "actorId": actor_id,
            "reference": str(command.get("reference", "")),
        },
        "importance": importance,
        "roleRelevance": sorted(set(relevance), key=ROLES.index),
        "assignmentTypes": sorted(set(assignments)),
        "createdAt": now,
        "updatedAt": now,
        "supersedesClaimId": str(command.get("supersedesClaimId", "")),
    }


def _style(seed: str) -> Dict[str, str]:
    digest = hashlib.sha256(("style\x1f" + seed).encode("utf-8")).digest()
    choices = (
        ("planning", ("plan-first", "prototype-first")),
        ("communication", ("concise", "explanatory")),
        ("exploration", ("broad", "narrow")),
        ("risk", ("risk-first", "opportunity-first")),
        ("design", ("simplification", "extensibility")),
    )
    return {name: values[digest[index] % 2] for index, (name, values) in enumerate(choices)}


def _name(seed: str) -> str:
    digest = hashlib.sha256(("name\x1f" + seed).encode("utf-8")).digest()
    return "%s %s" % (FIRST_NAMES[digest[0] % len(FIRST_NAMES)], LAST_NAMES[digest[1] % len(LAST_NAMES)])


def _personnel(snapshot: Dict[str, Any], command: Dict[str, Any], actor: str, now: str) -> List[str]:
    action = command.get("action")
    if action == "ensure":
        role, seat, specialty, seed = (command.get(key, "") for key in ("role", "seat", "specialty", "seed"))
        if role not in ROLES or not isinstance(seat, str) or not seat.strip() or not isinstance(seed, str) or not seed:
            raise MemoryError("personnel ensure requires role, seat, and stable seed")
        existing = next((item for item in snapshot["personnel"] if item["role"] == role and item["seat"] == seat and item["employmentStatus"] not in {"former", "retired", "replaced"}), None)
        if existing:
            return [existing["id"]]
        person_id = _stable_id("person", seed, role, seat, specialty)
        if any(item["id"] == person_id for item in snapshot["personnel"]):
            return [person_id]
        person = {
            "id": person_id,
            "name": str(command.get("name") or _name(seed)),
            "role": role,
            "seat": seat.strip(),
            "specialty": str(specialty),
            "seed": seed,
            "workingStyle": _style(seed),
            "employmentStatus": "active",
            "task": {
                "status": "unregistered",
                "taskId": "",
                "wakePath": "",
                "prompt": "",
                "registeredAt": "",
                "expectedTitle": "",
                "title": "",
                "titleVerifiedAt": "",
                "wokenAt": "",
                "attemptId": "",
                "cleanupReason": "",
            },
            "assignmentReferences": [],
            "reviews": [],
            "performanceSummaries": [],
            "createdAt": now,
            "updatedAt": now,
        }
        snapshot["personnel"].append(person)
        return [person_id]
    person = _person(snapshot, str(command.get("personnelId", "")))
    permanent = person["role"] in {"Management", "Operations", "Consultant"}
    if permanent and actor != "User" and command.get("userApproved") is not True:
        raise MemoryError("changing a permanent seat requires explicit user approval")
    if action == "fire":
        person["employmentStatus"] = "former"
        person["task"]["status"] = "inactive"
    elif action == "retire":
        person["employmentStatus"] = "retired"
        person["task"]["status"] = "inactive"
    elif action == "rehire":
        person["employmentStatus"] = "rehired"
        if person["task"]["taskId"]:
            person["task"]["status"] = "created"
            person["task"]["wokenAt"] = ""
        else:
            person["task"]["status"] = "unregistered"
    elif action == "replace":
        if permanent and actor != "User" and command.get("userApproved") is not True:
            raise MemoryError("personnel replacement requires explicit user approval")
        person["employmentStatus"] = "replaced"
        person["task"]["status"] = "inactive"
    elif action == "assign":
        reference = command.get("reference")
        if not isinstance(reference, str) or not reference:
            raise MemoryError("assignment reference is required")
        if reference not in person["assignmentReferences"]:
            person["assignmentReferences"].append(reference)
    elif action == "edit":
        if actor != "User" and (permanent or command.get("userApproved") is not True):
            raise MemoryError("editing this personnel identity requires explicit user approval")
        if "name" in command:
            if not isinstance(command["name"], str) or not command["name"].strip():
                raise MemoryError("personnel name must be non-empty")
            person["name"] = command["name"].strip()
        if "workingStyle" in command:
            style = command["workingStyle"]
            if not isinstance(style, dict) or set(style) != set(person["workingStyle"]):
                raise MemoryError("working style must contain the five bounded professional traits")
            person["workingStyle"] = copy.deepcopy(style)
    else:
        raise MemoryError("unsupported personnel action")
    person["updatedAt"] = now
    return [person["id"]]


def _bootstrap_roster_ready(snapshot: Dict[str, Any]) -> bool:
    roster = snapshot["bootstrap"]["roster"]
    if not roster:
        return False
    people = {person["id"]: person for person in snapshot["personnel"]}
    return all(
        personnel_id in people
        and people[personnel_id]["role"] in {"Management", "Operations", "Consultant"}
        and people[personnel_id]["task"]["status"] == "online"
        and bool(people[personnel_id]["task"]["taskId"])
        and bool(people[personnel_id]["task"]["wakePath"])
        and bool(people[personnel_id]["task"].get("expectedTitle"))
        and people[personnel_id]["task"].get("title")
        == people[personnel_id]["task"].get("expectedTitle")
        and bool(people[personnel_id]["task"].get("titleVerifiedAt"))
        and bool(people[personnel_id]["task"].get("wokenAt"))
        for personnel_id in roster
    )


def _refresh_bootstrap_readiness(snapshot: Dict[str, Any]) -> None:
    bootstrap = snapshot["bootstrap"]
    if not bootstrap["confirmedAt"]:
        return
    bootstrap["status"] = (
        "complete" if _bootstrap_roster_ready(snapshot) else "in-progress"
    )


def _has_preferred_name(snapshot: Dict[str, Any]) -> bool:
    return any(
        claim.get("status") == "confirmed"
        and claim.get("category") == "preference"
        and claim.get("subject") == "user"
        and "bootstrap" in claim.get("assignmentTypes", [])
        for claim in snapshot.get("claims", [])
    )


def _bootstrap_roster_established(snapshot: Dict[str, Any]) -> bool:
    expected = [("Management", "Management"), ("Operations", "Operations")]
    expected.extend(
        ("Consultant", seat)
        for seat in snapshot["bootstrap"]
        .get("provisionalProject", {})
        .get("consultantSeats", [])
    )
    people = {
        (person["role"], person["seat"]): person
        for person in snapshot.get("personnel", [])
        if person.get("employmentStatus") not in {"former", "retired", "replaced"}
    }
    return all(
        key in people
        and people[key]["task"]["status"] in {"online", "awaiting-task"}
        for key in expected
    )


def _bootstrap_next_step(snapshot: Dict[str, Any]) -> str:
    bootstrap = snapshot["bootstrap"]
    if bootstrap["status"] == "needs-integration":
        return "needs-integration"
    if bootstrap.get("cleanupTasks"):
        return "cleanup-team"
    provisional = bootstrap.get("provisionalProject", {})
    if provisional.get("projectPresetConfirmed") is not True:
        return "confirm-project-preset"
    if not _has_preferred_name(snapshot):
        return "ask-preferred-name"
    if not bootstrap["confirmedAt"]:
        if bootstrap["status"] == "ready-for-confirmation":
            return "confirm-project-intent"
        return "discover-project"
    if bootstrap["status"] == "complete":
        return "complete"
    return "assemble-team"


def _assert_bootstrap_coordinator(
    snapshot: Dict[str, Any], command: Dict[str, Any]
) -> None:
    """Bind every onboarding and assembly write to its original task."""
    bootstrap = snapshot["bootstrap"]
    coordinator = bootstrap.get("provisionalProject", {}).get(
        "coordinatorTaskId", ""
    )
    if not coordinator:
        return
    invocation_task_id = command.get("invocationTaskId", "")
    if not isinstance(invocation_task_id, str) or invocation_task_id != coordinator:
        raise MemoryError(
            "bootstrap onboarding mutation must come from its original invoking task"
        )


def _project_intent_complete(project: Dict[str, Any]) -> bool:
    required_text = ("identity", "purpose", "users", "outcome")
    if any(
        not isinstance(project.get(field), str) or not project[field].strip()
        for field in required_text
    ):
        return False
    for field in ("constraints", "unresolved"):
        values = project.get(field)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            return False
    return (
        project.get("readinessProtocol") in READINESS_PROTOCOLS
        and project.get("clearanceProtocol") in CLEARANCE_PROTOCOLS
    )


def _profile_mismatch_fingerprint(
    configured_preset: str,
    recommended_preset: str,
    evidence_basis: str,
    evidence: List[str],
) -> str:
    return _stable_id(
        "profile-mismatch",
        configured_preset,
        recommended_preset,
        evidence_basis,
        json.dumps(evidence, ensure_ascii=False, separators=(",", ":")),
    )


def _source_repository_projection(
    project: Path,
    path: Path,
    expected_relative: str,
    error_message: str,
) -> Path:
    metadata_path = project / ".baton/metadata.json"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise MemoryError(error_message)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        resolved = path.resolve(strict=True)
        expected = (project / expected_relative).resolve(strict=True)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MemoryError(error_message) from error
    if (
        not isinstance(metadata, dict)
        or metadata.get("installationStatus") != "Source Repository"
        or resolved != expected
        or (project != resolved and project not in resolved.parents)
    ):
        raise MemoryError(error_message)
    return resolved


def _project_preset_ids(project: Path) -> set[str]:
    catalog_path = project / ".baton/team-presets.json"
    source_path = catalog_path
    if catalog_path.is_symlink():
        source_path = _source_repository_projection(
            project,
            catalog_path,
            "template/.baton/team-presets.json",
            "profile mismatch requires a safe project preset catalog",
        )
    if not source_path.is_file():
        raise MemoryError("profile mismatch requires a safe project preset catalog")
    try:
        catalog = json.loads(source_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MemoryError("project preset catalog is unreadable") from error
    presets = catalog.get("presets") if isinstance(catalog, dict) else None
    if (
        not isinstance(presets, dict)
        or not presets
        or any(not isinstance(identifier, str) or not identifier for identifier in presets)
    ):
        raise MemoryError("project preset catalog has no valid listed presets")
    return set(presets)


def _new_task_attempt(person: Dict[str, Any], nonce: str) -> str:
    return _stable_id(
        "task-attempt",
        person["id"],
        person["task"].get("expectedTitle", ""),
        nonce,
    )


def _reserve_task_attempt(person: Dict[str, Any], nonce: str) -> None:
    expected_title = person["task"].get("expectedTitle", "")
    attempt_id = _new_task_attempt(person, nonce)
    person["task"] = {
        "status": "create-pending",
        "taskId": "",
        "wakePath": "",
        "prompt": "BATON_BOOTSTRAP_ATTEMPT:%s" % attempt_id,
        "registeredAt": "",
        "expectedTitle": expected_title,
        "title": "",
        "titleVerifiedAt": "",
        "wokenAt": "",
        "attemptId": attempt_id,
        "cleanupReason": "",
    }


def _assert_task_seat(person: Dict[str, Any]) -> None:
    role = person["role"]
    active = person["employmentStatus"] in {"active", "awaiting-task", "rehired"}
    if role not in {"Management", "Operations", "Consultant"}:
        raise MemoryError(
            "permanent task registration is limited to Management, Operations, and active Consultants"
        )
    if role == "Consultant" and not active:
        raise MemoryError("permanent task registration requires an active Consultant")


def _task(snapshot: Dict[str, Any], command: Dict[str, Any], now: str) -> List[str]:
    person = _person(snapshot, str(command.get("personnelId", "")))
    action = command.get("action")
    roster = snapshot["bootstrap"]["roster"]
    in_bootstrap = person["id"] in roster
    task = person["task"]
    if in_bootstrap:
        _assert_bootstrap_coordinator(snapshot, command)
    if action == "created":
        _assert_task_seat(person)
        if not in_bootstrap or task.get("status") != "create-pending":
            raise MemoryError(
                "only a reserved bootstrap task attempt can record creation"
            )
        attempt_id = command.get("attemptId", "")
        if not attempt_id or attempt_id != task.get("attemptId"):
            raise MemoryError("created task does not match the reserved attempt")
        people = {item["id"]: item for item in snapshot["personnel"]}
        predecessors = roster[: roster.index(person["id"])]
        if any(
            personnel_id not in people
            or people[personnel_id]["task"]["status"] != "online"
            for personnel_id in predecessors
        ):
            raise MemoryError(
                "bootstrap tasks must be created, registered, and woken in roster order"
            )
        task_id, wake_path = command.get("taskId"), command.get("wakePath")
        if (
            not isinstance(task_id, str)
            or not task_id
            or not isinstance(wake_path, str)
            or not wake_path
        ):
            raise MemoryError(
                "created task requires stable taskId and message wake path"
            )
        for other in snapshot["personnel"]:
            if other["id"] != person["id"] and other["task"]["taskId"] == task_id:
                raise MemoryError(
                    "task identity is already registered to another coworker"
                )
        task.update(
            {
                "status": "created",
                "taskId": task_id,
                "wakePath": wake_path,
                "registeredAt": now,
                "cleanupReason": "",
            }
        )
    elif action == "cleanup-required":
        _assert_task_seat(person)
        task_id = command.get("taskId") or task.get("taskId")
        wake_path = command.get("wakePath") or task.get("wakePath")
        if not isinstance(task_id, str) or not task_id:
            raise MemoryError("cleanup-required task must retain its stable task ID")
        task.update(
            {
                "status": "cleanup-required",
                "taskId": task_id,
                "wakePath": wake_path if isinstance(wake_path, str) else "",
                "cleanupReason": str(command.get("reason") or "creation did not complete"),
            }
        )
    elif action == "archived":
        _assert_task_seat(person)
        if task.get("status") != "cleanup-required" or command.get(
            "archiveConfirmed"
        ) is not True:
            raise MemoryError(
                "task can be retried only after required archival is confirmed"
            )
        expected_title = task.get("expectedTitle", "")
        attempt_id = _new_task_attempt(
            person, str(command.get("idempotencyKey", now))
        )
        person["task"] = {
            "status": "create-pending",
            "taskId": "",
            "wakePath": "",
            "prompt": "BATON_BOOTSTRAP_ATTEMPT:%s" % attempt_id,
            "registeredAt": "",
            "expectedTitle": expected_title,
            "title": "",
            "titleVerifiedAt": "",
            "wokenAt": "",
            "attemptId": attempt_id,
            "cleanupReason": "",
        }
    elif action == "register":
        _assert_task_seat(person)
        if in_bootstrap:
            if task.get("status") in {"create-pending", "unregistered"}:
                raise MemoryError(
                    "native bootstrap registration requires the matching created checkpoint"
                )
            people = {item["id"]: item for item in snapshot["personnel"]}
            predecessors = roster[: roster.index(person["id"])]
            if any(
                personnel_id not in people
                or people[personnel_id]["task"]["status"] != "online"
                for personnel_id in predecessors
            ):
                raise MemoryError(
                    "bootstrap tasks must be registered and woken in roster order"
                )
        task_id, wake_path = command.get("taskId"), command.get("wakePath")
        if not isinstance(task_id, str) or not task_id or not isinstance(wake_path, str) or not wake_path:
            raise MemoryError("online task registration requires stable taskId and wakePath")
        expected_title = task.get("expectedTitle", "")
        observed_title = command.get("observedTitle", "")
        if in_bootstrap and (
            not expected_title
            or not isinstance(observed_title, str)
            or observed_title != expected_title
        ):
            raise MemoryError(
                "bootstrap task registration requires exact verified title readback"
            )
        for other in snapshot["personnel"]:
            if other["id"] != person["id"] and other["task"]["taskId"] == task_id:
                raise MemoryError("task identity is already registered to another coworker")
        person["task"] = {
            "status": "registered" if in_bootstrap else "online",
            "taskId": task_id,
            "wakePath": wake_path,
            "prompt": "",
            "registeredAt": now,
            "expectedTitle": expected_title,
            "title": observed_title if isinstance(observed_title, str) else "",
            "titleVerifiedAt": now if observed_title else "",
            "wokenAt": "",
            "attemptId": task.get("attemptId", ""),
            "cleanupReason": "",
        }
        person["employmentStatus"] = "active" if person["employmentStatus"] == "awaiting-task" else person["employmentStatus"]
        _refresh_bootstrap_readiness(snapshot)
    elif action == "online":
        if not in_bootstrap or task["status"] != "registered":
            raise MemoryError("only a registered bootstrap task can be marked online")
        if (
            not task.get("taskId")
            or not task.get("wakePath")
            or not task.get("expectedTitle")
            or task.get("title") != task.get("expectedTitle")
            or not task.get("titleVerifiedAt")
        ):
            raise MemoryError("bootstrap task is not ready for online activation")
        task["status"] = "online"
        task["wokenAt"] = now
        index = roster.index(person["id"])
        if index + 1 < len(roster):
            next_person = _person(snapshot, roster[index + 1])
            next_task = next_person["task"]
            if (
                not next_task.get("taskId")
                and next_task.get("status") == "unregistered"
            ):
                _reserve_task_attempt(
                    next_person,
                    "%s:%s"
                    % (command.get("idempotencyKey", now), next_person["id"]),
                )
                next_person["updatedAt"] = now
        _refresh_bootstrap_readiness(snapshot)
    elif action == "awaiting":
        _assert_task_seat(person)
        prompt = command.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise MemoryError("awaiting-task registration requires a copy-ready prompt")
        person["task"] = {
            "status": "awaiting-task",
            "taskId": "",
            "wakePath": "",
            "prompt": prompt,
            "registeredAt": now,
            "expectedTitle": task.get("expectedTitle", ""),
            "title": "",
            "titleVerifiedAt": "",
            "wokenAt": "",
            "attemptId": task.get("attemptId", ""),
            "cleanupReason": "",
        }
        person["employmentStatus"] = "awaiting-task"
        _refresh_bootstrap_readiness(snapshot)
    elif action == "inactive":
        person["task"]["status"] = "inactive"
    else:
        raise MemoryError("unsupported task action")
    person["updatedAt"] = now
    return [person["id"]]


def _review(snapshot: Dict[str, Any], command: Dict[str, Any], actor: str, now: str) -> List[str]:
    person = _person(snapshot, str(command.get("personnelId", "")))
    required = ("assignmentType", "outcome", "verificationQuality", "reviewers", "evidencePaths")
    if any(not command.get(key) for key in required):
        raise MemoryError("review requires assignment type, outcome, verification quality, reviewers, and evidence paths")
    reviewers, evidence = command["reviewers"], command["evidencePaths"]
    if not isinstance(reviewers, list) or not all(isinstance(item, str) and item for item in reviewers):
        raise MemoryError("reviewers must be non-empty identities")
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item for item in evidence):
        raise MemoryError("review evidence paths must be non-empty")
    review_id = command.get("reviewId") or _stable_id("review", command.get("idempotencyKey", snapshot["revision"] + 1), person["id"], command["assignmentType"])
    if any(review["id"] == review_id for item in snapshot["personnel"] for review in item["reviews"]):
        raise MemoryError("review identity already exists")
    review = {
        "id": review_id,
        "assignmentType": str(command["assignmentType"]),
        "outcome": str(command["outcome"]),
        "revisionCause": str(command.get("revisionCause", "")),
        "verificationQuality": str(command["verificationQuality"]),
        "workingStyleImpact": str(command.get("workingStyleImpact", "")),
        "sourceClass": str(command["sourceClass"]),
        "reviewers": sorted(set(reviewers)),
        "evidencePaths": sorted(set(evidence)),
        "recordedAt": now,
    }
    person["reviews"].append(review)
    summary = command.get("performanceSummary")
    if summary is not None:
        if actor not in {"User", "Management"}:
            raise MemoryError("active performance summaries require user or Management authority")
        if not isinstance(summary, dict) or not isinstance(summary.get("reviewIds"), list) or len(set(summary["reviewIds"])) < 2:
            raise MemoryError("performance summaries require at least two review references")
        known = {item["id"] for item in person["reviews"]}
        if not set(summary["reviewIds"]).issubset(known):
            raise MemoryError("performance summary references unknown reviews")
        person["performanceSummaries"].append(
            {
                "assignmentType": str(summary.get("assignmentType", command["assignmentType"])),
                "observation": str(summary.get("observation", "")),
                "reviewIds": sorted(set(summary["reviewIds"])),
                "updatedAt": now,
            }
        )
    person["updatedAt"] = now
    return [person["id"]]


def _bootstrap_seat(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise MemoryError("each bootstrap seat requires a permanent role and seat")
    role, seat = value.get("role"), value.get("seat")
    if role not in {"Management", "Operations", "Consultant"}:
        raise MemoryError(
            "each permanent bootstrap seat must be Management, Operations, or an active Consultant"
        )
    if not isinstance(seat, str) or not seat:
        raise MemoryError("each bootstrap seat requires a permanent role and seat")
    normalized = {
        "role": role,
        "seat": seat,
        "specialty": str(value.get("specialty", "")),
    }
    if role == "Consultant":
        consultant_id = value.get("id")
        title = value.get("title")
        domain = value.get("domain")
        config_path = value.get("configPath")
        acceptance = value.get("acceptanceAuthority")
        if value.get("status") != "active":
            raise MemoryError("bootstrap task registration requires an active Consultant")
        expected_config = ".baton/agents/consultant-%s.toml" % consultant_id
        if (
            not isinstance(consultant_id, str)
            or not consultant_id
            or consultant_id != seat
            or not isinstance(title, str)
            or not title
            or not isinstance(domain, str)
            or not domain
            or config_path != expected_config
            or not isinstance(acceptance, str)
            or not acceptance
        ):
            raise MemoryError(
                "active Consultant bootstrap seats require stable id, title, domain, exact configPath, and acceptance authority"
            )
        normalized.update(
            {
                "id": consultant_id,
                "title": title,
                "domain": domain,
                "configPath": config_path,
                "acceptanceAuthority": acceptance,
                "status": "active",
                "specialty": domain,
            }
        )
    return normalized


def _permanent_task_role_label(seat: Dict[str, Any]) -> str:
    if seat["role"] != "Consultant":
        return seat["role"]
    title = seat["title"].strip()
    return title if title.casefold().endswith(" consultant") else title + " Consultant"


def _permanent_task_title(project_name: str, seat: Dict[str, Any], name: str) -> str:
    values = (project_name, _permanent_task_role_label(seat), name)
    if any(
        not isinstance(value, str)
        or not value.strip()
        or "\n" in value
        or "\r" in value
        for value in values
    ):
        raise MemoryError("permanent task title requires one-line project, role, and person names")
    return "(%s) - %s - %s" % tuple(value.strip() for value in values)


def _confirmed_project_name(project: Path, snapshot: Dict[str, Any]) -> str:
    if not snapshot["bootstrap"].get("confirmedAt"):
        raise MemoryError("project intent must be confirmed before team assembly")
    path = project / ".baton/state/project.json"
    if path.is_symlink() or not path.is_file():
        raise MemoryError("confirmed project state is missing or unsafe")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        project_name = record["project"]["name"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise MemoryError("confirmed project state is unreadable") from error
    if not isinstance(project_name, str) or not project_name.strip():
        raise MemoryError("confirmed project intent requires a project identity")
    return project_name.strip()


def _promoted_project_direction(
    project: Path, provisional: Dict[str, Any], now: str
) -> bytes:
    """Return schema-valid canonical project bytes for confirmed onboarding intent."""
    path = project / ".baton/state/project.json"
    schema = project / ".baton/schemas/project.schema.json"
    if path.is_symlink() or not path.is_file() or schema.is_symlink() or not schema.is_file():
        raise MemoryError("project confirmation requires safe canonical project state and schema")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MemoryError("canonical project state is unreadable") from error
    users = provisional["users"].strip()
    record["project"].update(
        {
            "name": provisional["identity"].strip(),
            "purpose": provisional["purpose"].strip(),
            "users": [users],
            "outcome": provisional["outcome"].strip(),
            "constraints": copy.deepcopy(provisional["constraints"]),
            "nonGoals": copy.deepcopy(provisional.get("nonGoals", [])),
            "principles": copy.deepcopy(provisional.get("principles", [])),
            "openQuestions": copy.deepcopy(provisional["unresolved"]),
            "assuranceDefaults": {
                "readinessProtocol": provisional["readinessProtocol"],
                "clearanceProtocol": provisional["clearanceProtocol"],
            },
            "templateMode": False,
            "lastVerified": now.split("T", 1)[0],
        }
    )
    try:
        errors = schema_errors(record, schema)
    except SchemaContractError as error:
        raise MemoryError("canonical project schema is invalid") from error
    if errors:
        raise MemoryError("confirmed project direction is invalid: %s" % "; ".join(errors))
    return _json_bytes(record)


def _fallback_prompt(seat: Dict[str, Any], name: str, task_title: str) -> str:
    identity = seat["role"]
    details = ""
    if seat["role"] == "Consultant":
        identity = "Consultant %s (%s)" % (seat["id"], seat["title"])
        details = (
            " Domain: %s. Exact configPath: %s. Acceptance boundary: %s"
            % (
                seat["domain"],
                seat["configPath"],
                seat["acceptanceAuthority"],
            )
        )
    return (
        "Create one permanent top-level task with the exact title %s. "
        "This task is for %s, named %s.%s "
        "Have it follow .baton/AGENTS.md, including every mandatory rule, validated state, "
        "and .baton/roles/%s.md. A new task message is its sole wake mechanism; "
        "it must never create or attach a persistent goal. Return the stable task ID "
        "and message wake path without starting speculative project work."
        % (task_title, identity, name, details, seat["role"].casefold())
    )


def _fallback_existing_task_prompt(task_title: str, needs_title: bool) -> str:
    if needs_title:
        return (
            "Set the already registered task's exact title to %s, read it back, "
            "and return its stable task ID and message wake path. Do not create a duplicate."
            % task_title
        )
    return (
        "Send the registration-complete wake to the already registered task, "
        "then return its stable task ID and message wake path. Do not create a duplicate."
    )


def _bootstrap(
    project: Path,
    snapshot: Dict[str, Any],
    command: Dict[str, Any],
    actor: str,
    now: str,
) -> Tuple[List[str], Optional[bytes]]:
    action = command.get("action")
    bootstrap = snapshot["bootstrap"]
    reset_personnel_ids: List[str] | None = None
    project_after: Optional[bytes] = None
    if action == "reset-onboarding":
        if actor != "User" or command.get("userApproved") is not True:
            raise MemoryError(
                "onboarding reset requires explicit user authorization"
            )
        if bootstrap.get("status") == "complete":
            raise MemoryError(
                "complete onboarding cannot be reset through the incomplete-onboarding path"
            )
        provisional = bootstrap.get("provisionalProject", {})
        previous_epoch = provisional.get("onboardingEpoch", 0)
        if not isinstance(previous_epoch, int) or previous_epoch < 0:
            raise MemoryError("bootstrap onboarding epoch is invalid")
        seed_prefix = bootstrap["seed"] + ":" if bootstrap["seed"] else ""
        roster_ids = set(bootstrap["roster"])
        reset_people = [
            person
            for person in snapshot["personnel"]
            if person["id"] in roster_ids
            or (
                seed_prefix
                and person["role"] in {"Management", "Operations", "Consultant"}
                and person.get("seed", "").startswith(seed_prefix)
            )
        ]
        reset_personnel_ids = [person["id"] for person in reset_people]
        cleanup_tasks = list(bootstrap.get("cleanupTasks", []))
        known_cleanup_ids = {item["taskId"] for item in cleanup_tasks}
        for person in reset_people:
            task = person.get("task", {})
            task_id = task.get("taskId", "")
            if task_id and task_id not in known_cleanup_ids:
                cleanup_tasks.append(
                    {
                        "personnelId": person["id"],
                        "taskId": task_id,
                        "wakePath": task.get("wakePath", ""),
                        "title": task.get("title")
                        or task.get("expectedTitle", ""),
                        "status": "archive-required",
                    }
                )
                known_cleanup_ids.add(task_id)
        removed = set(reset_personnel_ids)
        snapshot["personnel"] = [
            person for person in snapshot["personnel"] if person["id"] not in removed
        ]
        snapshot["claims"] = [
            claim
            for claim in snapshot["claims"]
            if "bootstrap" not in claim.get("assignmentTypes", [])
        ]
        bootstrap.update(
            {
                "status": "not-started",
                "roster": [],
                "provisionalProject": {"onboardingEpoch": previous_epoch + 1},
                "confirmedAt": "",
                "cleanupTasks": cleanup_tasks,
            }
        )
    elif action == "cleanup-complete":
        if actor != "User" or command.get("userApproved") is not True:
            raise MemoryError(
                "bootstrap task cleanup requires explicit user authorization"
            )
        task_id = command.get("taskId", "")
        cleanup_tasks = bootstrap.get("cleanupTasks", [])
        if not isinstance(task_id, str) or not any(
            item.get("taskId") == task_id for item in cleanup_tasks
        ):
            raise MemoryError("bootstrap cleanup task is not pending")
        if command.get("archiveConfirmed") is not True:
            raise MemoryError(
                "bootstrap cleanup can complete only after archival succeeds"
            )
        bootstrap["cleanupTasks"] = [
            item for item in cleanup_tasks if item.get("taskId") != task_id
        ]
    elif action == "start":
        _assert_bootstrap_coordinator(snapshot, command)
        seed = command.get("seed")
        if not isinstance(seed, str) or not seed:
            raise MemoryError("bootstrap requires a stable seed")
        if bootstrap["seed"] and bootstrap["seed"] != seed:
            raise MemoryError("bootstrap seed cannot be silently regenerated")
        bootstrap["seed"] = seed
        bootstrap["status"] = "in-progress"
    elif action == "project-preset":
        _assert_bootstrap_coordinator(snapshot, command)
        if actor != "User" and command.get("userApproved") is not True:
            raise MemoryError("project preset confirmation requires explicit user approval")
        preset = command.get("preset")
        seats = command.get("consultantSeats")
        listed_presets = _project_preset_ids(project)
        if (
            not isinstance(preset, str)
            or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", preset) is None
            or preset not in listed_presets
            or not isinstance(seats, list)
            or len(seats) != len(set(seats))
            or any(
                not isinstance(seat, str)
                or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", seat) is None
                for seat in seats
            )
        ):
            raise MemoryError(
                "project preset confirmation requires a valid preset and unique Consultant seats"
            )
        provisional = copy.deepcopy(bootstrap.get("provisionalProject", {}))
        mismatch = provisional.get("profileMismatch")
        if isinstance(mismatch, dict) and mismatch.get("status") == "proposed":
            mismatch = copy.deepcopy(mismatch)
            mismatch["status"] = (
                "accepted"
                if mismatch.get("recommendedPreset") == preset
                else "superseded"
            )
            mismatch["resolvedAt"] = now
            provisional["profileMismatch"] = mismatch
        provisional.update(
            {
                "projectPreset": preset,
                "projectPresetConfirmed": True,
                "consultantSeats": list(seats),
                "projectPresetEpoch": int(
                    provisional.get("projectPresetEpoch", 0)
                )
                + 1,
            }
        )
        bootstrap["provisionalProject"] = provisional
        known = {person["id"]: person for person in snapshot["personnel"]}
        bootstrap["roster"] = [
            personnel_id
            for personnel_id in bootstrap["roster"]
            if personnel_id in known and known[personnel_id]["role"] == "Management"
        ]
        bootstrap["status"] = "in-progress"
    elif action == "profile-mismatch":
        _assert_bootstrap_coordinator(snapshot, command)
        provisional = copy.deepcopy(bootstrap.get("provisionalProject", {}))
        configured_preset = provisional.get("projectPreset", "")
        if provisional.get("projectPresetConfirmed") is not True or not isinstance(
            configured_preset, str
        ) or not configured_preset:
            raise MemoryError(
                "profile mismatch requires a confirmed configured project preset"
            )
        recommended_preset = command.get("recommendedPreset", "")
        listed_presets = _project_preset_ids(project)
        if (
            not isinstance(recommended_preset, str)
            or re.fullmatch(
                r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", recommended_preset
            )
            is None
            or recommended_preset not in listed_presets
            or recommended_preset == configured_preset
        ):
            raise MemoryError(
                "profile mismatch requires a different listed recommended preset"
            )
        recommendation_status = command.get("recommendationStatus", "proposed")
        if recommendation_status == "proposed":
            evidence = command.get("evidence")
            evidence_basis = command.get("evidenceBasis")
            if evidence_basis not in {"explicit-user", "discoverable-project-facts"}:
                raise MemoryError(
                    "profile mismatch recommendation requires an explicit-user or discoverable-project-facts evidence basis"
                )
            minimum_evidence = 1 if evidence_basis == "explicit-user" else 2
            if (
                not isinstance(evidence, list)
                or not minimum_evidence <= len(evidence) <= 4
                or any(
                    not isinstance(value, str)
                    or not value.strip()
                    or len(value.strip()) > 240
                    for value in evidence
                )
            ):
                raise MemoryError(
                    "profile mismatch recommendation requires one to four concise evidence statements"
                )
            normalized_evidence = sorted(value.strip() for value in evidence)
            if len(normalized_evidence) != len(set(normalized_evidence)):
                raise MemoryError(
                    "profile mismatch recommendation evidence contains a duplicate"
                )
            fingerprint = _profile_mismatch_fingerprint(
                configured_preset,
                recommended_preset,
                evidence_basis,
                normalized_evidence,
            )
            existing = provisional.get("profileMismatch")
            rejected_fingerprints = provisional.get(
                "rejectedProfileMismatchFingerprints", []
            )
            if (
                not isinstance(rejected_fingerprints, list)
                or any(
                    not isinstance(value, str) or not value
                    for value in rejected_fingerprints
                )
                or len(rejected_fingerprints) != len(set(rejected_fingerprints))
            ):
                raise MemoryError("rejected profile recommendation history is invalid")
            if isinstance(existing, dict) and existing.get("status") == "proposed":
                raise MemoryError(
                    "active profile recommendation must be resolved before another is proposed"
                )
            if (
                fingerprint in rejected_fingerprints
                or (
                    isinstance(existing, dict)
                    and existing.get("status") == "rejected"
                    and existing.get("configuredPreset") == configured_preset
                    and existing.get("recommendedPreset") == recommended_preset
                    and existing.get("evidenceFingerprint") == fingerprint
                )
            ):
                raise MemoryError(
                    "profile recommendation was already rejected for unchanged evidence"
                )
            provisional["profileMismatch"] = {
                "configuredPreset": configured_preset,
                "recommendedPreset": recommended_preset,
                "evidence": normalized_evidence,
                "evidenceBasis": evidence_basis,
                "evidenceFingerprint": fingerprint,
                "status": "proposed",
                "proposedAt": now,
                "resolvedAt": "",
            }
        elif recommendation_status == "rejected":
            if actor != "User" and command.get("userApproved") is not True:
                raise MemoryError(
                    "profile recommendation rejection requires explicit user approval"
                )
            existing = provisional.get("profileMismatch")
            if (
                not isinstance(existing, dict)
                or existing.get("status") != "proposed"
                or existing.get("configuredPreset") != configured_preset
                or existing.get("recommendedPreset") != recommended_preset
            ):
                raise MemoryError(
                    "profile recommendation rejection must match the active proposal"
                )
            existing = copy.deepcopy(existing)
            existing["status"] = "rejected"
            existing["resolvedAt"] = now
            provisional["profileMismatch"] = existing
            rejected_fingerprints = provisional.get(
                "rejectedProfileMismatchFingerprints", []
            )
            if not isinstance(rejected_fingerprints, list) or any(
                not isinstance(value, str) or not value
                for value in rejected_fingerprints
            ):
                raise MemoryError("rejected profile recommendation history is invalid")
            provisional["rejectedProfileMismatchFingerprints"] = sorted(
                set(rejected_fingerprints + [existing["evidenceFingerprint"]])
            )
        else:
            raise MemoryError(
                "profile mismatch status must be proposed or rejected"
            )
        bootstrap["provisionalProject"] = provisional
    elif action == "provisional":
        _assert_bootstrap_coordinator(snapshot, command)
        values = command.get("project")
        if not isinstance(values, dict):
            raise MemoryError("bootstrap provisional project must be an object")
        project_fields = {
            "identity",
            "purpose",
            "users",
            "outcome",
            "constraints",
            "nonGoals",
            "principles",
            "unresolved",
            "readinessProtocol",
            "clearanceProtocol",
        }
        if not set(values).issubset(project_fields):
            raise MemoryError(
                "bootstrap project answers cannot modify control metadata"
            )
        provisional = copy.deepcopy(bootstrap.get("provisionalProject", {}))
        provisional.update(copy.deepcopy(values))
        if command.get("ready") is True and not _project_intent_complete(
            provisional
        ):
            raise MemoryError(
                "project intent requires identity, purpose, users, outcome, constraints, unresolved items, Readiness Protocol, and Clearance Protocol"
            )
        bootstrap["provisionalProject"] = provisional
        bootstrap["status"] = "ready-for-confirmation" if command.get("ready") is True else "in-progress"
    elif action == "confirm":
        _assert_bootstrap_coordinator(snapshot, command)
        if actor != "User" and command.get("userApproved") is not True:
            raise MemoryError("bootstrap completion requires explicit user confirmation")
        if not bootstrap["provisionalProject"]:
            raise MemoryError("bootstrap has no provisional project to confirm")
        if bootstrap["provisionalProject"].get("projectPresetConfirmed") is not True:
            raise MemoryError("project preset must be confirmed before project intent")
        if not _has_preferred_name(snapshot):
            raise MemoryError("preferred name must be confirmed before project intent")
        if bootstrap["status"] != "ready-for-confirmation":
            raise MemoryError("project intent is not ready for confirmation")
        if not _project_intent_complete(bootstrap["provisionalProject"]):
            raise MemoryError(
                "project intent requires identity, purpose, users, outcome, constraints, unresolved items, Readiness Protocol, and Clearance Protocol"
            )
        project_after = _promoted_project_direction(
            project, bootstrap["provisionalProject"], now
        )
        provisional = copy.deepcopy(bootstrap["provisionalProject"])
        for field in (
            "identity",
            "purpose",
            "users",
            "outcome",
            "constraints",
            "nonGoals",
            "principles",
            "unresolved",
            "readinessProtocol",
            "clearanceProtocol",
        ):
            provisional.pop(field, None)
        bootstrap["provisionalProject"] = provisional
        bootstrap["confirmedAt"] = now
        _refresh_bootstrap_readiness(snapshot)
    elif action == "needs-integration":
        bootstrap["status"] = "needs-integration"
    elif action == "roster":
        roster = command.get("personnelIds")
        known = {person["id"]: person for person in snapshot["personnel"]}
        if not isinstance(roster, list) or not set(roster).issubset(known):
            raise MemoryError("bootstrap roster must reference known personnel")
        selected = [known[personnel_id] for personnel_id in roster]
        if any(
            person["role"] not in {"Management", "Operations", "Consultant"}
            or person["employmentStatus"] not in {"active", "awaiting-task", "rehired"}
            for person in selected
        ):
            raise MemoryError(
                "bootstrap roster accepts active Management, Operations, and Consultant seats only"
            )
        bootstrap["roster"] = list(dict.fromkeys(roster))
        _refresh_bootstrap_readiness(snapshot)
    elif action in {"reconcile-native", "reconcile-fallback"}:
        seed = command.get("seed") or bootstrap["seed"]
        seats = command.get("seats")
        if not isinstance(seed, str) or not seed or not isinstance(seats, list):
            raise MemoryError("bootstrap reconciliation requires a stable seed and seat list")
        if bootstrap["seed"] and bootstrap["seed"] != seed:
            raise MemoryError("bootstrap seed cannot be silently regenerated")
        bootstrap["seed"] = seed
        provisional = copy.deepcopy(bootstrap.get("provisionalProject", {}))
        invocation_task_id = command.get("invocationTaskId", "")
        registered_coordinator = provisional.get("coordinatorTaskId", "")
        if not bootstrap.get("confirmedAt") or registered_coordinator:
            if not isinstance(invocation_task_id, str) or not invocation_task_id.strip():
                raise MemoryError(
                    "bootstrap reconciliation requires the invoking task identity"
                )
            invocation_task_id = invocation_task_id.strip()
            legacy_partial = (
                not registered_coordinator
                and bootstrap.get("status") != "not-started"
                and bool(
                    bootstrap.get("roster")
                    or {
                        key: value
                        for key, value in provisional.items()
                        if key not in {"onboardingEpoch"}
                    }
                )
            )
            if legacy_partial:
                raise MemoryError(
                    "legacy incomplete onboarding requires an explicit reset before restart"
                )
            if registered_coordinator and invocation_task_id != registered_coordinator:
                raise MemoryError(
                    "bootstrap onboarding must continue in its original invoking task"
                )
            provisional["coordinatorTaskId"] = invocation_task_id
            bootstrap["provisionalProject"] = provisional
        normalized = [_bootstrap_seat(seat) for seat in seats]
        if normalized and not bootstrap.get("confirmedAt"):
            raise MemoryError("project intent must be confirmed before team assembly")
        project_name = _confirmed_project_name(project, snapshot) if normalized else ""
        keys = [(seat["role"], seat["seat"]) for seat in normalized]
        if len(keys) != len(set(keys)):
            raise MemoryError("bootstrap seat list contains a duplicate")
        roster = []
        for seat in normalized:
            person_seed = "%s:%s:%s:%s" % (
                seed,
                seat["role"],
                seat["seat"],
                seat.get("specialty", ""),
            )
            personnel_ids = _personnel(
                snapshot,
                {
                    "action": "ensure",
                    "role": seat["role"],
                    "seat": seat["seat"],
                    "specialty": seat.get("specialty", ""),
                    "seed": person_seed,
                },
                actor,
                now,
            )
            person = _person(snapshot, personnel_ids[0])
            if person["employmentStatus"] in {"former", "retired", "replaced"}:
                person["employmentStatus"] = "rehired"
                person["task"]["status"] = (
                    "created" if person["task"].get("taskId") else "unregistered"
                )
                person["task"]["wokenAt"] = ""
                person["updatedAt"] = now
            task_title = _permanent_task_title(project_name, seat, person["name"])
            person["task"]["expectedTitle"] = task_title
            roster.append(person["id"])
            predecessors_ready = all(
                _person(snapshot, personnel_id)["task"].get("status") == "online"
                for personnel_id in roster[:-1]
            )
            if (
                action == "reconcile-native"
                and predecessors_ready
                and not person["task"].get("taskId")
                and person["task"].get("status")
                in {"unregistered", "inactive", "awaiting-task"}
            ):
                _reserve_task_attempt(
                    person,
                    "%s:%s:%s"
                    % (
                        provisional.get("onboardingEpoch", 0),
                        provisional.get("projectPresetEpoch", 0),
                        person["id"],
                    ),
                )
            if (
                action == "reconcile-fallback"
                and not person["task"].get("taskId")
                and person["task"]["status"] != "online"
            ):
                _task(
                    snapshot,
                    {
                        "action": "awaiting",
                        "personnelId": person["id"],
                        "prompt": _fallback_prompt(seat, person["name"], task_title),
                    },
                    now,
                )
        bootstrap["roster"] = roster
        if bootstrap["status"] != "ready-for-confirmation":
            bootstrap["status"] = "in-progress"
        _refresh_bootstrap_readiness(snapshot)
    else:
        raise MemoryError("unsupported bootstrap action")
    return (
        (
            sorted(reset_personnel_ids)
            if reset_personnel_ids is not None
            else list(bootstrap["roster"])
        ),
        project_after,
    )


def _redact_event(event: Dict[str, Any], needles: List[str]) -> Dict[str, Any]:
    """Redact value-bearing event references without corrupting chain identities."""
    updated = copy.deepcopy(event)
    references = []
    for reference in updated.get("references", []):
        for needle in needles:
            if needle:
                reference = reference.replace(needle, "[redacted]")
        references.append(reference)
    updated["references"] = references
    return updated


def _apply(
    project: Path,
    snapshot: Dict[str, Any],
    events: List[Dict[str, Any]],
    command: Dict[str, Any],
) -> Tuple[List[str], List[str], str, bool, Optional[bytes]]:
    actor, actor_id, operation = _authority(command, snapshot)
    now = _timestamp(command)
    claim_ids = []
    personnel_ids = []
    result = "updated"
    redacted = False
    project_after: Optional[bytes] = None
    if operation == "candidate" and command.get("action") == "reject":
        claim = _claim(snapshot, str(command.get("claimId", "")))
        if claim["status"] != "pending-confirmation":
            raise MemoryError("only a pending candidate can be rejected")
        if claim["category"] in {"user", "preference"} and actor != "User" and command.get("userApproved") is not True:
            raise MemoryError("personal candidate rejection requires user authority")
        if actor not in {"User", "Management"}:
            raise MemoryError("candidate rejection requires user or Management authority")
        snapshot["claims"] = [item for item in snapshot["claims"] if item["id"] != claim["id"]]
        claim_ids = [claim["id"]]
        result = "rejected"
    elif operation in {"remember", "candidate"}:
        if (
            operation == "remember"
            and "bootstrap" in command.get("assignmentTypes", [])
        ):
            _assert_bootstrap_coordinator(snapshot, command)
        claim = _new_claim(snapshot, command, actor, actor_id, now, operation == "candidate")
        snapshot["claims"].append(claim)
        claim_ids = [claim["id"]]
        result = "recorded"
    elif operation == "confirm":
        claim = _claim(snapshot, str(command.get("claimId", "")))
        if claim["status"] != "pending-confirmation":
            raise MemoryError("only a pending candidate can be confirmed")
        if claim["category"] in {"user", "preference"} and actor != "User" and command.get("userApproved") is not True:
            raise MemoryError("personal candidates require explicit user confirmation")
        if actor not in {"User", "Management"}:
            raise MemoryError("candidate confirmation requires user or Management authority")
        claim["status"] = "confirmed"
        claim["updatedAt"] = now
        claim_ids = [claim["id"]]
        result = "confirmed"
    elif operation == "correct":
        old = _claim(snapshot, str(command.get("claimId", "")))
        if old["category"] in {"user", "preference"} and actor != "User" and command.get("userApproved") is not True:
            raise MemoryError("personal correction requires explicit user approval")
        if actor in {"Consultant", "Contractor"}:
            raise MemoryError("Consultants and Contractors may propose candidates, not correct confirmed memory")
        old["status"] = "superseded"
        old["updatedAt"] = now
        replacement_command = dict(command)
        replacement_command.update(
            {
                "category": command.get("category", old["category"]),
                "subject": command.get("subject", old["subject"]),
                "sourceClass": command.get("sourceClass", old["source"]["class"]),
                "roleRelevance": command.get("roleRelevance", old["roleRelevance"]),
                "assignmentTypes": command.get("assignmentTypes", old["assignmentTypes"]),
                "importance": command.get("importance", old["importance"]),
                "supersedesClaimId": old["id"],
            }
        )
        replacement_command.pop("claimId", None)
        replacement = _new_claim(snapshot, replacement_command, actor, actor_id, now, False)
        snapshot["claims"].append(replacement)
        claim_ids = [old["id"], replacement["id"]]
        result = "corrected"
    elif operation == "forget":
        requested = command.get("claimIds")
        if not isinstance(requested, list) or not requested:
            raise MemoryError("forget requires one or more claimIds")
        selected = [claim for claim in snapshot["claims"] if claim["id"] in set(requested)]
        if len(selected) != len(set(requested)):
            raise MemoryError("one or more requested claims do not exist")
        if actor != "User" and any(claim["category"] in {"user", "preference"} for claim in selected):
            raise MemoryError("forgetting personal memory requires user authority")
        needles = [claim["statement"] for claim in selected]
        matching = {
            claim["id"]
            for claim in snapshot["claims"]
            if claim["status"] == "pending-confirmation"
            and any(
                claim["subject"] == forgotten["subject"]
                and claim["statement"] == forgotten["statement"]
                for forgotten in selected
            )
        }
        removed = set(requested) | matching
        snapshot["claims"] = [claim for claim in snapshot["claims"] if claim["id"] not in removed]
        events[:] = [_redact_event(event, needles) for event in events]
        claim_ids = sorted(removed)
        result = "forgotten"
        redacted = True
    elif operation == "personnel":
        personnel_ids = _personnel(snapshot, command, actor, now)
    elif operation == "task":
        personnel_ids = _task(snapshot, command, now)
    elif operation == "review":
        personnel_ids = _review(snapshot, command, actor, now)
    elif operation == "bootstrap":
        personnel_ids, project_after = _bootstrap(
            project, snapshot, command, actor, now
        )
    references = command.get("references", [])
    if not isinstance(references, list) or not all(isinstance(item, str) and item for item in references):
        raise MemoryError("references must be non-empty strings")
    next_revision = snapshot["revision"] + 1
    previous = events[-1]["eventId"] if events else ""
    event_id = _stable_id("event", next_revision, command.get("idempotencyKey", ""), operation, actor, now)
    source_class = command.get("sourceClass") or (
        snapshot["claims"][-1]["source"]["class"]
        if operation in {"remember", "correct"}
        or (operation == "candidate" and command.get("action") != "reject")
        else "system"
    )
    event = {
        "schemaVersion": 1,
        "recordType": "memory-event",
        "revision": next_revision,
        "eventId": event_id,
        "previousEventId": previous,
        "operation": operation,
        "actor": actor,
        "actorId": actor_id,
        "timestamp": now,
        "claimIds": sorted(set(claim_ids)),
        "personnelIds": sorted(set(personnel_ids)),
        "references": sorted(set(references)),
        "details": {"result": result, "sourceClass": source_class, "redacted": redacted},
    }
    events.append(event)
    snapshot["revision"] = next_revision
    snapshot["historyHead"] = {"revision": next_revision, "eventId": event_id, "sha256": _sha256(_line_bytes(event))}
    snapshot["updatedAt"] = now
    key = command.get("idempotencyKey")
    if key:
        snapshot["idempotencyKeys"].append(_idempotency_binding(key, command))
    return claim_ids, personnel_ids, result, redacted, project_after


def prepare_under_lock(root: Path, command: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare validated memory bytes for a caller already holding the shared lock."""
    if not isinstance(command, dict):
        raise MemoryError("memory command must be an object")
    _reject_sensitive(command)
    _reject_forbidden_authorities(command)
    project, memory_path, history_path, schemas = _paths(Path(root))
    _recover_interrupted(project, memory_path, history_path)
    snapshot, events, history_before, _, _, _ = _load(project)
    expected = command.get("expectedRevision")
    if type(expected) is not int:
        raise MemoryError("expectedRevision is required")
    key = command.get("idempotencyKey")
    if key is not None and (
        not isinstance(key, str) or not key or len(key) > 200
    ):
        raise MemoryError(
            "idempotencyKey must be a non-empty string of at most 200 characters"
        )
    if key:
        key_prefix = "v1:%s:" % _sha256(key.encode("utf-8"))
        binding = _idempotency_binding(key, command)
        existing_bindings = [
            item
            for item in snapshot["idempotencyKeys"]
            if item.startswith(key_prefix)
        ]
        if existing_bindings:
            if binding not in existing_bindings:
                raise MemoryError(
                    "idempotencyKey was already used for different request semantics"
                )
            return {
                "changed": False,
                "idempotent": True,
                "snapshot": snapshot,
                "events": events,
                "historyBefore": history_before,
                "historyAfter": history_before,
                "memoryAfter": _json_bytes(snapshot),
                "projection": _projection(snapshot, events),
                "claimIds": [],
                "personnelIds": [],
                "result": "unchanged",
                "redacted": False,
                "projectAfter": None,
            }
        if key in snapshot["idempotencyKeys"]:
            raise MemoryError(
                "unbound legacy idempotencyKey cannot be replayed safely"
            )
    if expected != snapshot["revision"]:
        raise MemoryError("expected revision does not match current memory revision")
    proposed = copy.deepcopy(snapshot)
    proposed_events = copy.deepcopy(events)
    claim_ids, personnel_ids, result, redacted, project_after = _apply(
        project, proposed, proposed_events, command
    )
    history_after = b"".join(_line_bytes(event) for event in proposed_events)
    memory_after = _json_bytes(proposed)
    _validate(proposed, proposed_events, history_after, schemas)
    return {
        "changed": True,
        "idempotent": False,
        "snapshot": proposed,
        "events": proposed_events,
        "historyBefore": history_before,
        "historyAfter": history_after,
        "memoryAfter": memory_after,
        "projection": _projection(proposed, proposed_events),
        "claimIds": sorted(set(claim_ids)),
        "personnelIds": sorted(set(personnel_ids)),
        "result": result,
        "redacted": redacted,
        "projectAfter": project_after,
    }


def _transaction_directory(root: Path, transaction_id: str) -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).expanduser().resolve()
    project_id = _sha256(str(root.resolve()).encode("utf-8"))[:16]
    target = (state_home / "baton" / project_id / "memory" / transaction_id).resolve(strict=False)
    project = root.resolve()
    if target == project or project in target.parents:
        raise MemoryError("memory transaction evidence must stay outside the working tree")
    return target


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=".%s." % path.name, dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _starter_snapshot() -> Dict[str, Any]:
    return {
        "schemaVersion": 1,
        "recordType": "memory",
        "revision": 0,
        "historyHead": {
            "revision": 0,
            "eventId": "",
            "sha256": EMPTY_SHA256,
        },
        "claims": [],
        "personnel": [],
        "bootstrap": {
            "status": "not-started",
            "seed": "",
            "roster": [],
            "provisionalProject": {},
            "confirmedAt": "",
        },
        "settings": {
            "automaticContextMaxClaims": 10,
            "automaticContextMaxUtf8Bytes": 1800,
            "automaticContextMaxEstimatedTokens": 600,
            "allowSensitiveMemory": False,
            "historyCompaction": False,
        },
        "idempotencyKeys": [],
        "updatedAt": "1970-01-01T00:00:00+00:00",
    }


def _initialization_metadata(
    project: Path,
) -> Tuple[Path, Optional[bytes], Optional[bytes]]:
    """Return the installed metadata update that classifies memory as project-owned."""
    metadata_path = project / ".baton/metadata.json"
    if not metadata_path.exists() and not metadata_path.is_symlink():
        return metadata_path, None, None
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise MemoryError("memory initialization requires safe installed Baton metadata")
    before = metadata_path.read_bytes()
    try:
        metadata = json.loads(before.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MemoryError("installed Baton metadata is unreadable") from error
    managed = metadata.get("managedFiles")
    owned = metadata.get("projectOwnedFiles")
    if not isinstance(managed, dict) or not isinstance(owned, list):
        raise MemoryError("installed Baton metadata has invalid ownership records")
    paths = {".baton/memory/memory.json", ".baton/memory/history.jsonl"}
    if paths.intersection(managed):
        raise MemoryError("project-owned memory cannot also be Baton-managed")
    if not all(isinstance(path, str) and path for path in owned):
        raise MemoryError("installed Baton project-owned paths are invalid")
    metadata["projectOwnedFiles"] = sorted(set(owned).union(paths))
    return metadata_path, before, _json_bytes(metadata)


def initialize(root: Path) -> Dict[str, Any]:
    """Explicitly initialize absent project-owned memory without overwriting it."""
    project, memory_path, history_path, schemas = _paths(Path(root))
    memory_dir = memory_path.parent
    try:
        with mutation_lock(project, "memory-initialize"):
            _recover_interrupted(project, memory_path, history_path)
            memory_present = memory_path.is_file() and not memory_path.is_symlink()
            history_present = history_path.is_file() and not history_path.is_symlink()
            if memory_present and history_present:
                snapshot, events, _, _, _, _ = _load(project)
                return {
                    "ok": True,
                    "changed": False,
                    "idempotent": True,
                    "revision": snapshot["revision"],
                    "historyEvents": len(events),
                }
            if (
                memory_path.exists()
                or memory_path.is_symlink()
                or history_path.exists()
                or history_path.is_symlink()
            ):
                raise MemoryError(
                    "memory initialization collision: both authoritative files must be absent or valid"
                )
            baton_dir = project / ".baton"
            if baton_dir.is_symlink() or not baton_dir.is_dir():
                raise MemoryError("memory initialization requires a safe .baton directory")
            if memory_dir.exists() and (memory_dir.is_symlink() or not memory_dir.is_dir()):
                raise MemoryError("memory initialization collision: memory path is unsafe")
            schema_source = schemas
            if schemas.is_symlink():
                schema_source = _source_repository_projection(
                    project,
                    schemas,
                    "template/.baton/schemas",
                    "memory initialization requires installed memory schemas",
                )
            if not schema_source.is_dir():
                raise MemoryError("memory initialization requires installed memory schemas")

            snapshot = _starter_snapshot()
            memory_after = _json_bytes(snapshot)
            history_after = b""
            metadata_path, metadata_before, metadata_after = _initialization_metadata(project)
            _validate(snapshot, [], history_after, schemas)
            generated = _generated_views(
                project,
                snapshot,
                [],
                metadata_after=metadata_after,
            )
            generated_metadata = generated.pop(".baton/metadata.json", None)
            if generated_metadata is not None:
                metadata_after = generated_metadata
            paths = {
                "memory": memory_path,
                "history": history_path,
                **(
                    {"metadata": metadata_path}
                    if metadata_after is not None
                    else {}
                ),
                **(
                    {"dashboard": project / ".baton/views/dashboard.html"}
                    if ".baton/views/dashboard.html" in generated
                    else {}
                ),
                **(
                    {"teamTasks": project / ".baton/views/team-tasks.md"}
                    if ".baton/views/team-tasks.md" in generated
                    else {}
                ),
            }
            after = {
                "memory": memory_after,
                "history": history_after,
                **(
                    {"metadata": metadata_after}
                    if metadata_after is not None
                    else {}
                ),
                **(
                    {"dashboard": generated[".baton/views/dashboard.html"]}
                    if ".baton/views/dashboard.html" in generated
                    else {}
                ),
                **(
                    {"teamTasks": generated[".baton/views/team-tasks.md"]}
                    if ".baton/views/team-tasks.md" in generated
                    else {}
                ),
            }
            before: Dict[str, Optional[bytes]] = {
                "memory": None,
                "history": None,
            }
            if metadata_after is not None:
                before["metadata"] = metadata_before
            for name in ("dashboard", "teamTasks"):
                if name not in paths:
                    continue
                path = paths[name]
                if path.is_symlink() or not path.is_file():
                    raise MemoryError(
                        "memory initialization generated view is missing or unsafe"
                    )
                before[name] = path.read_bytes()
            transaction_id = "memory-init-%s-%s" % (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                uuid.uuid4().hex[:8],
            )
            transaction = _transaction_directory(project, transaction_id)
            backup = transaction / "backup"
            backup.mkdir(parents=True, exist_ok=False)
            backup_names = {
                "metadata": "metadata.json",
                "dashboard": "dashboard.html",
                "teamTasks": "team-tasks.md",
            }
            for name, content in before.items():
                if content is not None:
                    _atomic_write(backup / backup_names[name], content)
            report_path = transaction / "memory-report.json"
            report = {
                "schemaVersion": 1,
                "transactionId": transaction_id,
                "operation": "initialize",
                "beforeSha256": {
                    name: _sha256(content) if content is not None else None
                    for name, content in before.items()
                },
                "afterSha256": {
                    name: _sha256(content) for name, content in after.items()
                },
                "backupPath": str(backup),
                "rollbackLocation": str(backup),
                "reportPath": str(report_path),
                "result": "prepared",
            }
            _write_report(report_path, report)
            created_directory = not memory_dir.exists()
            try:
                memory_dir.mkdir(parents=False, exist_ok=True)
                _atomic_write(history_path, history_after)
                if os.environ.get("BATON_TEST_MEMORY_INIT_EXIT_AFTER") == "after-history":
                    os._exit(98)
                if os.environ.get("BATON_TEST_MEMORY_INIT_FAIL_AT") == "after-history":
                    raise OSError("injected memory initialization failure after history replacement")
                for name in ("dashboard", "teamTasks", "metadata"):
                    if name in after:
                        _atomic_write(paths[name], after[name])
                _atomic_write(memory_path, memory_after)
                if os.environ.get("BATON_TEST_MEMORY_INIT_EXIT_AFTER") == "after-memory":
                    os._exit(98)
                if os.environ.get("BATON_TEST_MEMORY_INIT_FAIL_AT") == "after-memory":
                    raise OSError("injected memory initialization failure after memory replacement")
                checked, checked_events, checked_raw, _, _, _ = _load(project)
                if checked != snapshot or checked_events or checked_raw != history_after:
                    raise MemoryError("initialized memory did not validate byte-for-byte")
            except BaseException as error:
                for name, path in paths.items():
                    content = before[name]
                    if content is None:
                        path.unlink(missing_ok=True)
                    else:
                        _atomic_write(path, content)
                if created_directory:
                    try:
                        memory_dir.rmdir()
                    except OSError:
                        pass
                report["result"] = "rolled-back"
                report["errorClass"] = type(error).__name__
                _write_report(report_path, report)
                raise MemoryError(
                    "memory initialization failed and was rolled back; external recovery evidence is available"
                ) from error
            report["result"] = "committed"
            _write_report(report_path, report)
            return {
                "ok": True,
                "changed": True,
                "idempotent": False,
                "revision": 0,
                "historyEvents": 0,
                "transactionId": transaction_id,
                "reportPath": str(report_path),
                "backupPath": str(backup),
                "rollbackLocation": str(backup),
            }
    except MutationLockError as error:
        raise MemoryError("shared mutation lock failed: %s" % error) from error


def _write_report(path: Path, report: Dict[str, Any]) -> None:
    _atomic_write(path, _json_bytes(report))


def _artifact_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not relative:
        raise MemoryError("memory transaction report contains an unsafe artifact path")
    resolved = (root / candidate).resolve(strict=False)
    project = root.resolve()
    if resolved != project and project not in resolved.parents:
        raise MemoryError("memory transaction artifact escapes the project")
    return resolved


def _recover_interrupted(
    root: Path, memory_path: Path, history_path: Path
) -> List[Dict[str, str]]:
    base = _transaction_directory(root, "placeholder").parent
    if not base.is_dir():
        return []
    recovered: List[Dict[str, str]] = []
    for transaction in sorted(base.iterdir()):
        report_path = transaction / "memory-report.json"
        if not report_path.is_file():
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MemoryError("an external memory transaction report is unreadable") from error
        if report.get("result") != "prepared":
            continue

        def finish_recovery(result: str) -> None:
            report["result"] = result
            _write_report(report_path, report)
            recovered.append(
                {
                    "transactionId": str(report.get("transactionId", transaction.name)),
                    "result": result,
                    "reportPath": str(report_path),
                }
            )

        if report.get("operation") == "initialize":
            current = {}
            paths = {
                "memory": memory_path,
                "history": history_path,
                "metadata": root / ".baton/metadata.json",
                "dashboard": root / ".baton/views/dashboard.html",
                "teamTasks": root / ".baton/views/team-tasks.md",
            }
            before = report.get("beforeSha256")
            after = report.get("afterSha256")
            if not isinstance(before, dict) or not isinstance(after, dict):
                raise MemoryError("interrupted memory initialization report is invalid")
            names = tuple(before)
            if set(names) != set(after) or not set(names).issubset(paths):
                raise MemoryError("interrupted memory initialization artifact map is invalid")
            for name in names:
                path = paths[name]
                if path.is_symlink() or (path.exists() and not path.is_file()):
                    raise MemoryError(
                        "interrupted memory initialization left an unsafe artifact"
                    )
                current[name] = _sha256(path.read_bytes()) if path.is_file() else None
            if current == after:
                finish_recovery("committed-recovered")
                continue
            if current == before:
                finish_recovery("rolled-back-recovered")
                continue
            if all(current.get(name) in {before.get(name), after.get(name)} for name in names):
                backup_names = {
                    "metadata": "metadata.json",
                    "dashboard": "dashboard.html",
                    "teamTasks": "team-tasks.md",
                }
                for name in names:
                    path = paths[name]
                    if before.get(name) is None:
                        path.unlink(missing_ok=True)
                        continue
                    backup_name = backup_names.get(name)
                    if backup_name is None:
                        raise MemoryError(
                            "interrupted memory initialization backup map is invalid"
                        )
                    artifact_backup = transaction / "backup" / backup_name
                    if artifact_backup.is_symlink() or not artifact_backup.is_file():
                        raise MemoryError(
                            "interrupted memory initialization backup is missing"
                        )
                    content = artifact_backup.read_bytes()
                    if _sha256(content) != before[name]:
                        raise MemoryError(
                            "interrupted memory initialization backup is invalid"
                        )
                    _atomic_write(path, content)
                try:
                    memory_path.parent.rmdir()
                except OSError:
                    pass
                finish_recovery("rolled-back-recovered")
                continue
            raise MemoryError(
                "unrecognized interrupted memory initialization; inspect external recovery evidence"
            )
        artifacts = report.get("artifacts")
        if isinstance(artifacts, dict) and artifacts:
            current_artifacts = {}
            for relative, record in artifacts.items():
                if not isinstance(record, dict):
                    raise MemoryError("memory transaction artifact report is invalid")
                path = _artifact_path(root, relative)
                if path.is_symlink() or not path.is_file():
                    raise MemoryError("memory transaction artifact is missing or unsafe")
                current_artifacts[relative] = _sha256(path.read_bytes())
            if all(
                current_artifacts[relative] == record.get("afterSha256")
                for relative, record in artifacts.items()
            ):
                finish_recovery("committed-recovered")
                continue
            if all(
                current_artifacts[relative] == record.get("beforeSha256")
                for relative, record in artifacts.items()
            ):
                finish_recovery("rolled-back-recovered")
                continue
            if all(
                current_artifacts[relative]
                in {record.get("beforeSha256"), record.get("afterSha256")}
                for relative, record in artifacts.items()
            ):
                backup = transaction / "backup"
                for relative, record in artifacts.items():
                    backup_name = record.get("backupName")
                    if not isinstance(backup_name, str) or not backup_name:
                        raise MemoryError("memory transaction backup map is invalid")
                    backup_path = backup / backup_name
                    if not backup_path.is_file() or backup_path.is_symlink():
                        raise MemoryError("memory transaction backup is missing or unsafe")
                    _atomic_write(_artifact_path(root, relative), backup_path.read_bytes())
                finish_recovery("rolled-back-recovered")
                continue
            raise MemoryError(
                "unrecognized interrupted memory transaction; inspect external recovery evidence"
            )
        current = {
            "memory": _sha256(memory_path.read_bytes()),
            "history": _sha256(history_path.read_bytes()),
        }
        if current == report.get("afterSha256"):
            finish_recovery("committed-recovered")
            continue
        before = report.get("beforeSha256")
        if current == before:
            finish_recovery("rolled-back-recovered")
            continue
        backup = transaction / "backup"
        if current.get("memory") == before.get("memory") and current.get("history") == report.get("afterSha256", {}).get("history"):
            _atomic_write(history_path, (backup / "history.jsonl").read_bytes())
            finish_recovery("rolled-back-recovered")
            continue
        raise MemoryError("unrecognized interrupted memory transaction; inspect external recovery evidence")
    return recovered


def recover_interrupted_transactions(root: Path) -> Dict[str, Any]:
    """Recover fully recognized interrupted Memory transactions under the shared lock."""
    project, memory_path, history_path, _ = _paths(Path(root))
    try:
        with mutation_lock(project, "memory-recover"):
            recovered = _recover_interrupted(project, memory_path, history_path)
    except MutationLockError as error:
        raise MemoryError("shared mutation lock failed: %s" % error) from error
    return {
        "ok": True,
        "recovered": recovered,
        "recoveredCount": len(recovered),
    }


def transact(root: Path, command: Dict[str, Any]) -> Dict[str, Any]:
    """Apply one authority-checked expected-revision mutation under the shared lock."""
    if not isinstance(command, dict):
        raise MemoryError("memory command must be an object")
    project, memory_path, history_path, _ = _paths(Path(root))
    try:
        with mutation_lock(project, "memory-%s" % str(command.get("operation", "unknown"))):
            prepared = prepare_under_lock(project, command)
            proposed = prepared["snapshot"]
            proposed_events = prepared["events"]
            if not prepared["changed"]:
                return {
                    "ok": True,
                    "changed": False,
                    "idempotent": True,
                    "revision": proposed["revision"],
                    "projection": prepared["projection"],
                }
            history_before = prepared["historyBefore"]
            history_after = prepared["historyAfter"]
            memory_after = prepared["memoryAfter"]
            project_after = prepared["projectAfter"]
            generated = _generated_views(
                project, proposed, proposed_events, project_after
            )
            promoted = (
                {".baton/state/project.json": project_after}
                if project_after is not None
                else {}
            )
            after = {
                ".baton/memory/memory.json": memory_after,
                ".baton/memory/history.jsonl": history_after,
                **promoted,
                **generated,
            }
            before = {}
            for relative in after:
                path = _artifact_path(project, relative)
                if path.is_symlink() or not path.is_file():
                    raise MemoryError(
                        "memory transaction artifact is missing or unsafe: %s" % relative
                    )
                before[relative] = path.read_bytes()
            transaction_id = "memory-%s-%s" % (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
            transaction = _transaction_directory(project, transaction_id)
            backup = transaction / "backup"
            backup.mkdir(parents=True, exist_ok=False)
            backup_names = {
                ".baton/memory/memory.json": "memory.json",
                ".baton/memory/history.jsonl": "history.jsonl",
                ".baton/views/dashboard.html": "dashboard.html",
                ".baton/views/team-tasks.md": "team-tasks.md",
                ".baton/state/project.json": "project.json",
                ".baton/metadata.json": "metadata.json",
            }
            for relative, content in before.items():
                (backup / backup_names[relative]).write_bytes(content)
            report_path = transaction / "memory-report.json"
            report = {
                "schemaVersion": 1,
                "transactionId": transaction_id,
                "operation": command["operation"],
                "expectedRevision": command["expectedRevision"],
                "committedRevision": proposed["revision"],
                "claimIds": prepared["claimIds"],
                "personnelIds": prepared["personnelIds"],
                "beforeSha256": {"memory": _sha256(memory_path.read_bytes()), "history": _sha256(history_before)},
                "afterSha256": {"memory": _sha256(memory_after), "history": _sha256(history_after)},
                "artifacts": {
                    relative: {
                        "beforeSha256": _sha256(before[relative]),
                        "afterSha256": _sha256(after[relative]),
                        "backupName": backup_names[relative],
                    }
                    for relative in sorted(after)
                },
                "backupPath": str(backup),
                "rollbackLocation": str(backup),
                "reportPath": str(report_path),
                "result": "prepared",
            }
            _write_report(report_path, report)
            try:
                _atomic_write(history_path, history_after)
                if os.environ.get("BATON_TEST_MEMORY_FAIL_AT") == "after-history":
                    raise OSError("injected memory transaction failure after history replacement")
                _atomic_write(memory_path, memory_after)
                if os.environ.get("BATON_TEST_MEMORY_FAIL_AT") == "after-memory":
                    raise OSError("injected memory transaction failure after logical commit")
                for relative in sorted({**promoted, **generated}):
                    _atomic_write(_artifact_path(project, relative), after[relative])
                if os.environ.get("BATON_TEST_MEMORY_FAIL_AT") == "after-generated":
                    raise OSError("injected memory transaction failure after generated views")
                checked, checked_events, checked_raw, _, _, _ = _load(project)
                if checked != proposed or checked_events != proposed_events or checked_raw != history_after:
                    raise MemoryError("committed memory did not validate byte-for-byte")
                if project_after is not None and _artifact_path(
                    project, ".baton/state/project.json"
                ).read_bytes() != project_after:
                    raise MemoryError("committed project direction differs from the confirmed intent")
            except BaseException as error:
                for relative, content in before.items():
                    _atomic_write(_artifact_path(project, relative), content)
                report["result"] = "rolled-back"
                report["errorClass"] = type(error).__name__
                _write_report(report_path, report)
                raise MemoryError("memory transaction failed and was rolled back; external recovery evidence is available") from error
            report["result"] = "committed"
            _write_report(report_path, report)
            payload = {
                "ok": True,
                "changed": True,
                "idempotent": False,
                "revision": proposed["revision"],
                "result": prepared["result"],
                "claimIds": prepared["claimIds"],
                "personnelIds": prepared["personnelIds"],
                "transactionId": transaction_id,
                "reportPath": str(report_path),
                "backupPath": str(backup),
                "rollbackLocation": str(backup),
                "generatedViews": sorted(generated),
                "projection": prepared["projection"],
            }
            if prepared["redacted"]:
                payload["warning"] = "Local memory and local memory history were redacted; earlier Git commits may retain forgotten values. Git history was not rewritten."
            return payload
    except MutationLockError as error:
        raise MemoryError("shared mutation lock failed: %s" % error) from error


def select_context(root: Path, request: Dict[str, Any]) -> Dict[str, Any]:
    """Select deterministic confirmed role-specific context within the automatic cap."""
    if not isinstance(request, dict):
        raise MemoryError("context request must be an object")
    snapshot, _, _, _, _, _ = _load(Path(root))
    role = request.get("role")
    if role not in CONTEXT_ROLES:
        raise MemoryError("context role must be a stable Baton role or Internal Audit")
    evaluation_boundary = ""
    if role == "Internal Audit":
        evaluation_boundary = request.get("evaluationBoundary", "")
        if not isinstance(evaluation_boundary, str) or not evaluation_boundary.strip():
            raise MemoryError(
                "Internal Audit context requires an explicit authorized evaluation boundary"
            )
        evaluation_boundary = evaluation_boundary.strip()
    assignment_type = str(request.get("assignmentType", ""))
    assignment_text = str(request.get("assignment", "")).casefold()
    mode = request.get("mode", "automatic")
    if mode not in {"automatic", "on-demand"}:
        raise MemoryError("context mode must be automatic or on-demand")
    subject = str(request.get("subject", "")).casefold()
    query = str(request.get("query", "")).casefold()
    active_people = {
        value.casefold()
        for person in snapshot["personnel"]
        if person["employmentStatus"] not in {"former", "retired", "replaced"}
        for value in (person["id"], person["name"])
    }
    candidates = []
    for claim in snapshot["claims"]:
        if claim["status"] != "confirmed" or claim["statement"].casefold() in assignment_text:
            continue
        if role != "Internal Audit" and role not in claim["roleRelevance"]:
            continue
        if claim["category"] == "personnel" and claim["subject"].casefold() not in active_people:
            continue
        haystack = "%s %s %s" % (claim["subject"], claim["statement"], claim["category"])
        if mode == "on-demand" and query and query not in haystack.casefold():
            continue
        role_score = 1 if role == "Internal Audit" or role in claim["roleRelevance"] else 0
        assignment_score = 1 if assignment_type and assignment_type in claim["assignmentTypes"] else 0
        subject_score = 1 if subject and subject in claim["subject"].casefold() else 0
        candidates.append((role_score, assignment_score, subject_score, claim["importance"], claim["updatedAt"], claim["id"], claim))
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5]), reverse=True)
    selected = []
    lines = []
    for _, _, _, _, _, _, claim in candidates:
        if len(selected) >= 10:
            break
        line = "[%s] %s: %s" % (claim["id"], claim["subject"], claim["statement"])
        proposed = "\n".join(lines + [line])
        byte_count = len(proposed.encode("utf-8"))
        if byte_count > 1800 or math.ceil(byte_count / 3) > 600:
            continue
        selected.append(claim["id"])
        lines.append(line)
    content = "\n".join(lines)
    byte_count = len(content.encode("utf-8"))
    result = {
        "schemaVersion": 1,
        "mode": mode,
        "role": role,
        "assignmentType": assignment_type,
        "claimIds": selected,
        "claimCount": len(selected),
        "utf8Bytes": byte_count,
        "estimatedTokens": math.ceil(byte_count / 3),
        "content": content,
        "limits": {"claims": 10, "utf8Bytes": 1800, "estimatedTokens": 600},
    }
    if role == "Internal Audit":
        result["authority"] = "read-only-evaluation"
        result["evaluationBoundary"] = evaluation_boundary
    return result


def _ordered_bootstrap_seats(raw_seats: List[Any]) -> List[Dict[str, Any]]:
    """Validate seats and return the stable permanent-role assembly order."""
    indexed = [(index, _bootstrap_seat(seat)) for index, seat in enumerate(raw_seats)]
    rank = {"Management": 0, "Operations": 1, "Consultant": 2}
    indexed.sort(key=lambda item: (rank[item[1]["role"]], item[0]))
    return [seat for _, seat in indexed]


def reconcile_bootstrap(root: Path, capability_snapshot: Dict[str, Any], observations: Dict[str, Any]) -> Dict[str, Any]:
    """Keep discovery task-local, then return an idempotent post-confirmation task plan."""
    if not isinstance(capability_snapshot, dict) or not isinstance(observations, dict):
        raise MemoryError("bootstrap capability snapshot and observations must be objects")
    snapshot, _, _, _, _, _ = _load(Path(root))
    cleanup_tasks = copy.deepcopy(snapshot["bootstrap"].get("cleanupTasks", []))
    if cleanup_tasks:
        return {
            "ok": True,
            "revision": snapshot["revision"],
            "capability": "cleanup",
            "bootstrapStatus": snapshot["bootstrap"]["status"],
            "plan": [],
            "cleanupPlan": cleanup_tasks,
            "nextStep": "cleanup-team",
            "publicStatus": {
                "state": "Onboarding reset",
                "nextStep": "cleanup-team",
                "question": "",
            },
            "discoveryAvailable": False,
            "deliveryReady": False,
            "coordinatorTaskId": "",
        }
    seed = observations.get("seed") or snapshot["bootstrap"]["seed"]
    raw_seats = observations.get("seats", [])
    if not isinstance(seed, str) or not seed or not isinstance(raw_seats, list):
        raise MemoryError("bootstrap reconciliation requires a stable seed and seat list")
    requested_seats = _ordered_bootstrap_seats(raw_seats)
    seats = requested_seats if snapshot["bootstrap"].get("confirmedAt") else []
    keys = [(seat["role"], seat["seat"]) for seat in seats]
    if len(keys) != len(set(keys)):
        raise MemoryError("bootstrap seat list contains a duplicate")
    native = all(
        capability_snapshot.get(name) is True
        for name in (
            "list",
            "create",
            "stableIdentity",
            "read",
            "message",
            "title",
            "archive",
        )
    )
    semantic_seats = json.dumps(
        seats,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    mode = "native" if native else "fallback"
    if native and seats and "liveTasks" not in observations:
        raise MemoryError(
            "native bootstrap requires a complete live task inventory"
        )
    provisional = snapshot["bootstrap"].get("provisionalProject", {})
    invocation_task_id = observations.get("invocationTaskId", "")
    registered_coordinator = provisional.get("coordinatorTaskId", "")
    if not snapshot["bootstrap"].get("confirmedAt") or registered_coordinator:
        if not isinstance(invocation_task_id, str) or not invocation_task_id.strip():
            raise MemoryError(
                "bootstrap reconciliation requires the invoking task identity"
            )
        invocation_task_id = invocation_task_id.strip()
        legacy_partial = (
            not registered_coordinator
            and snapshot["bootstrap"].get("status") != "not-started"
            and bool(
                snapshot["bootstrap"].get("roster")
                or {
                    key: value
                    for key, value in provisional.items()
                    if key not in {"onboardingEpoch"}
                }
            )
        )
        if legacy_partial:
            raise MemoryError(
                "legacy incomplete onboarding requires an explicit reset before restart"
            )
        if registered_coordinator and invocation_task_id != registered_coordinator:
            raise MemoryError(
                "bootstrap onboarding must continue in its original invoking task"
            )
    onboarding_epoch = provisional.get("onboardingEpoch", 0)
    preset_epoch = provisional.get("projectPresetEpoch", 0)
    if (
        not isinstance(onboarding_epoch, int)
        or onboarding_epoch < 0
        or not isinstance(preset_epoch, int)
        or preset_epoch < 0
    ):
        raise MemoryError("bootstrap reconciliation epoch is invalid")
    transact(
        Path(root),
        {
            "operation": "bootstrap",
            "action": "reconcile-%s" % mode,
            "actor": "Management",
            "actorId": "bootstrap",
            "expectedRevision": snapshot["revision"],
            "idempotencyKey": _stable_id(
                "bootstrap-%s" % mode,
                seed,
                str(onboarding_epoch),
                str(preset_epoch),
                semantic_seats,
            ),
            "timestamp": observations.get("timestamp", _timestamp({})),
            "seed": seed,
            "seats": seats,
            "invocationTaskId": invocation_task_id,
        },
    )
    snapshot, _, _, _, _, _ = _load(Path(root))
    project_name = _confirmed_project_name(Path(root).resolve(), snapshot) if seats else ""
    live_tasks = observations.get("liveTasks", [])
    if not isinstance(live_tasks, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("taskId"), str)
        or not item.get("taskId")
        or not isinstance(item.get("title", ""), str)
        or not isinstance(item.get("attemptId", ""), str)
        or not isinstance(item.get("wakePath", ""), str)
        for item in live_tasks
    ):
        raise MemoryError("live task inventory must contain stable task records")
    live_task_ids = [item["taskId"] for item in live_tasks]
    if len(live_task_ids) != len(set(live_task_ids)):
        raise MemoryError("live task inventory contains a duplicate task identity")

    eligible_people: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for person in snapshot["personnel"]:
        if person["employmentStatus"] in {"former", "retired", "replaced"}:
            continue
        eligible_people.setdefault((person["role"], person["seat"]), []).append(person)
    collisions = [key for key, people in eligible_people.items() if len(people) > 1]
    if collisions:
        raise MemoryError("bootstrap personnel reconciliation is ambiguous")
    existing_by_seat = {
        key: people[0] for key, people in eligible_people.items()
    }
    plan = []
    prior_ready = True
    for seat in seats:
        key = (seat["role"], seat["seat"])
        person = existing_by_seat.get(key)
        person_seed = "%s:%s:%s:%s" % (seed, seat["role"], seat["seat"], seat.get("specialty", ""))
        personnel_id = (
            person["id"]
            if person
            else _stable_id(
                "person",
                person_seed,
                seat["role"],
                seat["seat"],
                seat.get("specialty", ""),
            )
        )
        name = person["name"] if person else _name(person_seed)
        task_title = _permanent_task_title(project_name, seat, name)
        task = person["task"] if person else {}
        title_ready = (
            task.get("expectedTitle") == task_title
            and task.get("title") == task_title
            and bool(task.get("titleVerifiedAt"))
        )
        attempt_id = task.get("attemptId", "")
        attempt_matches = [
            item
            for item in live_tasks
            if attempt_id and item.get("attemptId") == attempt_id
        ]
        recorded_live_task = next(
            (
                item
                for item in live_tasks
                if task.get("taskId") and item.get("taskId") == task.get("taskId")
            ),
            None,
        )
        provider_ready = bool(
            not native
            or (
                recorded_live_task
                and recorded_live_task.get("title") == task_title
                and (
                    not task.get("wakePath")
                    or recorded_live_task.get("wakePath") == task.get("wakePath")
                )
                and (
                    not attempt_id
                    or recorded_live_task.get("attemptId") == attempt_id
                )
            )
        )
        delivery_ready = bool(
            person
            and task.get("status") == "online"
            and title_ready
            and task.get("taskId")
            and task.get("wakePath")
            and task.get("wokenAt")
            and provider_ready
        )
        needs_task = not delivery_ready
        copy_prompt = ""
        registration = ""
        if needs_task and not native:
            if task.get("taskId"):
                copy_prompt = _fallback_existing_task_prompt(
                    task_title, not title_ready
                )
            else:
                copy_prompt = (
                    task.get("prompt")
                    if task.get("prompt")
                    else _fallback_prompt(seat, name, task_title)
                )
            registration = (
                "Register the returned task ID and wake path for personnel %s through "
                "the public `boot record` task transaction, then rerun $boot."
                % personnel_id
            )
        recovered_task_id = ""
        recovered_wake_path = ""
        if delivery_ready:
            task_action = "reuse"
        elif task.get("status") == "cleanup-required":
            task_action = "archive" if native else "manual-archive"
        elif task.get("status") == "create-pending":
            if len(attempt_matches) > 1:
                task_action = "resolve-duplicate"
            elif len(attempt_matches) == 1:
                task_action = "recover-created"
                recovered_task_id = attempt_matches[0]["taskId"]
                recovered_wake_path = attempt_matches[0].get("wakePath", "")
            else:
                task_action = "create" if native else "copy-prompt"
        elif task.get("status") == "created":
            if not native:
                task_action = "manual-title" if not title_ready else "manual-register"
            elif recorded_live_task is None:
                task_action = "inspect-created"
            elif recorded_live_task.get("title") == task_title:
                task_action = "register"
            else:
                task_action = "retitle"
        elif task.get("status") == "online" and native and not provider_ready:
            task_action = "inspect-recorded"
        elif task.get("taskId") and not title_ready:
            task_action = (
                "inspect-recorded"
                if native and recorded_live_task is None
                else "retitle" if native else "manual-title"
            )
        elif task.get("status") == "registered":
            task_action = (
                "inspect-recorded"
                if native and recorded_live_task is None
                else "wake" if native else "manual-wake"
            )
        else:
            task_action = "create" if native else "copy-prompt"
        if not prior_ready and not delivery_ready:
            task_action = "wait-for-prior"
        plan.append(
            {
                "role": seat["role"],
                "seat": seat["seat"],
                "specialty": seat.get("specialty", ""),
                "personnelId": personnel_id,
                "name": name,
                "taskTitle": task_title,
                "workingStyle": copy.deepcopy(person["workingStyle"]) if person else _style(person_seed),
                "taskAction": task_action,
                "attemptId": attempt_id,
                "creationMarker": (
                    "BATON_BOOTSTRAP_ATTEMPT:%s" % attempt_id
                    if attempt_id
                    else ""
                ),
                "recoveredTaskId": recovered_task_id,
                "recoveredWakePath": recovered_wake_path,
                "copyPrompt": copy_prompt,
                "registrationInstruction": registration,
                "deliveryReady": delivery_ready,
            }
        )
        prior_ready = prior_ready and delivery_ready
    next_step = _bootstrap_next_step(snapshot)
    preset_label = observations.get("presetLabel")
    if not isinstance(preset_label, str) or not preset_label.strip():
        preset_label = "the configured project type"
    public_status = {
        "state": (
            "Team online"
            if plan and all(item["deliveryReady"] for item in plan)
            else "Onboarding"
        ),
        "nextStep": next_step,
        "question": (
            "Keep %s, or change it before I assemble the team?" % preset_label.strip()
            if next_step == "confirm-project-preset"
            else ""
        ),
    }
    return {
        "ok": True,
        "revision": snapshot["revision"],
        "capability": "native" if native else "fallback",
        "bootstrapStatus": snapshot["bootstrap"]["status"],
        "plan": plan,
        "cleanupPlan": [],
        "nextStep": next_step,
        "publicStatus": public_status,
        "discoveryAvailable": snapshot["bootstrap"]["status"] != "needs-integration",
        "deliveryReady": bool(plan) and all(item["deliveryReady"] for item in plan),
        "coordinatorTaskId": snapshot["bootstrap"]
        .get("provisionalProject", {})
        .get("coordinatorTaskId", ""),
    }


def _input(path: str) -> Dict[str, Any]:
    try:
        raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise MemoryError("input must be a readable JSON object") from error
    if not isinstance(value, dict):
        raise MemoryError("input must be a JSON object")
    return value


def _emit(value: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(os.environ.get("BATON_PROJECT_ROOT", Path.cwd())))
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("--json", action="store_true", dest="command_json")
    initialize_parser = commands.add_parser("initialize")
    initialize_parser.add_argument("--json", action="store_true", dest="command_json")
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--section", default="summary")
    inspect_parser.add_argument("--json", action="store_true", dest="command_json")
    recover_parser = commands.add_parser("recover")
    recover_parser.add_argument("--json", action="store_true", dest="command_json")
    for name in ("transact", "select-context"):
        child = commands.add_parser(name)
        child.add_argument("input", nargs="?", default="-")
        child.add_argument("--json", action="store_true", dest="command_json")
    reconcile = commands.add_parser("reconcile-bootstrap")
    reconcile.add_argument("input", nargs="?", default="-")
    reconcile.add_argument("--json", action="store_true", dest="command_json")
    args = parser.parse_args(argv)
    as_json = args.json or getattr(args, "command_json", False)
    try:
        if args.command == "check":
            snapshot, events, _, _, _, _ = _load(args.project_root)
            payload = {"ok": True, "revision": snapshot["revision"], "historyEvents": len(events)}
        elif args.command == "initialize":
            payload = initialize(args.project_root)
        elif args.command == "inspect":
            payload = inspect(args.project_root, {"section": args.section})
        elif args.command == "recover":
            payload = recover_interrupted_transactions(args.project_root)
        elif args.command == "transact":
            payload = transact(args.project_root, _input(args.input))
        elif args.command == "select-context":
            payload = select_context(args.project_root, _input(args.input))
        else:
            value = _input(args.input)
            payload = reconcile_bootstrap(args.project_root, value.get("capabilities", {}), value.get("observations", {}))
        _emit(payload, as_json)
        return 0
    except MemoryError as error:
        payload = {"ok": False, "error": str(error)}
        if as_json:
            _emit(payload, True)
        else:
            print("ERROR: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
