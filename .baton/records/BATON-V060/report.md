# BATON-V060 — Report

Returned: 2026-07-16
Scope: Goal
Reviewed by: Operations

## Outcome and change

Baton v0.6.0 is published from exact candidate `d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f`. The release includes the fail-closed public-v0.5 migration boundary, state schema v2, durable company Memory, permanent-team bootstrap, deterministic public management commands, and the validated dual-payload installer.

## Decisions

PR [#4](https://github.com/FabienGreard/baton/pull/4) merged the reviewed candidate. Annotated tag `v0.6.0` peels to the exact candidate while `main` points to merge commit `e65fe90e39b04a8f627b8c37a1271cf5d676f493`. The release uses the five prevalidated assets without rebuilding.

## Verification

- Readiness Protocol: Standard Protocol
- Clearance Protocol: Release Clearance
- Commands, environment, observations, and results: exact candidate evaluation passed 19/19; the complete suite passed 139/139 on Python 3.13.5 and 139/139 on Python 3.9.23; shell syntax, `git diff --check`, fresh/mature local assets, authentic public-v0.5 adoption, coherent forged-baseline and incomplete-set atomic rejection, bundle validation, independent rebuild, public asset digest verification, latest-stable installer verification, and `bash tests/install_remote_smoke.sh v0.6.0 d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f` passed. Repository immutable-release protection is enabled.
- Consultant decisions and evidence: no Consultant was required; two independent code reviews approved and fresh Internal Audit passed.
- Goal or Ticket Clearances and status: exact-candidate Goal Release clearance approved for `d1b3e7b3f7cc6af741f8323424a0d2e0eb74d49f` and its recorded five-asset set, with only `main` permitted to remain locally and remotely after completion.

## Limits and follow-up

The [GitHub release](https://github.com/FabienGreard/baton/releases/tag/v0.6.0), tag, assets, latest redirect, and remote installation are proven. Complete local/remote non-`main` branch cleanup remains pending. GitHub reports repository immutable-release protection enabled while the newly published release remains inside its platform grace interval.

## Ownership returned

Operations retains ownership until publication and cleanup are proven.
