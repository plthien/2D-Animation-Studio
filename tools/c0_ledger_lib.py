"""Shared, production-independent C0 ledger parsing and reachability analysis."""
from __future__ import annotations

import ast
import re
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA = "b35834808d99067e362a6e728ce7af8e04d2b6bd"
ALLOWED = {"KEEP", "ADAPT", "EXTRACT", "DELETE"}
LEDGER_COLUMNS = (
    "path", "classification", "reason", "current_domain_dependencies",
    "target_owner_path", "extraction_responsibility", "replacement_or_retained_test",
    "transition_phase", "active_runtime_dependency", "entrypoint_root",
    "reachability_evidence", "human_review",
)

PY_ROOTS = {
    "app/main.py",
    "app/durable_media_workflow_runner.py",
    "app/durable_render_runner.py",
    "app/render_coordinator_runner.py",
    "app/scene_asset_coordinator_runner.py",
    "app/visual_reference_coordinator_runner.py",
    "app/voice_coordinator_runner.py",
}
TS_ROOTS = {"src/main.tsx"}
OPERATIONAL_ROOTS = {
    "start.bat", "package.json", "requirements.txt", "alembic.ini",
    "alembic/env.py", ".github/workflows/refresh-release-manifest.yml",
    ".github/workflows/scene-assets-v2-candidate-audit.yml",
}
PROTECTED_UI = {
    "src/layout/CockpitShell.tsx", "src/layout/GlobalSidebar.tsx",
    "src/layout/PageHeader.tsx", "src/layout/PipelineStepper.tsx",
    "src/theme/theme.ts", "src/index.css", "src/App.tsx", "src/app/workspace.ts",
}

@dataclass(frozen=True)
class Reachability:
    active: str
    root: str
    chain: str


def baseline_paths() -> list[str]:
    return subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASELINE_SHA], cwd=ROOT, text=True,
        encoding="utf-8",
    ).splitlines()


def _python_module(path: str) -> str:
    value = path[:-3].replace("/", ".")
    return value[:-9] if value.endswith(".__init__") else value


def _resolve_python_import(module: str, level: int, current: str, modules: dict[str, str]) -> str | None:
    if level:
        parts = current.split(".")[:-1]
        parts = parts[: max(0, len(parts) - level + 1)]
        module = ".".join(parts + ([module] if module else []))
    while module:
        if module in modules:
            return modules[module]
        module = module.rpartition(".")[0]
    return None


def _python_graph(paths: list[str]) -> dict[str, set[str]]:
    py_paths = [p for p in paths if p.endswith(".py")]
    modules = {_python_module(p): p for p in py_paths}
    graph = {p: set() for p in py_paths}
    for path in py_paths:
        try:
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
        except (OSError, SyntaxError, UnicodeError):
            continue
        current = _python_module(path)
        for node in ast.walk(tree):
            candidates: list[tuple[str, int]] = []
            if isinstance(node, ast.Import):
                candidates.extend((alias.name, 0) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                candidates.append((base, node.level))
                candidates.extend(((base + "." + alias.name).strip("."), node.level) for alias in node.names)
            for name, level in candidates:
                resolved = _resolve_python_import(name, level, current, modules)
                if resolved and resolved != path:
                    graph[path].add(resolved)
    return graph


TS_IMPORT = re.compile(r"(?:import|export)\s+(?:[^;]*?\s+from\s+)?[\"']([^\"']+)[\"']|import\(\s*[\"']([^\"']+)[\"']\s*\)")


def _resolve_ts(path: str, spec: str, candidates: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = PurePosixPath(path).parent.joinpath(spec)
    normalized: list[str] = []
    for part in base.parts:
        if part == "..":
            if normalized:
                normalized.pop()
        elif part != ".":
            normalized.append(part)
    stem = "/".join(normalized)
    for candidate in (stem, *(stem + ext for ext in (".ts", ".tsx", ".js", ".jsx")),
                      *(stem + "/index" + ext for ext in (".ts", ".tsx", ".js", ".jsx"))):
        if candidate in candidates:
            return candidate
    return None


def _ts_graph(paths: list[str]) -> dict[str, set[str]]:
    candidates = {p for p in paths if p.startswith("src/") and Path(p).suffix in {".ts", ".tsx", ".js", ".jsx", ".css"}}
    graph = {p: set() for p in candidates}
    for path in candidates:
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for match in TS_IMPORT.finditer(text):
            resolved = _resolve_ts(path, match.group(1) or match.group(2), candidates)
            if resolved:
                graph[path].add(resolved)
        for css_match in re.finditer(r"[\"'](\.?\.?/[^\"']+\.css)[\"']", text):
            resolved = _resolve_ts(path, css_match.group(1), candidates)
            if resolved:
                graph[path].add(resolved)
    return graph


def _walk(graph: dict[str, set[str]], roots: set[str]) -> dict[str, tuple[str, list[str]]]:
    found: dict[str, tuple[str, list[str]]] = {}
    queue: deque[tuple[str, str, list[str]]] = deque()
    for root in sorted(roots & graph.keys()):
        queue.append((root, root, [root]))
    while queue:
        node, root, chain = queue.popleft()
        if node in found:
            continue
        found[node] = (root, chain)
        for nxt in sorted(graph.get(node, ())):
            queue.append((nxt, root, chain + [nxt]))
    return found


def analyze_reachability(paths: list[str] | None = None) -> dict[str, Reachability]:
    paths = paths or baseline_paths()
    result = {p: Reachability("no", "-", "not reachable from audited runtime roots") for p in paths}
    for graph, roots, label in ((_python_graph(paths), PY_ROOTS, "python AST import"), (_ts_graph(paths), TS_ROOTS, "TS/React import")):
        for path, (root, chain) in _walk(graph, roots).items():
            result[path] = Reachability("yes", root, f"{label}: {' -> '.join(chain)}")
    for path in OPERATIONAL_ROOTS | PY_ROOTS | TS_ROOTS:
        if path in result and result[path].active != "yes":
            result[path] = Reachability("yes", path, "declared launcher/package/CI entrypoint")
    for path in paths:
        if path.startswith("scripts/windows/"):
            result[path] = Reachability("yes", "start.bat", f"launcher command: start.bat -> {path}")
        elif path.startswith("alembic/versions/"):
            result[path] = Reachability("yes", "alembic/env.py", f"Alembic revision graph: alembic/env.py -> {path}")
    return result


def parse_ledger(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    start = lines.index("```tsv") + 1
    end = lines.index("```", start)
    header = tuple(lines[start].split("\t"))
    if header != LEDGER_COLUMNS:
        raise ValueError(f"ledger columns differ: {header}")
    rows: list[dict[str, str]] = []
    for line in lines[start + 1:end]:
        if line:
            values = line.split("\t")
            if len(values) != len(header):
                raise ValueError(f"wrong field count for {values[0] if values else '<empty>'}")
            rows.append(dict(zip(header, values, strict=True)))
    return rows
