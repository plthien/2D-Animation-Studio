# C2 coding rules (animation authority)

- Only the animation platform owns routes, data and workflow projections.
- C2 OpenAPI must exactly match the 19 ACCEPTED contract rows; no future PROPOSED route placeholders.
- Keep all persisted state in the new 14-table SQLite schema. No localStorage workflow state (workspace IDs are navigation only).
- Validate channel/project ownership, revision, immutable artifact hashes and idempotency at a single write transaction boundary.
- Never perform large uploads or paid/network IO while holding SQLite locks.
- Reject reused idempotency keys with different canonical inputs.
- All user data is retained on unsupported legacy signature; fail closed.
- Keep only approved neutral extraction modules from the YTB donor, not old orchestrators.
- Windows-only testing with actual source and browser evidence; missing evidence is NOT_RUN/BLOCKED.
- Apply fixes on the same C2 PR; no C3–C12 functionality to make C2 green.
