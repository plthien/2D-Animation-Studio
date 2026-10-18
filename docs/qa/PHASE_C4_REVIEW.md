# PHASE C4 — Character Rigging Studio — final targeted-repair review

**PR:** https://github.com/plthien/2D-Animation-Studio/pull/7 (keep Draft pending exact final-head CI).  
**Base merged C3 main:** `cb1447b41043dba8f6b9a52f3216567cbda61c83`.  
**Audited repair baseline:** `d81c3efc6676bdd4740675e5bd2a38ace11ef8ff`.  
**Fully tested repair implementation SHA:** `618e317393aec535a7c678e56aa6136d52e39273`.  
**Windows C4 exact-code-SHA run:** https://github.com/plthien/2D-Animation-Studio/actions/runs/39100956495 — **SUCCESS** (all steps, including genuine Chromium); evidence artifact: https://github.com/plthien/2D-Animation-Studio/actions/runs/39100956495/artifacts/12126622329.  
**Final documentation commit/PR HEAD:** use GitHub PR HEAD; final-head workflow must be checked again after this documentation update. This report never pre-claims that future run.

## Implementation and targeted finding dispositions

| Finding | Disposition | Verification |
|---|---|---|
| C4-H1 — pivot and crop-space mismatch | **PASS (tested)** | `normalized_top_left` pivots now refer to full source canvas, with Spine Y-up conversion and pivot-preserving atlas crop. Replacement PNG has saved canvas-normalized x/y/width/height and is raster-composited before export. Pixel-coordinate regression covers off-center pivots, trimming, replacement placement and restart. |
| C4-H2 — newer source version draft | **PASS (tested)** | Logical rig ID remains tied to asset, repeated same-source start reopens existing draft, changed approved asset version creates a fresh revision and all parts start unreviewed. Immutable prior rig versions and exported bytes are not overwritten. |
| C4-H3 — same-channel reuse | **PASS (tested)** | Read-only version-info endpoint and official viewport no longer require the origin project's draft. Project B successfully pins and previews Project A's approved rig version; unchanged skeleton SHA checked across restart. |
| C4-H4 — all actor requirements | **PASS (tested)** | Rig approval no longer approves project stage. Project-owned `project_rig_resolution.v1` revisioned artifact records exact current ShotPlan/Resolver actor pins, selected immutable rigs, capabilities and manifest digests. One of two required actors = incomplete, both = approved. Project B's single pinned actor = approved. No ShotPlan cannot falsely approve stage. CAS revision checking and stale source/requirements revalidation apply. |
| C4-H5 — manifest integrity | **PASS (tested)** | Actual immutable PartsManifest, RigProfile and RigManifest bytes, size, relative path, artifact ID, schema/kind and owner checked against SQLite on proof/approval/read-only open/selection/readiness. Injecting individually modified *valid JSON* into all three previously approved files moved Project B readiness to stale; restoring originals restored readiness. |
| C4-G2 — visible pose quality | **PASS for the two controlled G2 characters; limited generalization** | Actual official Spine/Pixi WebGL canvas screenshots and contact sheet manually inspected. Distinct characters are continuous in idle, left arm remains attached in reach/grab, legs articulate in a bounded stepping pose, neutral reset reproduces idle. No significant floating pieces or gross displaced torso. `walk` is only a diagnostic stepping pose (not C5 locomotion). Assisted Voronoi masks are not claimed to understand human anatomy autonomously. |

## Exact test evidence

- **C4 focused Python:** **7 passed**, 2 warnings, **11.53 s**. Tests use actual PNG pixels and disposable SQLite, including image-version drafts, source-space pivot math, replacement crop/placement persistence, and schema-valid manifest tamper rejection.
- **Affected C3 regression:** **14 passed**, 2 warnings, **15.47 s**.
- API registry parity, frontend TypeScript/build, exact-SHA checkout: **PASS**.
- Real Windows Chromium → FastAPI → SQLite → official Spine/Pixi loader: **PASS**.
- Actual image source import/approval, source binding, mask paint+erase via UI, pivot via UI, 14 individual part corrections and review per character, atlas/skeleton export, live pose captures, runtime proof, immutable rig approval, refresh and backend restart: **PASS**.
- Project A→B reuse via exact approved rig version, distinct read-only official loader and persisted actor binding: **PASS**.
- Approved parts/profile/manifest tamper fault-injection and recovery: **PASS**.
- G2 contact sheet generation and GitHub Actions artifact upload: **PASS**.
- The exact run URL above refers to implementation HEAD `618e3173`. Final documentation-head CI must be inspected separately.

## Two genuinely different G2 character images

These are independent, original programmatically authored disposable test drawings from `tools/c4_fixture.py`, 320×400 RGBA. They are **not** Spineboy and not customer-owned samples. The 14 source-specific semantic PNGs per character are deliberately authored correction references rather than fictitious auto-segmentation successes. The first-pass pixel extractor still reports uncertain/unreviewed regions. Each character uses explicit 14/14 corrections, pivot/layer/placement review, and then approved immutable output.

| Evidence | Character A | Character B |
|---|---|---|
| Source SHA-256 | `d77ce3b48b0c930e5ec8bb41d3d85ca140f11d1b346795338d312fcec23d621e` | `643e6ed9b2d5debe986cd710fcb710d72869c46a1697859ee75524bbd0aba74d` |
| Source asset version | `av_3b1f600e9dc940eba06406e1f7df2043` | `av_dca32369002c4fd3ad0edcc7089e15d2` |
| Logical rig | `rg_cc1c01632cfd4c5cb41eaa6eedf86293` | `rg_86cabec6eab1454fb2433648a30b94bd` |
| Approved rig version | `rv_586b1b3048344b90ac91ab4666cc7fbe` | `rv_ab6929a6fe044a629bdb91b929db0c9b` |
| Corrected reviewed sprites | 14/14 | 14/14 |
| Mandatory mapped bones | 16/16 | 16/16 |
| Direct idle-canvas PNG SHA | `fcd8763fa3860a8bcb0188a745f09c9b96ec585182fa3ad29abf8567379cbc19` | `c21c5345219d1e88698c361be0e812e474eb0c73cbdedeabe6eda27b7bc53e40` |
| Official loader / five poses / approval / reload | PASS | PASS |

The same exact approved Character A rig was reused by Project B; original skeleton SHA remained `44d1d0f59c61136c6c32be51608abe6067e62180bd3c2b5ea48ef89dcf4ad190` across reuse and backend restart. These rig/asset IDs are **ephemeral CI fixture IDs**, not hardcoded application identities.

**Screenshot evidence:** GitHub Actions artifact `12126622329` contains both source images, both pivot/joint overlays, A/B idle, walk, reach and grab **direct canvas PNGs**, the cross-project preview, backend-restart preview and `c4-g2-direct-canvas-contact-sheet.png`. The contact sheet was opened and visually reviewed, not approved by hash uniqueness alone. Compared with the prior audited screenshots, the corrected fixture rigs do not exhibit conspicuously detached limbs. Minor flat-cutout elbow contours and exaggerated stepping remain quality limitations, not blockers for C4's bounded diagnostic pose requirement.

## C4 gate matrix

| Gate | Status | Basis |
|---|---|---|
| C4_EXTRACTION | PASS | Real pixel masks created; source uncertainty retained |
| C4_MANUAL_EDIT | PASS | UI mask/pivot, explicit corrected PNG/placement and persisted revision |
| C4_PARTS_14 | PASS | 14 reviewed nonblank alpha sprites for A and B |
| C4_BONE_ROLES | PASS | 16 actual mapped runtime bones |
| C4_SPINE_EXPORT | PASS | Actual valid Spine 4.2 skeleton, atlas page and exact digest chain |
| C4_OFFICIAL_RUNTIME_LOAD | PASS | Real official Chromium/Pixi/WebGL load for both and Project B reuse |
| C4_POSE_PREVIEW | PASS | Real bone articulation in idle/walk/reach/grab/neutral reset |
| C4_G2_TWO_REAL_RIGS | PASS | Two distinct reviewed, approved, persistent rigs + visual contact sheet |
| GLABS_LIVE_E2E | NOT_RUN — C7 | Paid service explicitly excluded |
| WINDOWS_CONSUMER_E2E | NOT_RUN — C7 | Windows Server Actions is not consumer Windows 11 |

## Frozen inventory, official versions and licenses

- 14 sprite roles: frozen `parts_manifest.v1`. Only `foot_l` is a standalone foot sprite in that inventory. Right foot is represented by the right lower-leg artwork plus a separate right-foot **bone**; no invented 15th sprite.
- 16 mandatory bone-role mappings, optional `neck` schema enum member as documented in D-004. The actual skeleton contains 16 required bones; sprites and bone roles are not one-to-one.
- Official packages: `@esotericsoftware/spine-pixi-v8@4.2.120`, `pixi.js@8.16.0`; Spine JSON `4.2`. Generated PNG textures are local test artifacts, not Spineboy evaluation art.
- Spine runtime/editor integration and commercial redistribution **license rights still must be confirmed by the owner** before commercial use. npm installation and technical loader success are not proof of a commercial Spine license. No G-Labs payment, voice synthesis or credential redistribution was used.

## Exact C5 handoff and deferred C7 scope

C5 receives project-owned resolved actor→approved rig-version mappings pinned to the current ShotPlan/Resolver source and frozen manifest/sprite/skeleton/atlas file hashes. Unsupported capabilities must be rejected; no idle fallback. General motion compiler, production two-bone IK, world scheduling and nine-action animation remain C5, multi-shot delivery C6. Paid G-Labs live end-to-end and consumer Windows 11 acceptance remain C7. Do **not** broaden C4 with those phases.

## Historical audit and final decision

The pre-repair screenshots and earlier failing CI jobs are **superseded historical evidence**, not retroactively PASS. The original C4 working review's no-approved-rig statements no longer describe this implementation. The code-level exact-SHA Windows C4 run passed and the visual evidence was reviewed. Merge approval still requires a successful exact final PR HEAD workflow after this documentation commit; PR stays Draft until that check is complete.
