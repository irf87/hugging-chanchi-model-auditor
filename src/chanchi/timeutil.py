"""UTC timestamps stored as ISO-8601 text: YYYY-MM-DDTHH:MM:SSZ."""

from __future__ import annotations

from datetime import datetime, timezone

from chanchi.errors import ChanchiError

FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(FORMAT)


def parse(ts: str) -> datetime:
    return datetime.strptime(ts, FORMAT).replace(tzinfo=timezone.utc)


def since_to_iso(day: str) -> str:
    """Turn a --since YYYY-MM-DD value into the start-of-day timestamp."""
    try:
        parsed = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        raise ChanchiError(
            "invalid_value", f"{day!r} is not a date", field="since", hint="use YYYY-MM-DD"
        ) from None
    return parsed.strftime(FORMAT)
