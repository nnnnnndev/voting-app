"""Date/time helpers for scheduled vote close times.

HTML datetime-local inputs return naive strings ("2026-05-21T18:00") in
the user's local zone. We treat them as the configured app timezone and
convert to Unix timestamps for storage. Display goes the other way.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from . import app_config


def _zone() -> ZoneInfo:
    return ZoneInfo(app_config.load().timezone)


def parse_datetime_local(s: str) -> float:
    """Parse <input type='datetime-local'> string into a Unix timestamp.
    Empty input returns 0.0, meaning 'no scheduled close'."""
    s = (s or "").strip()
    if not s:
        return 0.0
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_zone())
    return dt.timestamp()


def format_local(ts: float) -> str:
    """Format a Unix timestamp for display, e.g. 'May 21 2026 at 6:00 PM EDT'."""
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts, tz=_zone())
    # Format parts separately to avoid %-d (POSIX) vs %#d (Windows) issues.
    date = dt.strftime("%b ") + str(dt.day) + dt.strftime(" %Y")
    hour = dt.hour % 12 or 12
    minute = dt.strftime("%M")
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{date} at {hour}:{minute} {ampm} {dt.tzname()}"


def to_datetime_local_value(ts: float) -> str:
    """Render a timestamp in the format <input type='datetime-local'> wants:
    'YYYY-MM-DDTHH:MM' in the configured local zone."""
    if not ts:
        return ""
    dt = datetime.fromtimestamp(ts, tz=_zone())
    return dt.strftime("%Y-%m-%dT%H:%M")
