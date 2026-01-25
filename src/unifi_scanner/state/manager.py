"""State management with atomic writes for crash-safe persistence."""

import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class RunState:
    """Persistent state for tracking successful runs."""

    last_successful_run: datetime  # UTC timezone-aware
    last_report_count: int = 0
    schema_version: str = "1.0"


class StateManager:
    """Manages persistent state with atomic writes.

    Uses the same atomic write pattern as FileDelivery to ensure
    crash-safe state persistence.
    """

    STATE_FILENAME = ".last_run.json"

    def __init__(self, state_dir: str) -> None:
        """Initialize state manager.

        Args:
            state_dir: Directory path for state file storage
        """
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / self.STATE_FILENAME

    def read_last_run(self) -> Optional[datetime]:
        """Read the last successful run timestamp from state file.

        Returns:
            UTC datetime of last successful run, or None if:
            - File doesn't exist (first run)
            - File is corrupted/unparseable
            - Timestamp is invalid
        """
        if not self.state_file.exists():
            log.debug("state_file_not_found", path=str(self.state_file))
            return None

        try:
            content = self.state_file.read_text(encoding="utf-8")
            data = json.loads(content)

            # Validate required field exists
            if "last_successful_run" not in data:
                log.warning(
                    "state_file_missing_field",
                    path=str(self.state_file),
                    field="last_successful_run",
                )
                return None

            # Parse timestamp
            timestamp_str = data["last_successful_run"]
            timestamp = datetime.fromisoformat(timestamp_str)

            # Ensure timezone-aware UTC
            if timestamp.tzinfo is None:
                log.warning(
                    "state_timestamp_invalid",
                    path=str(self.state_file),
                    reason="timestamp is not timezone-aware",
                )
                return None

            # Convert to UTC for consistency
            utc_timestamp = timestamp.astimezone(timezone.utc)
            log.debug(
                "state_loaded",
                path=str(self.state_file),
                last_run=utc_timestamp.isoformat(),
            )
            return utc_timestamp

        except json.JSONDecodeError as e:
            log.warning(
                "state_file_corrupted",
                path=str(self.state_file),
                error=str(e),
            )
            return None
        except ValueError as e:
            log.warning(
                "state_timestamp_invalid",
                path=str(self.state_file),
                error=str(e),
            )
            return None

    def write_last_run(self, timestamp: datetime, report_count: int = 0) -> None:
        """Write the last successful run timestamp atomically.

        Uses temp file + rename pattern to prevent partial writes on crash.

        Args:
            timestamp: UTC datetime of successful run
            report_count: Number of findings in the report

        Raises:
            PermissionError: If writing to state directory is not allowed
        """
        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Build state object
        state = RunState(
            last_successful_run=timestamp,
            last_report_count=report_count,
        )

        # Serialize to JSON
        state_dict = asdict(state)
        # Convert datetime to ISO 8601 string
        state_dict["last_successful_run"] = timestamp.isoformat()
        content = json.dumps(state_dict, indent=2) + "\n"

        # Atomic write: temp file in same directory, then rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.state_dir,
            prefix=".tmp-state-",
            suffix=".json",
        )
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            # Atomic rename (same filesystem)
            shutil.move(temp_path, self.state_file)
            log.info(
                "state_saved",
                path=str(self.state_file),
                last_run=timestamp.isoformat(),
                report_count=report_count,
            )
        except PermissionError:
            # Clean up temp file on permission failure
            Path(temp_path).unlink(missing_ok=True)
            log.error(
                "state_write_permission_denied",
                path=str(self.state_dir),
            )
            raise
        except Exception:
            # Clean up temp file on any other failure
            Path(temp_path).unlink(missing_ok=True)
            raise
