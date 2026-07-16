# BATON-V060 — Brief

Status: Approved
Scope: Goal
Owner: Management
Priority: P0

## Outcome and context

Publish the approved current Baton implementation as the stable `v0.6.0` release. It supersedes the older pending v0.6 branch and must leave the repository on `main` after publication.

## Scope and non-goals

Scope includes version normalization, stable release assets, supported v0.5 adoption, exact-candidate verification, independent review, Internal Audit, GitHub publication, immutable remote smoke testing, and obsolete release-branch cleanup.

This Goal does not authorize unrelated feature expansion, weakening fail-closed migration rules, automatic deletion of consumer-owned files, or publication of an unverified commit.

## Acceptance

- `VERSION`, public documentation, evaluator metadata, and the changelog agree on `0.6.0`.
- The strict evaluator and smoke suites pass on the exact candidate under the supported Python versions.
- A real stable v0.5 installation adopts v0.6 without overwriting legacy skill discovery; activation remains blocked until human-approved cleanup installs every exact v0.6 discovery link.
- Two independent code reviews approve the frozen candidate and disposable Internal Audit passes.
- The exact candidate is merged, tagged `v0.6.0`, published with the complete validated asset set, and verified from immutable remote URLs.
- The superseded v0.6 branch is removed and the local checkout finishes clean on `main`.

## Dependencies, constraints, and risks

The release depends on the published v0.5.0 origin tuple, GitHub release availability, and exact asset digests. Principal risks are an unsupported installed-layout transition, tag/source mismatch, duplicated verification masquerading as independent evidence, or branch cleanup before publication is proven.

## Protocols and evidence

- Readiness Protocol: Standard Protocol
- Clearance Protocol: Release Clearance
- Override reason: none
- Required Consultants: none
- Verification: strict evaluator, complete smoke suite on Python 3.13 and 3.9, shell syntax, exact public v0.5 adoption, bundle validation, two independent reviews, Internal Audit, immutable remote smoke

## Systems and execution boundary

The bounded systems are the Baton source and template, lifecycle installer and updater, release builder and installer, test and evaluator surfaces, repository-local release records, GitHub pull request/tag/release assets, and local/remote v0.6 branches.
