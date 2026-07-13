# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-07-13

### Added

- Interactive and agent-friendly `install.sh` Codex bootstrapper.
- Native project-scoped Codex custom agents with independently selectable reasoning levels for Director, Delivery, optional Specialist, worker, and evaluator roles.
- Generated installation metadata, project README, and first-agent `BOOTSTRAP_PROMPT.md`.
- Isolated local and standalone-download smoke coverage for role configuration, provenance, rollback, dry-run behavior, Git initialization, invalid inputs, and non-empty-target refusal.

## [0.1.0] - 2026-07-13

### Added

- Generic Director, Delivery Lead, Specialist Lead, worker, and evaluator contracts.
- Readiness, transactional state, baton, interruption, review, and run-to-idle workflows.
- Decision, PRD, ticket, implementation-report, and review-packet templates.
- Machine-readable project-state schema and dependency-free static harness evaluator.
- Canonical scenario evaluation suite.
- Game-development and business-operations adaptation examples.
- GitHub contribution and community-health files.

[Unreleased]: https://github.com/FabienGreard/agentic-project-harness/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/FabienGreard/agentic-project-harness/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/FabienGreard/agentic-project-harness/releases/tag/v0.1.0
