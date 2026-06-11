from __future__ import annotations

from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Kolkata"
DISPLAY_TIMEZONE_ALIASES = {
    "Asia/Calcutta": DEFAULT_TIMEZONE,
    "Indian Standard Time (IST) UTC+5:30": DEFAULT_TIMEZONE,
    "IST": DEFAULT_TIMEZONE,
}


def normalize_timezone_name(value: str | None, fallback: str = DEFAULT_TIMEZONE) -> str:
    timezone_name = (value or fallback).strip() or fallback
    timezone_name = DISPLAY_TIMEZONE_ALIASES.get(timezone_name, timezone_name)
    try:
        ZoneInfo(timezone_name)
    except Exception:
        return fallback
    return timezone_name

