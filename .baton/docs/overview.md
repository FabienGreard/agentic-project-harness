# Baton project overview

Baton is being separated into a normal product/source repository and an isolated consumer control plane. The source repository owns product code, tests, release tooling, documentation, and its own live `.baton/` state. Consumer payloads are built only from `template/`.

The active boundary is `BATON-002`, implementing the unpublished v0.7.0 bootstrap and company-memory candidate on top of the completed BATON-001 distribution architecture. The source repository is now `FabienGreard/baton` and GitHub template mode is disabled, as explicitly authorized for the prior architecture change. No push, tag, release asset, latest-stable change, or stable publication is authorized until the candidate passes the recorded verification and returns to Management for an explicit decision.
