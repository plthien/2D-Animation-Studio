# C0 implementation authority

This repository is in a temporary C0 source-baseline state on `feat/c0-clean-cutover-contracts`; it is **not** a released dual-mode product. The checked-in YTB implementation is evidence for UI and neutral-infrastructure reuse only. C0 may add documentation, contract fixtures, validators, and baseline evidence. It must not alter production routes, models, migrations, services, or legacy files.

The authoritative transition is the clean-cut plan v3: C1 is an isolated Spine feasibility proof; C2 is the single atomic deletion/replacement change. No contributor may introduce a compatibility mode, YTB data migration, dual read/write path, legacy adapter, or a second workflow authority. Preserve the Cockpit UX named in `docs/architecture/UI_PARITY.md`.

For all later phases, `contracts/animation/` and the architecture documents created by C0 are the proposed normative input. A change to table count, seven-stage authority, contract schema, ID semantics, or paid-operation fence requires an explicit decision-register entry and tests. Do not treat legacy README, MANIFEST, old schemas, or old migrations as authority after C2.
