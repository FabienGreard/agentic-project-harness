---
name: control
description: Inspect or update canonical Project controls, especially Readiness and Clearance Protocol defaults. Use when the user asks to change Project-level Baton settings, policies, or protocols, or explicitly invokes $control.
---

# Control

Follow `AGENTS.md` and the authority and delivery rules. Use only `.baton/bin/baton control`; never edit canonical State or generated views.

1. Run `control show --json` and `control check --json`.
2. Identify whether the request is a Project default or a Goal/Ticket-specific override. Do not widen a scoped decision.
3. Explain the current and proposed value and any inherited Goal/Ticket changes.
4. Obtain explicit human authority for a protocol change.
5. Run `control protocols --readiness <level> --clearance <level> --json`, supplying only changed flags.
6. Run `control check --json` and report the final defaults and changed records.

For another schema-valid Project State change, prepare one bounded operation file and run `control apply <operation> --json`. Do not use this as a bypass for role authority, Clearance, or transactional validation.

## Voice

Use the restrained company-terminal voice. Start with the current controls, describe one approved change and its inherited effect, show only changed records or validation evidence, and end with one exact next action. Never imply that a displayed control is approval.
