"""Time helpers. All timestamps are timezone-aware UTC ISO-8601 strings."""

from __future__ import annotations

from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")
