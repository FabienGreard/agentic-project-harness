---
name: scrap
description: Preview and safely remove Baton from a Repository with exact-plan verification, external backup, and rollback. Use only when the user explicitly asks to remove, uninstall, scrap, or decommission Baton, or invokes $scrap.
---

# Scrap

Follow `AGENTS.md` and the authority and lifecycle rules. Use only `.baton/bin/baton scrap`. Removal is destructive and always requires explicit human authority.

1. Run `scrap plan --output <outside-.baton-path> --json`.
2. Present the exact automatic removals, preserved collisions, manual actions, plan digest, and backup guarantee.
3. Ask for approval of that exact plan. A general `--yes` preference is insufficient.
4. Run `scrap apply --plan <path> --yes --json` only after approval.
5. Report removed paths, preserved paths, external backup, and transaction report.

Apply fails if the plan, metadata, Baton tree, discovery block, or managed host path changed after preview. Never delete the external backup. Do not manually finish preserved collisions.

## Voice

Use the restrained company-terminal voice and remain direct. State whether this is a preview or completed removal, distinguish automatic removals from preserved collisions, say `No changes were made` during planning, and end with the exact approval or backup-retention action. Never make removal playful.
