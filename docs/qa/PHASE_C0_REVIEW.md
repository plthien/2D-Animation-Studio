# Phase C0 remediation review

> Prior Ubuntu check results below are historical only; see the newest Windows-only repair section for active gates.

Baseline: `b35834808d99067e362a6e728ce7af8e04d2b6bd`. Audited remediation start: `3a44fedc60092f5f29679c747ea0df70958f0f50`. Branch: `feat/c0-clean-cutover-contracts`; existing PR: [#1](https://github.com/plthien/2D-Animation-Studio/pull/1). No `app/`, `src/`, old migration or dependency-lock source was changed. No user database was opened or migrated.

## Acceptance matrix

| Gate | Exact local evidence | Status |
|---|---|---|
| R0 authority | reviewed v3 plan in `docs/plans`; SHA-256 `39A0677432A511F49DC8C5896BC1D101E8512CC3C7388917083F61B476B08F41`; 56,516 bytes; decision register D-001–D-009 | PASS |
| Ledger | `check_c0_ledger.py`: 813 rows exactly once; ADAPT 174, DELETE 569, EXTRACT 53, KEEP 17 | PASS |
| Reachability | Python AST, TS imports, launchers, package scripts, Alembic and CI roots: reachable 338, unreachable 475, unknown 0, roots 15 | PASS |
| Database | executable fresh SQLite DDL: 14 tables, foreign keys clean, channel-scoped NULL-project revision duplicate rejected | PASS |
| Contracts | 18 Draft 2020-12 schemas; 36 positive fixtures; 108 purposeful negative fixtures; semantic bundle and duplicate-key/non-finite checks | PASS |
| API | 37 unique method/path rows; C2 accepted and later routes proposed; DTO/status/error/CAS/idempotency/lineage/invalidation rules linted | PASS |
| UI G0 | 10 real Chrome PNGs, six routes, three viewports, two dialog clicks plus navigation, all hashes verified | PASS |
| Scope | production `app/`, `src/` and `alembic/versions/` diff is empty | PASS |
| Local C0 tests | 39 passed, 0 skipped | PASS |
| Legacy baseline | Python 1226 passed/6 declared environment skips; legacy contracts 131 schemas/143 operations; Node 160 passed; build and health smoke passed | PASS |
| Dedicated remote CI | [C0 exact-HEAD run 38725859780](https://github.com/plthien/2D-Animation-Studio/actions/runs/38725859780): Ubuntu + Windows; [legacy exact-HEAD run 38725859742](https://github.com/plthien/2D-Animation-Studio/actions/runs/38725859742): backend + frontend + Windows Render | PASS on implementation HEAD `4767189a7ecd3b94e9a6b3833a82f152e39fce42` |

Overall status is **PASS** for implementation HEAD `4767189a7ecd3b94e9a6b3833a82f152e39fce42`: every mandatory local gate, dedicated C0 job and applicable legacy job is green. The PR remains Draft for owner review and is not merged. The PR conversation records the check URLs for the final documentation-only descendant because a commit cannot contain its own future SHA/check-run URL.

## Commands and results

All Python commands used `%TEMP%/c0-ytb-baseline-venv/Scripts/python.exe` on Windows Python 3.12 unless stated otherwise.

```text
python tools/check_c0_ledger.py
PASS tracked=813 rows=813 ADAPT=174 DELETE=569 EXTRACT=53 KEEP=17

python tools/verify_c0_reachability.py
PASS tracked=813 reachable=338 unreachable=475 unknown=0 roots=15

python tools/check_c0_db_contract.py
PASS tables=14 foreign_keys=clean nullable_channel_revision=rejected

python tools/validate_c0_contracts.py
PASS schemas=18 positive=36 negative=108 semantic_bundle=1

python tools/check_g0_evidence.py
PASS screenshots=10 routes=6 viewports=3 actions=3 hashes=verified

python -m pytest tests/c0 -q --confcutdir=tests/c0
39 passed in 4.10s

python -m pytest -q
1226 passed, 6 skipped, 3 warnings in 538.88s

python tools/validate_contracts.py
validated schemas=131 operations=143 platform_registry=28 v4_registry=93

npm.cmd ci --no-audit --no-fund
added 192 packages in 40s

npm.cmd test
160 passed, 0 failed, 0 skipped

npm.cmd run build
1898 modules transformed; build passed in 7.48s; existing >500 kB chunk warning

GET http://127.0.0.1:8030/api/health
200 {"status":"ok","version":"3.0.0-external-authoring.18-rc1"}

git diff --exit-code b35834808d99067e362a6e728ce7af8e04d2b6bd -- src package.json package-lock.json vite.config.ts index.html
exit 0

git diff --name-only b35834808d99067e362a6e728ce7af8e04d2b6bd -- app src alembic/versions
no output

git diff --check
exit 0 (Windows line-ending notices only)

GitHub C0 contract audit, run 38725859780
C0 contracts (Ubuntu, Python 3.12): success
C0 portability (Windows, Python 3.12): success

GitHub Main Candidate Audit, run 38725859742
Backend review gates: success; 1230 passed, 2 skipped, 3 warnings in 300.87s
Frontend and cutover review gates: success
Windows Render review gates: success
```

The six legacy skips are predeclared platform/tool availability cases (Windows/POSIX executable provenance and real FFmpeg coverage), not C0 tests. Dedicated C0 has no skips. The legacy GitHub Windows gate installs FFmpeg and retains its own render coverage.

## Contract coverage

- Ledger tests remove a baseline row, duplicate a row, inject an unknown classification, mark root `app/main.py` unused, and erase an EXTRACT responsibility; each mutation is rejected. All 53 EXTRACT rows name a destination, responsibility and retained/replacement test.
- DB tests execute the complete 14-table DDL, check `foreign_key_check`, both partial uniqueness indexes, composite ownership rejection, statuses/stages, one-winner CAS, transaction ownership conflict and byte-unchanged legacy DB refusal.
- Schema tests run `check_schema` on all 18 contracts, positive and negative catalogs, cross-artifact IDs/ownership, shot-local bounds, 14 unique attachment roles, 16 unique bone roles, rig capability/action targets, asset pins, compiled ordering, exact render frames and voice-last sample timing.
- API tests freeze exact routes and fields, seven stages, typed errors, C2/future availability, lineage fingerprints, DNA invalidation, CAS and idempotency. Removing `expected_head_revision` or adding `voice_first` to accepted authority makes the linter fail.
- G0 tests verify PNG signatures, paths, hashes, sizes, routes, actions and viewports. Removing one image from an isolated copy fails the gate.
- CI tests require exact event-head checkout, pinned Python 3.12 dependencies, Ubuntu and Windows jobs, every validator, C0 pytest, scope guard, `git diff --check`, report upload and evidence upload.

## Confirmed findings and repairs

| Severity | Finding | Repair and rerun |
|---|---|---|
| BLOCKER | G0 was previously text-only/BLOCKED | Captured genuine unchanged-baseline Chrome evidence with disposable data; visual review and hash/missing-image tests pass |
| HIGH | Filename-led ledger could discard reachable UI/runtime code | Rebuilt 813-row ledger from dependency graphs and manual responsibility review; protected UI/root mutation tests pass |
| HIGH | DB prose did not prove NULL uniqueness, FK ownership or CAS | Added executable 14-table DDL and SQLite concurrency/legacy-refusal suite; 15 DB+ledger tests initially passed and full C0 now passes |
| HIGH | Schemas accepted semantically inconsistent artifacts | Replaced shallow schemas/fixtures with 36 valid and 108 negative cases plus cross-artifact validator; fixed an empty-pivot validator crash found by negative testing |
| HIGH | API descriptions lacked exact implementation contract | Added 37-row endpoint registry, DTO/error/CAS/idempotency/lineage/invalidation freeze and mutation linter |
| HIGH | No independent C0 or Windows gate | Added exact-head Ubuntu/Windows workflow, pinned tool requirements, scope and evidence checks |
| HIGH | First remote C0 run loaded legacy `tests/conftest.py` and failed on absent production `pydantic` after every standalone validator passed | Added `--confcutdir=tests/c0` so the independent suite uses only its pinned dependencies; rerun required on the repaired HEAD |
| HIGH | Legacy backend CI used a shallow checkout, so its otherwise passing full suite could not inspect the pinned baseline tree (`1225 passed`, five ledger errors) | Set backend checkout `fetch-depth: 0`; exact-HEAD rerun required |
| MEDIUM | YTB manifest bot generated repeated PR commits | Exempted only this C0 branch from push regeneration; legacy PR CI skips only the YTB manifest generation/diff steps and records the freeze |
| MEDIUM | Earlier contract fixture had a malformed closing delimiter | Corrected during R3 and reran schema plus full C0 tests |

## Manifest policy and remaining limitations

`MANIFEST.json` remains the generated YTB package snapshot created by the two pre-remediation bot commits. It is not animation contract authority and is deliberately not regenerated to include C0-only documents, evidence or validators. Regeneration would create repeated mechanical churn and falsely present C0 evidence as YTB release authority. The narrow workflow conditions apply only to `feat/c0-clean-cutover-contracts`; `main` release behavior is unchanged. Deletion of this package manifest remains C2 work, while animation `rig_manifest`, `render_manifest` and `voice_manifest` contracts remain normative.

No C1/C2 implementation, compatibility mode, production migration, YTB source deletion, backend/frontend behavior change or UI redesign is included. Future `PROPOSED` routes are not available until their owner phase. License/security and later runtime provider gates remain phase-specific work and do not weaken C0. Keep PR #1 Draft for owner review; do not merge it as part of C0 execution.

## Targeted F1–F8 final repair (pending remote CI verification)

Starting SHA: `0805a95a427ecf226fcac3138f7f849ec57461bc` (13,639 PR additions at start). Final SHA is recorded in PR HEAD and subsequent GitHub workflow; this file must not claim a CI run before it completes. The pre-repair historical PASS above applies to earlier HEADs, **not** to this repair.

- F1: positive catalog 1,869 → 918 physical lines; negative catalog 5,990 → 501 physical lines (7,859 → 1,419 total). One canonical fixture for each of 18 schemas, 40 intentional mutation negatives; removed 18 near-duplicate revision examples and redundant full-document negatives. Shared mutation application replaces full invalid payloads. Retained basic missing-field/nested schema checks for every schema, source-lineage negative and 18 cross-artifact representative semantic checks; no future runtime mock tests.
- F2: explicit, exclusive locomotion/gaze/expression/left/right arm channel enforcement, hand-specific grip and overlapping compatible motions. Advanced composition/blending remains deferred.
- F3: compiled shot plan exact identity/order, exact duration, contiguous global frame offsets, render frame completeness and frame-to-shot ownership. Other than explicit versioned future policy, timing overrides are forbidden.
- F4: overflowing floating exponent, nested non-finite numbers and non-finite canonical serialization/hash fail closed.
- F5: `docs/architecture/RENDERER_BOUNDARY.md` freezes pure frame evaluator authority; FFmpeg and future Remotion remain downstream adapters.
- F6: manual high-risk source evidence summarized in `docs/architecture/C0_REUSE_SOURCE_AUDIT.md`; classifications are reuse decisions, not reachability decisions.
- F7: 37 unique API pairs (19 ACCEPTED C2, 18 PROPOSED future), with no new endpoints.
- F8: retained existing exact-head Ubuntu/Windows C0 CI, ledger, DB, evidence, scope and C0-only tests. The C1 future acceptance spec is document-only, NOT_STARTED.

Changed: `tools/validate_c0_contracts.py`, compact fixture catalogs, `tests/c0/test_animation_contracts.py`, API documentation, this review, two new architecture/QA documents and targeted reuse audit. No production or user database modification. Remote CI links/status to be verified independently before reporting a final PASS; no fabricated runtime-test evidence.

## Windows-only F9–F13 targeted repair (2026-10-16)

Starting HEAD `2df15a3005b3ad468058948e25c2a20c0832d8f8`; code HEAD verified before this report: `d6bc60c106d5f9abcca01c5100d3fc3c203cc374`. Final report commit cannot embed its own SHA: use the PR tip and exact-HEAD GitHub Actions as the final source authority. Previous Ubuntu results above are **historical YTB baseline evidence only**, not active animation acceptance gates.

| Finding | Repair |
|---|---|
| F9 | Resolve every action target against frozen shot-local actor/prop coordinates or explicit `spatial_anchors`; reject unknown, ambiguous, incompatible types and nonspatial location IDs |
| F10 | Global per-shot prop ownership across actors and hands, matching grab/carry/place, no two-hand ownership or implicit handoffs; reject ambiguous same-frame transfers |
| F11 | Every initial actor/prop has an explicit finite position and exact approved ID; validated initial `held_by` must be `actor_id:hand` |
| F12 | Compiled action IDs exactly equal approved shot-local actions, deterministic ordering, no missing/foreign/duplicate; explicit no-action static shot allowed |
| F13 | Valid motion test cases assert zero semantic errors; compiled action fixture remains synchronized |

**Windows-only policy:** D-010 and `docs/qa/WINDOWS_ONLY_TEST_POLICY.md`. Primary Windows 11 x64, Windows 10 x64 conditional on separate testing. Windows Server `windows-latest` CI cannot prove consumer Windows compatibility. C1 Spine/PixiJS/FFmpeg and C12 real target tests remain future gates; C1 **NOT_STARTED**.

**Active workflow inventory:** `c0-contract-audit.yml` has only one Windows C0 job (Ubuntu job removed). `scene-assets-v2-candidate-audit.yml` has three transitional YTB baseline jobs migrated to Windows (backend, frontend, render); they remain historical safety tests, not animation contracts. `refresh-release-manifest.yml` uses Windows, preserves exact C0 branch exclusion and guards scoped YTB artifact updates. Both legacy workflows must be deleted/replaced in C2. No active Ubuntu/Linux/macOS job remains.

**Real Windows C0 check on implementation SHA:** [Run 38846323814](https://github.com/plthien/2D-Animation-Studio/actions/runs/38846323814/job/116797563073): `python tools/check_c0_ledger.py`, `python tools/verify_c0_reachability.py`, `python tools/check_c0_db_contract.py`, `python tools/validate_c0_contracts.py`, `python tools/check_g0_evidence.py`, `python tools/check_c0_scope.py`, `git diff --check` all passed. Validator: **18 schemas, 18 positive fixtures, 40 negative mutations**; G0: **10 hash-verified screenshots**; production diff: **0 paths**. `python -m pytest tests/c0 -q --confcutdir=tests/c0 --junitxml=c0-reports/pytest.xml`: **53 passed in 4.53s**. Recheck on final PR HEAD is mandatory; separate Main Candidate Windows legacy status is not inferred from this C0 success.

No production app/src, original YTB repository, old database or `main` modification. No C1/C2 implementation, UI redesign, merge or additional PR. Remaining target Windows 10/11, licensing and real motion/video proof are NOT_RUN, not falsely marked PASS.

## C0 SCOPE FROZEN — FINAL EXIT REVIEW (C0-EXIT-01)

**Starting audited HEAD:** `fab288781d8f2f9f87175b3d92231273664afc65`. **Final report HEAD:** the immutable SHA shown by PR #1 current `head.sha` and its exact-HEAD Windows Actions run; a Git commit cannot contain its own hash. Preserve earlier audit data above as historical, not evidence for later commits.

**Only permitted final C0 defect:** On the starting HEAD, Windows Backend review gates had **1 failed / 1,244 passed / 1 skipped** in the full backend regression: `tests/v4/test_kokoro_setup_static.py::test_release_manifest_refresh_targets_active_branch`. Its test looked for Bash `git push origin "HEAD:${GITHUB_REF_NAME}"` while the active Windows workflow correctly invokes PowerShell `git push origin ('HEAD:' + $env:GITHUB_REF_NAME)`. The failure did not implicate Kokoro implementation.

**Fix:** Keep the regression test and make it parse the actual refresh YAML: active-branch checkout and PowerShell push, no fixed main target, exactly the approved generated manifest/OpenAPI paths for diff/add/staged verification, `contents: write` constrained to its single workflow job, C0 branch excluded from both triggers and execution. No fake Bash strings, test skipping, production code, or manifest regeneration. `tools/check_c0_scope.py` now has a single exact exception `tests/v4/test_kokoro_setup_static.py`; AST comparison against the pinned baseline rejects changes outside the one approved test function. `tests/v4/*` remains forbidden in general.

**Deferred issues:** All **14** stable future IDs and explicit owners/acceptance evidence are in the existing v3 plan's *Deferred issue ownership register*; phase ownership C1 (three), C2, C3, C4, C5, C6/C7, C8 (two), C9, C10, C11 and C12. Detailed C1 handoff is in `docs/qa/C1_FEASIBILITY_TEST_SPEC.md`. These are **DEFERRED / NOT_STARTED; not C0 blockers**. No C1–C12 executable tests or product implementation were added. `C1 = NOT_STARTED`.

**Frozen scope:** 813-file ledger, 14-table SQLite contract, 18 schemas, 18 canonical positives, 40 negative mutations, 53 pre-repair C0 tests, 37 API contract routes, 10 authentic G0 images with verified hashes, Windows-only D-010 and renderer boundary are retained. No `app/`, `src/`, legacy Alembic, user DB or original YTB repository changes; no release manifest edit, no new PR and no merge.

**Mandatory Windows verification on the final HEAD:** `python -m pytest -q tests/v4/test_kokoro_setup_static.py::test_release_manifest_refresh_targets_active_branch`, `python -m pytest tests/c0 -q --confcutdir=tests/c0`, `python tools/check_c0_ledger.py`, `python tools/verify_c0_reachability.py`, `python tools/check_c0_db_contract.py`, `python tools/validate_c0_contracts.py`, `python tools/check_g0_evidence.py`, `python tools/check_c0_scope.py`, `git diff --check`. Four same-SHA Windows jobs required: C0 contracts, Backend review, Frontend and cutover review, Windows Render review. Historical green runs are not transferable to this document's commit. See current PR Checks for the final job URLs and conclusions. **Recommendation is BLOCKED until all four exact-final-HEAD jobs pass; then READY FOR OWNER REVIEW, never auto-merge.**

### Verified final-exit code HEAD evidence — 2026-10-16

Implementation HEAD `6c99540e7132acdd75a6e1ffa7f15e25e60f3a2c` has now passed **all four mandatory Windows jobs**, on one exact SHA, without test skips or bypasses added by this repair:

| Windows job | Exact evidence | Result |
|---|---|---|
| C0 contracts (Windows Python 3.12) | [run 38850530421 / job 116810513301](https://github.com/plthien/2D-Animation-Studio/actions/runs/38850530421/job/116810513301) | **PASS**: 53 C0 tests, 18 schemas, 18 valid and 40 negative fixtures, 14 SQLite tables, 813 ledger paths, 10 G0 images with hashes, 0 production changes |
| Backend review gates | [run 38850530539 / job 116810513965](https://github.com/plthien/2D-Animation-Studio/actions/runs/38850530539/job/116810513965) | **PASS**: 1,245 backend tests passed, 1 preexisting skip; legacy Windows manifest assertion repaired |
| Frontend and cutover review gates | [run 38850530539 / job 116810514098](https://github.com/plthien/2D-Animation-Studio/actions/runs/38850530539/job/116810514098) | **PASS**: 160 tests and build |
| Windows Render review gates | [run 38850530539 / job 116810514130](https://github.com/plthien/2D-Animation-Studio/actions/runs/38850530539/job/116810514130) | **PASS**: 33 render/launcher tests |

The targeted regression is part of the passing full backend pytest suite, not a separately claimed command invocation. No Windows 10/11 consumer runtime, Spine/IK or final video proof was executed; these are deferred to C1/C12.

**Final reporting-commit rule:** adding this evidence creates a new documentation-only HEAD, so the four results above are immutable evidence for the *previous code HEAD*, not an automatic PASS for the new commit. The current PR #1 tip must itself have all four Windows jobs PASS in GitHub Actions. Once that exact-tip condition is verified, the outcome is **C0 READY FOR OWNER MERGE APPROVAL** (PR remains Draft; only the owner chooses whether to merge). Otherwise, **C0 BLOCKED** with the failing job as evidence. Final HEAD identity and its run links are recorded in the PR description, which can be updated without making a new commit.
