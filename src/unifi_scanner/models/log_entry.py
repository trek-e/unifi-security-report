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
