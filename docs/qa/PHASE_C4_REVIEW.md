# PHASE C4 — Character Rigging Studio (working review)

**Repository:** plthien/2D-Animation-Studio  
**Base merged C3 main:** `cb1447b41043dba8f6b9a52f3216567cbda61c83`  
**PR:** https://github.com/plthien/2D-Animation-Studio/pull/7 (Draft, NOT merge-ready)  
**Last testable implementation SHA before this report:** `bb3b0c866ca68b69be137e9f81a06aa29b360366`  
**Exact HEAD validation:** pending Windows C4 run https://github.com/plthien/2D-Animation-Studio/actions/runs/39087616728; this document does not anticipate its outcome.

## C4 vertical work in this PR

- Approved channel-owned C3 actor image is verified by exact asset-version, source SHA, approval status and visual-style SHA before draft extraction; cross-channel lookup fails.
- Native Pillow pixel-assisted foreground segmentation creates real raster masks; conservative Voronoi partitions use source pixels only. All role boundaries and occluded anatomy are **uncertain and unreviewed**. This is not image-understanding or hands-free human segmentation.
- The Cockpit Rigging Workshop offers direct mask paint/erase, normalized pivot and z-layer editing, transparent PNG replacement, per-role review and reset. Each edit creates a revisioned draft file; saved revisions survive SQLite/backend restart.
- Candidate Spine 4.2 JSON with actual mapped bones, attachments and a real non-overlapping PNG texture atlas can be exported after fourteen nonblank parts are reviewed. The official Spine/PixiJS packages are pinned at 4.2.120 / 8.16.0; the Studio viewport attempts real runtime loading and pose switching.
- Backend **does not yet trust browser-provided loader evidence**. Rig approval fails closed with `RIG_RUNTIME_NOT_VERIFIED`. No rig is marked approved and no motion capability beyond idle is claimed. Rigging readiness projection is not yet integrated; C5/C6 remain blocked.

## Inventory decisions

- **Sprites:** exactly fourteen frozen roles; source contract has `foot_l` but not `foot_r`. Do not invent a 15th sprite. Right-foot bone may exist, but no independently extracted right-foot sprite is claimed. This means visual adequacy still requires review.
- **Bones:** exactly sixteen mandatory roles: root, hip, chest, head, left/right upper arm, lower arm, hand, upper/lower leg and foot. `neck` is optional in the schema, not the mandatory seventeenth role (D-004).
- Every automated partition is a *proposed region*, not a reliable anatomical label. Reconstructed/painted/externally supplied parts have distinct provenance.

## Honest preliminary C4 gate matrix

| Gate | Status | Evidence/remaining acceptance |
|---|---|---|
| C4_EXTRACTION | NOT_VERIFIED | Pixel code and Windows tests submitted; need full G2 accuracy review |
| C4_MANUAL_EDIT | NOT_VERIFIED | Revisioned mask/pivot code and tests; browser operation and reload smoke missing |
| C4_PARTS_14 | NOT_VERIFIED | Fourteen-role export test; independent visual review missing |
| C4_BONE_ROLES | NOT_VERIFIED | Contract mapping tests; official loader still unverified |
| C4_SPINE_EXPORT | NOT_VERIFIED | Real atlas/JSON created; runtime compatibility proof missing |
| C4_OFFICIAL_RUNTIME_LOAD | NOT_RUN | No real exported rig has been loaded in a verified Chromium CI job |
| C4_POSE_PREVIEW | NOT_RUN | UI implementation is not runtime evidence |
| C4_G2_TWO_REAL_RIGS | NOT_RUN | Two test character drawings are distinct, but two playable approved rigs not verified |
| GLABS_LIVE_E2E | NOT_RUN — C7 | Owner-deferred paid test; no spending in C4 |
| WINDOWS_CONSUMER_E2E | NOT_RUN — C7 | Windows Server CI is not consumer Windows 11 evidence |

**Initial Windows run** https://github.com/plthien/2D-Animation-Studio/actions/runs/39087430450 was red: 1 failed and 2 passed, due to `rig_versions` frozen table 10-column INSERT mismatch. Fixed in `bb3b0c8`; rerun evidence required.

## Licensing

The production runtime is official `@esotericsoftware/spine-pixi-v8@4.2.120` + `pixi.js@8.16.0`. An installed package does **not** establish a Spine integration/editor license. The official C1 Spineboy evaluation asset is not treated as an approved production or commercially redistributable character. The two disposable test drawings are original programmatic test fixtures; no claim that a separately owned customer character was supplied.

## Blocking C4 items before owner approval

1. Independently run official Spine/Pixi loader against both exported original-source rigs, verify atlas, exact bones/attachments and poses, record actual screenshot hashes.
2. Implement trustworthy runtime proof, candidate review/CAS approval, immutable stage head/readiness/reuse, stale source and changed part handling.
3. Complete true browser→FastAPI→SQLite mask/pivot edit, pose, approval, refresh/backend-restart smoke on Windows.
4. Run full G2 two distinct character visual review and save actual evidence/metrics.
5. Achieve passing exact final HEAD Windows C4 CI, API registry parity and frontend build.

**Decision: C4 BLOCKED — official runtime G2 acceptance and immutable rig approval unverified.** No merge and no C5 start.
