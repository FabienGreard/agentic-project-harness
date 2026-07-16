---
name: terminal
description: Inspect Baton installation status and locate or open its generated HTML control room. Use for status, provenance, integrity, dashboard, visualization, or explicit $terminal requests.
---

# Terminal

Use only `.baton/bin/baton terminal`.

- Run `terminal status --json` for version, provenance, integrity, integration, cleanup, and last-transaction status.
- Run `terminal view --json` to return the verified dashboard path and digest.
- Run `terminal view --open --json` only when the user asks to open or visualize it.

The HTML view is generated and non-authoritative. Report drift or missing output; do not edit it.

## Voice

Use the restrained company-terminal voice. Lead with the installation or control-room state, show only material version, integrity, digest, and path evidence, and end with one exact inspect, open, or return action. Do not imply that the generated view is canonical.
