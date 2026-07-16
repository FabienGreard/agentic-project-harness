---
name: upgrade
description: Inspect and upgrade an installed Baton release, including required State or Memory migrations. Use when the user asks to update, upgrade, migrate, or repair an older Baton installation, or explicitly invokes $upgrade.
---

# Upgrade

Follow `AGENTS.md` and the lifecycle rule. Use only `.baton/bin/baton upgrade`.

1. Run `upgrade status --json` and report the installed release, provenance, integrity, pending integration, and cleanup boundaries.
2. Stop on modified managed files, unsupported provenance, an unsafe path, a downgrade, or unresolved adoption.
3. Explain the target stable release and required State or Memory migrations. Obtain explicit authority before applying.
4. Run `upgrade apply --yes --json`.
5. Run `upgrade status --json` and report the immutable source, transaction report, backup, migrations, preserved files, and manual actions.

Never delete backups or preserved legacy paths. Upgrade uses the same verified release lifecycle as the installer.

## Voice

Use the restrained company-terminal voice. State `Current`, `Upgrade ready`, `Updated`, or `Attention required`, show immutable source and recovery evidence, and end with one approval or validation action. Do not announce success before the post-upgrade status check passes.
