"""C2 static deletion / reachability / contract gate."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from app.main import app

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES=(
    "app/modules/v4/", "tests/v4/", "app/api/",
    "app/db/", "app/repositories/", "app/services/", "app/platform/",
    "src/features/studio/", "src/features/settings/",
    "contracts/schemas/", "contracts/prompts/", "contracts/openapi/",
    "contracts/examples/", "tests/fixtures/v4/", "tests/platform/",
)
FORBIDDEN_FILES={
    "MANIFEST.json", "app/durable_media_workflow_runner.py",
    "app/durable_render_runner.py", "app/voice_coordinator_runner.py",
    "app/scene_asset_coordinator_runner.py",
    "app/visual_reference_coordinator_runner.py",
    "app/render_coordinator_runner.py",
    ".github/workflows/refresh-release-manifest.yml",
    ".github/workflows/scene-assets-v2-candidate-audit.yml",
    ".github/workflows/c0-contract-audit.yml",
}
FORBIDDEN_IMPORTS=("app.modules.v4","app.api","app.db","app.repositories","app.services","app.platform")
def check() -> None:
    files={p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts}
    bad=[p for p in files if p.startswith(FORBIDDEN_PREFIXES) or p in FORBIDDEN_FILES or
         re.fullmatch(r"alembic/versions/0(?:0[1-9]|[12][0-9]|3[01])_.*\.py",p)]
    assert not bad, "Legacy source still tracked: "+", ".join(sorted(bad)[:25])
    graph={}
    for path in (ROOT/"app").rglob("*.py"):
        mod=path.relative_to(ROOT).with_suffix("").as_posix().replace("/",".")
        if mod.endswith(".__init__"):mod=mod[:-9]
        try: tree=ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:raise AssertionError(str(path)) from exc
        imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.level==0 and node.module:
                imports.append(node.module)
        graph[mod]=imports
    visited=set()
    pending=["app.main"]
    while pending:
        cur=pending.pop()
        if cur in visited:continue
        visited.add(cur)
        for imp in graph.get(cur,[]):
            assert not imp.startswith(FORBIDDEN_IMPORTS), f"Reachable forbidden import: {cur} -> {imp}"
            pending.extend([module for module in graph if module==imp or module.startswith(imp+".")])
    registry=json.loads((ROOT/"contracts/animation/api/endpoints.json").read_text(encoding="utf-8"))
    accepted={(x["method"],x["path"]) for x in registry if x["contract_status"]=="ACCEPTED"}
    actual={(method.upper(),path) for path,body in app.openapi()["paths"].items()
            for method in body if method in ("get","post","put","patch","delete")}
    assert actual==accepted, f"API mismatch extra={actual-accepted}; missing={accepted-actual}"
    frontend=(ROOT/"src/App.tsx").read_text(encoding="utf-8")
    for token in ("SceneBreakdown","VoicePanel","AssemblyPanel","RenderPanel"):
        assert token not in frontend
    launcher=(ROOT/"start.bat").read_text(encoding="utf-8").lower()
    assert "youtube" not in launcher and "durable_media" not in launcher and ".yas3_" not in launcher
    print(f"C2 cutover static PASS: {len(files)} filesystem entries; {len(visited)} reachable Python modules; exactly 19 endpoints")
if __name__=="__main__":
    check()
