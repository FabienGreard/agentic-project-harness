# BATON-V060-REL — Report

Returned: 2026-07-16
Scope: Ticket
Parent Goal: BATON-V060
Reviewed by: Operations

## Outcome and change

Exact candidate `d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f` is published as Baton v0.6.0 with the validated five-asset set. Public immutable-SHA installation passed.

## Decisions

Publication is one exact-source transaction. The audit-discovered public v0.5 collision is resolved through zero-link quarantine bound to the immutable public v0.5 path-and-hash set rather than mutable local baselines, destructive changes, or partial discovery installation.

## Verification

- Readiness Protocol: Standard Protocol
- Clearance Protocol: Release Clearance
- Commands, environment, observations, and results: 19/19 source checks; 139/139 tests on Python 3.13.5 and Python 3.9.23; authentic public-v0.5 positive and atomic negative migration paths; five-asset validation and independent rebuild; PR #4 merge; exact annotated tag; live digest equality; latest-stable installer equality; repository immutable-release protection; and immutable remote smoke all passed.
- Consultant decisions and evidence: none required.
- Goal or Ticket Clearances and status: both independent technical reviews approved, Internal Audit passed, and Goal Release clearance approved exact commit `d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f` plus its recorded five-asset set, conditioned on leaving only `main` locally and remotely.

## Limits and follow-up

Local and remote branch inventories each contain only `main`, and the local checkout is clean on `main`. GitHub reports repository immutable-release protection enabled while the new release remains inside its grace interval. The only non-blocking limitation is that the historical v0.5 regression fixture requires full Git history; runtime and release assets are unaffected.

## Ownership returned

Operations returned ownership after every release and cleanup acceptance criterion passed.
