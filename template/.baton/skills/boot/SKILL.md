---
name: boot
description: Onboard a new Baton Project or resume mature-repository adoption and permanent-team assembly. Use when Baton was just installed, onboarding is incomplete, adoption needs reviewed activation, or the user explicitly invokes $boot.
---

# Boot

Follow `AGENTS.md` and `rules/bootstrap.md`. Use only `.baton/bin/baton boot`; never call Baton's private engines or edit State, Memory, team files, or generated views.

## Inspect

Run `boot status --json`, `boot inspect --json`, and `boot catalog --json`. Initialize absent internal onboarding State with `boot initialize --json`.

If status is `Needs Integration`, inspect the quarantined proposal against the live Repository. After the user approves its exact content, run `boot activate --from <proposal> --yes --json`. Do not treat quarantine as canonical before activation.

## Confirm Project intent

Keep one conversation and ask one question at a time:

1. Keep or change the listed preset?
2. If changed, select listed Consultants or none.
3. What name should Baton use for the user?
4. What are the Project identity, purpose, users, outcome, constraints, and unresolved items?
5. Select the Readiness Protocol.
6. Select the Clearance Protocol.
7. Confirm one plain-language summary.

Use `boot configure` only after the user selects a preset. Submit onboarding facts and corrections through `boot record <input.json> --json` or stdin with `boot record - --json`; ask `boot next <context.json> --json` for the next deterministic action. Never create Goals or Tickets during Boot.

Present every choice with text; color, symbols, or decoration may reinforce but never carry meaning alone. Never fabricate progress, confidence, diagnostics, privileges, task identity, or success. When Project evidence suggests another preset, submit its explicit evidence basis and respect the reconciler's durable recommendation fingerprint and rejection.

Use the temporary `root` designation only during onboarding. It has bootstrap authority only and never becomes Management.

Use Baton's restrained company-terminal voice: state the current onboarding outcome, show only material choices or evidence, and end with one question or next action. Keep decoration secondary to text. Boot alone may close with the one-time statement that the company is awake.

## Assemble the permanent team

After confirmation, pass the complete live-task inventory and configured seats to `boot next`. Follow exactly its first action. For each seat, persist the creation attempt before creating, record the returned stable ID immediately, verify the exact title, send one wake, then mark it online. Recover by stable identity or creation marker; never duplicate a seat.

Only explicit user authority permits onboarding reset or reviewed activation. If the task provider cannot safely list, create, verify, title, message, and archive failed creations, create nothing and return the reconciler's copy-ready action.

For reset, record `reset-onboarding` first. Archive superseded tasks only after that transaction commits. Keep normal output to the current action; do not introduce an uncreated coworker.

Finish when every permanent seat is online. State that the company is awake and relinquish `root` authority.
