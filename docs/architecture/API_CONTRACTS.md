# Single-product API and state contract

All future routes use `/api/v1`, JSON, and envelope `{ "data": ..., "meta": {"request_id": "..."} }`; errors use `{ "error": {"code":"...","message":"...","details":{}} }`. Loopback-only MVP binds `127.0.0.1`; no authentication is required locally, but mutating routes require an `Idempotency-Key` where stated. C2 implements only health, system, channels/DNA, projects/workflow and read-only jobs/artifacts. Later routes are absent (or typed `501 NOT_IMPLEMENTED` only if a declared shell endpoint is necessary), never fake success.

| Method / route | DTO / status | Owner / phase |
|---|---|---|
| `GET /health`, `GET /api/v1/system` | health/build/schema; `200` | platform/C2 |
| `GET,POST /api/v1/channels`; `GET,PATCH,DELETE /api/v1/channels/{channel_id}` | Channel; create validates unique slug; `201,200,409` | platform/C2 |
| `GET,PUT /api/v1/channels/{channel_id}/dna`; `POST .../dna/approve` | DNA revision + `expected_head_revision`; `409 STALE_HEAD`, `422` | platform/C2 shell; authoring later |
| `GET,POST /api/v1/projects`; `GET,PATCH,DELETE /api/v1/projects/{project_id}` | Project, channel scope; `404/409/422` | platform/C2 |
| `GET /api/v1/projects/{project_id}/workflow` | seven-stage projection, computed readiness | platform/C2 |
| `POST /api/v1/projects/{id}/authoring/{topic-ideas,script,shot-plan}/{prompt,validate,import,approve}` | reservation/source head/import JSON | authoring/C3 |
| `GET,POST /api/v1/channels/{id}/assets`; `POST /api/v1/projects/{id}/asset-bindings` | asset/version/binding | assets/C4 |
| `POST /api/v1/projects/{id}/generation/{prepare,confirm,cancel}` | explicit `consent_id`, idempotency key | generation/C5 |
| `POST /api/v1/channels/{id}/rigs/{prepare,approve}` | parts/rig DTO | rigging/C6–C7 |
| `POST /api/v1/projects/{id}/director/{prompt,validate,import,approve}` | AnimationPlan import | director/C9 |
| `POST /api/v1/projects/{id}/{motion,render}/{compile,preview,approve}` | deterministic request | motion/renderer/C8–C10 |
| `POST /api/v1/projects/{id}/{delivery,voice}/{prepare,generate,mux,qc}` | voice-last request | delivery/C11 |
| `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `GET /api/v1/artifacts/{id}` | projection/immutable metadata | platform/C2 |

Never mount historical `/api/...` Scene/Beat/Visual Reference/Voice-first/Assembly/Render endpoints after C2.

## State, consistency and recovery

Top stages are exactly `authoring`, `resolver`, `generation`, `rigging`, `director`, `motion`, `delivery`. Approval states are only `draft|approved|rejected`; computed readiness is `blocked|ready|draft|approved|stale|running|failed`. `stale` means `SHA-256(canonical JSON of sorted source artifact IDs + SHA-256 + relevant DNA hash domains + contract version)` differs from `project_stage_heads.dependency_fingerprint`; it is not written as an approval status.

Mutations declare expected head revision and return `409 STALE_HEAD` with current head/revision on a CAS miss. Publishing is one owning transaction and a single connection/session. An outer session with a flushed write is rejected before nested immediate locking. Files are written/staged and streaming-hashed outside the transaction, rechecked before metadata commit, and attempt-owned temporary bytes alone may be cleaned on rollback. After response loss, retry reads idempotency/operation state and reconciles; no blind re-submit or paid retry. Provider submission is `unknown` when acknowledgement is ambiguous and must reconcile by frozen handle/fingerprint before any retry. Paid generation requires unexpired explicit consent that binds cost scope, input fingerprint, provider and operation.
