#!/usr/bin/env python3
"""Focused contract coverage for public ticket states and internal work steps."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import harness_state  # noqa: E402


ticket_statuses = {
    "Backlog",
    "Ready",
    "In Progress",
    "Blocked",
    "In Review",
    "Done",
    "Cancelled",
}
ownership_steps = {
    "Assigned",
    "Building",
    "Blocked",
    "Integrating",
    "Verifying",
    "Awaiting Review",
}
ownership_to_ticket = {
    "Assigned": "In Progress",
    "Building": "In Progress",
    "Blocked": "Blocked",
    "Integrating": "In Progress",
    "Verifying": "In Progress",
    "Awaiting Review": "In Review",
}

tickets_schema = json.loads(
    (ROOT / "docs/schemas/tickets.schema.json").read_text(encoding="utf-8")
)
ownership_schema = json.loads(
    (ROOT / "docs/schemas/ownership.schema.json").read_text(encoding="utf-8")
)

assert harness_state.STATUS == ticket_statuses
assert harness_state.ACTIVE_STATUS == ownership_steps
assert harness_state.EXECUTABLE_STATUS == {
    "Ready",
    "In Progress",
    "Blocked",
    "In Review",
    "Done",
}
assert harness_state.OWNERSHIP_TICKET_STATUS == ownership_to_ticket
assert set(
    tickets_schema["properties"]["tickets"]["items"]["properties"]["status"]["enum"]
) == ticket_statuses
assert set(
    ownership_schema["properties"]["ownership"]["items"]["properties"]["status"]["enum"]
) == ownership_steps

rendered = harness_state.render_dashboard(
    harness_state.load_records([])
)
assert "const ticketStatusOrder=['Backlog','Ready','In Progress','Blocked','In Review','Done','Cancelled']" in rendered

print("PASS: simplified status lifecycle contract")
