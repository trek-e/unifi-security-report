"""LogEntry model for normalized UniFi log data."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import LogSource


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

    @classmethod
    def from_unifi_event(cls, event_data: Dict[str, Any]) -> "LogEntry":
        """Factory for creating LogEntry from raw UniFi API response.

        This is a stub implementation that extracts common fields.
        Will be enhanced in Phase 2 with specific event type handling.

        Args:
            event_data: Raw event dictionary from UniFi API

        Returns:
            LogEntry instance with extracted fields
        """
        # Extract timestamp - UniFi uses 'time' field with milliseconds
        timestamp_ms = event_data.get("time", event_data.get("datetime"))
        if isinstance(timestamp_ms, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
        elif isinstance(timestamp_ms, str):
            timestamp = datetime.fromisoformat(timestamp_ms.replace("Z", "+00:00"))
        else:
            timestamp = datetime.utcnow()

        return cls(
            timestamp=timestamp,
            source=LogSource.API,
            device_mac=event_data.get("ap_mac") or event_data.get("sw_mac") or event_data.get("gw_mac"),
            device_name=event_data.get("ap_name") or event_data.get("sw_name") or event_data.get("gw_name"),
            event_type=event_data.get("key", "UNKNOWN"),
            message=event_data.get("msg", ""),
            raw_data=event_data,
        )
