# BATON-V060-REL — Brief

Status: Approved
Scope: Ticket
Owner: Operations
Parent Goal: BATON-V060
Priority: P0

## Outcome and context

Freeze one exact v0.6.0 candidate, prove its source, supported v0.5 adoption, asset set, reviews, and remote installation, then publish it and clean up the superseded branch.

## Scope and non-goals

The Ticket covers the release source and records, lifecycle migration boundary, evaluator and smoke matrix, bundle generation, independent review, Internal Audit, pull request, tag, release assets, remote smoke, and final branch state. It excludes unrelated features and automatic consumer cleanup.

## Acceptance

Every acceptance criterion and required verification recorded in canonical Ticket `BATON-V060-REL` must pass against the exact published source commit.

## Dependencies, constraints, and risks

The stable v0.5 source commit and manifest digest must authenticate the only supported upgrade origin. Publication is blocked by any review failure, stale candidate, asset mismatch, or remote-smoke failure.

## Protocols and evidence

- Readiness Protocol: Standard Protocol
- Clearance Protocol: Release Clearance
- Override reason: none
- Required Consultants: none
- Verification: exact-candidate source, smoke, migration, asset, review, audit, and remote-install evidence

## Systems and execution boundary

Operations owns the release files, verification surface, GitHub release transaction, and obsolete-branch cleanup until all evidence is recorded and ownership is returned.
