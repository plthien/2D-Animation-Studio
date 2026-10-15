# Renderer-neutral frame evaluation boundary — C0

Status: **C0 design contract only**. C1 runtime experiment **NOT_STARTED**. Remotion, Spine and PixiJS dependencies are not added by C0.

## Authority and dependency direction

`ShotPlan → AnimationPlan → Motion compiler / deterministic pose evaluator → EvaluatedFrameState → renderer adapters`.

The approved shot plan controls ordered shot IDs, exactly 24 FPS, and local duration. AnimationPlan controls action intervals, actor and prop references, rig capabilities and motion-channel ownership. Frozen inputs include content-addressed asset and rig versions, motion-compiler identity, runtime identity, initial world state, deterministic camera state and shot-local frame index. Every downstream artifact retains hashes/lineage pointing to these inputs.

Conceptual renderer-independent call (not a production TypeScript implementation):

```ts
evaluateFrame(
  shotId: string,
  frameIndex: number,
  frozenContext: FrozenAnimationContext
): EvaluatedFrameState
```

The immutable returned state contains root/character transforms, bone pose transforms, prop ownership/attachment/grip and world transforms, camera transforms, flattened background/layer state, and deterministic input fingerprint. Coordinates/time are numeric and finite. Evaluation is shot-local, zero-based and rejects frameIndex outside [0, shot.duration_frames).

## Deterministic evaluation contract

The outcome for frame N is a pure function of frozen context and N: no hidden previous-frame state, wall clock, unseeded randomness, unordered provider response, or mutable renderer state. Frame 168 must yield the same pose after [0, 168] and [200, 7, 168]; repeated evaluation must hash identically. Motion compiler resolves deterministic prop grip transitions against action intervals at the target frame (not by executing all earlier rendered frames). Intermediate state is never trusted without its frozen-context fingerprint.

Action-channel contract (C0 only): locomotion (`idle`, `walk_to`, `carry_to`); gaze (`look_at`); expression (`react`); independent arm channels (`reach_for`, `point_at`, `grab`, `place_at`, hand-specific); interaction state (`grab`, `carry_to`, `place_at` ownership transitions). Same-channel overlapping intervals are forbidden; distinct-channel overlaps are allowed when the rig declares both capabilities. Grip ownership is per shot/actor/hand; matching grab/carry/place required. C0 does not claim IK, blending, full-body compositing, contact physics or prop transfer. Any unrepresented composition must fail with `unsupported composition` rather than silently improvise motion.

## Adapters

- **Spine/PixiJS**: renders evaluated transforms and attachments for C1 feasibility.
- **Frame export / FFmpeg**: encodes already-evaluated still frames and synchronizes output; it cannot redefine character movement.
- **Potential Remotion adapter**: may assemble shots, transitions, titles, subtitles and final composition from the same evaluated states. It must not own canonical character motion, change approved action semantics, move props, modify shot timing, or change artifact identity.

These are conceptual interface boundaries; no adapter is implemented in C0. Adding Remotion later must not require changes to AnimationPlan's motion semantics. Any downstream timing override requires an explicit versioned policy and lineage; current C0 policy prohibits such overrides.

## C1 proof obligations

The independent official Spine/PixiJS runtime must load a licensed manually-prepared rig, evaluate frame indices in arbitrary order, and verify exact repeated frame hashes against the frozen input fingerprint. Produce 240 frames at 24 FPS and an independently validated 10s MP4 via FFmpeg. Document versions, licensing, bone movement, prop grip and failure cases, without declaring C1 complete from C0 schema checks.
