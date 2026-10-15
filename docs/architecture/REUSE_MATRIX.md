# Reuse matrix

| Classification | Source | C2+ destination / rule |
|---|---|---|
| KEEP | `src/layout/CockpitShell.tsx`, `GlobalSidebar.tsx`, `PageHeader.tsx`, `PipelineStepper.tsx`; `src/components/ui/*`; `src/theme/theme.ts`; `src/index.css`; `tailwind.config.js` | Preserve DOM hierarchy, dark tokens, navigation and interaction patterns. Only labels/DTOs/stages change. |
| ADAPT | `src/App.tsx`, `src/app/workspace.ts`, channels/projects/settings/pages and reusable Studio panels | One animation DTO graph and seven stages; no old selection state or Scene/Beat semantics. |
| KEEP/ADAPT | `app/core/{ids,hashing,time,diagnostic_redaction,external_authoring}.py`, `app/api/errors.py`, `app/db/{base,session,sqlite_pragmas,types}.py`, `app/infrastructure/sqlite.py` | Keep only neutral behavior behind animation-owned interfaces. |
| ADAPT | `app/modules/media/{bounded_http_transport,glabs_webhook_client,image_upload_validation,media_secret_safety,media_provider_errors,transport_policy}.py`, durable-workflow coordinator | Explicit consent, new operation tables and attempt fencing; strip Beat/Anchor dependencies. |
| EXTRACT | V4 voice provider/pacing/alignment/audio modules and `kokoro/*` | `app/modules/animation/voice/`; providers, pacing and alignment only, never voice-first control plane. |
| EXTRACT | V4 process guard/job object/diagnostics/validation plus safe FFmpeg process portions | `app/core/process/` and `app/modules/animation/delivery/ffmpeg_runner.py`; no old render graph. |
| DELETE | V4 Scene/Beat/VisualPlan/Prompt/Assembly/static-image render, their models/routers/workers/tests/schemas/prompts; old migration chain and package authority manifest | Delete in C2 after named extractions and regression tests exist. |
| NEW | `app/modules/animation/*`, `runtime/spine/*`, `src/features/animation/*`, `contracts/animation/*` | Animation-owned single product only. |

Extracted neutral regression tests required before removal: duplicate-key external JSON parsing; streaming/hash/path safety; provider retry/lease/unknown-submit fencing; Kokoro pacing identity and alignment; subprocess cancellation/FFmpeg validation.
