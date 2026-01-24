"""LogEntry model for normalized UniFi log data."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator

from unifi_scanner.utils.timestamps import normalize_timestamp

from .enums import LogSource

logger = structlog.get_logger(__name__)

# Regex for MAC address validation (6 groups of 2 hex chars)
MAC_PATTERN = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", re.IGNORECASE)

# Regex for syslog format: "Jan 24 10:30:15 hostname program[pid]: message"
SYSLOG_PATTERN = re.compile(
    r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<hostname>\S+)\s+(?P<program>[^\[]+)(?:\[(?P<pid>\d+)\])?"
    r":\s*(?P<message>.*)$"
)


class LogEntry(BaseModel):
    """Normalized log entry from UniFi controller.

    Captures all relevant fields from various UniFi log sources
    (API, SSH, syslog) in a consistent format.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str,
        },
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier for this log entry")
    timestamp: datetime = Field(..., description="When the event occurred")
    source: LogSource = Field(..., description="Where the log came from (api, ssh, syslog)")
    device_mac: Optional[str] = Field(
        default=None, description="MAC address of device that generated event"
    )
    device_name: Optional[str] = Field(default=None, description="Human-readable device name")
    event_type: str = Field(..., description="UniFi event type code like 'EVT_AP_Connected'")
    message: str = Field(..., description="Human-readable message")
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="Original data for debugging"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Extensibility field for additional data"
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp_field(cls, v: Any) -> datetime:
        """Convert various timestamp formats to UTC datetime."""
        try:
            return normalize_timestamp(v)
        except (ValueError, TypeError) as e:
            logger.warning(
                "timestamp_parse_failed",
                value=repr(v)[:100],
                error=str(e),
            )
            return datetime.now(timezone.utc)

    @field_validator("device_mac", mode="before")
    @classmethod
    def normalize_mac_address(cls, v: Any) -> Optional[str]:
        """Normalize MAC address to lowercase with colons."""
        if v is None or v == "":
            return None

        if not isinstance(v, str):
            return v

        # Normalize: lowercase, replace dashes with colons
        normalized = v.lower().replace("-", ":")

        # Validate format
        if not MAC_PATTERN.match(normalized):
            logger.warning(
                "mac_address_invalid_format",
                original=v,
                normalized=normalized,
            )
            return v  # Return original if invalid format

        return normalized

    @field_validator("event_type", mode="before")
    @classmethod
    def default_event_type(cls, v: Any) -> str:
        """Default empty event types to UNKNOWN."""
        if v is None or v == "":
            return "UNKNOWN"
        return v

    @classmethod
    def from_unifi_event(cls, event_data: Dict[str, Any]) -> "LogEntry":
        """Factory for creating LogEntry from raw UniFi API response.

        Args:
            event_data: Raw event dictionary from UniFi API

        Returns:
            LogEntry instance with extracted fields
        """
        # Extract timestamp - UniFi uses 'time' field with milliseconds
        timestamp = event_data.get("time") or event_data.get("datetime")

        # Extract device MAC - check multiple possible fields
        device_mac = (
            event_data.get("mac")
            or event_data.get("ap_mac")
            or event_data.get("sw_mac")
            or event_data.get("gw_mac")
        )

        # Extract device name
        device_name = (
            event_data.get("ap_name")
            or event_data.get("sw_name")
            or event_data.get("gw_name")
        )

        # Build metadata with subsystem info
        metadata: Dict[str, Any] = {}
        if "subsystem" in event_data:
            metadata["subsystem"] = event_data["subsystem"]
        if "site_id" in event_data:
            metadata["site_id"] = event_data["site_id"]

        return cls(
            timestamp=timestamp,
            source=LogSource.API,
            device_mac=device_mac,
            device_name=device_name,
            event_type=event_data.get("key"),
            message=event_data.get("msg", ""),
            raw_data=event_data,
            metadata=metadata,
        )

    @classmethod
    def from_syslog(cls, line: str) -> "LogEntry":
        """Factory for creating LogEntry from syslog line.

        Parses standard syslog format: "Jan 24 10:30:15 hostname program[pid]: message"

        Args:
            line: Raw syslog line

        Returns:
            LogEntry instance with extracted fields

        Raises:
            ValueError: If line cannot be parsed
        """
        match = SYSLOG_PATTERN.match(line.strip())
        if not match:
            raise ValueError(f"Cannot parse syslog line: {line[:100]}")

        groups = match.groupdict()

        # Parse timestamp (syslog omits year, use current year)
        current_year = datetime.now().year
        timestamp_str = f"{groups['month']} {groups['day']} {current_year} {groups['time']}"

        # Build metadata
        metadata: Dict[str, Any] = {
            "hostname": groups["hostname"],
            "program": groups["program"].strip(),
        }
        if groups.get("pid"):
            metadata["pid"] = int(groups["pid"])

        return cls(
            timestamp=timestamp_str,
            source=LogSource.SYSLOG,
            device_name=groups["hostname"],
            event_type=f"SYSLOG_{groups['program'].strip().upper()}",
            message=groups["message"],
            raw_data={"line": line},
            metadata=metadata,
        )
