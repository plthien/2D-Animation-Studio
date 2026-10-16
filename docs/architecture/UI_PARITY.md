# UI parity freeze

The C2 application must remain recognizably the baseline cockpit, not a generic MUI dashboard. Preserve unchanged: `CockpitShell`, `GlobalSidebar`, `PageHeader`, `PipelineStepper`, all shared UI primitives, Channel and Project card grids, Create Channel/Project dialogs, Channel DNA editing interaction pattern, dark palette, typography/spacing tokens, workspace selection/navigation, badges/toasts/empty/loading feedback.

| Baseline component | Future responsibility | C2 treatment |
|---|---|---|
| CockpitShell / GlobalSidebar | selected channel/project and product navigation | preserve layout/selection; rename data only |
| PageHeader | titles, actions, context | preserve hierarchy and actions; animation DTOs |
| PipelineStepper | seven canonical stage projection | preserve visual component; labels become Authoring, Resolver, Generation, Rigging, Director, Motion, Delivery |
| Channel cards/editor/modal | Channel metadata and `channel_dna.v2` editor | preserve grid/modal/editor UX; replace V3 fields |
| Project cards/modal | channel-owned animation projects | preserve grid/modal; remove old story/voice pointers |
| Studio panels | one stage authority each | retain reusable authoring/prompt interaction only; remove Scene Breakdown, Scene Assets, Assembly, Render and Voice panels |
| Settings/Jobs/Artifacts pages | animation settings, operations and immutable metadata | preserve page styling/list patterns; new DTOs |

New later panels: Shot Plan, Asset Resolver, Generation Review, Rig Workshop, Animation Director, Motion Preview, Voice-last Delivery. They must use the same shell/section/card/status language.

The immutable G0 comparison set is `docs/qa/evidence/g0/manifest.json` plus its ten hash-verified PNG files. It includes a 768×900 narrow capture showing the baseline's sidebar-first reflow; this is an observed baseline behavior, not a C0 redesign.

Acceptance: baseline and C2 screenshots at 1440×900 and 1920×1080 retain sidebar width, header/stepper placement, card-grid hierarchy, modal visual language, tokens, and selected-workspace feedback. Allowed differences: product text, seven stage names/statuses, animation fields/panels, removal of retired controls. Mobile may reflow but retains navigation and feedback semantics.
