# Baton project overview

Baton is being separated into a normal product/source repository and an isolated consumer control plane. The source repository owns product code, tests, release tooling, documentation, and its own live `.baton/` state. Consumer payloads are built only from `template/`.

The active boundary is `BATON-001`. The source repository is now `FabienGreard/baton` and GitHub template mode is disabled, as explicitly authorized for this architecture change. No push, tag, release asset, latest-stable change, or stable publication is authorized until the candidate passes the recorded verification and returns to Management for an explicit decision.
