# Animation contract package

Every artifact has a versioned JSON Schema in `schemas/`, a valid fixture in `examples/valid/`, and a rejected fixture in `examples/invalid/`. Schemas reject unknown top-level properties. Contracts are owned by the phase named in `docs/architecture/API_CONTRACTS.md`; C0 freezes structure only and does not create runtime import/approval services.

IDs are opaque non-empty strings. Immutable revisions carry `artifact_id`, `channel_id`, optional `project_id`, `schema_version`, `revision`, `sha256`, `created_at`, and `source_fingerprints`. References must be same channel; project-scoped references must be same project. Semantic checks are in `tools/validate_c0_contracts.py`.

Decision register: (D-01) canonical JSON is UTF-8, recursively sorted object keys, compact separators, no float normalization beyond JSON parser semantics; SHA-256 operates on those bytes. (D-02) string timestamps are RFC3339 UTC. (D-03) voice manifests may reference only final rendered timeline/approved script and cannot be a dependency of ShotPlan, Resolver, Generation, Rigging, Director or Motion. These are minimal decisions not otherwise fixed by v3.
