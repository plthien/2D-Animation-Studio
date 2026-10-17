# WINDOWS_ONLY_TEST_POLICY — ACCEPTED (C0–C12)

**Product decision:** 2D Animation Studio is one Windows desktop/local application, not a cross-platform release. All active GitHub Actions jobs for this repository use `windows-latest` and PowerShell. No Ubuntu, Linux, macOS or CI OS matrix is a product acceptance requirement.

**Targets:** Windows 11 x64; Windows 10 x64 only after explicit separate compatibility testing before release. `windows-latest` is a Windows Server runner: success does **not** establish compatibility with Windows 10/11 consumer installs. Python 3.12, Node.js 22, Windows FFmpeg/FFprobe and Chromium, pinned licensed Spine/PixiJS versions.

**C0:** Windows-only contract, SQLite, ledger/reachability, source scope, G0 hashed screenshots and targeted pytest. Legacy YTB CI is transitional, Windows-only baseline safety, NOT animation authority. Existing historically true Linux results stay in history without becoming active gates.

**C1:** Actual official Spine/PixiJS on Windows; one 240-frame 24fps articulated shot, independently evaluated nonsequential frames, true prop grip and real FFmpeg/FFprobe MP4; valid license and runtime identities. Run on a real Windows 11 target as well as Windows CI. Windows 10 real evidence is additionally required if targeted. NOT_STARTED until separate C1 PR.

**C2:** Atomically delete obsolete YTB-only CI/workflows, manifests and legacy runtime; introduce animation-only Windows API, fresh DB, launcher, UI and cutover safety checks. No old Linux compatibility tests.

**C3–C5:** Windows-only phase-specific authoring, assets and paid provider tests, bounded to behavior actually implemented. Never perform paid provider calls without explicit approval.

**C6–C10:** Windows Spine/PixiJS graphics and worker/process-lifecycle tests with actual frames; deterministic rig/motion/IK only after implementation; no synthetic C0 runtime proof.

**C11:** Windows Kokoro/ElevenLabs voice adapters, Windows FFmpeg/FFprobe, job-object cancellation/process-tree ownership and real sample/frame mux QC.

**C12:** Windows-only release workflow plus actual consumer Windows 11 cold start, installation/launcher, SQLite and rendering proof, two completed distinct videos with QC; Windows 10 compatibility testing if release claims Windows 10.

**Fail-closed rule:** An applicable Windows safety check that cannot run or fails is BLOCKED, not silently skipped or replaced by an old Linux PASS. No new C2–C12 execution suites in C0. Historical YTB baseline checks may be retired with rationale in C2; keep applicable Windows process/FFmpeg protections through transition.

**2026-10-17 owner-directed C2 PR #4 source-merge exception:** The owner chose to defer final integrated C2 Windows platform test acceptance until the *full animation flow* is built. This narrowly authorizes the C2 source merge before platform job completion; the job is **NOT_VERIFIED**, not PASS. All corresponding Windows platform/integration tests and consumer Windows 11 evidence remain mandatory **before full-flow/C12 release signoff**. No change to CI implementation, no test bypass and no inference that a Windows Server result proves consumer Windows 11. See the signed-off decision and pending gate inventory in `docs/qa/PHASE_C2_REVIEW.md`. This exception applies only to PR #4.
