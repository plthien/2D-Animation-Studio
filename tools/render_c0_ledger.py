"""Render the reviewed 813-row C0 ledger to stdout for review/apply_patch."""
from __future__ import annotations
from pathlib import Path
from c0_ledger_lib import LEDGER_COLUMNS, analyze_reachability, baseline_paths

EXTRACT_V4 = {
    "app/modules/v4/host_owned_process.py": ("HostOwnedProcess supervision and cancellation", "app/core/process/host_owned_process.py", "tests/platform/test_host_owned_process.py"),
    "app/modules/v4/windows_job_object.py": ("Windows Job Object lifecycle", "app/core/process/windows_job_object.py", "tests/platform/test_windows_job_object.py"),
    "app/modules/v4/windows_subprocess_guard.py": ("subprocess path/creation guard", "app/core/process/windows_subprocess_guard.py", "tests/platform/test_windows_subprocess_guard.py"),
    "app/modules/v4/render_process_diagnostics.py": ("bounded process diagnostics/redaction", "app/core/process/diagnostics.py", "tests/platform/test_process_diagnostics.py"),
    "app/modules/v4/render_validation.py": ("FFprobe output integrity checks only", "app/modules/animation/delivery/media_validation.py", "tests/delivery/test_media_validation.py"),
    "app/modules/v4/render_ffmpeg.py": ("safe FFmpeg process/progress/cancel primitives; exclude Ken Burns/filter graph", "app/modules/animation/delivery/ffmpeg_runner.py", "tests/delivery/test_ffmpeg_runner.py"),
}
for name in ("voice_provider_adapters", "voice_pacing", "voice_pacing_calibration", "voice_pacing_calibration_settings", "voice_alignment", "voice_audio", "elevenlabs_client", "elevenlabs_credentials", "elevenlabs_model_policy", "elevenlabs_provider_adapter"):
    EXTRACT_V4[f"app/modules/v4/{name}.py"] = (f"neutral {name} provider/pacing primitive; exclude voice-first orchestration", f"app/modules/animation/voice/{name}.py", f"tests/voice/test_{name}.py")

MANUAL = {
    "app/main.py": ("ADAPT", "Live FastAPI composition is required but must be rebuilt with animation-only routers/lifespan.", "app/main.py", "Replace old router/recovery mounts while retaining application factory/error/CORS shape.", "tests/platform/test_app_composition.py", "manual source review: create_app, app_lifespan, include_router"),
    "app/repositories/core.py": ("EXTRACT", "Contains neutral artifact/revision/CAS and CRUD guards mixed with YTB project pointers.", "app/repositories/artifacts.py", "ArtifactRepository create/read/publish CAS, ownership guards and neutral Channel/Project CRUD; omit Scene/Beat pointer methods.", "tests/platform/test_artifact_repository.py", "manual symbol review: ArtifactRepository, ChannelRepository, ProjectRepository"),
    "app/services/artifacts.py": ("EXTRACT", "Neutral staging, streamed hashing, immutable publication and attempt cleanup are reusable.", "app/modules/animation/platform/artifact_publication.py", "Path containment, staged bytes, streaming SHA/size, finalize/rollback/orphan reconciliation; exclude YTB kind policy.", "tests/platform/test_artifact_publication.py", "manual function review: stage/publish/finalize/cleanup paths"),
    "app/services/external_authoring_reservations.py": ("EXTRACT", "Reservation expiry and consume-CAS are neutral external-authoring safety behavior.", "app/modules/animation/authoring/reservations.py", "Reserve IDs/source fingerprint, expire/cancel, one-time consume CAS for Topic/Script/ShotPlan/Director.", "tests/authoring/test_reservations.py", "manual service/repository call review"),
    "app/modules/platform/services.py": ("EXTRACT", "Topic/Script external-authoring logic is reusable but voice-first/static stage composition is not.", "app/modules/animation/authoring/services.py", "Topic idea/script prompt-import-review primitives and ownership checks; delete TTS readiness and old project pointer invalidation.", "tests/authoring/test_topic_script_services.py", "manual class/method split review"),
    "app/modules/media/glabs_webhook_client.py": ("ADAPT", "Secure provider HTTP transport is reusable after removing YTB payload ownership.", "app/modules/animation/generation/glabs_client.py", "Retain bounded submit/status/download/error parsing with animation operation DTOs and explicit consent.", "tests/generation/test_glabs_client.py", "manual transport method review"),
    "app/db/models.py": ("ADAPT", "Live ORM owner must be replaced by the frozen fourteen-table model set; selected neutral patterns inform implementation.", "app/db/models.py", "Rewrite in C2; no old Scene/Beat/Voice pointers survive.", "tests/platform/test_fresh_schema.py", "manual ORM class/FK review"),
    "start.bat": ("ADAPT", "Live Windows launcher currently starts old API/media/render hosts.", "start.bat", "Retain environment bootstrap pattern; launch only implemented animation processes after C2.", "tests/platform/test_windows_launcher.py", "manual command-flow review"),
}

def classify(path: str) -> tuple[str, str, str, str, str, str]:
    if path in MANUAL:
        return MANUAL[path]
    if path in EXTRACT_V4:
        symbol, target, test = EXTRACT_V4[path]
        return "EXTRACT", "Neutral voice/process primitive inside a legacy V4 owner.", target, symbol, test, "manual function-level extraction review"
    if path.startswith("src/layout/") or path.startswith("src/components/ui/") or path in {"src/theme/theme.ts", "src/index.css", "tailwind.config.js"}:
        return "KEEP", "Protected cockpit visual implementation and design tokens.", path, "Retain implementation; adapt only branding/security where required.", "tests/e2e/test_ui_parity.py", "manual DOM/style review + React reachability graph"
    if path.startswith(("src/features/channels/", "src/features/projects/", "src/pages/")) or path in {"src/App.tsx", "src/app/workspace.ts"}:
        return "ADAPT", "Reachable proven workspace/card/dialog/page UX with YTB DTO coupling.", path, "Preserve DOM/interaction hierarchy; bind animation DTOs and seven-stage state.", "tests/e2e/test_ui_parity.py", "manual component/import review"
    if path.startswith("src/features/studio/"):
        legacy = any(token in Path(path).name for token in ("SceneBreakdown", "SceneAssets", "Assembly", "RenderPanel", "VoicePanel", "StyleBibleVisual"))
        if legacy:
            return "DELETE", "Legacy Scene/Beat/voice-first/static-render panel; shared patterns are separately owned.", "src/features/animation/", "Remove content owner in C2; reuse only shared UI primitives already classified KEEP.", "tests/e2e/test_no_legacy_stages.py", "manual Studio component review"
        return "ADAPT", "Reusable Studio interaction/prompt/progress pattern with old stage DTOs.", "src/features/animation/", "Rebind interaction pattern to one seven-stage animation workflow.", "tests/e2e/test_animation_studio_shell.py", "manual Studio component review"
    if path.startswith("src/"):
        return "ADAPT", "Reachable frontend support/API wiring must change to animation contracts.", path, "Preserve neutral client/helper behavior and replace YTB DTO authority.", "tests/frontend/test_contract_parity.py", "React/TS graph and source review"
    if path.startswith("app/modules/media/durable_workflow/") or path == "app/repositories/durable_workflow_protocol.py":
        return "ADAPT", "Neutral durable lease/claim/idempotency machinery with old task DTO coupling.", "app/modules/animation/operations/", "Retain owner/lease/fencing/reconcile mechanics on new operation tables.", "tests/platform/test_operation_fencing.py", "manual durable state-machine review"
    if path.startswith("app/modules/media/") and Path(path).name in {"bounded_http_transport.py", "image_upload_validation.py", "media_provider_errors.py", "media_secret_safety.py", "transport_policy.py"}:
        return "ADAPT", "Neutral bounded provider transport/security primitive.", "app/modules/animation/generation/", "Retain bounded IO, validation, redaction and typed transport errors.", "tests/generation/test_transport_security.py", "manual transport/security review"
    if path.startswith("app/modules/v4/"):
        return "DELETE", "Legacy V4 Scene/Beat/voice-first/static render authority with no retained neutral symbol.", "removed", "Remove in C2 after all separately listed EXTRACT items land.", "tests/platform/test_no_legacy_imports.py", "manual V4 inventory review"
    if path.startswith("alembic/versions/"):
        return "DELETE", "Old YTB migration revision is reachable only through legacy Alembic history.", "alembic/versions/0001_animation_initial.py", "Delete all 001–031 in atomic C2; no data migration.", "tests/platform/test_fresh_schema.py", "manual Alembic chain review"
    if path.startswith("app/api/routes/"):
        return "ADAPT", "Live router surface must be replaced or removed under exact animation route register.", "app/api/routes/animation/", "Preserve neutral error/response patterns only; no old route remains registered.", "tests/platform/test_openapi_routes.py", "FastAPI registration/import graph review"
    if path.startswith("app/api/"):
        if path == "app/api/errors.py":
            return "ADAPT", "Neutral typed error envelope infrastructure.", path, "Retain handler mechanics; replace code registry with animation errors.", "tests/platform/test_error_envelopes.py", "manual exception-handler review"
        return "DELETE", "YTB request/response schema owner superseded by animation DTOs.", "app/api/animation/", "Remove after new DTO tests exist.", "tests/platform/test_api_contracts.py", "manual schema owner review"
    if path.startswith("app/core/"):
        return "ADAPT", "Core primitive/configuration is reusable but product defaults and contracts change.", path, "Preserve neutral ID/hash/time/redaction/parser behavior; replace YTB defaults.", "tests/platform/test_core_primitives.py", "manual core module review"
    if path.startswith("app/db/"):
        return "DELETE", "YTB-specific persistence owner superseded by fresh schema.", "app/db/", "Remove in C2 after fresh model/repository replacement.", "tests/platform/test_fresh_schema.py", "manual DB owner review"
    if path.startswith(("app/repositories/", "app/services/", "app/modules/platform/")):
        return "DELETE", "YTB domain service/repository has no neutral extraction beyond explicitly listed files.", "removed", "Remove after explicit neutral extractions and replacement tests.", "tests/platform/test_no_legacy_imports.py", "manual repository/service inventory review"
    if path.startswith("app/"):
        if path.endswith("runner.py"):
            return "DELETE", "Reachable old worker/coordinator entrypoint.", "removed", "Remove from launcher/import graph in C2.", "tests/platform/test_no_legacy_workers.py", "manual runner/launcher review"
        return "ADAPT", "Package/runtime support remains needed but must become animation-owned.", path, "Retain package boundary where neutral; replace YTB authority.", "tests/platform/test_import_graph.py", "Python AST graph + source review"
    if path.startswith("kokoro/"):
        return "EXTRACT", "Neutral local voice provider asset/tooling used only in voice-last delivery.", "app/modules/animation/voice/kokoro/", "Provider CLI/config/voice synthesis identity; exclude old orchestration and model/user data.", "tests/voice/test_kokoro_provider.py", "manual provider file review"
    if path.startswith("contracts/schemas/core/"):
        return "EXTRACT", "Neutral validation/error/external-authoring contract pattern.", "contracts/animation/common/", "Port strict envelope/import primitives with animation identifiers.", "tests/c0/test_animation_contracts.py", "manual schema field review"
    if path.startswith("contracts/"):
        return "DELETE", "Legacy YTB schema/prompt/example/OpenAPI authority.", "contracts/animation/", "Remove in C2 after animation replacements are executable.", "tests/platform/test_no_legacy_contracts.py", "manual contract inventory review"
    if path.startswith("tests/"):
        neutral = any(token in path for token in ("external_authoring", "durable", "transport", "redaction", "hash", "subprocess", "sqlite", "artifact"))
        if neutral:
            return "EXTRACT", "Test contains a neutral safety/regression behavior worth transferring.", "tests/platform/", "Transfer the neutral assertion to the new owner; discard YTB fixture coupling.", "tests/c0/test_ledger.py", "manual test-name and dependency review"
        return "DELETE", "Test asserts obsolete YTB product semantics.", "removed", "Delete only in C2 with owning replacement test where applicable.", "tests/platform/test_no_legacy_tests.py", "manual test inventory review"
    if path.startswith(".github/workflows/"):
        return "ADAPT", "CI is active operational authority but currently validates YTB release behavior.", path, "Retain source-integrity coverage; add independent C0 gates and later rewrite product jobs.", "tests/c0/test_scope_and_ci.py", "manual workflow trigger/command review"
    if path.startswith("scripts/windows/"):
        return "ADAPT", "Live launcher child script for old processes.", path, "Retain Windows supervision pattern; remove old hosts/labels in C2.", "tests/platform/test_windows_launcher.py", "manual batch command review"
    if path in {"MANIFEST.json", "tools/package_manifest.py"} or path.startswith("tools/manifest_authority/"):
        return "DELETE", "YTB package authority machinery is transitional evidence, not animation authority.", "removed", "Keep unchanged through C0 except bot hygiene; delete in C2.", "tests/platform/test_no_legacy_manifest_authority.py", "manual manifest workflow review"
    if path.startswith("docs/") or path in {"README.md", "00_START_HERE.md"}:
        return "ADAPT", "Product documentation is YTB-specific and must be replaced by animation authority.", "docs/", "Preserve useful operational facts; rewrite product claims in C2.", "tests/platform/test_document_authority.py", "manual document inventory review"
    return "ADAPT", "Build/package metadata supports the running source baseline.", path, "Retain or update for the single animation product in C2.", "tests/platform/test_build_metadata.py", "manual metadata review"

def main() -> int:
    paths = baseline_paths()
    reach = analyze_reachability(paths)
    print("# CLEAN-CUT FILE LEDGER\n")
    print("Baseline: `b35834808d99067e362a6e728ce7af8e04d2b6bd`; every path in that Git tree appears once. Reachability is recomputed from Python AST imports, React/TypeScript imports, launcher, package, Alembic and CI roots; the human-review column records the source-level review basis. C0 files are excluded.\n")
    print("## Machine-readable inventory\n\n```tsv")
    print("\t".join(LEDGER_COLUMNS))
    for path in paths:
        classification, reason, target, extraction, test, review = classify(path)
        r = reach[path]
        domain = "frontend" if path.startswith("src/") else "backend/platform" if path.startswith("app/") else path.split("/", 1)[0]
        row = (path, classification, reason, domain, target, extraction, test, "C2" if classification != "KEEP" else "C2+", r.active, r.root, r.chain, review)
        print("\t".join(value.replace("\t", " ").replace("\n", " ") for value in row))
    print("```\n\nValidated by `tools/check_c0_ledger.py`; reachability report is reproducible with `tools/verify_c0_reachability.py`.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
