"""Timestamp normalization utilities for UniFi log data."""

from datetime import datetime, timezone
from typing import Any, Union

from dateutil import parser as dateutil_parser


def normalize_timestamp(
    value: Any,
    assume_utc: bool = True,
) -> datetime:
    """Convert various timestamp formats to UTC datetime.

    Handles:
    - int/float: Unix timestamp (auto-detects milliseconds vs seconds)
    - str: ISO format or other parseable formats via dateutil
    - datetime: Returns as-is if aware, converts if naive

    Args:
        value: Timestamp as int (ms or s), float, str, or datetime
        assume_utc: If True, treat naive timestamps as UTC (default True)

    Returns:
        Timezone-aware datetime in UTC

    Raises:
        ValueError: If value cannot be parsed as a timestamp

    Example:
        >>> normalize_timestamp(1705084800000)  # milliseconds
        datetime.datetime(2024, 1, 12, 20, 0, tzinfo=datetime.timezone.utc)
        >>> normalize_timestamp("2024-01-12T20:00:00Z")
        datetime.datetime(2024, 1, 12, 20, 0, tzinfo=datetime.timezone.utc)
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        # UniFi uses milliseconds - detect by magnitude
        # Timestamps > 1e12 are definitely milliseconds (after year 2001)
        if value > 1e12:
            value = value / 1000
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
        return dt  # Already UTC, no further conversion needed
    elif isinstance(value, str):
        dt = dateutil_parser.parse(value)
    else:
        raise ValueError(f"Cannot parse timestamp: {value!r} (type: {type(value).__name__})")

    # Handle naive datetimes
    if dt.tzinfo is None:
        if assume_utc:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Treat as local time, then convert to UTC
            dt = dt.astimezone(timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt
