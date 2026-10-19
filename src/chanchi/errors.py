"""Structured errors for agent callers: every failure names a code, a field and a fix."""

from __future__ import annotations

from collections.abc import Iterable

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_VALIDATION = 2

ERROR_CODES = frozenset(
    {
        "invalid_value",
        "unknown_model",
        "unknown_change",
        "unknown_session",
        "duplicate",
        "missing_prerequisite",
        "project_not_detected",
        "link_conflict",
        "schema_too_new",
        "database_busy",
        "internal",
    }
)


class ChanchiError(Exception):
    """A failure the caller can act on. Rendered as the JSON error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
        valid_values: Iterable | None = None,
        hint: str | None = None,
    ) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {code}")
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.valid_values = list(valid_values) if valid_values is not None else None
        self.hint = hint

    @property
    def exit_code(self) -> int:
        return EXIT_INTERNAL if self.code == "internal" else EXIT_VALIDATION

    def to_dict(self) -> dict:
        error: dict = {"code": self.code, "message": self.message}
        if self.field is not None:
            error["field"] = self.field
        if self.valid_values is not None:
            error["valid_values"] = self.valid_values
        if self.hint is not None:
            error["hint"] = self.hint
        return {"ok": False, "error": error}
