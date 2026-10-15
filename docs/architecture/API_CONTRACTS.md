# Single-product API and state contract

The machine-checkable method/path/phase/owner/DTO/status/precondition/idempotency register is `contracts/animation/api/endpoints.json`. Rows marked `ACCEPTED` are the implementable C2 platform contract. Rows marked `PROPOSED` are future phase drafts and must not be registered until implemented; they are not described as frozen. No compatibility or legacy route exists after C2.

All JSON success responses are `{ "data": <DTO>, "meta": {"request_id": "req_*", "schema_version": "api.v1"} }`. Errors are `{ "error": {"code": "...", "message": "...", "details": {}, "request_id": "req_*"} }`. IDs and hashes follow D-001/D-002. Loopback MVP binds `127.0.0.1`; requests from non-loopback origins are rejected before route logic. Every mutating response returns the new `revision`, authoritative identity, lineage IDs/hashes and `updated_at`.

## Accepted C2 DTOs

- `ChannelCreateRequest`: `name`, `slug`; `ChannelUpdateRequest`: `name?`, `slug?`, `expected_updated_at`; `ChannelResponse`: `channel_id`, names, nullable `current_dna_artifact_id/current_dna_revision`, three hashes, timestamps.
- `ChannelDnaRevisionCreateRequest`: complete `channel_dna.v2`, nullable `expected_head_revision` (must be null only when no head), `expected_head_artifact_id`, `Idempotency-Key`. `ChannelDnaRevisionResponse` adds artifact ID/revision/SHA and unchanged prior head. Approval request supplies `expected_head_revision`, candidate artifact ID/SHA, actor and review timestamp. `409 STALE_HEAD` includes `current_head_artifact_id/current_head_revision` while preserving the submitted draft artifact.
- `ProjectCreateRequest`: `channel_id`, `name`, `slug`; update/archive requests carry `expected_updated_at`. `ProjectResponse`: IDs, channel, name/slug/status/timestamps. Create atomically initializes the seven workflow projections; it does not claim future stage capability.
- `WorkflowProjectionResponse`: project/channel IDs, dependency fingerprint algorithm version and exactly seven ordered `StageProjection` objects. Each has `stage_key`, independent `approval_status` (`draft|approved|rejected`), computed `readiness` (`blocked|ready|draft|approved|stale|running|failed`), nullable head ID/revision, stored dependency fingerprint, freshly computed fingerprint and explicit blocker codes.
- `JobResponse` is a projection: job/operation/project IDs, kind, status, percent/message and timestamps. It cannot mutate execution. `ArtifactMetadataResponse` exposes identity/scope/kind/schema/logical key/revision/approval/SHA/size/relative artifact handle/parents/source fingerprints/timestamps; it never returns an unchecked filesystem path.

List queries use `limit` 1..100, opaque cursor, and explicit channel/project scope. List responses return `items` and nullable `next_cursor`. `DELETE` in C2 means archive/soft state where declared; FK-restricted owned data is never erased implicitly.

## Typed errors

`404 NOT_FOUND` does not disclose cross-channel existence. `409` codes are `STALE_HEAD`, `IDEMPOTENCY_CONFLICT`, `DUPLICATE_SLUG`, `OWNERSHIP_CONFLICT`, `ACTIVE_OPERATION`, and `TRANSACTION_OWNERSHIP_CONFLICT`. `413 IMPORT_TOO_LARGE` is limited to external imports. `422` codes include `VALIDATION_FAILED`, `LINEAGE_MISMATCH`, `UNAPPROVED_DEPENDENCY`, `CAPABILITY_UNSUPPORTED`, `CONSENT_INVALID`, and `LEGACY_DATABASE_UNSUPPORTED` (startup/system readiness). `503 NOT_READY` reports schema/runtime readiness. Each `details` object contains the relevant current revision/fingerprint and field-path issues; secrets and filesystem paths are redacted.

## Stages, fingerprint and transaction semantics

Stage order is exactly `authoring → resolver → generation → rigging → director → motion → delivery`. Approval never changes merely because inputs changed. `stale` is computed when `SHA-256(canonical JSON({algorithm_version, stage_key, sorted source artifact {id,revision,sha256}, relevant DNA hashes, contract versions, runtime identity where applicable}))` differs from the stored head fingerprint.

Publication follows the single-writer contract in `contracts/animation/DB_SCHEMA.md`. Prepared files and provider IO occur outside SQLite. Head CAS is one owning transaction; zero updated rows returns `409 STALE_HEAD`. Idempotency keys bind canonical request and source fingerprint. A reused key with a different request is `409 IDEMPOTENCY_CONFLICT`. Provider acknowledgement ambiguity becomes durable `unknown`; reconciliation by provider handle/fingerprint precedes any retry. Paid generation also requires the attempt-scoped consent artifact defined by D-006.

## DNA invalidation matrix

| Changed input | Directly stale when present | Must not be invalidated solely by this change |
|---|---|---|
| `visual_style_hash` | resolver, generation, rigging, director, motion, delivery | approved Topic/Script/ShotPlan authoring |
| `performance_style_hash` | director, motion, delivery | resolver/generation asset image pins, rig geometry, narration identity |
| `narration_identity_hash` | delivery voice/timeline/video/QC | authoring ShotPlan, resolver, generation, rigging, director, motion/render frames |
| approved ShotPlan head | resolver and every downstream stage | ChannelDNA and earlier authoring revisions |
| approved asset/rig version | director, motion, delivery as fingerprint-dependant | approved ShotPlan and unrelated channel assets |
| approved AnimationPlan | motion and delivery | rigging and earlier stages |
| approved render | delivery only | upstream approval states |

Voice is always downstream of an approved render. It cannot invalidate ShotPlan, asset, rig, Director or Motion authorities; only final timing holds/selective rerender create new downstream revisions with explicit lineage.

## OpenAPI and availability

C2 OpenAPI contains only the `ACCEPTED` register rows. Historical Scene/Beat/Visual Reference/Voice-first/Assembly/static-render paths are absent and have no side effects. Future `PROPOSED` rows are disabled in UI by readiness/blocker state and absent from routing; they never return fake success or generic placeholder completion.
