"""Report model for analysis output."""

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .enums import DeviceType, Severity
from .finding import Finding


class Report(BaseModel):
    """Container for analysis results.

    Holds all findings from analyzing UniFi logs for a given time period
    and site, with computed properties for severity counts.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str,
        },
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier for this report")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When this report was generated"
    )
    period_start: datetime = Field(..., description="Analysis window start")
    period_end: datetime = Field(..., description="Analysis window end")
    site_name: str = Field(..., description="UniFi site name")
    controller_type: DeviceType = Field(..., description="Type of controller (UDM Pro, etc.)")
    findings: List[Finding] = Field(default_factory=list, description="All findings")
    log_entry_count: int = Field(default=0, description="How many logs were analyzed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Extensibility field for additional data"
    )

    @computed_field
    @property
    def severe_count(self) -> int:
        """Count of findings with severity=SEVERE."""
        return sum(1 for f in self.findings if f.severity == Severity.SEVERE)

    @computed_field
    @property
    def medium_count(self) -> int:
        """Count of findings with severity=MEDIUM."""
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @computed_field
    @property
    def low_count(self) -> int:
        """Count of findings with severity=LOW."""
        return sum(1 for f in self.findings if f.severity == Severity.LOW)
