"""Delivery subsystem for report output."""

from unifi_scanner.delivery.email import EmailDelivery, EmailDeliveryError

__all__ = ["EmailDelivery", "EmailDeliveryError"]
