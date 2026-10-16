# 2D Animation Studio — implementation authority

This repository is **animation-only**. The old YTB product and its migration/routers/worker graph must not be reintroduced.

Order of authority:
1. Explicit clean-cut user requirements.
2. `docs/plans/2D_ANIMATION_STUDIO_CLEAN_CUTOVER_IMPLEMENTATION_PLAN_v3.md`.
3. `contracts/animation/`, especially the frozen SQLite DDL, ChannelDNA v2 and exact 19 accepted C2 endpoints.
4. `docs/architecture/` and `docs/qa/WINDOWS_ONLY_TEST_POLICY.md`.
5. Executable C2 tests are evidence, not a replacement for contracts.

C2 scope is platform + seven-stage projections; C3–C12 actions are disabled, not stubbed to fabricated success. No fallback animation mode, old YTB database migration, hidden LLM or unconfirmed paid request. No automatic merging.

Windows 11 consumer is the primary target; all CI runs on Windows/PowerShell. A Windows Server runner is not consumer Windows 11 proof.

Preserve Cockpit layout and UI primitives. Immutable revisions and CAS must be verified with actual SQLite, including preflushed session ownership. Keep PR Draft when any C2 blocker remains. Follow `docs/architecture/CODING_RULES_C2.md`; do not use retired YTB rules.
