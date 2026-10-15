# Phase C0 remediation review

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
