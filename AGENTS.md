# C0 implementation authority

**ACCEPTED WINDOWS_ONLY_TEST_POLICY:** Windows-only application and CI for C0–C12, per `docs/qa/WINDOWS_ONLY_TEST_POLICY.md` and decision D-010. Windows 11 x64 primary target; Windows 10 x64 only with actual compatibility evidence. Historical YTB/Linux checks are not animation acceptance authority. No active Ubuntu jobs or OS matrix.

This repository is in a temporary C0 source-baseline state on `feat/c0-clean-cutover-contracts`; it is **not** a released dual-mode product. The checked-in YTB implementation is evidence for UI and neutral-infrastructure reuse only. C0 may add documentation, contract fixtures, validators, and baseline evidence. It must not alter production routes, models, migrations, services, or legacy files.

The authoritative transition is the clean-cut plan v3: C1 is an isolated Spine feasibility proof; C2 is the single atomic deletion/replacement change. No contributor may introduce a compatibility mode, YTB data migration, dual read/write path, legacy adapter, or a second workflow authority. Preserve the Cockpit UX named in `docs/architecture/UI_PARITY.md`.

Normative authority, highest first:

1. Explicit user clean-cut instructions.
2. The reviewed plan at `docs/plans/2D_ANIMATION_STUDIO_CLEAN_CUTOVER_IMPLEMENTATION_PLAN_v3.md`.
3. `contracts/animation/` for JSON shapes and the DB/API/semantic architecture documents for behavior.
4. Phase-specific design and QA documents.
5. Executable C0 tests, which verify—but cannot silently redefine—the authorities above.

Any conflict is a blocker until it is recorded and resolved in `docs/architecture/DECISION_REGISTER.md`. Only decisions marked `ACCEPTED` may be described as frozen. A change to table count, seven-stage authority, contract schema, ID semantics, or paid-operation fence requires an explicit decision entry and corresponding tests. Legacy `README.md`, `MANIFEST.json`, V3 schemas, migrations, and tests are temporary source evidence only; they are never animation-product authority.

## Frozen C0 exit and deferred-issue ownership

**C0 acceptance is frozen.** A finding concerning functionality owned by C1–C12 must be recorded under its owning phase in the deferred-issue register of plan v3; it is **not** a new PR #1 blocker unless it demonstrably violates an existing C0 normative contract, baseline integrity, essential security/ownership requirement, prohibited production scope, or mandatory Windows CI gate.

Test each phase only after that phase implements the behavior being verified. C0 does not require real Spine/IK/multi-shot production functionality. Future-phase issues must neither be silently discarded nor used to keep C0 open indefinitely; the phase ownership, acceptance condition and required evidence in the existing v3 plan are the authoritative handoff. C1 remains NOT_STARTED. The narrowly approved C0-EXIT-01 edit of a pre-existing Windows/Bash-coupled legacy regression test is governed by `tools/check_c0_scope.py`; it does not authorize other legacy source or test changes. D-010 Windows-only policy remains binding.
