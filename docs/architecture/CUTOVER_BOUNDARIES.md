# Atomic C2 cutover boundary

C2 deletes—not disables—old production authorities: all 31 `alembic/versions/001..031` revisions; old `app/db/models.py` pointers and scene/visual-reference working models; Scene Breakdown/Beat/VisualPlan/Prompt Composer/Scene Asset services; voice-first orchestration and invalidation; Ken Burns/static-image render graph; old route composition and lifespan recoveries; coordinator runners/media-render hosts; retired Studio panels; V4 schemas/prompts/fixtures/tests; `MANIFEST.json` package authority tooling; YTB product docs and launch scripts.

The only permitted extractions are those listed in `REUSE_MATRIX.md`; each gets a new neutral owner and regression test before its former owner is removed.

Static C2 gates reject: `app/modules/v4/`, `tests/v4/`, old migrations, legacy contract/prompts, legacy runner commands, forbidden production imports (`scene_breakdown`, `scene_asset`, `beat_timing`, `visual_plan`, `voice_first`, `assembly_motion`, `render_graph`), legacy OpenAPI paths, non-animation DB tables/columns, old UI workflow states, `legacy_mode`/compatibility adapters, dual routes, and startup recovery of old operations. Documentation/tests may mention forbidden tokens only in this explicit ban list.
