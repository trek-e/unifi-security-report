"""Base types for external integrations.

Provides the Integration Protocol interface, result models, and section types
for optional external integrations (Cloudflare, Cybersecure, etc.) that
fail gracefully without affecting core UniFi report generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class IntegrationResult:
    """Result from an integration fetch call.

    Captures success/failure status along with optional data or error message.
    Used by the IntegrationRunner to track individual integration outcomes.
    """

    name: str
    """Unique integration identifier (e.g., 'cloudflare', 'cybersecure')."""

    success: bool
    """Whether the fetch operation succeeded."""

    data: Optional[Dict[str, Any]] = None
    """Integration-specific data on success."""

    error: Optional[str] = None
    """Error message if fetch failed."""


@dataclass
class IntegrationSection:
    """Section data for a single integration in the report.

    Used by templates to render integration-specific sections with
    appropriate headers, data, and error messages.
    """

    name: str
    """Integration identifier (e.g., 'cloudflare')."""

    display_name: str
    """Human-readable name for report headers (e.g., 'Cloudflare Security')."""

    success: bool
    """Whether data was successfully fetched."""

    data: Optional[Dict[str, Any]] = None
    """Data for template rendering on success."""

    error_message: Optional[str] = None
    """User-friendly error message if fetch failed (e.g., 'Unable to fetch data')."""


@dataclass
class IntegrationResults:
    """Aggregated results from all integrations for report generation.

    Collects all integration sections and provides helper methods
    for querying results by integration name.
    """

    sections: List[IntegrationSection] = field(default_factory=list)
    """All integration sections (both successful and failed)."""

    @property
    def has_data(self) -> bool:
        """Check if any integration returned data.

        Returns:
            True if at least one section has success=True and non-empty data.
        """
        return any(s.success and s.data for s in self.sections)

    def get_section(self, name: str) -> Optional[IntegrationSection]:
        """Get a specific integration's section by name.

        Args:
            name: Integration identifier to look up.

        Returns:
            IntegrationSection if found, None otherwise.
        """
        for section in self.sections:
            if section.name == name:
                return section
        return None


@runtime_checkable
class Integration(Protocol):
    """Protocol for external integrations.

    Defines the interface that all integrations must implement.
    Uses Protocol for duck typing with static type checking support.

    Integrations are optional enrichments that:
    - Fail gracefully without affecting core UniFi reports
    - Run in parallel with each other and UniFi data collection
    - Are skipped silently when not configured
    """

    @property
    def name(self) -> str:
        """Unique integration identifier (e.g., 'cloudflare', 'cybersecure').

        Used for logging, registry lookup, and error reporting.
        """
        ...

    def is_configured(self) -> bool:
        """Check if integration has all required credentials.

        Returns True only when ALL required environment variables
        or settings are present. Partial configuration returns False.

        Returns:
            True if fully configured and ready to fetch data.
        """
        ...

    def validate_config(self) -> Optional[str]:
        """Validate configuration completeness.

        Checks for partial configuration (some but not all required
        credentials) and returns a warning message for logging.

        Returns:
            None if fully configured or not configured at all.
            Warning message string if partially configured.
        """
        ...

    async def fetch(self) -> IntegrationResult:
        """Fetch data from external service.

        Called by IntegrationRunner with circuit breaker protection.
        May raise exceptions - caller handles isolation and error capture.

        Returns:
            IntegrationResult with success status and data or error.

        Raises:
            Any exception from the external service call.
        """
        ...
