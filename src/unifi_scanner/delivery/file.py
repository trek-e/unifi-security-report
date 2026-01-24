"""File-based report delivery with retention management."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Literal, Optional
import tempfile
import shutil

import structlog

from unifi_scanner.models.report import Report

log = structlog.get_logger()


class FileDeliveryError(Exception):
    """Raised when file delivery fails."""

    pass


class FileDelivery:
    """File output delivery with datetime naming and retention cleanup."""

    def __init__(
        self,
        output_dir: str,
        file_format: Literal["html", "text", "both"] = "both",
        retention_days: int = 30,
        timezone: str = "UTC",
    ) -> None:
        """Initialize file delivery.

        Args:
            output_dir: Directory path for report output
            file_format: Format(s) to save - html, text, or both
            retention_days: Days to retain files (0 = keep forever)
            timezone: Timezone for filename timestamps
        """
        self.output_dir = Path(output_dir)
        self.file_format = file_format
        self.retention_days = retention_days
        self.timezone = timezone

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, report: Report, extension: str) -> str:
        """Generate datetime-based filename.

        Format: unifi-report-2026-01-24-1430.html
        """
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(self.timezone)
        timestamp = report.generated_at.astimezone(tz)
        date_str = timestamp.strftime("%Y-%m-%d-%H%M")
        return f"unifi-report-{date_str}.{extension}"

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write file atomically (write to temp, then rename).

        Prevents partial writes and cleanup race conditions.
        """
        # Write to temp file in same directory (for same-filesystem rename)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.output_dir,
            prefix=".tmp-",
            suffix=path.suffix,
        )
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            # Atomic rename (same filesystem)
            shutil.move(temp_path, path)
        except Exception:
            # Clean up temp file on failure
            Path(temp_path).unlink(missing_ok=True)
            raise

    def cleanup_old_reports(self) -> int:
        """Delete report files older than retention_days.

        Returns count of files deleted.
        """
        if self.retention_days <= 0:
            return 0  # Keep forever

        if not self.output_dir.exists():
            return 0

        cutoff = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0

        # Clean up both HTML and text files
        for pattern in ["unifi-report-*.html", "unifi-report-*.txt"]:
            for file_path in self.output_dir.glob(pattern):
                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff:
                        file_path.unlink()
                        deleted_count += 1
                        log.debug(
                            "deleted_old_report",
                            path=str(file_path),
                            age_days=(datetime.now() - mtime).days,
                        )
                except (OSError, PermissionError) as e:
                    log.warning("cleanup_failed", path=str(file_path), error=str(e))

        if deleted_count > 0:
            log.info(
                "cleanup_complete",
                deleted=deleted_count,
                retention_days=self.retention_days,
            )

        return deleted_count

    def save(
        self,
        report: Report,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
    ) -> List[Path]:
        """Save report to file(s) based on configured format.

        Args:
            report: Report object for filename generation
            html_content: Rendered HTML report (required if format includes html)
            text_content: Rendered text report (required if format includes text)

        Returns:
            List of paths to saved files

        Raises:
            FileDeliveryError: If saving fails
        """
        self._ensure_output_dir()
        saved_paths: List[Path] = []

        try:
            if self.file_format in ("html", "both") and html_content:
                html_filename = self._generate_filename(report, "html")
                html_path = self.output_dir / html_filename
                self._atomic_write(html_path, html_content)
                saved_paths.append(html_path)
                log.info("report_saved", path=str(html_path), format="html")

            if self.file_format in ("text", "both") and text_content:
                text_filename = self._generate_filename(report, "txt")
                text_path = self.output_dir / text_filename
                self._atomic_write(text_path, text_content)
                saved_paths.append(text_path)
                log.info("report_saved", path=str(text_path), format="text")

            # Run cleanup after successful save
            self.cleanup_old_reports()

            return saved_paths

        except PermissionError as e:
            log.error("file_permission_error", path=str(self.output_dir), error=str(e))
            raise FileDeliveryError(
                f"Permission denied writing to {self.output_dir}: {e}"
            )
        except OSError as e:
            log.error("file_write_error", error=str(e))
            raise FileDeliveryError(f"Failed to write report file: {e}")

    def deliver_report(
        self,
        report: Report,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
    ) -> bool:
        """Deliver report via file output.

        Args:
            report: Report object for filename generation
            html_content: Rendered HTML report
            text_content: Rendered text report

        Returns:
            True if at least one file was saved, False otherwise
        """
        try:
            paths = self.save(report, html_content, text_content)
            return len(paths) > 0
        except FileDeliveryError:
            return False
