"""Check 5: import layers of src/chanchi (docs/designs/chanchi-agents-mvp.md, Layer 3)."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "chanchi"
LEAVES = {"errors", "timeutil", "dedup", "hfsignals"}
LEAF_MAY_IMPORT = {"errors"}


def chanchi_imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "chanchi":
                found.update(alias.name for alias in node.names)
            elif node.module.startswith("chanchi."):
                found.add(node.module.split(".")[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("chanchi."):
                    found.add(alias.name.split(".")[1])
    return found


MODULES = {p.stem: chanchi_imports(p) for p in sorted(SRC.glob("*.py"))}


def test_leaf_modules_import_only_errors():
    for leaf in LEAVES:
        extra = MODULES[leaf] - LEAF_MAY_IMPORT
        assert not extra, (
            f"{leaf}.py imports {sorted(extra)}; leaf modules may import only chanchi.errors. "
            "Move the shared code into a leaf or import it from the caller."
        )


def test_only_main_imports_cli():
    offenders = sorted(m for m, deps in MODULES.items() if "cli" in deps and m != "__main__")
    assert not offenders, f"{offenders} import chanchi.cli; only __main__ may. Move the code out of cli.py."


def test_only_cli_imports_render():
    offenders = sorted(m for m, deps in MODULES.items() if "render" in deps and m != "cli")
    assert not offenders, f"{offenders} import chanchi.render; only cli.py renders output."
