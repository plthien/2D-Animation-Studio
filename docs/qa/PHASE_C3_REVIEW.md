# C3 — Authoring & Asset Production: targeted QA evidence

**PR:** https://github.com/plthien/2D-Animation-Studio/pull/6 (one Draft PR; no merge).
**Branch:** feat/c3-authoring-assets.
**Base main HEAD:** f86f9178278230158f06aa3310ed3553a0d388a7.
**Verified implementation HEAD:** `8da15b1a0108bd10d423c507eb89ba0efb273729` (before this QA-report-only update). Exact-SHA Windows C3 GitHub Actions: https://github.com/plthien/2D-Animation-Studio/actions/runs/39027158050 — SUCCESS.
**Test policy:** Windows-hosted C3 CI now, integrated/consumer Windows 11 in C7.

## Completed feature implementation

- Authoring: external Topic → Script → optional Analysis → ShotPlan prompt/reservation, import, schema/semantic validation, exact Script spans, source hash, immutable revisions, CAS approval and history.
- Readiness/lineage: computed Authoring/Resolver/Generation stage states; rejects stale ShotPlan after Script/Topic/source revision change. Visual style invalidates asset eligibility without corrupting Script approvals.
- Resolver: deterministic requirements derived from approved ShotPlan, immutable requirements/resolution revisions and resolver head, exact channel-scoped compatible pins and same-channel reuse, rejects cross-channel bindings. Rig capability validation remains pending C4.
- Local images: actual bounded PNG/JPEG/WebP decode, SHA/bytes persistence, project-owned candidate review, exact version pin, preview and restart recovery. Precommit failure removes only unreferenced attempt files.
- G-Labs: extracted donor glabs_webhook_client, bounded_http_transport, transport_policy and neutral safety routines from plthien/ytb-ai-studio at 393d0eb5516ac8bb8455f859b79bfc64388b128e, adapting to animation namespaces. Actual donor HTTP routes are POST api/image/generate, GET api/status/{task_id}, GET api/result/{task_id}, validated image download. One durable owner-consented operation authority uses existing operations/operation_tasks/jobs/artifacts and asset_versions; exact frozen quote/attempt, pre-I/O submit fence, unknown acknowledgement with NO auto resubmit, manual existing-handle GET reconciliation, cancellation, polling, candidate creation. No legacy YTB domain DB or orchestration imported.
- Studio UI: functional panels for authoring, resolver and generation with explicit consent controls and persisted operation status. No fake G-Labs image; no paid call at startup.
- API: exactly 19 frozen C2 ACCEPTED route pairs preserved, 23 implemented C3 ACCEPTED route pairs registered; C4–C6 remain PROPOSED/absent. Checker validates full runtime/registry parity.
- Targeted dependencies: Pillow 12.3.0, python-multipart 0.0.31.

## Test proof and limitations

- **PASS:** Windows C3 CI run https://github.com/plthien/2D-Animation-Studio/actions/runs/39026421773 on immutable HEAD 4dd13c38ee6a064a31364dca4320ee6b1f2783bf: Python C3 tests, frontend TS/Vite build, API checker, actual Chromium Studio browser smoke.
- Real Chromium smoke used Vite + FastAPI + disposable SQLite (no mock backend): Channel → approved ChannelDNA → Project → imported/approved Topic/Script/ShotPlan → Resolver → real local PNG import → version approval → pin → browser refresh → backend restart, with C3 screenshots uploaded as Actions artifact.
- **PASS on 8da15b1a:** updated stale-lineage, deterministic resolver, exact pin/failure cleanup, mocked provider HTTP and ambiguity/reconciliation, typed error mapping, targeted C2 API/Project regressions, clean frontend build, full C3 API checker and genuine Chromium backend/SQLite/restart smoke.
- GLABS_ADAPTER_IMPLEMENTED = YES (source implementation present).
- GLABS_MOCK_CONTRACT_TEST = PASS — exact implementation HEAD `8da15b1a` Windows CI.
- GLABS_LIVE_E2E = NOT_RUN — OWNER DEFERRED TO C7.
- WINDOWS_CONSUMER_E2E = NOT_RUN — C7.
- C2_FULL_PLATFORM_E2E = DEFERRED — OWNER DECISION.
- Actual provider fee estimation/capping has NOT been verified. Owner-defined consent ceiling is NOT a provider-enforced billing cap; UI discloses this, and C7 live-price verification is necessary before owner spending.
- C4 rig/Spine, C5 motion/director, C6 render/voice/MP4 are intentionally excluded.

## Self-review and merge verdict

All artifacts are persisted in the original fourteen-table animation-only SQLite and managed artifact root. No automatic merge or real paid network call. **C3 READY FOR OWNER MERGE APPROVAL — GLABS LIVE TEST DEFERRED TO C7**, based on exact implementation HEAD `8da15b1a` green Windows C3 CI with real Chromium, fake provider and relevant regressions. This report-only commit changes no runtime/test/contract files. PR remains Draft pending owner decision; no automatic merge.

## Five-finding C3 integrity repair — final targeted self-review (2026-10-17)

Audited baseline: 39cf5e611d5ca4d649302e0e10436d3b84c6a627.
Verified implementation HEAD: 51b981965acde411885fe01d6f89af2595c522ad.
Exact-SHA Windows C3 CI: https://github.com/plthien/2D-Animation-Studio/actions/runs/39034475023 — **PASS**: Python C3 tests, two affected C2 regressions, TS/Vite build, API checker, and genuine Chromium → FastAPI → SQLite journey with user-supplied PNG, approval, pin, refresh and backend restart.

### Scoped repair checklist

- **H1 PASS:** cancellation-safe provider acknowledgement, preserving a known task handle even after cancel; distinguish queued cancel from unknown submit result, prohibit automatic second paid POST. Regression: before/during submit, valid/missing acknowledgement, repeated cancel/advance, cancel during download and restart.
- **H2 PASS:** single-owner SQLite operation lease/task claim, CAS transitions, idempotent provider result materialization by operation/task/provider task/result index and verified hash. Concurrent advance/poll, post-download interruption, post-candidate crash, expired lease, changed result digest and terminal replay covered by deterministic fake-provider tests. Result candidates remain traceable.
- **M1 PASS:** same-transaction exact Snapshot/ShotPlan/style validation and canonical sorted pin mapping, not resolved count alone. Midpublication swap/approval fault injection rejects stale artifact with rolled-back SQLite changes.
- **H3 PASS:** authoritative backend prompt_text includes full reserved identities, source fingerprints and metadata, DNA/Topic/Script IDs and SHAs, optional current Analysis, actual source text, and frozen JSON schema. UI copies actual prompt with a Windows-compatible user-gesture method and visible errors. Chromium uses real clipboard content to build and import external JSON; stale optional Analysis excluded.
- **H4 PASS:** new or reused resolution artifact passes exact source/pin validation and CAS head activation. A → B → A reuses immutable A and restores Resolver head without duplicate artifact; monotonic head revision and idempotent repeat verified.

### Bounded conclusion and deferrals

No new SQLite tables, status enum, paid network request, legacy YTB runtime or C4–C7 functionality was introduced. Scoped self-review found no remaining confirmed H1/H2/M1/H3/H4 blocker on the tested implementation HEAD. The next QA-only commit changes no runtime/contract/tests and should also have an exact-HEAD CI check.

- GLABS_ADAPTER_IMPLEMENTED = YES; GLABS_MOCK_CONTRACT_TEST = PASS.
- GLABS_LIVE_E2E = NOT_RUN — OWNER DEFERRED TO C7.
- WINDOWS_CONSUMER_E2E = NOT_RUN — C7.
- C2_FULL_PLATFORM_E2E = DEFERRED — OWNER DECISION.
- No provider-enforced billing cap has been verified; live pricing/consent validation remains C7.

**C3 READY FOR OWNER MERGE APPROVAL — FIVE REPAIR GATES PASS; GLABS LIVE DEFERRED TO C7.** PR #6 remains Draft, without merge.
