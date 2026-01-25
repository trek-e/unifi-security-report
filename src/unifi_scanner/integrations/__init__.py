"""Integration infrastructure for optional external data sources.

Provides the framework for integrations that:
- Fail gracefully without affecting core UniFi reports
- Run in parallel with each other and UniFi data collection
- Are skipped silently when not configured

Example usage::

    from unifi_scanner.integrations import (
        Integration,
        IntegrationResult,
        IntegrationSection,
        IntegrationResults,
        IntegrationRegistry,
    )

    # Get configured integrations
    integrations = IntegrationRegistry.get_configured(settings)

    # Run integration
    result = await integration.fetch()
"""

from unifi_scanner.integrations.base import (
    Integration,
    IntegrationResult,
    IntegrationResults,
    IntegrationSection,
)

__all__ = [
    "Integration",
    "IntegrationResult",
    "IntegrationResults",
    "IntegrationSection",
]
