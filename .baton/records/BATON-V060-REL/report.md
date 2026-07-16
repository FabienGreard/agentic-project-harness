# BATON-V060-REL — Report

Returned: 2026-07-16
Scope: Ticket
Parent Goal: BATON-V060
Reviewed by: Operations

## Outcome and change

The repaired v0.6.0 source tree passes its pre-freeze source matrix on Python 3.13. Exact-commit Python 3.13/3.9, artifact, review, and publication evidence remains in progress.

## Decisions

Publication is one exact-source transaction. The audit-discovered public v0.5 collision is resolved through zero-link quarantine bound to the immutable public v0.5 path-and-hash set rather than mutable local baselines, destructive changes, or partial discovery installation.

## Verification

- Readiness Protocol: Standard Protocol
- Clearance Protocol: Release Clearance
- Commands, environment, observations, and results: before freeze, `python3 scripts/harness_eval.py --strict` passed 19/19 and `bash tests/install_smoke.sh` passed 139/139 on Python 3.13.5; shell syntax, `git diff --check`, authentic-v0.5 quarantine/activation, modified-byte, coherent forged-baseline, incomplete-set, extra-file, and collision tests, plus `baton doctor check`, passed. The commit containing this report is the exact candidate to be rechecked on Python 3.13 and 3.9 and bundled.
- Consultant decisions and evidence: none required.
- Goal or Ticket Clearances and status: the earlier Goal Release Clearance was invalidated by material audit repairs; exact-candidate Release clearance, technical review, and audit are pending.

## Limits and follow-up

Bundle validation, authentic public v0.5 adoption, both independent reviews, Internal Audit, publication, remote smoke, and cleanup remain pending exact-candidate proof.

## Ownership returned

Not yet; Operations remains in `Verifying` state.
