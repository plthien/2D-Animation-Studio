# 2D Animation Studio — implementation authority

This repository is **animation-only**. The old YTB product and its migration/routers/worker graph must not be reintroduced.

Order of authority:
1. Explicit clean-cut user requirements.
2. `docs/plans/2D_ANIMATION_STUDIO_FAST_TRACK_PLAN_v4.md` for active C3–C7 execution and `docs/plans/2D_ANIMATION_STUDIO_CLEAN_CUTOVER_IMPLEMENTATION_PLAN_v3.md` for historical/frozen C0–C2 requirements.
3. `contracts/animation/`, especially the frozen SQLite DDL, ChannelDNA v2 and exact 19 accepted C2 endpoints.
4. `docs/architecture/` and `docs/qa/WINDOWS_ONLY_TEST_POLICY.md`.
5. Executable C2 tests are evidence, not a replacement for contracts.

C2 scope is platform + seven-stage projections; C3–C12 actions are disabled, not stubbed to fabricated success. No fallback animation mode, old YTB database migration, hidden LLM or unconfirmed paid request. No automatic merging.

Windows 11 consumer is the primary target; all CI runs on Windows/PowerShell. A Windows Server runner is not consumer Windows 11 proof.

Preserve Cockpit layout and UI primitives. Immutable revisions and CAS must be verified with actual SQLite, including preflushed session ownership. Keep PR Draft when any C2 blocker remains. Follow `docs/architecture/CODING_RULES_C2.md`; do not use retired YTB rules.

From 2026-10-17 the owner explicitly consolidated **historical C3–C12 into exactly five implementation phases C3–C7**. Seven product workflow stages remain unchanged. Each new feature phase gets one vertical PR; internal workstreams are commits, not extra PRs. C3–C6 run targeted Windows tests and practical smoke gates; C7 owns final integrated Windows platform/consumer Windows 11 tests previously deferred by owner at C2 merge. Do not confuse deferral with PASS.

The tool is **local, single-user**. Prioritize working animation, reliable SQLite/assets, no surprise paid calls, safe local processes, credentials and localhost binding. Do not add SaaS RBAC/auth/multi-tenant features or block on unrelated/unreachable security advisories; address demonstrable risks proportionately. License requirements still apply.
