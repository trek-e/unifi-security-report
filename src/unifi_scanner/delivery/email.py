"""SMTP email delivery for reports."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate
from typing import List, Optional

import structlog

from unifi_scanner.models.report import Report

log = structlog.get_logger()


class EmailDeliveryError(Exception):
    """Raised when email delivery fails."""

    pass


class EmailDelivery:
    """SMTP email delivery with BCC recipients and multipart support.

    Sends HTML reports with plaintext fallback via SMTP. All recipients
    receive the email via BCC (no To/CC headers exposed). Subject line
    includes severity count when severe findings exist.

    Supports both:
    - Port 587 with STARTTLS (explicit TLS)
    - Port 465 with implicit TLS (SMTPS)
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
        from_addr: str = "unifi-scanner@localhost",
        timezone: str = "UTC",
    ) -> None:
        """Initialize email delivery.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (587=STARTTLS, 465=implicit TLS)
            smtp_user: Authentication username
            smtp_password: Authentication password
            use_tls: Enable TLS encryption
            from_addr: Sender email address
            timezone: Timezone for date formatting in subject
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_tls = use_tls
        self.from_addr = from_addr
        self.timezone = timezone

    def build_subject(self, report: Report) -> str:
        """Build email subject with optional severity prefix.

        Format when severe findings exist:
            "[N SEVERE] UniFi Report - Jan 24, 2026"

        Format when no severe findings:
            "UniFi Report - Jan 24, 2026"

        Args:
            report: Report object containing severity counts

        Returns:
            Formatted subject line string
        """
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(self.timezone)
        date_str = report.generated_at.astimezone(tz).strftime("%b %d, %Y")

        if report.severe_count > 0:
            return f"[{report.severe_count} SEVERE] UniFi Report - {date_str}"
        return f"UniFi Report - {date_str}"

    def send(
        self,
        recipients: List[str],
        subject: str,
        html_content: str,
        text_content: str,
    ) -> None:
        """Send multipart email to BCC recipients.

        All recipients are sent via BCC - no To/CC headers are set.
        This ensures recipient privacy (recipients cannot see each other).

        Args:
            recipients: List of email addresses (all BCC, never shown)
            subject: Email subject line
            html_content: HTML body content
            text_content: Plain text fallback content

        Raises:
            EmailDeliveryError: If sending fails
        """
        if not recipients:
            log.warning("email_skipped", reason="no recipients")
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["Date"] = formatdate(localtime=True)
        # NOTE: No To/Cc headers - all recipients via BCC (hidden)
        # Recipients are passed directly to sendmail() below

        # Set plaintext first, then add HTML alternative
        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype="html")

        try:
            context = ssl.create_default_context()

            if self.use_tls and self.smtp_port == 465:
                # Implicit TLS (SMTPS) - connection encrypted from start
                with smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, context=context
                ) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.from_addr, recipients, msg.as_string())
            else:
                # Explicit TLS (STARTTLS) or no TLS
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.use_tls:
                        server.starttls(context=context)
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.from_addr, recipients, msg.as_string())

            log.info("email_sent", recipients_count=len(recipients), subject=subject)

        except smtplib.SMTPAuthenticationError as e:
            log.error("email_auth_failed", error=str(e))
            raise EmailDeliveryError(f"SMTP authentication failed: {e}")
        except smtplib.SMTPException as e:
            log.error("email_send_failed", error=str(e))
            raise EmailDeliveryError(f"SMTP error: {e}")
        except Exception as e:
            log.error("email_delivery_error", error=str(e))
            raise EmailDeliveryError(f"Email delivery failed: {e}")

    def deliver_report(
        self,
        report: Report,
        html_content: str,
        text_content: str,
        recipients: List[str],
    ) -> bool:
        """Deliver report via email.

        High-level method that builds the subject line from the report
        and handles delivery errors gracefully.

        Args:
            report: Report object for subject line generation
            html_content: Rendered HTML report
            text_content: Rendered plain text report
            recipients: List of recipient addresses

        Returns:
            True if delivery succeeded, False otherwise
        """
        subject = self.build_subject(report)
        try:
            self.send(recipients, subject, html_content, text_content)
            return True
        except EmailDeliveryError:
            # Error already logged in send()
            return False
