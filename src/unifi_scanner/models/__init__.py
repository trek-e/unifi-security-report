"""Data models for UniFi Scanner."""

from .enums import Category, DeviceType, LogSource, Severity
from .log_entry import LogEntry

__all__ = [
    "Category",
    "DeviceType",
    "LogEntry",
    "LogSource",
    "Severity",
]
