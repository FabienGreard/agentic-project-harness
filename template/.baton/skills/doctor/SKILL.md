---
name: doctor
description: Diagnose Baton integrity, canonical State, roster, Memory, and interrupted transactions. Use when Baton is broken, inconsistent, partially written, failing validation, or the user explicitly invokes $doctor.
---

# Doctor

Follow `AGENTS.md` and the lifecycle rule. Use only `.baton/bin/baton doctor`.

Run `doctor check --json` first. Report the failing layer and exact evidence without mutating the Repository.

Use `doctor recover --json` only when interrupted team or Memory transactions may exist. Recovery accepts only a fully validated before- or after-image; ambiguous evidence fails closed for manual inspection.

Do not hand-edit State, generated views, transaction reports, or backups. Diagnosis does not authorize upgrade, removal, destructive cleanup, or publication.

## Voice

Use the restrained company-terminal voice and remain clinical. Lead with `Healthy`, `Attention required`, or `Recovered`, name the failing or recovered layer, show exact report or backup evidence, and end with one recovery action. Do not use celebratory language for diagnosis or recovery.
