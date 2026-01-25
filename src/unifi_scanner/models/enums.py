"""Shared enumerations for the UniFi Scanner models."""

from enum import Enum


class Severity(str, Enum):
    """Severity level for findings."""

    LOW = "low"
    MEDIUM = "medium"
    SEVERE = "severe"


class Category(str, Enum):
    """Category of finding or log entry."""

    CONNECTIVITY = "connectivity"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SYSTEM = "system"
    UNCATEGORIZED = "uncategorized"
    WIRELESS = "wireless"


class LogSource(str, Enum):
    """Source of log data."""

    API = "api"
    SSH = "ssh"
    SYSLOG = "syslog"


class DeviceType(str, Enum):
    """Type of UniFi controller."""

    UDM_PRO = "udm_pro"
    SELF_HOSTED = "self_hosted"
