# C1 real Spine/PixiJS feasibility — isolated noncommercial experiment

PR #3 is an isolated G1 technology proof, not C2 production. Uses official `@esotericsoftware/spine-pixi-v8@4.2.120`, `pixi.js@8.16.0`, pinned Vite/Playwright and Node 22. The default official candidate is **Spineboy Pro (Spine 4.2.22)**, an example with explicit *noncommercial* image rights; it cannot be used as a commercial product asset. See `assets/README.md` for pinned source URLs and legal restrictions. Neither npm installation nor a Spine Trial grants general commercial integration rights.

## Windows PowerShell reproduction

Install Node 22, Chrome, Windows FFmpeg and FFprobe first. For official noncommercial **private evaluation**:

```powershell
cd experiments/spine-feasibility
npm.cmd ci
$env:C1_OFFICIAL_SAMPLE_EVAL='1'
$env:C1_USAGE_SCOPE='private_local_evaluation'
$env:VITE_C1_SCOPE='private_local_evaluation'
npm.cmd run c1:acquire-example
npm.cmd run c1:preflight
npm.cmd run c1:test
npm.cmd run c1:render
npm.cmd run c1:verify
```

For another licensed 4.2 rig, provide private `public/assets/provenance.json` and SHA-matched skeleton/atlas/textures. Ensure the usage scope and legal notices match the actual permissions; do not fake license acknowledgements. The official sample is intentionally downloaded at runtime into a gitignored folder; it is not bundled. All official example screenshots/exports must accompany its noncommercial image-license notice.

`npm.cmd run dev` loads the real rig using `Spine.from({skeleton, atlas, autoUpdate:false})` (4.2 API). The evaluator derives shot movement/grip from the approved actions and validates exact frozen action identity. Rendering uses actual Spine bone transforms and the hand bone for prop grip; no prerecorded footage or fallback fake rig.

Successful G1 **requires** real 240 PNG captures at 1280×720, 24fps, deterministic frame/pixel hashes in independent contexts, 10.000s verified H264 MP4 with FFprobe frame decoding, visual review of all seven motion phases including continuous pickup/drop, AND real consumer Windows 11 evidence. GitHub `windows-latest` is Windows Server and does not prove Windows 11 compatibility.

Scope excludes C2 cutover, automatic rigging (C6/C7), general C8 IK, C10 multi-shot and C11 voice. G1 cannot be marked PASS by unit tests or a green browser bundle alone. See `docs/qa/C1_SPINE_FEASIBILITY.md` for exact gate status and evidence.
