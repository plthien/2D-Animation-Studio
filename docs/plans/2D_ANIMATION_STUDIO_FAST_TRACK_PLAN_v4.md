# 2D Animation Studio — fast-track implementation plan v4 (C3–C7)

**Status:** owner-requested execution-plan replacement on 2026-10-17; docs-only planning PR. **Base:** C2 source merge `5719c1b9acc6f99c44bf366f37201ee0b9295515`. **Repo:** `plthien/2D-Animation-Studio`. **Owner:** single user, local Windows 11 workstation. No SaaS/multi-tenant target.

**Authority:** This plan supersedes the **future phase scheduling, phase ownership and per-phase gates** in v3 sections 8 (C3–C12), 9.3 and its future-phase handoff tables. All other accepted v3 clean-cut rules and C0–C2 frozen contracts survive. Historical issue IDs continue to refer to original requirements, not to ten remaining PRs.

## 1. Why five phases, not ten

The v3 plan made individual implementation components into separate approval units: authoring, resolver, provider, segmentation, rigging, motion, director, rendering, voice and release. That multiplied PRs, repetitive audits and blocked delivery of a first playable film. Move to **five vertical deliverables and five feature PRs**. Internal coding checkpoints are commits/workstreams within one PR, **not additional phase gates or mini-PRs**.

**Do not** simplify away the animation engine or convert this into static-image/Ken Burns motion. The quality-sensitive pieces—real cutout rig, real contact/IK, real Spine frames, voice-last mux—remain mandatory, but acceptance is placed at natural end-to-end seams.

### Exactly five implementation phases

| New phase / one PR | Historical phases consolidated | End-to-end output at phase exit |
|---|---|---|
| **C3 — Authoring & Asset Production** | old C3 + C4 + C5 | Topic → Script (+ optional Analysis) → approved ShotPlan → requirements/resolver → approved pinned image/asset versions, including optional consented G-Labs generation |
| **C4 — Character Rigging Studio** | old C6 + C7 | Two distinct real input images → reviewed parts/pivots → valid approved rig versions loaded and posed by official Spine 4.2/PixiJS |
| **C5 — Director & Motion** | old C9 + C8, built in that dependency order | Approved rig + ShotPlan → external AnimationPlan approval → deterministic articulated shot preview with grip, ground and supported nine-action choreography |
| **C6 — Render & Voice Delivery** | old C10 + C11 | Multi-shot Spine render → voice *after* picture → frame/sample reconciliation → playable, audible verified H.264/AAC MP4 + provenance |
| **C7 — Full-flow Integration & Windows Acceptance** | old C12 | Two distinct finished films, full regression, owner-operated Windows 11 verification, final reliability/quality signoff |

**No phase C8–C12 remains as an implementation/PR gate after this amendment.** Their preexisting issue IDs are still traceability references. The seven **product UI stages are unchanged**: `authoring → resolver → generation → rigging → director → motion → delivery`. A product stage is not an implementation phase.

### Ownership remapping

| Old implementation phase | New owner phase |
|---|---|
| C3 Authoring, C4 Asset Resolver, C5 Generation | **C3** |
| C6 Parts, C7 Rigging | **C4** |
| C8 Motion, C9 Director | **C5** |
| C10 Renderer, C11 Voice/Delivery | **C6** |
| C12 Release/QA | **C7** |

Maintain historical IDs `C3-AUTHORING-01`, `C4-ASSETS-01`, `C5-OPS-01`, `C6-C7-RIG-01`, `C8-MOTION-01`, `C8-WORLD-02`, `C9-DIRECTOR-01`, `C10-RENDER-01`, `C11-VOICE-01`, `C12-RELEASE-01`; group their deliverables under the new owner. **Do not rename persisted artifacts, stage keys or schema versions.**

## 2. Global product constraints (unchanged)

- One animation-only product, one new animation SQLite DB, exactly the existing **seven workflow stages**; no YTB migration, old V4 route/worker, voice-first dependencies or Ken Burns fallback.
- Keep the **14 frozen C2 tables**, accepted 19 C2 method/path pairs and ChannelDNA v2. The 18 additional API register rows were `PROPOSED`, not automatically approved by changing phases. Validate and activate only with their real implementation. Extra schema/index modifications require review of the accepted contract.
- Preserve the Cockpit shell, sidebar, cards, modals, state projections and existing dark design language. No generic dashboard rewrite.
- **1280×720, 24 FPS**, max **30 shots**, each **24..720** base frames and at most **48** terminal hold frames; up to **2 humanoids + 3 props** per shot. Exactly nine supported semantic actions (`idle`, `walk_to`, `look_at`, `reach_for`, `grab`, `carry_to`, `place_at`, `point_at`, `react`). Half-open integer-frame intervals and frozen-source hashes.
- Real Spine 4.2-compatible skeleton/atlas/PixiJS; 14 reviewed semantic sprites and 16 mandatory semantic bones for humanoid rigs. C1 official Spineboy sample remains **evaluation only**, not automatic commercial-asset authorization.
- External authoring is **copy prompt → user obtains output → strict JSON import → review → approve**. No hidden in-app LLM. G-Labs paid actions require explicit attempt-scoped user confirmation, cost cap and duplicate-submit protection.
- Voice is produced **after** approved picture. Canonical intermediate audio 48k mono PCM, 2000 samples per 24fps frame; no fabricated alignment or unapproved speech truncation.
- Immutable file/DB lineage and idempotent recovery matter because this is a local user project, not an ephemeral demo.

## 3. Implementation details and acceptance by phase

### C3 — Authoring & Asset Production (old C3 + C4 + C5)

**User outcome:** From a fresh Channel/Project, author or import real Topic, Script, optional Script Analysis and ShotPlan; review/approve them; see deterministic actor/prop/background requirements; reuse existing channel assets, import user-owned images and/or explicitly trigger G-Labs to produce assets; approve and pin exact immutable versions. A project survives restart.

**Ordered workstreams within one PR (not three phases):**
1. Adapt existing cockpit Topic/Script/import editors; issue source-bound prompt packages and authoring reservations; strict external JSON validation, stale head, quote boundaries, ID/location/prop consistency, silent shots, 24–720 frames.
2. Deterministic requirements/resolver; channel-local logical asset IDs, source/view/style/capability checks, immutable versions and project pins, reuse across projects; no invented generation.
3. Local user-owned reference import as an always-available path. Integrate bounded G-Labs transport/durable operations, attempt-scoped paid consent and cost limit, ambiguous-result reconciliation, cancel/restart/fencing, candidate review; live spending only when user explicitly approves.
4. Wire working Authoring, Resolver and Generation UI to real C2 authorities; unlock only operations genuinely implemented. Add proposed endpoints only when they exist, with typed errors and real persistence.

**Fast, honest phase acceptance:** One real project reaches **approved ShotPlan + resolved requirements + pinned approved asset** using local user-supplied input, with one same-channel reuse case and one cross-channel rejection. Validate malformed/stale imports and a provider cancelled/unknown/duplicate-attempt path using deterministic fake transport. If no G-Labs account/explicit consent exists, leave **live paid-provider E2E = NOT_RUN**; do not call G-Labs integrated-live PASS. This status is carried into C7 and does not block work on actual user assets.

**Not C3:** Native image decomposition, Spine rig building, motion, final render or voice.

### C4 — Character Rigging Studio (old C6 + C7)

**User outcome:** From the **approved C3 image** create/review 14 transparent semantic sprite parts, masks, pivots, layer order and missing/occluded regions; correct manually when automatic extraction is uncertain; export/load an actual **Spine 4.2** skeleton/atlas with 16 required bone-role mappings and approved capabilities; pose preview and persist an immutable rig version.

**Ordered workstreams:** image segmentation and uncertainty flags → actual editable parts/pivot UI → atlas + skeleton export → official runtime load → pose checks/version approval. Integrate with existing channel assets and project bindings. Never invent unseen limbs as if detected; show manual-repair requirement. Measure auto-detected vs manually corrected parts honestly.

**Phase acceptance:** Two visually distinct real user-owned/generated input images, separately extracted and corrected as required, **two actual approved playable Spine rigs** and pose evidence (idle/walk/reach/grab). Broken atlas, missing mandatory roles or unverified runtime loader = phase BLOCKED. `G2` is a measured **assisted rigging** gate; do not advertise hands-free auto-rig unless demonstrated. Spine editor/runtime and asset rights remain truthful.

**Not C4:** General IK/action compiler or full video render.

### C5 — Animation Director & Motion (old C9 + C8)

**User outcome:** Given a frozen ShotPlan, real asset pins and approved rigs, export a contextual **Animation Director prompt**; strict import/review/approve of `animation_plan.v1`; compile supported motions into deterministic actual skeleton poses; play/reseek a real shot preview.

**Dependency-correct order:** Director plan/schema/capability validator first, then nine-action scheduler and world-state compiler; finally Spine preview. Enforce same-hand channel conflicts, one-owner-per-prop, action target type, duration boundaries, ground contact, basic two-bone IK, reach→grab→carry→place continuity and safe rejection when unsupported. This is a bounded MVP action vocabulary, **not** generalized physics, motion synthesis or arbitrary animation.

**Phase acceptance:** One actual approved rig/plan plays a complete articulated walk/reach/grab/carry/place/react sequence; evaluate frame N in arbitrary order after other frames with identical fingerprint/pose/render evidence; prop has no teleport/slip at contact; invalid plan/stale rig is rejected. Use C1 as an evidence/reference experiment, not as an unreviewed production engine.

**Not C5:** Complex multishot production, audio generation or final MP4. Single-shot preview must nevertheless be real Spine frames, not static mock screenshots.

### C6 — Render & Voice Delivery (old C10 + C11)

**User outcome:** Render an approved multi-shot project using real rig poses/camera/background, supervise Windows frame workers, verify `render_manifest.v1`; then synthesize/align speech **after** picture, reconcile safe terminal holds and mux an actually playable MP4. No old static image graph.

**Ordered workstreams:** multi-shot frame driver and persistent render operations → controlled cancellation/restart/resume/ffprobe → voice provider adapter(s), pacing identity and correct text alignment → frame/sample policy with at most 48 hold frames per shot and selective rerender → FFmpeg H.264/AAC output, hashes and QC.

Prefer an operational **local Kokoro** voice path for an end-to-end audible video without requiring paid credentials; keep ElevenLabs voice/alignment as supported adapters when configured, with truthful provider-specific capability. A silent-shot path is valid, but a silent-only film does not satisfy audible delivery acceptance.

**Phase acceptance:** A **minimum three-shot** film generated from real approved Spine rig and AnimationPlan, **1280×720/24fps**, valid frame/hash provenance, audible aligned narration through at least one real installed provider, 48k mono PCM intermediate, correct 2000-sample/frame reconciliation, H.264/AAC MP4 verified by FFprobe. Test unschedulable voice timing, worker cancellation/recovery, and project data integrity. Do not create duplicate paid requests during retry.

**Not C6:** Full two-film release matrix and owner-machine Windows 11 compatibility signoff.

### C7 — Full Flow, Deferred Windows Platform & Release QA (old C12)

**User outcome:** On the owner's Windows 11 machine, complete *two distinct 30–60 second animations*, each with three or more shots, two distinct character rigs, real articulated motions/prop interactions, audio, manifests and final MP4; show real UI work across all seven stages.

**Mandatory integrated evidence (including owner-authorized deferred C2 checks):**
1. Cold Windows 11 startup/launcher with spaces in paths; create Channel/DNA/Project, restart/reopen, seven-stage projections; legacy DB refusal, exact 14-table schema, 19 original API routes and no old YTB worker/route.
2. End-to-end authoring → asset import/G-Labs as configured → two reviewed rigs → director plans → deterministic motion → frames → voice → final MP4. Record which optional paid/provider operations were **NOT_RUN** instead of fabricating proof.
3. Native Windows Job Object child/descendant cleanup and cancel/restart; SQLite CAS/immutability, local file containment and source hash checks; full C2 deferred platform test suite.
4. UI screenshot baseline and responsive regression on required viewports; manual visual acceptance of grip, walk, contact, pivots, shot continuity, speech and rendered output.
5. Supported, lawful Spine use/asset provenance; relevant dependency issues reviewed by **actual local exposure**, API keys unlogged, localhost-bound application, explicit paid consent; no OAuth/RBAC/multi-tenant hardening mandate.
6. Real H.264/AAC streams, 720p/24fps CFR, per-shot frame hashes, source lineage, audio sync, recoverable local files and visible failure states.

**Gate:** No unresolved defects that prevent user operation, lose files, corrupt SQLite, allow surprise paid charges, leak credentials or break animation/voice/film output. Missing/failed **required** Windows 11 or two-film verification stays BLOCKED. Evidence from GitHub Windows Server does **not** equal consumer Windows 11. The owner supplies consumer-machine proof after full flow is implemented, as explicitly decided at C2 merge.

## 4. Single-user local security policy — right-size, don't remove safety

**Priority:** correctness of outputs, animation quality, project/data recovery, predictable costs, simple UI. The tool is used by **one owner on local Windows**; no SaaS, cloud hosted API or multi-tenant accounts are planned.

- **Must protect:** local project/SQLite/artifact data against loss/corruption, unsafe path traversal/reparse points, unapproved or duplicate paid requests, secrets in logs, process leaks and inadvertent network exposure. Retain loopback binding and validation around external JSON or media payloads.
- **Do not implement** sign-in, RBAC, teams, multi-tenant row security infrastructure, cloud-scale queue security or enterprise-grade audit logging for this product.
- **Do not block unrelated feature PRs** merely because an advisory exists. Classify dependency exposure in the actual local runtime/toolchain; patch when compatible or demonstrably reachable, otherwise record a nonblocking note and handle at C7 when justified. Do not blind-force major upgrades that break Cockpit or the renderer. Critical real exposure remains a blocker.
- **Provider operations:** consent, cost ceiling, deterministic attempt identity, unknown-result reconciliation and no hidden provider call remain mandatory even for one user: they protect the user's money, not enterprise multi-user access.
- License compliance for Spine/editor/assets still applies to local use and any later distribution; do not claim an evaluation example is a commercially distributable production asset.

## 5. Speed-oriented implementation and PR policy

**Exactly five feature PRs** following this plan: `feat/c3-authoring-assets`, `feat/c4-rigging-studio`, `feat/c5-director-motion`, `feat/c6-render-voice`, `feat/c7-full-flow-qa`. These branch names are suggestions; each PR must clearly state its owner phase.

**Within each PR:** implement internal workstreams directly; use multiple commits, not multiple speculative planning PRs. Build backend + frontend + tests together for the same vertical feature; reuse Cockpit and source/fixtures rather than rebuilding common infrastructure. No more than **one scheduled comprehensive audit at PR completion** plus targeted reruns for real blockers. Repair confirmed phase-local BLOCKER/HIGH before proposing merge. Record later-phase issues in their true owner phase without expanding the current PR.

**C3–C6 lean gates:** typecheck/build, API & SQLite contract checks for **changed operations**, focused negative cases (corrupt data, duplicates, bad ownership, contact, timing), a **real end-to-end smoke** from the previous phase's approved artifact to the new outcome, and a small UI sanity proof. CI on Windows only. Do **not** require repeating ten G0 screenshots, all old C2 platform tests, security inventory deep-dive and full-film proof at every phase. Where a regression is impacted, run its targeted test. Keep high-value smoke/regression tests executable to prevent accumulated breakage.

**C7 deep gates:** all historical/phase-independent regressions, full workflow on consumer Windows 11, two real films, stability, manual visual QC, render/voice metrics, relevant security/licensing. The C2 platform test explicitly deferred by owner **must run here**. Do not label it PASS earlier.

**Blocking policy:** a failing core behavior of the current phase, incorrect output, project/data loss, unpaid/duplicate provider spend or a broken affected acceptance test **does block**; tests involving optional unconfigured providers can be `NOT_RUN` and carried to C7 with no false success claim. Nonreproducible speculation and requirements exclusively owned by later phases **do not block**.

**Evidence format per phase (one compact file):** one `docs/qa/PHASE_Cx_REVIEW.md` with feature checklist, tested HEAD/commands, 3–8 links/screenshots/logs, PASS/FAIL/NOT_RUN, known owner-phase handoffs and merge verdict. No repeated huge security/ledger/source audits after the C2 clean cut.

## 6. Required authority sync at first new implementation

At the start of **C3** reconcile the metadata and UI *phase-owner labels* so existing `app/animation/service.py` workflow projections no longer report historical C8/C9/C11 as implementation owners. The seven stage keys/statuses and accepted C2 endpoint paths remain **unchanged**. Future `PROPOSED` endpoint registry rows are mapped to the new phase owner below; their contract status remains `PROPOSED` until implemented.

| Stage key | New owner |
|---|---|
| authoring / resolver / generation | C3 |
| rigging | C4 |
| director / motion | C5 |
| delivery | C6 |
| final product acceptance (not a UI stage) | C7 |

No new persisted stage key, extra DB table or duplicate ChannelDNA authority may be created to represent these five engineering phases. The historical C1/C2 QA evidence and explicit deferred Windows platform requirement remain intact.

## 7. Source traceability and handoff

Read the superseded v3 plan only for **detailed technical requirements** and original issue identities:
- v3 §§2, 4–7: product envelope, canonical contracts, renderer/data boundaries.
- v3 §§8 C3–C12: complete original sub-workstream descriptions, now assigned to C3–C7 above.
- v3 §8 deferred issue IDs: retained for regression ownership, not additional PRs.
- v3 §9: safety and test cases—apply selectively in C3–C6, fully in C7.
- `contracts/animation/`: authoritative schemas/DDL (not replaced by this plan).
- `docs/qa/PHASE_C2_REVIEW.md`: C2 source merged with owner-authorized deferred platform acceptance, mandatory at C7.
- `docs/qa/WINDOWS_ONLY_TEST_POLICY.md`: Windows-only execution and separate consumer Windows 11 proof.

**Next action after adopting this planning PR:** create **C3 Authoring & Asset Production** branch from up-to-date main and implement Topic → Script → ShotPlan → resolver → approved user-owned or explicitly consented generated asset, in **one PR**. No more architecture-only phases.
