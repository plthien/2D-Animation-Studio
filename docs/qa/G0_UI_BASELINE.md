# G0 UI baseline — BLOCKED

Source commit: `b35834808d99067e362a6e728ce7af8e04d2b6bd`. Host: Windows, Python 3.12.10, Node 22.14.0, npm 11.21.0. Baseline was started unchanged using temporary paths: `%TEMP%/c0-ytb-runtime/baseline.sqlite` and `%TEMP%/c0-ytb-runtime/artifacts`, API `127.0.0.1:8010`, Vite `127.0.0.1:5180`. The API completed the legacy 001–031 migration chain against that disposable DB; Vite returned HTTP 200. No existing user DB or artifact was accessed.

Browser evidence is **not available**, so G0 is BLOCKED and C0 cannot be PASS. The connected browser provider had no available surfaces (`iab` creation rejected), the native browser-control pipe was unavailable, and local Chrome headless rendering failed before capture with repeated `GPU process exited unexpectedly` / `GPU process isn't usable` errors. Therefore no mock, generated, or substitute screenshots were committed. The required views remain uncaptured: Channels/DNA/editor/modal; Projects/modal; Studio/stepper; Settings; Jobs; Artifacts; selected sidebar state at 1440×900, 1920×1080, and a narrow viewport.

Observed baseline runtime facts: `/health` returned 404 (the baseline system route is under its API prefix); Vite served the frontend. The attempted actual Chrome command was `chrome.exe --headless=new --disable-gpu --use-angle=swiftshader --window-size=1440,900 --screenshot=... http://127.0.0.1:5180`; it failed before writing an image. No browser click/navigation evidence can honestly be claimed.

Resolution: run the same unchanged baseline on a host with functioning Chrome GPU/software compositor or a connected browser provider, use the above disposable paths, capture the required pages/modals and record hashes. Do not proceed to C2 based on this document.
