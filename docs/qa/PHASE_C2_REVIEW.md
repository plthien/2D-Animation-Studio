# C2 acceptance evidence — exact-HEAD verification pending

**Phase:** C2 Atomic animation-only clean cutover, PR [#4](https://github.com/plthien/2D-Animation-Studio/pull/4) (Draft).  
**Verified base:** `main@41e558d623ef36eabd03cba97435197c6d196b63`; C1 PR #3 merged.  
**Implementation HEAD:** consult the PR head at audit time; this report cannot embed the SHA of its own future commit.  
**Platform:** GitHub-hosted `windows-latest` Windows Server with Python 3.12, Node 22, PowerShell. Real consumer Windows 11 verification remains distinct.

## 1. Files, cutover and runtime authority

Pre-C2 base contained **907 tracked blobs** (1003 tree entries). The first full-source cutover head `e447e9f` contained **171 tracked blobs** (222 tree entries); the PR diff reported **804 changed files, ~187,289 removed and ~2,700 added lines** before later focused fixes. These figures are commit-sensitive and must be rechecked on the final PR HEAD.

The active application now uses `app/main.py`, `app/animation/{database,service,strict_json,...}`, fresh `0001_animation_initial.py`, `src/` cockpit and `scripts/windows/start_studio.ps1`. The isolated `experiments/spine-feasibility/` is retained as C1 evidence only, not imported as the C2 production renderer. Neutral process, strict JSON and bounded transport primitives are kept separately; no old YTB domain worker is launched.

Automated structural authority: `python tools/check_c2_cutover.py`; on [run 38926471496](https://github.com/plthien/2D-Animation-Studio/actions/runs/38926471496), output was `C2 cutover static PASS: 189 filesystem entries; 9 reachable Python modules; exactly 19 endpoints`. The checker rejects old migrations, `app/modules/v4`, old API/platform/db/worker trees, old frontend production panels and retired package authority. Historical audit docs and C1 experiments are not production routes.

## 2. Frozen schema and transactions

The single initial migration creates **14 application tables + `alembic_version`** from `contracts/animation/animation_schema.sql`, including the two required partial uniqueness indexes. C2 pytest covers fresh boot, exact table inventory, FKs, database restart, signature-based legacy refusal without writing user database bytes, ownership, immutable revision publication, idempotency, stale head CAS and preflushed SQLAlchemy transaction ownership. Use only disposable test database paths.

Authoritative migration: `alembic/versions/0001_animation_initial.py`; fresh revision has no dependency on YTB 001–031. Legacy data import/migration is explicitly unsupported.

## 3. Accepted API method/path pairs

The authoritative register is `contracts/animation/api/endpoints.json`. `tools/check_c2_cutover.py` compares the actual OpenAPI method/path pairs to exactly **19 ACCEPTED** rows. These are:

1. GET `/health`
2. GET `/api/v1/system`
3. GET and POST `/api/v1/channels`
4. GET, PATCH and DELETE `/api/v1/channels/{channel_id}`
5. GET and PUT `/api/v1/channels/{channel_id}/dna`
6. POST `/api/v1/channels/{channel_id}/dna/{artifact_id}/approve`
7. GET and POST `/api/v1/projects`
8. GET, PATCH and DELETE `/api/v1/projects/{project_id}`
9. GET `/api/v1/projects/{project_id}/workflow`
10. GET `/api/v1/jobs`
11. GET `/api/v1/jobs/{job_id}`
12. GET `/api/v1/artifacts/{artifact_id}`

The combined groups total 19 method/path pairs. The 18 `PROPOSED` future routes remain absent; built-in documentation/OpenAPI URLs are not domain method/path pairs. Old YTB routes do not produce operations or paid calls.

## 4. Real workflow and browser evidence

At [Windows CI run 38926471496](https://github.com/plthien/2D-Animation-Studio/actions/runs/38926471496), real Chromium executed Channel creation → ChannelDNA v2 save → approval → Project creation → seven stages → browser refresh → API restart → persisted reopen without local mock storage. This stage passed after repairing ChannelsPage's asynchronous channel-name draft initialization in commit `0d0b953`.

Evidence archive: [38 browser PNG/JSON files](https://github.com/plthien/2D-Animation-Studio/actions/runs/38926471496/artifacts/12056204287). Captures cover 1440×900, 1920×1080 and 768×900. The G0 comparison script verified hashes of the original ten baseline screenshots and produced ten side-by-side comparisons.

**Manual visual review of the ten side-by-side comparisons:** Cockpit's dark palette, sidebar, selected workspace, header hierarchy, cards and modal surfaces remain recognizable. The ChannelDNA modal is intentionally smaller with fewer animation-only fields; Studio's seven-stage layout differs legitimately from the old Story/Scene/Voice arrangement. The 768-pixel screenshot preserves the baseline sidebar-first responsive reflow. No obvious C2-blocking hierarchy loss was observed in the comparison images. This is a visual assessment, not pixel equality.

## 5. Executable gates and exact commands

Windows CI workflow `.github/workflows/c2-animation-cutover.yml`:

- `python -m pytest -q tests/c2`: **20 passed / 1 skipped** at `0d0b953`; skipped fixture required Windows reparse-link testing. A replacement junction fixture has been committed; **its final exact-SHA Windows result remains to be verified** before passing the filesystem safety gate.
- `python tools/check_c2_cutover.py`: PASS at `0d0b953`.
- `npm ci --ignore-scripts`, `npm run build`: PASS at `0d0b953`.
- `node tools/c2_browser.mjs`: PASS at `0d0b953`.
- `python tools/c2_g0_compare.py`: PASS for 10 pairs at `0d0b953`.
- `./tests/c2/windows_launcher_smoke.ps1`: PASS from disposable path containing spaces, first run/migration and owned process shutdown at `0d0b953`.
- Python `pip-audit`: “No known vulnerabilities found” at `0d0b953`.
- `npm audit --omit=dev --audit-level=high`: reports **one moderate** `yaml` advisory GHSA-48c2-rrv3-qjmp; exit 0 because threshold is high. It is not a clean zero-advisory report. The full `npm ci` at launcher first-run also reports 15 audit findings (6 moderate, 9 high) including developer dependencies; precise provenance and supported upgrade plan require follow-up before release. No blind `npm audit fix --force`.
- C1 consumer Windows 11 acceptance not provided by Windows Server CI. Do not mark that historical gap as resolved.

## 6. Gate status by C2 requirement

| Gate | Status | Evidence / gap |
|---|---|---|
| C2-01 Source deletion and reachable imports | PASS on `0d0b953` | Static scanner + runtime/CI, source is animation-only |
| C2-02 DB, immutable revision, CAS, path safety | BLOCKED | 20 Python PASS but Windows symlink fixture was skipped; junction regression rerun pending |
| C2-03 Exact 19 API endpoints | PASS on `0d0b953` | Live OpenAPI equality and API suite |
| C2-04 Real Channel → DNA → Project → restart | PASS on `0d0b953` | Chromium, real backend, persisted SQLite |
| C2-05 G0 Cockpit UI parity | PASS on `0d0b953` | 10 hash-verified screenshot pairs + documented manual review |
| C2-06 Windows launcher/process | PASS on `0d0b953` | Disposable spaced path first-run + shutdown |
| C2-07 Security/dependencies | BLOCKED for final closure | Moderate npm advisory and full developer-dependency report need triage; no known Python CVEs |

The source and CI results are **not** release acceptance. C3–C12 actions remain non-operational. User data are never migrated from YTB.

## 7. Findings and handoff

- **BLOCKER (C2 evidence)**: rerun security path containment fixture on Windows without privilege-dependent skip; require passing actual reparse/junction check at final exact HEAD.
- **MEDIUM (C2)**: investigate and pin supported `yaml` dependency fix; document the production advisory and developer-tool dependency findings without forced upgrades.
- **DEFERRED (C1/C12)**: consumer Windows 11 x64 execution evidence is still absent; hosted Windows Server CI does not substitute for consumer test.
- **DEFERRED (C3–C12)**: external authoring, paid image generation, native rigging, motion, multi-shot rendering and voice-last delivery are future functional phases; their shells cannot claim working generation.
- **LOW**: updated frontend and API library deprecation warnings in hosted CI; not proof of runtime failure.

**Merge verdict:** keep PR #4 in Draft until all applicable C2 mandatory gates pass on its final implementation SHA, and the known advisory/execution gaps have an explicit reviewed disposition. No automatic merge.
