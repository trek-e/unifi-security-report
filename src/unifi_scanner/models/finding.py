"""Finding model for analysis results."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import Category, Severity


class Finding(BaseModel):
    """Represents an analysis finding from UniFi log analysis.

    A finding is a detected issue, anomaly, or noteworthy event that
    links back to one or more source log entries.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str,
        },
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier for this finding")
    severity: Severity = Field(..., description="Severity level (low, medium, severe)")
    category: Category = Field(..., description="Category of the finding")
    title: str = Field(..., description="Short description like 'Failed Login Attempt'")
    description: str = Field(..., description="Detailed plain-English explanation")
    remediation: Optional[str] = Field(
        default=None, description="Step-by-step fix for severe issues"
    )
    source_log_ids: List[UUID] = Field(
        default_factory=list, description="Links to LogEntry.id that triggered this finding"
    )
    occurrence_count: int = Field(default=1, description="Count for deduplication")
    first_seen: datetime = Field(..., description="When first occurrence was detected")
    last_seen: datetime = Field(..., description="When most recent occurrence was detected")
    device_mac: Optional[str] = Field(
        default=None, description="MAC address if finding relates to specific device"
    )
    device_name: Optional[str] = Field(default=None, description="Human-readable device name")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Extensibility field for additional data"
    )

    @field_validator("last_seen")
    @classmethod
    def last_seen_after_first_seen(cls, v: datetime, info) -> datetime:
        """Validate that last_seen >= first_seen."""
        first_seen = info.data.get("first_seen")
        if first_seen is not None and v < first_seen:
            raise ValueError("last_seen must be >= first_seen")
        return v
