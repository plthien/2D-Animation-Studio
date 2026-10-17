# 2D Animation Studio

Windows-only, local-first **2D Animation Studio**. This is a new product, not a YouTube AI Studio compatibility mode.

## Current implementation

C2 platform: Channels, channel-scoped immutable ChannelDNA v2 revisions and approval, Projects, seven workflow projections, persisted job/artifact metadata, animation-only API and Cockpit UI. The later authoring, asset generation, auto-rigging, Director, Spine motion, rendering and voice-last delivery stages are **not implemented** in C2. Their actions remain disabled.

## Requirements

- Windows 11 x64 (primary target; real consumer acceptance pending)
- Python 3.12
- Node.js 22
- PowerShell
- A current browser

Run `start.bat` from the repository folder. On first launch it creates a project-owned Python virtual environment, installs pinned Python/npm dependencies and migrates a fresh `2d_animation_studio.db`. UI is bound to `http://127.0.0.1:5173`, API to `http://127.0.0.1:8000`.

## Data safety

Do not point `DATABASE_URL` to an old YTB database. The loader checks for old schemas and refuses them as `LEGACY_DATABASE_UNSUPPORTED` without modifying user data. All artifacts are in `ARTIFACT_ROOT` (default `./local_artifacts`). Do not delete an existing database to get a clean boot.

## C2 verification

Windows-only commands:

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 -m pytest -q tests/c2
py -3.12 tools/check_c2_cutover.py
npm ci --ignore-scripts
npm run build
```

The C2 verification workflow runs on `windows-latest` (Windows Server). It does not replace a real consumer Windows 11 acceptance test.

See `docs/plans/2D_ANIMATION_STUDIO_CLEAN_CUTOVER_IMPLEMENTATION_PLAN_v3.md` and `docs/qa/PHASE_C2_REVIEW.md` for normative contracts and gate status.
