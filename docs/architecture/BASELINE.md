# C0 source baseline

Verified repository: `plthien/2D-Animation-Studio`; baseline `b35834808d99067e362a6e728ce7af8e04d2b6bd` (`main`, first commit). Origin is `https://github.com/plthien/2D-Animation-Studio.git`. The approved read-only donor is `plthien/ytb-ai-studio@393d0eb5516ac8bb8455f859b79bfc64388b128e`; no other repository or PR is an implementation source.

The exact reviewed v3 plan is committed at `docs/plans/2D_ANIMATION_STUDIO_CLEAN_CUTOVER_IMPLEMENTATION_PLAN_v3.md`: 56,516 bytes, SHA-256 `39a0677432a511f49dc8c5896bc1d101e8512cc3c7388917083f61b476b08f41`. The local source copy remains user-owned and untracked.

`git ls-files` at baseline returns 813 paths. The app currently identifies as YouTube AI Studio V3, uses YTB migrations `001..031`, and mounts platform, V4, scene asset, visual reference, voice, jobs and render authorities in `app/main.py`. This is evidence only: C0 leaves it unchanged; C2 replaces it atomically.

Active baseline entrypoints: `app.main:create_app`; `app.durable_media_workflow_runner`; `app.durable_render_runner`; `app.scene_asset_coordinator_runner`; `app.visual_reference_coordinator_runner`; `app.voice_coordinator_runner`; `app.render_coordinator_runner`; `start.bat`; `scripts/windows/*.bat`; Vite `src/main.tsx`. `app_lifespan` upgrades the old DB and invokes visual-reference/media recovery. `start.bat` starts API, media host, render host, and Vite.

## C0 safety boundary

No existing database, artifact root, generated artifact, legacy route, model, migration, service, or UI source has been modified. Any local runtime uses a disposable DB and artifact root. The baseline’s old source remains temporarily visible and must never be represented as an approved permanent mode.
