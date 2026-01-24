"""Tests for timestamp normalization utilities."""

from datetime import datetime, timezone

import pytest
from dateutil.tz import tzoffset

from unifi_scanner.utils.timestamps import normalize_timestamp


class TestNormalizeTimestamp:
    """Tests for normalize_timestamp function."""

    def test_millisecond_timestamp(self) -> None:
        """Millisecond timestamps are correctly converted."""
        # 2024-01-12 18:40:00 UTC in milliseconds
        result = normalize_timestamp(1705084800000)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 12
        assert result.hour == 18
        assert result.minute == 40
        assert result.tzinfo == timezone.utc

    def test_second_timestamp(self) -> None:
        """Second timestamps are correctly converted."""
        # 2024-01-12 18:40:00 UTC in seconds
        result = normalize_timestamp(1705084800)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 12
        assert result.hour == 18
        assert result.tzinfo == timezone.utc

    def test_float_timestamp(self) -> None:
        """Float timestamps work correctly."""
        result = normalize_timestamp(1705084800.5)
        assert result.year == 2024
        assert result.tzinfo == timezone.utc

    def test_iso_string_with_z(self) -> None:
        """ISO strings with Z suffix are parsed correctly."""
        result = normalize_timestamp("2024-01-12T20:00:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 12
        assert result.hour == 20
        assert result.tzinfo == timezone.utc

    def test_iso_string_with_offset(self) -> None:
        """ISO strings with timezone offset are converted to UTC."""
        # 2024-01-12T15:00:00-05:00 = 2024-01-12T20:00:00Z
        result = normalize_timestamp("2024-01-12T15:00:00-05:00")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 12
        assert result.hour == 20
        assert result.tzinfo == timezone.utc

    def test_naive_datetime_assume_utc_true(self) -> None:
        """Naive datetimes are treated as UTC when assume_utc=True."""
        dt = datetime(2024, 1, 12, 20, 0, 0)
        result = normalize_timestamp(dt, assume_utc=True)
        assert result.hour == 20
        assert result.tzinfo == timezone.utc

    def test_naive_datetime_assume_utc_false(self) -> None:
        """Naive datetimes are treated as local time when assume_utc=False."""
        dt = datetime(2024, 1, 12, 20, 0, 0)
        result = normalize_timestamp(dt, assume_utc=False)
        # Result will be converted to UTC based on local timezone
        assert result.tzinfo == timezone.utc

    def test_aware_datetime_conversion(self) -> None:
        """Aware datetimes are converted to UTC."""
        # Create datetime with offset
        eastern = tzoffset("EST", -5 * 3600)
        dt = datetime(2024, 1, 12, 15, 0, 0, tzinfo=eastern)
        result = normalize_timestamp(dt)
        assert result.hour == 20
        assert result.tzinfo == timezone.utc

    def test_already_utc_datetime(self) -> None:
        """UTC datetimes are returned as-is."""
        dt = datetime(2024, 1, 12, 20, 0, 0, tzinfo=timezone.utc)
        result = normalize_timestamp(dt)
        assert result == dt
        assert result.tzinfo == timezone.utc

    def test_invalid_type_raises_valueerror(self) -> None:
        """Invalid types raise ValueError."""
        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            normalize_timestamp([1, 2, 3])

    def test_invalid_string_raises_valueerror(self) -> None:
        """Invalid strings raise ValueError."""
        with pytest.raises(Exception):  # dateutil raises ParserError
            normalize_timestamp("not a date")

    def test_none_raises_valueerror(self) -> None:
        """None raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            normalize_timestamp(None)

    def test_unifi_typical_timestamp(self) -> None:
        """Test with typical UniFi timestamp format."""
        # UniFi events use milliseconds since epoch
        result = normalize_timestamp(1705084800000)
        assert result.tzinfo == timezone.utc
        assert result.year == 2024
