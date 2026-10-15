# C1 feasibility — executable acceptance specification (NOT_STARTED)

**Phase status:** NOT_STARTED. This document is not evidence that Spine, PixiJS, IK, encoder output or actual rig loading works. The C1 implementation PR must provide real rendered artifacts.

## Required input and versions

One legally reusable manually cut-out actor with official Spine-compatible rig, one independently articulated prop, one static background, pinned Spine runtime/data version, pinned PixiJS version, recorded licensing/seat/distribution prerequisites and frozen asset hashes. Use a single approved shot of exactly 10 seconds: 240 local frames at 24 FPS.

## Acceptance checks for the future C1 PR

1. Load actual rig assets in official Spine/PixiJS; record exact runtime/data versions and licensing proof.
2. Create unmistakable animated action chain: idle → walk to target → reach → grab → carry → place → stable idle. Verify visible bone transforms and actual prop attachment changes; reject pan/zoom-only (Ken Burns).
3. Compile one shot with indices 0–239. Assert exactly 240 independently evaluable RGBA frames and correct 1280×720 dimensions.
4. Evaluate predetermined frame samples and the entire sequence twice in different evaluation orders; assert exact final pose/attachment/fingerprint and stable pixel hashes after renderer-state reset.
5. Encode 240 frames with FFmpeg at 24 FPS. Inspect output with FFprobe for single video track, 1280×720, 24 FPS and exact 10s expected duration.
6. Publish frame manifest, individual deterministic hashes, output MP4/hash, source rig/version/license manifest and automated test logs, including one human-visible walk/grip/release evidence sequence.
7. Reject unsupported rig capability, missing required bone/attachment, frame -1 or 240, invalid prop grip or release, and observed nondeterministic repeated evaluation.

C0 validates only schema/contract prerequisites and does not fabricate runtime tests, visual proof, video or passing C1 status. Acceptance fails closed when licensed rig, official runtime or supported capability is unavailable.
