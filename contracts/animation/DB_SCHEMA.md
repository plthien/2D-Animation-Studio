# Animation database contract — C0 accepted design

`animation_schema.sql` is the executable normative DDL for future `0001_animation_initial.py`; C0 does not install it into production. The default future URL is `sqlite:///./2d_animation_studio.db`. A fresh database contains exactly the fourteen application tables in this file plus `alembic_version`; the next migration is `0002_*`.

## Table and ownership inventory

| Table | Owner and lifecycle |
|---|---|
| `channels` | Channel metadata plus nullable current DNA pointer and the three current hash snapshots. Initial insert has a NULL pointer; DNA artifact insert and deferred pointer CAS complete the bootstrap. |
| `projects` | Channel-owned project identity; no Scene/Beat/voice-first pointers. |
| `artifacts` | Sole immutable revision store, including ChannelDNA with `project_id IS NULL`; bytes and metadata never update after insert. |
| `project_stage_heads` | One CAS pointer per project and one of exactly seven stages; persisted approval is independent from computed readiness. |
| `authoring_reservations` | Expiring, single-consume reserved identity/source fingerprint for external authoring. |
| `assets`, `asset_versions` | Channel-owned logical identity and immutable reviewed candidates. |
| `project_asset_bindings` | Project pin to an exact same-channel asset version. |
| `rigs`, `rig_versions` | Same-channel reusable rig identity and immutable profile/manifest version. |
| `motion_templates` | Channel-scoped immutable reusable action-template revisions. |
| `operations`, `operation_tasks` | Durable execution authority and fenced child attempts. |
| `jobs` | User-facing projection only; never execution authority. |

Every column, NULL rule, `CHECK`, FK action, unique constraint and index name is exact in `animation_schema.sql`. SQLite uses `PRAGMA foreign_keys=ON`, WAL, a bounded busy timeout and one write-owning connection/session. Required partial indexes are `ux_artifacts_channel_revision(channel_id,kind,logical_key,revision) WHERE project_id IS NULL` and `ux_artifacts_project_revision(project_id,kind,logical_key,revision) WHERE project_id IS NOT NULL`; this prevents SQLite NULL uniqueness from admitting duplicate ChannelDNA revisions.

Composite ownership FKs make project artifacts/stage heads/reservations/operations/jobs match `(project_id,channel_id)` and asset bindings match `(asset_version_id,asset_id,channel_id)`. Rig and asset-version references likewise carry channel scope. Cross-channel/project writes therefore fail at the DB boundary. Artifact kind/schema compatibility and monotonically allocated next revision are mandatory service validations inside the same publication transaction; tests exercise those named validators when C2 implements them.

## ChannelDNA and hashing

There is no second DNA revision table. Canonical `channel_dna.v2` JSON is stored as a channel-scoped artifact; `channels.current_dna_artifact_id` is a nullable CAS head and the three channel hash columns are a denormalized current snapshot updated in the same transaction. Canonical JSON and hash rules are D-001. `visual_style_hash` invalidates visual/asset/rig dependants, `performance_style_hash` invalidates director/motion dependants, and `narration_identity_hash` invalidates voice/delivery only.

## Paid consent within fourteen tables

`operations.paid_consent_artifact_id` references an approved project artifact of kind `paid_operation_consent.v1`. Before submission, the service verifies same project/channel, provider, operation kind, exact input fingerprint, cost/currency ceiling, expiry, user confirmation actor/time and permitted attempt. It records consent fingerprint in `request_json`. An ambiguous provider submission enters `unknown` and reconciles its frozen handle; consent never authorizes a blind retry or a different fingerprint/attempt.

## Publication, CAS and failure ownership

1. Prepare/stage bytes outside SQLite using containment/reparse checks and streaming SHA-256; no network or large-file work occurs in a DB transaction.
2. A single repository owner begins the write transaction. If the supplied SQLAlchemy Session has an already-flushed write transaction, publication returns `TRANSACTION_OWNERSHIP_CONFLICT` before trying nested `BEGIN IMMEDIATE`.
3. Revalidate file identity, channel/project ownership, kind/schema, parent heads and expected head revision; allocate the next logical revision and insert immutable metadata.
4. CAS update uses `WHERE revision=:expected_revision`; zero rows produces HTTP `409 STALE_HEAD` with current head/revision. Only the winner commits the head. A loser cleans only its attempt-owned temporary path; finalized or referenced bytes are left for idempotent orphan reconciliation.
5. Response loss is reconciled by artifact/operation/idempotency identity; it never republishes or repeats a paid call blindly.

SQLite contention tests use independent connections. The contract rejects nested ownership rather than waiting on a second writer. `foreign_key_check` must be empty after every fresh migration test.

## Legacy refusal

Before opening a migration write transaction, C2 reads `sqlite_master` and `alembic_version`. Any known YTB table or revision `001_*` through `031_*` raises `LEGACY_DATABASE_UNSUPPORTED` and closes the connection without writes. Tests use only a disposable signature DB and verify its SHA-256 is unchanged. Existing user databases/artifacts are never dropped, converted, imported or deleted.
