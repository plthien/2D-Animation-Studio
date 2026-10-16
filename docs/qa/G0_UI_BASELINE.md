# G0 UI baseline — PASS

Source commit: `b35834808d99067e362a6e728ce7af8e04d2b6bd`. The backend was started from a detached worktree at that exact commit on Windows 11 against `%TEMP%/c0-g0-runtime-remediation/baseline.sqlite` and a disposable artifact directory. Its legacy 001–031 migrations ran only against that database. The frontend files used by Vite were proven byte-identical with:

```powershell
git diff --exit-code b35834808d99067e362a6e728ce7af8e04d2b6bd -- src package.json package-lock.json vite.config.ts index.html
```

The command exited 0. Vite served those unchanged files at `127.0.0.1:5190` with its API base pointed to the disposable baseline API at `127.0.0.1:8020`. No user database, artifact directory, credential, or production record was accessed.

`tools/capture_g0_baseline.py` created one named synthetic channel, valid Channel DNA and one project through the real baseline API, launched installed Google Chrome through Playwright, navigated real routes, opened both real create dialogs, and wrote lossless viewport PNGs. The capture covers Channels grid/DNA editor/dialog, Projects grid/dialog, Studio and pipeline stepper, Settings, Jobs, Artifacts, selected sidebar/workspace, 1440×900, 1920×1080 and 768×900.

Evidence is indexed by [the cryptographic manifest](evidence/g0/manifest.json). It records the baseline SHA, exact routes, viewport, Chrome version, Windows version, synthetic fixture IDs, UTC timestamp, browser action, byte count and SHA-256 for all ten images. `python tools/check_g0_evidence.py` returns:

```text
PASS screenshots=10 routes=6 viewports=3 actions=3 hashes=verified
```

The negative regression test removes one referenced image from an isolated copy and proves the gate fails. The capture script rejects any baseline SHA other than the full audited SHA. Reviewers can reproduce the capture with a disposable baseline service; the committed PNGs are the review authority for later C2 parity comparison.
