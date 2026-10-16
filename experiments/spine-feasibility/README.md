# C1: genuine Spine 4.2 / PixiJS 8 feasibility (isolated)

This is not an animation-product runtime. This repository intentionally ships **NO rig, atlas or texture**, because the owner's Spine Editor/runtime integration rights and an approved rig's redistribution rights have not been established. All real-runtime results are **BLOCKED until lawful assets and rights are supplied**. No fake skeleton, no static-PNG fallback and no pre-recorded frames.

## Windows PowerShell

Requires consumer Windows 11 x64, Node 22, Google Chrome/Chromium installed locally, Windows FFmpeg + FFprobe, a valid licensed 4.2 Spine export, and approved asset provenance. Runtime package pins: `@esotericsoftware/spine-pixi-v8 4.2.120`, `pixi.js 8.16.0`.

```powershell
cd experiments/spine-feasibility
npm.cmd ci
npm.cmd run c1:test
# Copy your authorized rig /atlas /png to public/assets and complete provenance.json
npm.cmd run c1:preflight
npm.cmd run c1:render
npm.cmd run c1:verify
```

`npm.cmd run dev` can load the rig in a local test browser. The browser refuses startup without approved, SHA-matched local assets. A headless Chrome render is **NOT** accepted as consumer Windows 11 evidence. Record OS, browser, versions, license evidence, screenshots and human motion review separately.

The official Spine 4.2 API is `Spine.from({skeleton, atlas,autoUpdate:false})`, not the 4.3 constructor API. Pixi WebGL required for full attachment operations. Actions are single-shot [start,end) at 24 FPS. The independent evaluator is order-independent, and the browser adapter applies real Spine bone rotations and derives prop position from a real hand bone. The exact rig needs mapping/calibration and a visual continuity review. Each of 240 `output/frames/000000.png...000239.png` must be an actual Pixi canvas capture. `output/` is ignored and reserved for real generated evidence.

### Manual proof checks (mandatory)
Verify locomotion through leg articulation/ground contact, visible arm reach, prop pickup without jump, hand-following throughout carry, correct drop position and no residual attachment. Compare sampled 0,48,97,143,239 and independently evaluated 143→0→143 before accepting pixel hashes. Check FFprobe 240 frames, 24fps, 1280×720, exactly 10s. Do not mark G1 PASS without Windows 11 consumer device proof.

Official licenses: https://esotericsoftware.com/spine-runtimes-license and https://esotericsoftware.com/spine-editor-license. Runtime docs: https://esotericsoftware.com/spine-pixi.

### What remains blocked
The initial PR cannot produce a legal real frame or MP4 without licensed assets and runtime entitlement. A green isolated Node unit test proves only deterministic planning; it is not C1-RUNTIME-03 or G1 rendering acceptance.
