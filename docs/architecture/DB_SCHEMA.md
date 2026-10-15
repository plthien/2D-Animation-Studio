# Database schema authority

The normative table/column/FK/constraint freeze is [contracts/animation/DB_SCHEMA.md](../../contracts/animation/DB_SCHEMA.md). It establishes exactly fourteen application tables, ChannelDNA revisions as channel-scoped immutable `artifacts` (not a duplicate revision table), the `0001_animation_initial` origin, and the legacy-database fail-closed rule. C0 does not create models or a migration.
