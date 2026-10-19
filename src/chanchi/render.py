"""Compact text rendering (--format text) for humans reading agent output."""

from __future__ import annotations


def render_text(payload: dict) -> str:
    lines: list[str] = []
    _render(payload, lines, 0)
    return "\n".join(lines) + "\n"


def _scalar(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        return ", ".join(_scalar(item) for item in value) or "-"
    return str(value)


def _is_flat(value) -> bool:
    if isinstance(value, dict):
        return False
    if isinstance(value, list):
        return all(not isinstance(item, (dict, list)) for item in value)
    return True


def _render(value, lines: list[str], indent: int) -> None:
    pad = "  " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "ok":
                continue
            if _is_flat(item):
                lines.append(f"{pad}{key}: {_scalar(item)}")
            else:
                lines.append(f"{pad}{key}:")
                _render(item, lines, indent + 1)
    elif isinstance(value, list):
        if not value:
            lines.append(f"{pad}(none)")
        elif all(isinstance(item, dict) and all(_is_flat(v) for v in item.values()) for item in value):
            _table(value, lines, pad)
        else:
            for number, item in enumerate(value, 1):
                lines.append(f"{pad}- [{number}]")
                _render(item, lines, indent + 1)
    else:
        lines.append(f"{pad}{_scalar(value)}")


def _table(rows: list[dict], lines: list[str], pad: str) -> None:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    cells = [[_scalar(row.get(column)) for column in columns] for row in rows]
    widths = [max(len(column), *(len(row[i]) for row in cells)) for i, column in enumerate(columns)]
    lines.append(pad + "  ".join(c.ljust(w) for c, w in zip(columns, widths)).rstrip())
    lines.append(pad + "  ".join("-" * w for w in widths))
    for row in cells:
        lines.append(pad + "  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip())
