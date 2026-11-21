"""Check 4: the runtime stays standard library only."""

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "chanchi"


def test_no_runtime_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project.get("dependencies", []) == [], (
        "chanchi has no runtime dependencies. Put dev tools in [dependency-groups] dev, "
        "or write the feature with the standard library."
    )


def test_src_imports_only_stdlib_and_chanchi():
    allowed = set(sys.stdlib_module_names) | {"chanchi", "__future__"}
    bad = []
    for path in sorted(SRC.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            bad += [f"{path.name}: {n}" for n in names if n.split(".")[0] not in allowed]
    assert not bad, f"non-stdlib imports in src/chanchi: {bad}. chanchi's runtime is stdlib only."
