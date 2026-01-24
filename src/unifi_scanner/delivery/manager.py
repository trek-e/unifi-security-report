"""Delivery orchestration for reports."""

from typing import List, Optional

import structlog

from unifi_scanner.delivery.email import EmailDelivery, EmailDeliveryError
from unifi_scanner.delivery.file import FileDelivery, FileDeliveryError
from unifi_scanner.models.report import Report

log = structlog.get_logger()


class DeliveryManager:
    """Orchestrates report delivery via email and/or file.

    Implements fallback logic: if email delivery fails, automatically
    saves to file even if file output wasn't configured.
    """

    def __init__(
        self,
        email_delivery: Optional[EmailDelivery] = None,
        file_delivery: Optional[FileDelivery] = None,
        fallback_dir: str = "./reports",
    ) -> None:
        """Initialize delivery manager.

        Args:
            email_delivery: Configured EmailDelivery instance (None = disabled)
            file_delivery: Configured FileDelivery instance (None = disabled)
            fallback_dir: Directory for file fallback when email fails
        """
        self.email_delivery = email_delivery
        self.file_delivery = file_delivery
        self.fallback_dir = fallback_dir

    def deliver(
        self,
        report: Report,
        html_content: str,
        text_content: str,
        email_recipients: Optional[List[str]] = None,
    ) -> bool:
        """Deliver report via configured channels.

        Email failure triggers file fallback (per CONTEXT.md decision).

        Args:
            report: Report object
            html_content: Rendered HTML report
            text_content: Rendered plain text report
            email_recipients: List of email addresses (for email delivery)

        Returns:
            True if at least one delivery succeeded, False if all failed
        """
        email_success = False
        file_success = False

        # Attempt email delivery
        if self.email_delivery and email_recipients:
            try:
                self.email_delivery.send(
                    recipients=email_recipients,
                    subject=self.email_delivery.build_subject(report),
                    html_content=html_content,
                    text_content=text_content,
                )
                email_success = True
                log.info("email_delivery_success", recipients_count=len(email_recipients))
            except EmailDeliveryError as e:
                log.error("email_delivery_failed", error=str(e))
                # Activate fallback if file delivery not configured
                if not self.file_delivery:
                    log.warning("activating_file_fallback", reason="email_failed")
                    self.file_delivery = FileDelivery(
                        output_dir=self.fallback_dir,
                        file_format="both",
                        retention_days=30,
                    )

        # File delivery (explicit or fallback)
        if self.file_delivery:
            try:
                paths = self.file_delivery.save(
                    report=report,
                    html_content=html_content,
                    text_content=text_content,
                )
                file_success = len(paths) > 0
                if file_success:
                    log.info("file_delivery_success", paths=[str(p) for p in paths])
            except FileDeliveryError as e:
                log.error("file_delivery_failed", error=str(e))

        # Log overall result
        if not email_success and not file_success:
            log.error("all_delivery_failed", message="No delivery method succeeded")

        return email_success or file_success
