# C0 review

Base: `b35834808d99067e362a6e728ce7af8e04d2b6bd`; branch: `feat/c0-clean-cutover-contracts`.

| Requirement | Evidence | Status |
|---|---|---|
| Exact baseline/source audit | `BASELINE.md`, 813-row ledger, source route/lifespan inspection | PASS |
| Every baseline path classified once | `tools/check_c0_ledger.py`: `tracked=813 rows=813 ADAPT=153 DELETE=621 EXTRACT=22 KEEP=17` | PASS |
| 14-table clean schema / legacy refusal | `contracts/animation/DB_SCHEMA.md` | PASS (design freeze) |
| animation contracts, examples, semantic checks | `tools/validate_c0_contracts.py`: 18 schemas, 18 valid, 4 invalid catalog cases, 3 semantic invariants | PASS |
| API/CAS/state and C2 deletion design | `API_CONTRACTS.md`, `CUTOVER_BOUNDARIES.md` | PASS (design freeze) |
| Cockpit UX reuse boundary | `UI_PARITY.md` | PASS (design freeze) |
| Spine/security research boundary | `SECURITY_LICENSE.md` | PASS (license remains a G1 gate) |
| Real G0 screenshots and click evidence | `G0_UI_BASELINE.md` | BLOCKED |

Commands executed: `npm.cmd ci --no-audit --no-fund` (0); isolated Python `pip install -r requirements.txt` (0); disposable `uvicorn app.main:app --host 127.0.0.1 --port 8010` (started; old migrations completed); Vite on 5180 (200); `tools/check_c0_ledger.py` (0); `tools/validate_c0_contracts.py` (0); `npm.cmd test` (0, 160 pass; expected legacy YTB assertions); `npm.cmd run build` (0; >500kB chunk warning); `git diff --check` (0). Full Python pytest was started under `%TEMP%/c0-pytest`; it did not produce a final exit result during this run and is NOT_RUN for signoff.

Self-review repair: the first contract run caught an invalid `shot_plan.v1` JSON closing delimiter; it was fixed and validator rerun passed. A final check caught the ledger incorrectly reading post-C0 tracked files; it now reads the pinned baseline tree, explicitly excluding C0 deliverables. The checker detects missing, duplicate, unclassified and unexpected baseline paths. C0 changed only documentation, contract fixtures and standalone C0 validators; no production source/routes/models/migrations were changed.

Overall: **BLOCKED**, solely because G0 evidence is mandatory and unavailable. Do not label this as an implementation-ready/pass C0 or begin C1/C2. No unresolved normative contract conflict was found; browser evidence remains the blocking external condition.
