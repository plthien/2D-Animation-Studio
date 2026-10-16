# C1 rig acquisition and rights (noncommercial evaluation only)

**Official candidate:** EsotericSoftware/spine-runtimes `4.2`, pinned commit `e7dc1435fa4a0083ab431f1b28e083c14a1f5c68`, `examples/spineboy/export/spineboy-pro.json` (Spine 4.2.22), `spineboy.atlas`, `spineboy.png`, and `examples/spineboy/license.txt`.

Authoritative [runtime repository](https://github.com/EsotericSoftware/spine-runtimes#licensing) explicitly welcomes free evaluation of its runtime and examples. [Exact Spineboy image notice](https://github.com/EsotericSoftware/spine-runtimes/blob/e7dc1435fa4a0083ab431f1b28e083c14a1f5c68/examples/spineboy/license.txt) allows distribution of example images **with the notice** and **forbids all commercial use**. This is evidence for a limited **noncommercial technical evaluation**, not commercial product integration or asset redistribution rights. See [governing runtime license](https://esotericsoftware.com/spine-runtimes-license) and [Editor license](https://esotericsoftware.com/spine-editor-license), including the Spine Trial restriction.

## Reproducible evaluation (Windows PowerShell)

```powershell
cd experiments/spine-feasibility
npm.cmd ci
$env:C1_OFFICIAL_SAMPLE_EVAL='1'
$env:C1_USAGE_SCOPE='private_local_evaluation'
$env:VITE_C1_SCOPE='private_local_evaluation'
npm.cmd run c1:acquire-example
npm.cmd run c1:preflight
npm.cmd run c1:test
npm.cmd run c1:render
npm.cmd run c1:verify
```

The downloader pins the official source Git revision, reads and verifies its `license.txt`, validates Spine export version, computes full SHA-256 for skeleton, atlas, PNG and notice, and writes **only gitignored** `public/assets/` files. It does not set a false product/editor-license confirmation. Outputs remain noncommercial evaluation artifacts and include the image license attribution. Hosted CI chooses `hosted_ci_evaluation` explicitly and checks the accompanying license notice. Never use the official example in a commercial video/product.

For a user-owned commercial rig, provide a verified editor/runtime license route, explicitly licensed rig/atlas/texture, bone names, actual hashes, authorized hosted CI and separately confirmed redistribution rights when needed. Do not share private license activation keys, credentials or unsupported commercial-use flags. Use `provenance.example.json` as an illustrative schema, not as a claim of authorization.

**Minimum rig:** Spine 4.2 JSON or .skel plus compatible atlas and every referenced texture page; actual articulated root/torso/head, both arms, identifiable gripping hand, both thighs/shins/feet, supported skin and no missing regions. Calibrate scale, 2D ground, hand contact and grip offset. Verify genuine rendered poses in official Spine 4.2/Pixi 8 before any G1 PASS. If assets are unavailable, report `BLOCKED`, not a fake screenshot. `public/assets/*` and render outputs are intentionally outside Git history.
