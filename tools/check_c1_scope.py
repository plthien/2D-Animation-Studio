"""Phase C1 PR source-only scope guard. Never authorizes production changes."""
from __future__ import annotations
import subprocess
import sys

EXACT = {
    ".github/workflows/c0-contract-audit.yml",
    ".github/workflows/c1-spine-feasibility.yml",
    ".github/workflows/c1-lock-bootstrap.yml",
    ".github/workflows/refresh-release-manifest.yml",
    ".github/workflows/scene-assets-v2-candidate-audit.yml",
    "tests/v4/test_kokoro_setup_static.py",
    "tools/check_c1_scope.py",
    "docs/qa/C1_SPINE_FEASIBILITY.md",
    "contracts/animation/examples/valid/catalog.json",
}
PREFIXES = ("experiments/spine-feasibility/",)
FORBIDDEN = ("app/", "src/", "alembic/versions/")
def main():
    base = "origin/main"
    p = subprocess.run(["git","diff","--name-only",base+"...HEAD"],
        check=True,text=True,capture_output=True)
    paths = [s.strip().replace("\\","/") for s in p.stdout.splitlines() if s.strip()]
    violations = [s for s in paths if s.startswith(FORBIDDEN) or (s not in EXACT and not s.startswith(PREFIXES))]
    if violations:
        print("FAIL C1_SCOPE_UNAUTHORIZED:", violations)
        return 1
    print("PASS C1_SCOPE",len(paths),"changed paths, production=0")
    return 0
if __name__=="__main__":
    sys.exit(main())
