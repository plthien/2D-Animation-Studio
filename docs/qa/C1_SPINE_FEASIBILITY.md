# C1 Spine/PixiJS feasibility — evidence ledger (G1 BLOCKED)

- **PR:** https://github.com/plthien/2D-Animation-Studio/pull/3 (Draft; do not merge)
- **Branch:** `feat/c1-spine-feasibility`; base `main` at `4ce03bed0b0c95b5de11709ee13830a152b46774`.
- **Task's previously verified main:** `eb4c5da899f74be066665395165db43a6b11bf1c`. Ahead by one commit touching only legacy `MANIFEST.json` before C1 branch creation; reconciled rather than silently assuming old SHA.
- **C1 HEAD:** obtain immutable GitHub PR head.sha and exact job SHA. This documentation must not claim future commit SHA/CI verdict.
- **Status:** `G1 = BLOCKED`. No approved Spine Editor integration license/rig license evidence, no user-provided manual rig/atlas/texture, no consumer Windows 11 access in this execution environment. No actual Spine frame or MP4 has been produced. No visual proof, FFprobe JSON, frame hashes or G1 PASS is claimed.

## Actual code implemented

`experiments/spine-feasibility/` is isolated. Node 22 ESM modules implement one 240-frame 24fps shot, frame-local absolute evaluation without prior-frame simulation, ownable prop and hand conflict validation, static-only shot, explicit target anchors and distinct locomotion/arm pose outputs. Test samples: 0, 48, 97, 143, 239, arbitrary permutations. Vite browser module loads only genuine **official** Spine 4.2 via `Spine.from` and PixiJS 8.16 WebGL; no fake renderer or generated rig. Local PNG capture through Playwright uses the real canvas and requires a verified rig. FFmpeg/FFprobe drivers and per-frame/source SHA manifest are implemented but **NOT_RUN** without authorized assets.

The sample scenario includes these boundaries: 0–23 idle, 24–71 walk, 72–95 reach, 96–113 grab, 114–167 carry, 168–195 place, 196–239 react. Exact 240 frames, 1280×720. There is no promise this particular motion will meet visual continuity for an arbitrary third-party rig: root scale, hand alignment, leg ground contact and release need **human review and tuning of a lawful rig**. Automated source tests alone cannot show an animated result.

## Licensing and provenance (hard prerequisite)

Official documents:
- https://esotericsoftware.com/spine-pixi — Spine 4.2 `Spine.from`, PixiJS v8 ≥8.16.
- https://esotericsoftware.com/spine-versioning — match exported data/runtime major.minor.
- https://esotericsoftware.com/spine-runtimes-license
- https://esotericsoftware.com/spine-editor-license — Trial explicitly does not grant runtime integration rights.

Pinned npm dependencies in isolated lockfile: `@esotericsoftware/spine-pixi-v8@4.2.120`, `pixi.js@8.16.0`, `vite@6.3.5`, `playwright@1.55.0`. **Version pinned ≠ runtime proven.** No Spine skeleton, atlas, image or licensed example has been committed. `assets/provenance.example.json` is only a schema/template; `public/assets/provenance.json` must be privately supplied with real evidence and SHA256, then `npm.cmd run c1:preflight` must pass. No authorized asset provenance or asset hash is available as of this report.

## Acceptance matrix

| Gate | Status | Required evidence |
|---|---|---|
| C1-MOTION-01: pure hand rule | Implemented; test result from Windows C1 job only | One grip→carry→place valid, same occupied hand reach/point rejected with frame interval; opposite hand independently allowed |
| C1-MOTION-01: real poses | BLOCKED | Official rig video/frame evidence of occupied hand and compatible opposite-hand action |
| C1-FIXTURE-02: canonical C0 example | Corrected in C1 diff | Idle-only initial and final actor/prop states equal; test static frame indices 0,48,143,239 |
| C1-RUNTIME-03: actual rig | BLOCKED | Rights record, matching Spine export, atlas textures and visible articulated bones |
| 240 real frames 1280×720/24fps | NOT_RUN | PNG manifest with 240 actual Spine/Pixi captures and all hashes |
| Independent render-order / pixel repeatability | NOT_RUN | Real browser contexts, sampled pose/pixel SHA |
| 10-second H264 MP4/FFprobe | NOT_RUN | Decodable MP4, FFprobe JSON, exact frames/fps/duration, SHA |
| Consumer Windows 11 | NOT_RUN | Environment report, local run log, visual/manual review |

`WINDOWS_11_REAL_DEVICE = NOT_RUN`. This GitHub-hosted Windows Server runner is not a Windows 11 consumer test.

## Test and evidence procedure

```powershell
cd experiments/spine-feasibility
npm.cmd ci
npm.cmd run c1:test
# Install approved private rig and complete public/assets/provenance.json
npm.cmd run c1:preflight
npm.cmd run c1:render
npm.cmd run c1:verify
```

Only after the legal/runtime prerequisites are satisfied should the Windows CI save `output/frames/*.png`, `output/manifest.json`, `output/g1-spine-feasibility.mp4` and `output/ffprobe.json`. No evidence artifact is currently available for those outputs. Artifacts expire under the workflow's retention policy; keep hashes and reproduction instructions.

## Product boundary

No production `app/` / `src/`, migrations, API, databases, Remotion, C2 cutover, C6 segmentation, C7 automatic rig, C8 full motion/IK, C10 multi-shot or C11 voice implementations. Any expanded rig/body geometry/IK claims remain in their owning later phase and must not be inferred from isolated evaluator tests. The experiment stays Draft/BLOCKED until licensed real rig, real visual proof, exact-head CI and Windows 11 target evidence exist.

## Verified implementation checkpoint (historical code HEAD)

At implementation SHA `eb03d87e3debb48bc35542ef1478e9c0b1f5ce87`, the dedicated [Windows C1 run 38858122240](https://github.com/plthien/2D-Animation-Studio/actions/runs/38858122240) recorded **9/9 core tests PASS** and [C1 scope](https://github.com/plthien/2D-Animation-Studio/actions/runs/38858122240/job/116834061619) **28 changed paths, 0 production paths**. The parallel [Windows C0 regression](https://github.com/plthien/2D-Animation-Studio/actions/runs/38858122224) passed. The [real G1 job](https://github.com/plthien/2D-Animation-Studio/actions/runs/38858122240/job/116834228958) deliberately **FAILED the legal-asset preflight**: `SPINE_LICENSE_OR_ASSET_BLOCKED: no approved provenance.json`. It never ran Spine frame rendering or made a video, as required by fail-closed policy.

An inherited manifest refresh had initially changed legacy `MANIFEST.json` on the feature branch before branch-specific protections were installed. That generated change was reverted to byte-identical `main`, and both transitional manifest workflows now exclude this branch. It is not C1 product authority.

**Provenance of these numbers:** exact code checkpoint above. Later changes (including browser bundling and independent FFprobe frame-count verification) require a fresh exact-HEAD Windows run. The final immutable SHA and CI links are recorded in PR #3's description, which can be updated without a new commit. No actual PNG, contact sheet or MP4 exists or is claimed.
