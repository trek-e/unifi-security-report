"""Tests for email delivery."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from unifi_scanner.delivery.email import EmailDelivery, EmailDeliveryError
from unifi_scanner.models.enums import Category, DeviceType, Severity
from unifi_scanner.models.finding import Finding
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
def severe_report(sample_report: Report) -> Report:
    """Create report with severe findings."""
    sample_report.findings = [
        Finding(
            event_type="EVT_IPS_Alert",
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="Test Severe",
            description="Test",
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            occurrence_count=1,
        ),
        Finding(
            event_type="EVT_IPS_Alert_2",
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="Test Severe 2",
            description="Test",
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            occurrence_count=1,
        ),
    ]
    return sample_report


class TestEmailDeliverySubject:
    """Test email subject line generation."""

    def test_subject_no_severe(self, sample_report: Report) -> None:
        """Subject without severity prefix when no severe findings."""
        delivery = EmailDelivery(smtp_host="test", timezone="UTC")
        subject = delivery.build_subject(sample_report)
        assert subject == "UniFi Report - Jan 24, 2026"
        assert "[" not in subject

    def test_subject_with_severe(self, severe_report: Report) -> None:
        """Subject with severity prefix when severe findings exist."""
        delivery = EmailDelivery(smtp_host="test", timezone="UTC")
        subject = delivery.build_subject(severe_report)
        assert subject == "[2 SEVERE] UniFi Report - Jan 24, 2026"

    def test_subject_timezone_formatting(self, sample_report: Report) -> None:
        """Subject uses configured timezone for date."""
        delivery = EmailDelivery(smtp_host="test", timezone="America/New_York")
        # 14:30 UTC = 09:30 EST, same day
        subject = delivery.build_subject(sample_report)
        assert "Jan 24, 2026" in subject


class TestEmailDeliverySend:
    """Test email sending functionality."""

    @patch("unifi_scanner.delivery.email.smtplib.SMTP")
    def test_send_starttls(self, mock_smtp: MagicMock) -> None:
        """Send email via STARTTLS (port 587)."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        delivery = EmailDelivery(
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pass",
            use_tls=True,
        )

        delivery.send(
            recipients=["test@example.com"],
            subject="Test Subject",
            html_content="<p>HTML</p>",
            text_content="Text",
        )

        mock_smtp.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()

    @patch("unifi_scanner.delivery.email.smtplib.SMTP_SSL")
    def test_send_implicit_tls(self, mock_smtp_ssl: MagicMock) -> None:
        """Send email via implicit TLS (port 465)."""
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_ssl.return_value.__exit__ = MagicMock(return_value=False)

        delivery = EmailDelivery(
            smtp_host="smtp.test.com",
            smtp_port=465,
            smtp_user="user",
            smtp_password="pass",
            use_tls=True,
        )

        delivery.send(
            recipients=["test@example.com"],
            subject="Test Subject",
            html_content="<p>HTML</p>",
            text_content="Text",
        )

        mock_smtp_ssl.assert_called_once()
        mock_server.sendmail.assert_called_once()

    def test_send_no_recipients_skipped(self) -> None:
        """Empty recipient list skips sending."""
        delivery = EmailDelivery(smtp_host="test")

        # Should not raise, just log warning
        delivery.send(
            recipients=[],
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
        )

    @patch("unifi_scanner.delivery.email.smtplib.SMTP")
    def test_bcc_not_in_headers(self, mock_smtp: MagicMock) -> None:
        """Recipients are NOT exposed in message headers."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        delivery = EmailDelivery(smtp_host="test", smtp_port=587, use_tls=False)

        delivery.send(
            recipients=["secret@example.com", "hidden@example.com"],
            subject="Test",
            html_content="<p>Test</p>",
            text_content="Test",
        )

        # Get the message string passed to sendmail
        call_args = mock_server.sendmail.call_args
        msg_string = call_args[0][2]  # Third argument is message string

        # Verify Bcc header is NOT present
        assert "Bcc:" not in msg_string
        assert "secret@example.com" not in msg_string
        assert "hidden@example.com" not in msg_string


class TestEmailDeliveryDeliver:
    """Test high-level deliver_report method."""

    @patch("unifi_scanner.delivery.email.smtplib.SMTP")
    def test_deliver_report_success(
        self, mock_smtp: MagicMock, sample_report: Report
    ) -> None:
        """deliver_report returns True on success."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        delivery = EmailDelivery(smtp_host="test", smtp_port=587, use_tls=False)
        result = delivery.deliver_report(
            report=sample_report,
            html_content="<p>Report</p>",
            text_content="Report",
            recipients=["test@example.com"],
        )

        assert result is True

    @patch("unifi_scanner.delivery.email.smtplib.SMTP")
    def test_deliver_report_failure(
        self, mock_smtp: MagicMock, sample_report: Report
    ) -> None:
        """deliver_report returns False on SMTP error."""
        import smtplib

        mock_server = MagicMock()
        mock_server.sendmail.side_effect = smtplib.SMTPException("Connection failed")
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        delivery = EmailDelivery(smtp_host="test", smtp_port=587, use_tls=False)
        result = delivery.deliver_report(
            report=sample_report,
            html_content="<p>Report</p>",
            text_content="Report",
            recipients=["test@example.com"],
        )

        assert result is False
