"""Tests for state manager."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from unifi_scanner.state import RunState, StateManager


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestStateManagerRead:
    """Tests for StateManager.read_last_run()."""

    def test_read_missing_file_returns_none(self, temp_state_dir: Path) -> None:
        """New state dir with no file returns None."""
        manager = StateManager(str(temp_state_dir))

        result = manager.read_last_run()

        assert result is None

    def test_read_valid_state_returns_datetime(self, temp_state_dir: Path) -> None:
        """Write valid JSON, read returns correct UTC datetime."""
        manager = StateManager(str(temp_state_dir))
        expected_time = datetime(2026, 1, 24, 14, 30, 0, tzinfo=timezone.utc)

        # Write valid state file directly
        state_file = temp_state_dir / ".last_run.json"
        state_data = {
            "last_successful_run": "2026-01-24T14:30:00+00:00",
            "last_report_count": 5,
            "schema_version": "1.0",
        }
        state_file.write_text(json.dumps(state_data))

        result = manager.read_last_run()

        assert result is not None
        assert result == expected_time
        assert result.tzinfo == timezone.utc

    def test_read_corrupted_json_returns_none(
        self, temp_state_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Write invalid JSON, read returns None and logs warning."""
        manager = StateManager(str(temp_state_dir))

        # Write corrupted JSON
        state_file = temp_state_dir / ".last_run.json"
        state_file.write_text("{invalid json content")

        result = manager.read_last_run()

        assert result is None
        # Verify warning was logged (structlog outputs to stdout)
        captured = capsys.readouterr()
        assert "state_file_corrupted" in captured.out

    def test_read_invalid_timestamp_returns_none(
        self, temp_state_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Write JSON with bad timestamp format, returns None."""
        manager = StateManager(str(temp_state_dir))

        state_file = temp_state_dir / ".last_run.json"
        state_data = {
            "last_successful_run": "not-a-valid-timestamp",
            "last_report_count": 0,
            "schema_version": "1.0",
        }
        state_file.write_text(json.dumps(state_data))

        result = manager.read_last_run()

        assert result is None
        # Verify warning was logged (structlog outputs to stdout)
        captured = capsys.readouterr()
        assert "state_timestamp_invalid" in captured.out

    def test_read_missing_required_field_returns_none(
        self, temp_state_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Write JSON missing last_successful_run, returns None."""
        manager = StateManager(str(temp_state_dir))

        state_file = temp_state_dir / ".last_run.json"
        state_data = {
            "last_report_count": 5,
            "schema_version": "1.0",
        }
        state_file.write_text(json.dumps(state_data))

        result = manager.read_last_run()

        assert result is None
        # Verify warning was logged (structlog outputs to stdout)
        captured = capsys.readouterr()
        assert "state_file_missing_field" in captured.out

    def test_read_naive_timestamp_returns_none(
        self, temp_state_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Write JSON with timezone-naive timestamp, returns None."""
        manager = StateManager(str(temp_state_dir))

        state_file = temp_state_dir / ".last_run.json"
        state_data = {
            "last_successful_run": "2026-01-24T14:30:00",  # No timezone
            "last_report_count": 0,
            "schema_version": "1.0",
        }
        state_file.write_text(json.dumps(state_data))

        result = manager.read_last_run()

        assert result is None
        # Verify warning was logged (structlog outputs to stdout)
        captured = capsys.readouterr()
        assert "state_timestamp_invalid" in captured.out


class TestStateManagerWrite:
    """Tests for StateManager.write_last_run()."""

    def test_write_creates_directory(self, temp_state_dir: Path) -> None:
        """Write to non-existent directory, directory created."""
        nested_dir = temp_state_dir / "nested" / "state"
        manager = StateManager(str(nested_dir))
        timestamp = datetime.now(timezone.utc)

        manager.write_last_run(timestamp, report_count=3)

        assert nested_dir.exists()
        assert (nested_dir / ".last_run.json").exists()

    def test_write_creates_valid_json(self, temp_state_dir: Path) -> None:
        """Write state, read back JSON matches expected format."""
        manager = StateManager(str(temp_state_dir))
        timestamp = datetime(2026, 1, 24, 14, 30, 0, tzinfo=timezone.utc)

        manager.write_last_run(timestamp, report_count=7)

        state_file = temp_state_dir / ".last_run.json"
        data = json.loads(state_file.read_text())

        assert "last_successful_run" in data
        assert "last_report_count" in data
        assert "schema_version" in data
        assert data["last_report_count"] == 7
        assert data["schema_version"] == "1.0"

    def test_write_is_atomic(self, temp_state_dir: Path) -> None:
        """Verify temp file is cleaned up on failure."""
        manager = StateManager(str(temp_state_dir))
        timestamp = datetime.now(timezone.utc)

        # First write succeeds
        manager.write_last_run(timestamp, report_count=1)
        original_content = (temp_state_dir / ".last_run.json").read_text()

        # Mock shutil.move to fail
        with patch("unifi_scanner.state.manager.shutil.move") as mock_move:
            mock_move.side_effect = OSError("Simulated failure")

            with pytest.raises(OSError, match="Simulated failure"):
                manager.write_last_run(timestamp, report_count=999)

        # Original state file should be unchanged
        assert (temp_state_dir / ".last_run.json").read_text() == original_content

        # No temp files should remain
        temp_files = list(temp_state_dir.glob(".tmp-*"))
        assert len(temp_files) == 0

    def test_write_overwrites_existing(self, temp_state_dir: Path) -> None:
        """Write twice, second value persists."""
        manager = StateManager(str(temp_state_dir))
        timestamp1 = datetime(2026, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        timestamp2 = datetime(2026, 1, 24, 14, 30, 0, tzinfo=timezone.utc)

        manager.write_last_run(timestamp1, report_count=1)
        manager.write_last_run(timestamp2, report_count=5)

        result = manager.read_last_run()
        assert result == timestamp2


class TestStateManagerRoundtrip:
    """Tests for write/read roundtrip consistency."""

    def test_roundtrip_preserves_timezone(self, temp_state_dir: Path) -> None:
        """Write UTC datetime, read back is UTC."""
        manager = StateManager(str(temp_state_dir))
        original = datetime(2026, 1, 24, 14, 30, 0, tzinfo=timezone.utc)

        manager.write_last_run(original, report_count=3)
        result = manager.read_last_run()

        assert result is not None
        assert result == original
        assert result.tzinfo == timezone.utc

    def test_roundtrip_microseconds(self, temp_state_dir: Path) -> None:
        """Microseconds are preserved in roundtrip."""
        manager = StateManager(str(temp_state_dir))
        original = datetime(2026, 1, 24, 14, 30, 0, 123456, tzinfo=timezone.utc)

        manager.write_last_run(original, report_count=0)
        result = manager.read_last_run()

        assert result is not None
        assert result.microsecond == 123456


class TestRunStateDataclass:
    """Tests for RunState dataclass."""

    def test_runstate_defaults(self) -> None:
        """RunState has correct default values."""
        timestamp = datetime.now(timezone.utc)
        state = RunState(last_successful_run=timestamp)

        assert state.last_successful_run == timestamp
        assert state.last_report_count == 0
        assert state.schema_version == "1.0"

    def test_runstate_custom_values(self) -> None:
        """RunState accepts custom values."""
        timestamp = datetime.now(timezone.utc)
        state = RunState(
            last_successful_run=timestamp,
            last_report_count=42,
            schema_version="2.0",
        )

        assert state.last_report_count == 42
        assert state.schema_version == "2.0"
