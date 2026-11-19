import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "chanchi"
FORBIDDEN_NETWORK = {
    "urllib.request",
    "http.client",
    "socket",
    "ssl",
    "urllib3",
    "requests",
}


def _matches_forbidden(module_name: str, forbidden: set[str]) -> str | None:
    for target in forbidden:
        if module_name == target or module_name.startswith(target + "."):
            return target
    return None


def _imported_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                names.append(base)
            for alias in node.names:
                if base:
                    names.append(f"{base}.{alias.name}")
                else:
                    names.append(alias.name)
        elif isinstance(node, ast.Call):
            func = node.func
            is_import_module = (
                (isinstance(func, ast.Attribute) and func.attr == "import_module")
                or (isinstance(func, ast.Name) and func.id == "import_module")
            )
            if is_import_module and node.args and isinstance(node.args[0], ast.Constant):
                if isinstance(node.args[0].value, str):
                    names.append(node.args[0].value)
    return names


def test_package_imports_no_network_or_unexpected_subprocess():
    py_files = sorted(SRC_ROOT.rglob("*.py"))
    assert py_files
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for imported in _imported_names(tree):
            net = _matches_forbidden(imported, FORBIDDEN_NETWORK)
            assert net is None, f"{path.relative_to(SRC_ROOT)} imports forbidden network module {net!r}"
            if path.name != "projects.py":
                sub = _matches_forbidden(imported, {"subprocess"})
                assert sub is None, f"{path.relative_to(SRC_ROOT)} imports subprocess outside projects.py"
