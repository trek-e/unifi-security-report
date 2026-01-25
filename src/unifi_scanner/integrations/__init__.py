"""External integrations infrastructure.

Provides the Integration Protocol, registry, and runner for optional
external integrations like Cloudflare and Cybersecure.

Importing this module triggers registration of all available integrations.

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

# Base types and infrastructure
from unifi_scanner.integrations.base import (
    Integration,
    IntegrationResult,
    IntegrationResults,
    IntegrationSection,
)
from unifi_scanner.integrations.registry import IntegrationRegistry
from unifi_scanner.integrations.runner import IntegrationRunner

# Import integration modules to trigger registration
# Each module registers itself via IntegrationRegistry.register()
from unifi_scanner.integrations import cloudflare  # noqa: F401

__all__ = [
    "Integration",
    "IntegrationRegistry",
    "IntegrationResult",
    "IntegrationResults",
    "IntegrationRunner",
    "IntegrationSection",
]
