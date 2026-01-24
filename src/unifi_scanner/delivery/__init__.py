"""Delivery subsystem for report output."""

from unifi_scanner.delivery.email import EmailDelivery, EmailDeliveryError
from unifi_scanner.delivery.file import FileDelivery, FileDeliveryError

__all__ = ["EmailDelivery", "EmailDeliveryError", "FileDelivery", "FileDeliveryError"]
