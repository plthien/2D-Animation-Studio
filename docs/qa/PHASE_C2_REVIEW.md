# C2 Phase Review — implementation incomplete (Draft only)

Checked on 2026-10-16. This is an evidence inventory, not a C2 pass certificate.

## Verified repository baseline
- Origin main SHA: `41e558d623ef36eabd03cba97435197c6d196b63`.
- PR #3 is merged. Windows 11 consumer C1 proof remains outstanding.
- Branch: `feat/c2-atomic-animation-cutover`; exact current SHA is the PR HEAD.
- At start of C2 main had 907 tracked blobs (1003 total tree entries).
- The codebase still includes active old YTB routes, migration revisions 001–031, V4 workers and frontend panels.

## Implemented in the initial branch commit
- `app/animation/database.py`: read-only SQLite signature inspection, animation table inventory, legacy refusal, migration bootstrap.
- `alembic/versions/0001_animation_initial.py`: first draft migration from normative frozen SQL.
- `alembic/env.py`: first draft fresh animation migration environment.
- `tests/c2/test_fresh_animation_database.py`: initial focused schema and immutable-legacy-file checks.

These are source changes only. They are not yet wired into the new production FastAPI runtime. Do not interpret the tests existing as evidence of their execution.

## Gates
| Gate | Status | Reason |
|---|---|---|
| C2-01 legacy deletion and reachability | FAIL | Old YTB source, imports, migrations and CI remain |
| C2-02 schema, ownership, CAS, legacy safety | BLOCKED | Source-level migration draft exists; exact runtime and Windows verification not executed; ownership/CAS not implemented |
| C2-03 exact 19 API routes | FAIL | Existing old API still active; new route implementation absent |
| C2-04 real Channel → DNA → Project → restart | NOT_RUN | New API/UI persistence not implemented |
| C2-05 G0 Cockpit UI parity | NOT_RUN | Frontend cutover and Chrome screenshots absent |
| C2-06 Windows launcher/process safety | FAIL | Old YTB launcher/worker startup remains |
| C2-07 security/dependency verification | NOT_RUN | Full cutover and scans not executed |

## Mandatory remaining C2 scope
- Physically remove old YTB route/worker/control-plane source and obsolete C0/YTB workflows only after safe neutral extraction.
- Implement immutable artifacts, ownership, channel/project CRUD, ChannelDNA v2 revisions, publication CAS, correct idempotency, seven computed stage projections and all 19 accepted API contracts.
- Preserve Cockpit shell and real cards/modals while adapting all seven stages and real backend DTOs.
- Replace Windows launcher, YTB product metadata, dead dependencies and previous migrations.
- Run all seven gates against exact implementation SHA on `windows-latest` and verify the source deletion graph and Chrome screenshots.
- Report Windows Server versus actual Windows 11 consumer evidence separately.

## Merge decision
**C2 BLOCKED. Keep Draft. Do not merge.**
