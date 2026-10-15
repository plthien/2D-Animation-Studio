PRAGMA foreign_keys = ON;

CREATE TABLE channels (
  channel_id TEXT PRIMARY KEY CHECK(length(channel_id) BETWEEN 3 AND 128),
  name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 200),
  slug TEXT NOT NULL UNIQUE CHECK(length(slug) BETWEEN 1 AND 100),
  current_dna_artifact_id TEXT,
  visual_style_hash TEXT NOT NULL CHECK(length(visual_style_hash)=64),
  performance_style_hash TEXT NOT NULL CHECK(length(performance_style_hash)=64),
  narration_identity_hash TEXT NOT NULL CHECK(length(narration_identity_hash)=64),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(current_dna_artifact_id, channel_id) REFERENCES artifacts(artifact_id, channel_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE projects (
  project_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(channel_id) ON DELETE RESTRICT,
  name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 200),
  slug TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(channel_id, slug), UNIQUE(project_id, channel_id)
);
CREATE INDEX ix_projects_channel_updated ON projects(channel_id, updated_at);

CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(channel_id) ON DELETE RESTRICT,
  project_id TEXT,
  kind TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  logical_key TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision >= 1),
  approval_status TEXT NOT NULL CHECK(approval_status IN ('draft','approved','rejected')),
  sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
  relative_path TEXT NOT NULL UNIQUE CHECK(relative_path NOT LIKE '/%' AND relative_path NOT LIKE '%..%'),
  parents_json TEXT NOT NULL,
  source_fingerprints_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reviewed_by TEXT,
  reviewed_at TEXT,
  FOREIGN KEY(project_id, channel_id) REFERENCES projects(project_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(artifact_id, channel_id), UNIQUE(artifact_id, project_id, channel_id)
);
CREATE UNIQUE INDEX ux_artifacts_channel_revision ON artifacts(channel_id, kind, logical_key, revision) WHERE project_id IS NULL;
CREATE UNIQUE INDEX ux_artifacts_project_revision ON artifacts(project_id, kind, logical_key, revision) WHERE project_id IS NOT NULL;
CREATE INDEX ix_artifacts_project_kind ON artifacts(project_id, kind);
CREATE INDEX ix_artifacts_sha256 ON artifacts(sha256);

CREATE TABLE project_stage_heads (
  project_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  stage_key TEXT NOT NULL CHECK(stage_key IN ('authoring','resolver','generation','rigging','director','motion','delivery')),
  artifact_id TEXT,
  approval_status TEXT NOT NULL CHECK(approval_status IN ('draft','approved','rejected')),
  dependency_fingerprint TEXT NOT NULL CHECK(length(dependency_fingerprint)=64),
  revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(project_id, stage_key),
  FOREIGN KEY(project_id, channel_id) REFERENCES projects(project_id, channel_id) ON DELETE CASCADE,
  FOREIGN KEY(artifact_id, project_id, channel_id) REFERENCES artifacts(artifact_id, project_id, channel_id) ON DELETE RESTRICT
);
CREATE INDEX ix_stage_heads_channel ON project_stage_heads(channel_id, stage_key);

CREATE TABLE authoring_reservations (
  reservation_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_head_artifact_id TEXT,
  source_fingerprint TEXT NOT NULL CHECK(length(source_fingerprint)=64),
  reserved_artifact_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('open','consumed','expired','cancelled')),
  expires_at TEXT NOT NULL,
  consumed_artifact_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id, channel_id) REFERENCES projects(project_id, channel_id) ON DELETE CASCADE,
  FOREIGN KEY(source_head_artifact_id, project_id, channel_id) REFERENCES artifacts(artifact_id, project_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(consumed_artifact_id, project_id, channel_id) REFERENCES artifacts(artifact_id, project_id, channel_id) ON DELETE RESTRICT
);
CREATE INDEX ix_authoring_reservation_expiry ON authoring_reservations(project_id, status, expires_at);

CREATE TABLE assets (
  asset_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(channel_id) ON DELETE RESTRICT,
  kind TEXT NOT NULL CHECK(kind IN ('actor','prop','location','background')),
  semantic_key TEXT NOT NULL,
  view_key TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(channel_id, kind, semantic_key, view_key), UNIQUE(asset_id, channel_id)
);

CREATE TABLE asset_versions (
  asset_version_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision >= 1),
  artifact_id TEXT NOT NULL,
  visual_style_hash TEXT NOT NULL CHECK(length(visual_style_hash)=64),
  capability_hash TEXT NOT NULL CHECK(length(capability_hash)=64),
  status TEXT NOT NULL CHECK(status IN ('candidate','approved','rejected')),
  source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
  created_at TEXT NOT NULL,
  reviewed_at TEXT,
  FOREIGN KEY(asset_id, channel_id) REFERENCES assets(asset_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_id, channel_id) REFERENCES artifacts(artifact_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(asset_id, revision), UNIQUE(artifact_id), UNIQUE(asset_version_id, asset_id, channel_id)
);
CREATE INDEX ix_asset_versions_status ON asset_versions(asset_id, status);

CREATE TABLE project_asset_bindings (
  binding_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  asset_version_id TEXT NOT NULL,
  usage_key TEXT NOT NULL,
  source_fingerprint TEXT NOT NULL CHECK(length(source_fingerprint)=64),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id, channel_id) REFERENCES projects(project_id, channel_id) ON DELETE CASCADE,
  FOREIGN KEY(asset_id, channel_id) REFERENCES assets(asset_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(asset_version_id, asset_id, channel_id) REFERENCES asset_versions(asset_version_id, asset_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(project_id, usage_key)
);
CREATE INDEX ix_project_asset_version ON project_asset_bindings(asset_version_id);

CREATE TABLE rigs (
  rig_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  semantic_key TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(asset_id, channel_id) REFERENCES assets(asset_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(asset_id, semantic_key), UNIQUE(rig_id, channel_id)
);

CREATE TABLE rig_versions (
  rig_version_id TEXT PRIMARY KEY,
  rig_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision >= 1),
  rig_manifest_artifact_id TEXT NOT NULL,
  rig_profile_artifact_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('candidate','approved','rejected')),
  capability_hash TEXT NOT NULL CHECK(length(capability_hash)=64),
  created_at TEXT NOT NULL,
  reviewed_at TEXT,
  FOREIGN KEY(rig_id, channel_id) REFERENCES rigs(rig_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(rig_manifest_artifact_id, channel_id) REFERENCES artifacts(artifact_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(rig_profile_artifact_id, channel_id) REFERENCES artifacts(artifact_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(rig_id, revision), UNIQUE(rig_version_id, channel_id)
);
CREATE INDEX ix_rig_versions_capability ON rig_versions(status, capability_hash);

CREATE TABLE motion_templates (
  motion_template_id TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(channel_id) ON DELETE RESTRICT,
  semantic_key TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision >= 1),
  artifact_id TEXT NOT NULL,
  capability_hash TEXT NOT NULL CHECK(length(capability_hash)=64),
  status TEXT NOT NULL CHECK(status IN ('draft','approved','rejected')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(artifact_id, channel_id) REFERENCES artifacts(artifact_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(channel_id, semantic_key, revision)
);

CREATE TABLE operations (
  operation_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','unknown','completed','failed','cancelled')),
  input_fingerprint TEXT NOT NULL CHECK(length(input_fingerprint)=64),
  idempotency_key TEXT NOT NULL,
  paid_consent_artifact_id TEXT,
  lease_owner TEXT,
  lease_token TEXT,
  lease_expires_at TEXT,
  attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt >= 0),
  request_json TEXT NOT NULL,
  result_json TEXT,
  error_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id, channel_id) REFERENCES projects(project_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(paid_consent_artifact_id, project_id, channel_id) REFERENCES artifacts(artifact_id, project_id, channel_id) ON DELETE RESTRICT,
  UNIQUE(project_id, kind, idempotency_key), UNIQUE(operation_id, project_id, channel_id),
  CHECK((lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) OR (lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);
CREATE INDEX ix_operations_status_lease ON operations(status, lease_expires_at);

CREATE TABLE operation_tasks (
  operation_task_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  task_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','claimed','submitted','running','unknown','completed','failed','cancelled')),
  claim_token TEXT,
  attempt INTEGER NOT NULL CHECK(attempt >= 1),
  provider_id TEXT,
  provider_handle_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(operation_id, project_id, channel_id) REFERENCES operations(operation_id, project_id, channel_id) ON DELETE CASCADE,
  UNIQUE(operation_id, task_key, attempt)
);
CREATE INDEX ix_operation_tasks_claim ON operation_tasks(status, claim_token);

CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  operation_id TEXT UNIQUE,
  project_id TEXT NOT NULL,
  channel_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','unknown','completed','failed','cancelled')),
  progress_message TEXT NOT NULL,
  progress_percent INTEGER NOT NULL DEFAULT 0 CHECK(progress_percent BETWEEN 0 AND 100),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(operation_id, project_id, channel_id) REFERENCES operations(operation_id, project_id, channel_id) ON DELETE RESTRICT,
  FOREIGN KEY(project_id, channel_id) REFERENCES projects(project_id, channel_id) ON DELETE RESTRICT
);
CREATE INDEX ix_jobs_project_updated ON jobs(project_id, updated_at);
