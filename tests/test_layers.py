"""Check 5: import layers of src/chanchi (docs/designs/chanchi-agents-mvp.md, Layer 3)."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "chanchi"
LEAVES = {"errors", "timeutil", "dedup", "hfsignals", "harnesses"}
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


def test_items_never_imports_inventory():
    assert "inventory" not in MODULES["items"], (
        "items.py imports inventory.py; the CLI passes scanned names into items.check and items.mirror."
    )


def test_inventory_imports_only_domain_modules_it_may():
    allowed = {"db", "items", "projects", "sync", "taxonomy", "errors", "timeutil"}
    extra = MODULES["inventory"] - allowed
    assert not extra, f"inventory.py imports {sorted(extra)}; it may import only {sorted(allowed)}."


def test_adoption_imports_only_domain_modules_it_may():
    assert "adoption" in MODULES, "adoption.py does not exist yet"
    allowed = {"db", "errors", "inventory", "items", "projects", "sync", "taxonomy", "timeutil"}
    extra = MODULES["adoption"] - allowed
    assert not extra, f"adoption.py imports {sorted(extra)}; it may import only {sorted(allowed)}."


def test_items_and_inventory_never_import_adoption():
    assert "adoption" not in MODULES["items"], "items.py must never import adoption.py"
    assert "adoption" not in MODULES["inventory"], "inventory.py must never import adoption.py"
