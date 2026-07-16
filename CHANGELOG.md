# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] - 2026-07-16

### Added

- Added `$boot` onboarding with stable named coworkers, idempotent permanent-task reconciliation, copy-ready fallback, interruption recovery, and one-question Project discovery.
- Added one project-local internal Memory service with confirmed claims, candidates, named personnel, evidence-backed reviews, privacy controls, local chronology, and bounded role-specific recall.
- Added an independent memory schema/version boundary, snapshot-authoritative transactional writer, mature-adoption quarantine, sequential migration contract, external rollback evidence, and local-history redaction with accurate Git-retention warnings.
- Added Boot selectors for the Readiness Protocol and Clearance Protocol, including canonical Project, Goal, Ticket, and Clearance State.
- Added seven matching management skills and CLI families: `boot`, `control`, `roster`, `terminal`, `upgrade`, `doctor`, and `scrap`.
- Added immutable Scrap plans with exact tree revalidation, explicit approval, external backup, transaction Reports, and rollback.
- Added a limited ubiquitous language for Goal, Ticket, Release, Publication, and their clearance boundaries.
- Expanded the ubiquitous language with Project, Repository, State, Record, Brief, Decision, Report, Evidence, Review, and Memory.
- Added aggregate state contract v2 so stable updates cannot silently mix legacy assurance fields with the new protocol model.
- Added authenticated v0.5 skill-discovery quarantine so unchanged legacy installations can adopt v0.6 without overwriting legacy files or partially installing new links; activation remains blocked until human-approved cleanup completes the exact link set.

### Changed

- Replaced generic first-task instructions with `$boot` while preserving Management, Operations, Consultant, Contractor, and Internal Audit authority.
- Extended the dashboard with privacy-filtered personnel, task-readiness, memory-candidate, and company-history views without universal worker scores or leaderboard behavior.
- Replaced `status`, `update`, `check`, hidden activation, and separate bootstrap/hire/fire/Memory skills with the seven public management families; each skill delegates only to its matching CLI family and Memory remains internal behind an advanced CLI-only `control memory` seam.
- Limited the curl installer to verified acquisition or update with safe starter defaults; Project, protocol, reasoning, and team choices now happen through installed skills.
- Made short skill discovery all-or-nothing: an occupied non-Baton name blocks installation before mutation.
- Replaced test-rigor and human-review-stage settings with Readiness Protocol levels (`Waived`, `Field Check`, `Standard Protocol`, `Full Certification`) and Clearance Protocol levels (`Autonomous`, `Release Clearance`, `Completion Clearance`, `Continuous Clearance`); fresh projects default to `Standard Protocol` and `Release Clearance`.
- Defined Continuous Clearance as review at every canonical Goal and Ticket boundary, while preserving Management authority for destructive, security, compliance, and new external-commitment decisions at every level.
- Replaced `.baton/work/` with flat Project, Goal, and Ticket scopes under `.baton/records/`, linked from canonical State with unambiguous ids and paths.
- Renamed host version metadata from `projectVersion` to `repositoryVersion`.
- Renamed the product to Baton and converted the repository from a consumer template into a normal source/product repository.
- Isolated all consumer runtime, state, governance, roles, schemas, dashboards, and reports under `.baton/`, with only thin `AGENTS.md`, Codex config, and per-skill discovery integrations outside it.
- Split stable distribution into exact checksum-bound new-project and mature-adoption payloads generated only from `template/`.
- Added schema-v3 Baton provenance, project-version separation, mature-state quarantine, legacy cleanup candidates, additive v0.2-v0.5 migration, external transactions, and rollback.
- Replaced installed root lifecycle tooling with the small `.baton/bin/baton` status, update, and check surface.
- Added explicit reviewed mature-state activation, immutable per-file GitHub evidence, checksum-rich transaction reports, and automatic Codex agent-registry reconciliation when Consultants are hired or fired.
- Made permanent-task messages the sole wake mechanism and prohibited persistent goals as role identity or lifecycle control, including legacy auto-resume handling.
- Removed the repository-wide source-classification inventory; release payloads now derive only from tracked `template/.baton/` content with shared defaults, explicit starter/adoption-only projections, and exact generated manifests.
- Made release proof single-pass, Python-3.9-selectable, physical-path-safe on macOS, and explicit about the immutable v0.5 upgrade origin.

## [0.5.0] - 2026-07-14

### Added

- Documented the approved v0.5 stable-release lifecycle, LLM-first operability rule, canonical operational state, generated project view, and human-governed cleanup boundary.
- Added one stable-release installer/updater with `status` and `update`, additive non-empty-repository adoption, version/provenance metadata, checksum-aware ownership, external transactions, rollback, conservative legacy migration, and copy-ready cleanup prompts.
- Added canonical JSON project, ticket, ownership, and review records with transactional `check`/`apply` tooling and a self-contained generated dashboard.
- Added a common, project-scoped rule library under `.agents/rules/` with a navigation-only root `AGENTS.md`.
- Added explicitly invoked `brainstorm`, `improve-codebase-architecture`, and `code-review` skills with one non-drifting Codex discovery link.
- Added independent static checks and installer smoke coverage for rule structure, skill metadata/discovery, generic language, and two-axis review integration.
- Added third-party attribution for the MIT-licensed upstream skill material adapted from Matt Pocock's skills repository.
- Added one canonical four-preset team catalog, deterministic Consultant hire/fire engine, team schema/state, project-scoped hire/fire skills, and full Game, Software, Business, and Research examples.
- Added user-overridable project assurance defaults, explicit per-ticket `Lean`/`Standard`/`Thorough` test rigor, and staged human review at `Readiness`, `Acceptance`, and `Release` with transactional gates and migration coverage.

### Changed

- Replaced generic user-facing agent titles with Management, Operations, Consultants, Contractors, and hidden Internal Audit while retaining opinionated professional personas per preset.
- Added Operations two-axis integration review and a bounded Management final-audit mode while preserving separate Consultant domain approval.
- Updated fresh installations and onboarding guidance to include the modular rules and project-scoped skills.
- Set the project-scoped Codex permission contract to on-request approval with Auto-review, workspace-write sandboxing, and sandbox network access; reduced the concurrency ceiling from six threads to four while keeping dispatch depth at one.
- Replaced the legacy Markdown backlog/active-work index and monolithic project-state JSON with canonical records under `docs/state/`.
- Replaced Balanced/Deep reasoning choices with Low, Medium, High, and Custom presets; Medium is the default, while Low uses medium Management/Operations/Consultants, low Contractors, and high Internal Audit.
- Made permanent top-level leadership tasks event-driven with explicit run-to-idle handoffs and no polling.
- Limited incoming-change classifications to Management/Operations triage, made Contractor blocker/result cases not applicable, and reserved whole-run interruption for cases where unaffected work cannot continue.
- Made resolved assurance and human-review timing visible in the generated dashboard, with a stable scrollable task table, dark phosphor goal/PRD cards, and yellow timeline bars across desktop and mobile.

## [0.3.0] - 2026-07-13

### Changed

- Raised the Harness Evaluator default reasoning level from `high` to `xhigh`.
- Reworked the installer into a styled, keyboard-first setup with folder-aware defaults, project-type context, and Balanced/Deep/Custom reasoning.
- Replaced the standalone bootstrap-prompt file with a copy-ready installation prompt in the public README and an inline first-project prompt in generated READMEs.
- Made Specialist Lead a standard installed role, removing the optional prompt and include/omit CLI flags.

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

[Unreleased]: https://github.com/FabienGreard/baton/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/FabienGreard/baton/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/FabienGreard/agentic-project-harness/compare/v0.3.0...v0.5.0
[0.3.0]: https://github.com/FabienGreard/agentic-project-harness/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/FabienGreard/agentic-project-harness/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/FabienGreard/agentic-project-harness/releases/tag/v0.1.0
