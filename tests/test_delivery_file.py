"""Tests for file delivery."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from unifi_scanner.delivery.file import FileDelivery, FileDeliveryError
from unifi_scanner.models.enums import DeviceType
from unifi_scanner.models.report import Report


@pytest.fixture
def sample_report() -> Report:
    """Create sample report for testing."""
    return Report(
        id=uuid4(),
        generated_at=datetime(2026, 1, 24, 14, 30, tzinfo=timezone.utc),
        period_start=datetime(2026, 1, 23, 14, 30, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 24, 14, 30, tzinfo=timezone.utc),
        site_name="default",
        controller_type=DeviceType.UDM_PRO,
        findings=[],
        log_entry_count=100,
    )


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestFileDeliveryFilename:
    """Test filename generation."""

    def test_filename_format(self, sample_report: Report) -> None:
        """Filename follows datetime pattern."""
        delivery = FileDelivery(output_dir="/tmp", timezone="UTC")
        filename = delivery._generate_filename(sample_report, "html")
        assert filename == "unifi-report-2026-01-24-1430.html"

    def test_filename_timezone(self, sample_report: Report) -> None:
        """Filename uses configured timezone."""
        delivery = FileDelivery(output_dir="/tmp", timezone="America/New_York")
        # 14:30 UTC = 09:30 EST
        filename = delivery._generate_filename(sample_report, "html")
        assert filename == "unifi-report-2026-01-24-0930.html"

    def test_filename_text_extension(self, sample_report: Report) -> None:
        """Text files use .txt extension."""
        delivery = FileDelivery(output_dir="/tmp", timezone="UTC")
        filename = delivery._generate_filename(sample_report, "txt")
        assert filename == "unifi-report-2026-01-24-1430.txt"


class TestFileDeliverySave:
    """Test file saving functionality."""

    def test_save_html_only(
        self, sample_report: Report, temp_output_dir: Path
    ) -> None:
        """Save only HTML when format is html."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            file_format="html",
            retention_days=0,  # Disable cleanup for test
        )

        paths = delivery.save(
            report=sample_report,
            html_content="<p>HTML</p>",
            text_content="Text",
        )

        assert len(paths) == 1
        assert paths[0].suffix == ".html"
        assert paths[0].exists()
        assert paths[0].read_text() == "<p>HTML</p>"

    def test_save_text_only(
        self, sample_report: Report, temp_output_dir: Path
    ) -> None:
        """Save only text when format is text."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            file_format="text",
            retention_days=0,
        )

        paths = delivery.save(
            report=sample_report,
            html_content="<p>HTML</p>",
            text_content="Plain text content",
        )

        assert len(paths) == 1
        assert paths[0].suffix == ".txt"
        assert "Plain text content" in paths[0].read_text()

    def test_save_both_formats(
        self, sample_report: Report, temp_output_dir: Path
    ) -> None:
        """Save both formats when format is both."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            file_format="both",
            retention_days=0,
        )

        paths = delivery.save(
            report=sample_report,
            html_content="<p>HTML</p>",
            text_content="Text",
        )

        assert len(paths) == 2
        suffixes = {p.suffix for p in paths}
        assert suffixes == {".html", ".txt"}

    def test_creates_output_dir(self, sample_report: Report) -> None:
        """Creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "nested" / "reports"
            delivery = FileDelivery(
                output_dir=str(new_dir),
                retention_days=0,
            )

            paths = delivery.save(
                report=sample_report,
                html_content="<p>HTML</p>",
                text_content="Text",
            )

            assert new_dir.exists()
            assert len(paths) > 0

    def test_atomic_write(
        self, sample_report: Report, temp_output_dir: Path
    ) -> None:
        """Verify atomic write produces complete file."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            file_format="html",
            retention_days=0,
        )

        content = "<html><body>Test content</body></html>"
        paths = delivery.save(
            report=sample_report,
            html_content=content,
            text_content="Text",
        )

        # File should be complete (atomic write)
        assert paths[0].read_text() == content


class TestFileDeliveryCleanup:
    """Test retention cleanup."""

    def test_cleanup_old_files(self, temp_output_dir: Path) -> None:
        """Deletes files older than retention days."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            retention_days=7,
        )

        # Create old file (simulate 10 days old)
        old_file = temp_output_dir / "unifi-report-2026-01-14-0800.html"
        old_file.write_text("old")
        # Set mtime to 10 days ago
        old_mtime = datetime.now().timestamp() - (10 * 24 * 60 * 60)
        os.utime(old_file, (old_mtime, old_mtime))

        # Create recent file
        recent_file = temp_output_dir / "unifi-report-2026-01-23-0800.html"
        recent_file.write_text("recent")

        deleted = delivery.cleanup_old_reports()

        assert deleted == 1
        assert not old_file.exists()
        assert recent_file.exists()

    def test_cleanup_zero_retention_keeps_all(self, temp_output_dir: Path) -> None:
        """Retention of 0 keeps all files."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            retention_days=0,
        )

        old_file = temp_output_dir / "unifi-report-2020-01-01-0000.html"
        old_file.write_text("ancient")

        deleted = delivery.cleanup_old_reports()

        assert deleted == 0
        assert old_file.exists()

    def test_cleanup_both_html_and_txt(self, temp_output_dir: Path) -> None:
        """Cleanup removes both HTML and text files."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            retention_days=7,
        )

        # Create old files of both types
        old_html = temp_output_dir / "unifi-report-2026-01-14-0800.html"
        old_txt = temp_output_dir / "unifi-report-2026-01-14-0800.txt"
        old_html.write_text("old html")
        old_txt.write_text("old txt")

        # Set mtime to 10 days ago
        old_mtime = datetime.now().timestamp() - (10 * 24 * 60 * 60)
        os.utime(old_html, (old_mtime, old_mtime))
        os.utime(old_txt, (old_mtime, old_mtime))

        deleted = delivery.cleanup_old_reports()

        assert deleted == 2
        assert not old_html.exists()
        assert not old_txt.exists()


class TestFileDeliveryDeliver:
    """Test high-level deliver_report method."""

    def test_deliver_report_success(
        self, sample_report: Report, temp_output_dir: Path
    ) -> None:
        """deliver_report returns True on success."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            retention_days=0,
        )

        result = delivery.deliver_report(
            report=sample_report,
            html_content="<p>Report</p>",
            text_content="Report text",
        )

        assert result is True
        # Verify files were created
        files = list(temp_output_dir.glob("unifi-report-*.html"))
        assert len(files) >= 1

    def test_deliver_report_no_content(
        self, sample_report: Report, temp_output_dir: Path
    ) -> None:
        """deliver_report returns False when no content provided."""
        delivery = FileDelivery(
            output_dir=str(temp_output_dir),
            file_format="html",
            retention_days=0,
        )

        result = delivery.deliver_report(
            report=sample_report,
            html_content=None,  # No HTML when format requires it
            text_content="Text",
        )

        # Should return False since no HTML content for html format
        assert result is False
