"""IPS event models for normalized UniFi IPS/IDS data.

Provides pydantic models for processing IPS events from the UniFi API,
including signature parsing and action classification.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .signature_parser import is_action_blocked, parse_signature_category

# Cybersecure (Proofpoint ET PRO) signature ID range
# ET PRO signatures are in the 2800000-2899999 range
ET_PRO_SID_MIN = 2800000
ET_PRO_SID_MAX = 2899999


class IPSEvent(BaseModel):
    """Normalized IPS/IDS event from UniFi API.

    Captures all relevant fields from UniFi IPS events with parsed
    signature categories and action classification.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
    )

    # Core identifiers
    id: str = Field(..., description="Unique identifier from UniFi API")
    timestamp: datetime = Field(..., description="When the event occurred")

    # Network details
    src_ip: str = Field(..., description="Source IP address")
    src_port: Optional[int] = Field(default=None, description="Source port")
    dest_ip: str = Field(..., description="Destination IP address")
    dest_port: Optional[int] = Field(default=None, description="Destination port")
    proto: str = Field(..., description="Protocol (TCP, UDP, ICMP)")

    # Signature details
    signature: str = Field(..., description="Full signature string")
    signature_id: int = Field(..., description="Numeric signature ID")
    category_raw: str = Field(..., description="Raw category from API")
    severity: int = Field(..., description="Severity level (1=high, 2=medium, 3=low)")
    action: str = Field(..., description="Action taken (blocked, allowed, etc.)")

    # Computed fields from parsing
    category_friendly: str = Field(
        default="", description="Human-friendly category name"
    )
    is_blocked: bool = Field(
        default=False, description="Whether the threat was blocked"
    )

    @computed_field
    @property
    def is_cybersecure(self) -> bool:
        """True if detected by Cybersecure (Proofpoint ET PRO) signature.

        Cybersecure uses Proofpoint's ET PRO ruleset which has signatures
        in the 2800000-2899999 SID range. This allows identification of
        threats detected by enhanced commercial signatures vs free ET Open.
        """
        return ET_PRO_SID_MIN <= self.signature_id <= ET_PRO_SID_MAX

    @classmethod
    def from_api_event(cls, event: dict[str, Any]) -> "IPSEvent":
        """Factory for creating IPSEvent from raw UniFi API response.

        Handles both nested inner_alert structure and flat structure.

        Args:
            event: Raw event dictionary from UniFi IPS API

        Returns:
            IPSEvent instance with parsed fields
        """
        # Handle nested alert structure - check for inner_alert first
        alert = event.get("inner_alert", event)

        # Extract signature info from the appropriate location
        signature = alert.get("signature", "")
        signature_id = alert.get("signature_id", 0)
        category_raw = alert.get("category", "")
        severity = alert.get("severity", 3)
        action = alert.get("action", "allowed")

        # Parse timestamp - UniFi uses milliseconds
        timestamp_value = event.get("timestamp", 0)
        if isinstance(timestamp_value, int) and timestamp_value > 1000000000000:
            # Milliseconds - convert to seconds
            timestamp = datetime.fromtimestamp(timestamp_value / 1000, tz=timezone.utc)
        elif isinstance(timestamp_value, int):
            # Already seconds
            timestamp = datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
        elif isinstance(timestamp_value, datetime):
            timestamp = timestamp_value
        else:
            timestamp = datetime.now(timezone.utc)

        # Parse signature to get friendly category
        _, friendly_name, _ = parse_signature_category(signature)

        # Determine if blocked
        blocked = is_action_blocked(action)

        return cls(
            id=event.get("_id", ""),
            timestamp=timestamp,
            src_ip=event.get("src_ip", ""),
            src_port=event.get("src_port"),
            dest_ip=event.get("dest_ip", ""),
            dest_port=event.get("dest_port"),
            proto=event.get("proto", ""),
            signature=signature,
            signature_id=signature_id,
            category_raw=category_raw,
            severity=severity,
            action=action,
            category_friendly=friendly_name,
            is_blocked=blocked,
        )
