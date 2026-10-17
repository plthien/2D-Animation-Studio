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

- `python -m pytest -q tests/c2`: **21 passed / 0 skipped** at `b104d654` on [run 38927938181](https://github.com/plthien/2D-Animation-Studio/actions/runs/38927938181). The Windows junction/reparse containment regression executes without privileged symlink creation and passed.
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
| C2-02 DB, immutable revision, CAS, path safety | PASS at `b104d654` | 21 Python PASS, zero skips, real Windows junction containment regression |
| C2-03 Exact 19 API endpoints | PASS on `0d0b953` | Live OpenAPI equality and API suite |
| C2-04 Real Channel → DNA → Project → restart | PASS on `0d0b953` | Chromium, real backend, persisted SQLite |
| C2-05 G0 Cockpit UI parity | PASS on `0d0b953` | 10 hash-verified screenshot pairs + documented manual review |
| C2-06 Windows launcher/process | PASS on `0d0b953` | Disposable spaced path first-run + shutdown |
| C2-07 Security/dependencies | PASS with MEDIUM advisory | No known Python CVEs; one moderate production `yaml` advisory and developer-tool reports explicitly retained for triage, no suppressed high-severity production audit |

The source and CI results are **not** release acceptance. C3–C12 actions remain non-operational. User data are never migrated from YTB.

## 7. Findings and handoff

- **RESOLVED (C2 evidence)**: Windows junction containment was rerun without a privilege-dependent skip: 21/21 Python tests PASS at `b104d654`.
- **MEDIUM (C2)**: investigate and pin supported `yaml` dependency fix; document the production advisory and developer-tool dependency findings without forced upgrades.
- **DEFERRED (C1/C12)**: consumer Windows 11 x64 execution evidence is still absent; hosted Windows Server CI does not substitute for consumer test.
- **DEFERRED (C3–C12)**: external authoring, paid image generation, native rigging, motion, multi-shot rendering and voice-last delivery are future functional phases; their shells cannot claim working generation.
- **LOW**: updated frontend and API library deprecation warnings in hosted CI; not proof of runtime failure.

**Historical C2 baseline verdict (prior to new targeted audit):** Windows platform tests passed at `f488c9ee`; the targeted six-finding audit below supersedes that result. No owner merge approval has been given.


---

## C2 targeted six-finding repair — 2026-10-17 (unverified final HEAD)

**Source audit authority:** user task against `f488c9ee4b9cb74517a7b2c0a42308dfc33da5ba`.
**Repair branch:** `feat/c2-atomic-animation-cutover`; latest implementation SHA before this QA edit: `19a9baca24b0d1090626fc9a7338ecb3bf577d3b`.
**Decision:** **C2 BLOCKED pending exact-head Windows targeted regression and security acceptance.** This section does not change historical PASS evidence into newly proven PASS.

| Finding | Code + tests implemented | Acceptance status |
|---|---|---|
| C2-B1 BLOCKER | `service.approve_dna` now requires candidate revision strictly greater than current approved revision; idempotent current-head replay retained. New tests assert rollback rejection and unchanged head, draft metadata, file SHA, cross-channel/wrong-SHA errors. | CODED — exact-HEAD regression not yet verified |
| C2-B2 BLOCKER | `database.verify_frozen_schema` compares SQLite DDL, indices (including partial predicates), structural PRAGMAs, FK integrity and Alembic revision against the 14-table normative DDL. Both automatic and manual startup pass through read-only guard. Six independent tampering regressions added. | CODED — exact-HEAD regression not yet verified |
| C2-H1 HIGH | Central `StrictC2JSONRoute` checks content type and 1 MiB raw-body bound, caches the same parsed JSON for FastAPI/Pydantic and rejects duplicate/nonfinite/overflow/malformed JSON with typed HTTP 422. Real TestClient raw-byte tests added. | CODED — exact-HEAD regression not yet verified |
| C2-H2 HIGH | C2 workflow fetches event PR head SHA, checkout ref is explicit and PowerShell verifies `git rev-parse HEAD == EXPECTED_HEAD`. Docs/qa and tools changes trigger the gate. | IMPLEMENTED — exact-HEAD run required |
| C2-H3 HIGH | Mandatory Python and npm production/full audits without `continue-on-error`; JSON inventories and fail-closed security policy; compatible-only npm lockfile fix committed (`d18f826`), `npm ci` verified; Vite server CORS constrained to loopback. | **BLOCKED — unreviewed high-severity full-graph advisories** |
| C2-M1 MEDIUM | Fake Win32 API validates Job Object configuration, assignment-failure cleanup and idempotent close; real Windows parent/descendant kill-on-close and unrelated-process isolation executed with bounded subprocess watchdog. | CODED — exact-HEAD Windows execution required |

### Security inventory and review disposition

One-time [compatible-only Windows lockfile remediation run](https://github.com/plthien/2D-Animation-Studio/actions/runs/38987497894) completed **SUCCESS**. It used `npm audit fix --package-lock-only --ignore-scripts`, explicitly without `--force`, installed the resulting lockfile using `npm ci` and committed only `package-lock.json` on PR #4. The temporary writer workflow and trigger were then removed.

The compatible-only resolver still reported **9 npm findings (6 HIGH, 3 MODERATE)** in the full installed dependency tree:

- `braces@3.0.3`, HIGH `GHSA-vfj7-8cjw-p6xm`, via `micromatch/chokidar/fast-glob` and `tailwindcss@3`. npm recommends breaking Tailwind v4 migration. No compatible published patched `braces` version was confirmed at review time. These packages operate on repository-owned CSS/globs; C2 does not expose attacker-controlled CSS compilation via HTTP, but owner review of that reachability/mitigation is pending.
- `esbuild@0.21.5`, MODERATE `GHSA-67mh-4wv8-2f99`, via `vite@5.4.21`. npm proposes breaking Vite v8. C2 now binds the Vite dev server to loopback and restricts CORS origin. An explicit updated-toolchain evaluation is needed; a green Python API test does not resolve this advisory.
- `postcss-selector-parser@6.1.4`, MODERATE `GHSA-rj75-hqrm-r3gf`, via Tailwind/PostCSS compile tooling. The latest patched selector parser is 7.1.6, but changing Tailwind's dependency tree requires compatibility validation. C2's CSS inputs are repository-controlled.
- The production moderate `yaml` advisory `GHSA-48c2-rrv3-qjmp` was addressed by a compatible lockfile update from `yaml@1.10.2` to `yaml@1.10.3`; exact-head production audit must reverify.

No full-graph HIGH exception has been accepted. `tools/c2_security_gate.mjs` blocks unknown/unreviewed high and moderate findings and scanner failures; precise advisory/package/version inventory is uploaded even on failed CI. **Never interpret an audit invocation or a CI `continue-on-error` as security PASS.** A major Tailwind/Vite migration was not introduced into this bounded C2 repair without an approved compatibility plan.

### Required exact-head evidence

Run from the final PR commit on `windows-latest`/PowerShell:

```powershell
python -m pytest -q --timeout=45 --timeout-method=thread tests/c2
python tools/check_c2_cutover.py
npm.cmd ci
npm.cmd run build
node tools/c2_browser.mjs
python tools/c2_g0_compare.py
./tests/c2/windows_launcher_smoke.ps1
```

Also require the `C2_VERIFIED_HEAD` log to match the PR HEAD, production+full audit JSON, fail-closed security policy result, and real process-tree test with no skip/xfail. Early post-repair CI runs contain failures and execution stalls; they are **not** final acceptance proof. Per-test watchdog coverage was added and native Windows test execution was moved behind a 25-second subprocess watchdog so hangs are reported as failures rather than concealed. Exact-HEAD CI must still finish successfully.

**Owner merge-readiness:** NOT READY. Keep existing PR #4 Draft. The Windows 11 consumer acceptance gap from C1/C12 remains visible and is not replaced by Windows Server CI evidence. No C3–C12 functional implementation was added. The repo owner must review any security exceptions or approved major-upgrade work before a merge recommendation.


---

## 2026-10-17 — Final security upgrade and cancelled-run investigation

**Audited HEAD:** `ccc3c4e6a46f6d6b3b00bf07fb7ac176a7c08aff`. The final PR commit after this evidence/cleanup edit must be confirmed separately by GitHub Actions. **No merge was performed.**

### Cancelled Windows run 38987765095

The [run](https://github.com/plthien/2D-Animation-Studio/actions/runs/38987765095) ended `cancelled`; job status was `Test animation C2 platform` in progress. GitHub's archived log download returned `404 BlobNotFound`. The recorded metadata does not distinguish manual cancellation, external interruption or test stall; **root cause of that cancellation is unverified**. Earlier C2 runs also stayed in pytest, prompting an independent reproduction. Do not conflate `cancelled` with `failed` or `passed`.

### Independently reproduced platform defects and repairs

A source-only exact-revision archive was used with disposable SQLite and no user data. The identified source defect was treating `with sqlite3.connect(...)` as a connection close; Python's sqlite context manager commits/rolls back but does not close. Open read-only guards and the migration postcheck could hold SQLite locks. `app/animation/database.py` now uses `contextlib.closing` and read-only SQLite `writable_schema` inspection to distinguish recognized malformed animation DDL from unrelated YTB databases before any mutation. A Win32 fake required `GetCurrentProcess` support in the deterministic test double.

Local Linux-based reproducer result: **46 passed / 1 skipped** (the Windows-only Job Object integration test cannot run on Linux). This is *debugging evidence*, not C2 Windows acceptance. It did demonstrate all six frozen-schema mutation tests, HTTP JSON tests, monotonic DNA tests and persisted byte guards passing. Applicable Win32 process safety still must pass in Windows CI with zero skips.

### Security: controlled major toolchain upgrade, no exception

Previous pinned graph from Windows security run [39002003012](https://github.com/plthien/2D-Animation-Studio/actions/runs/39002003012): production scan clean, full scan **nine flagged dependency nodes (six HIGH, three MODERATE)**, including `braces@3.0.3` and paths through Tailwind v3, plus esbuild/Vite v5 and PostCSS selector tooling. `braces` has no published patched release; no wildcard override, advisory suppression or owner exception was added.

The [isolated Windows toolchain upgrade run 39002408890](https://github.com/plthien/2D-Animation-Studio/actions/runs/39002408890) finished **SUCCESS** and published commit `5cdc8b8abec5437e760158a9142c224c3472d0aa` on this PR only. Targeted changes:

- `vite` 5.4.21 → **8.3.4** (Rolldown rather than old esbuild-based bundler).
- `@vitejs/plugin-react` 4.7.0 → **6.1.2**.
- `tailwindcss` 3.4.19 → **4.3.3**, with `@tailwindcss/postcss` **4.3.3** and native CSS `@import` / `@config` preserving the existing `tailwind.config.js` theme.
- Removed obsolete direct `autoprefixer` dependency; other pins preserved.
- Retained Vite loopback binding and restricted local-origin CORS.

The trial executed pinned `npm ci --ignore-scripts`, frontend build, production and full npm audit, real Chromium Channel → DNA → Project → refresh → API restart, and ten G0 comparison pairs. **Production audit: zero findings; full audit: zero findings.** Screenshot side-by-side visual inspection showed no obvious Cockpit hierarchy loss; expected animation-only domain changes remain. Python pip-audit and actual Windows launcher must still pass against the final immutable HEAD.

The independent policy tests `node --test tests/c2/security_gate.test.mjs` reported **10 PASS / zero FAIL** on the Windows security lane, covering valid clean reports, HIGH/MODERATE/CRITICAL, absent/malformed scanner output, count mismatch, lockfile mismatch and exact-owner-reviewed exception scope. No security exceptions are enabled in production. Audit report serialization was also fixed to produce valid trailing newline JSON.

### Six-finding reconciliation

| Finding | Final source repair | Acceptance authority |
|---|---|---|
| C2-B1 | Monotonic ChannelDNA revision and immutable rejected drafts | Local focused regression PASS; exact Windows HEAD pending |
| C2-B2 | Full frozen DDL validation, closed SQLite connections, read-only corrupt-schema inspection | Local focused regression PASS; exact Windows HEAD pending |
| C2-H1 | Single bounded strict raw HTTP JSON parser and real ASGI tests | Local focused regression PASS; exact Windows HEAD pending |
| C2-H2 | Both platform and security Windows jobs checkout + assert triggering exact head | Final Windows logs pending |
| C2-H3 | Pinned toolchain upgraded, zero npm prod/full audit findings, 10/10 security policy tests | Windows candidate PASS; final security job pending |
| C2-M1 | Deterministic Win32 tests plus real owned descendant process-tree test | Exact Windows HEAD pending |

**Remaining C2 gate:** complete clean `windows-latest` CI on final exact PR SHA, including 0-skipped applicable Win32 process ownership, Windows launcher, screenshots and independent Python/npm security job. Previous cancelled or pre-upgrade results are not final acceptance. Consumer Windows 11 evidence remains a separate C1/C12 gap, never fabricated from Windows Server.

**Merge verdict at document-authorship time: C2 BLOCKED — NOT MERGE READY until final exact-HEAD Windows jobs are green.** After all pass, owner approval is still required; no automatic merge.
