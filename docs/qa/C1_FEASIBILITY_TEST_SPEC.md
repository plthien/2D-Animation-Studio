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

## Windows-only execution gate (future C1, not implemented)

Use Windows 11 x64 on a real supported local target in addition to the Windows Server GitHub Actions runner. Pin Python 3.12, Node 22, actual Windows Chrome/Chromium, FFmpeg and FFprobe, and the official version-matched Spine/PixiJS runtime with recorded license rights. If Windows 10 x64 is declared supported, run separate compatibility evidence. Reject ambiguous/undeclared spatial targets, missing frozen initial actor/prop transforms, two hands/actors owning one prop, unsupported handoffs and compiled action-list mismatches. C0 JSON contract tests are not C1 visual/runtime evidence.

## Frozen handoff from C0 (NOT_STARTED)

These are **C1-only** obligations from the phase-owner register in `docs/plans/2D_ANIMATION_STUDIO_CLEAN_CUTOVER_IMPLEMENTATION_PLAN_v3.md`. They are not new C0 gates:

- **C1-MOTION-01 — carrying hand occupancy:** show one real valid grab/carry sequence, one rejected overlapping reach/point by the *occupied same hand*, and one functioning opposite-hand action when the rig supports it. Capture evaluated poses/frames and a clear rejected-plan result. No new action type or runtime simulator in C0.
- **C1-FIXTURE-02 — static/idle world-state:** reconcile the illustrative idle-only fixture so the frozen initial and final actor root and unheld prop coordinates match. At frame samples in arbitrary evaluation order, prove idle root and unattached stationary prop remain unchanged. Do not insert motion to justify previously inconsistent example coordinates.
- **C1-RUNTIME-03 — official Spine/PixiJS proof:** version-pinned, licensed official runtime and manually reviewed rig with actual bone articulation and walk → reach → grab → carry → place. Render **240 real independent frames at 24 FPS, 1280×720**, deterministic random-access state/pixel hashes, and one inspected 10-second Windows FFmpeg MP4 with FFprobe report. Include runtime/assets hashes, visual proof and real consumer Windows 11 evidence in addition to Windows Server CI.

**Status for all three:** DEFERRED / NOT_STARTED; not C0 blockers. If C1 cannot provide the actual rig, license, supported poses or verified video, C1 itself remains BLOCKED; never present C0 schema tests as C1 completion.
