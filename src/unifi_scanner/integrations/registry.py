"""Integration registry for managing available external integrations.

Provides centralized management of integration classes with filtering
for configured vs unconfigured integrations. Uses a hardcoded list
of integration classes (not dynamic plugin discovery).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Type

import structlog

from unifi_scanner.integrations.base import Integration

if TYPE_CHECKING:
    pass

log = structlog.get_logger()


class IntegrationRegistry:
    """Registry for available integrations.

    Manages the list of known integration classes and provides methods
    to instantiate and filter them based on configuration status.

    The registry uses a hardcoded list (populated via register()) rather
    than dynamic plugin discovery. Integrations register themselves at
    module import time.

    Example usage::

        # In cloudflare integration module:
        from unifi_scanner.integrations import IntegrationRegistry
        IntegrationRegistry.register(CloudflareIntegration)

        # In report generation:
        integrations = IntegrationRegistry.get_configured(settings)
        for integration in integrations:
            result = await integration.fetch()
    """

    _integration_classes: List[Type[Integration]] = []
    """Registered integration classes (hardcoded, not dynamic discovery)."""

    @classmethod
    def register(cls, integration_class: Type[Integration]) -> None:
        """Register an integration class with the registry.

        Called at module import time by each integration module.
        Registration order determines execution order.

        Args:
            integration_class: Integration class to register.
        """
        if integration_class not in cls._integration_classes:
            cls._integration_classes.append(integration_class)
            log.debug(
                "integration_registered",
                integration=getattr(integration_class, "__name__", str(integration_class)),
            )

    @classmethod
    def get_configured(cls, settings: Any) -> List[Integration]:
        """Get all integrations that are fully configured.

        Instantiates each registered integration class with settings,
        checks is_configured(), and returns only those that are ready.
        Logs warnings for partially configured integrations.

        Args:
            settings: Application settings object passed to integration constructors.

        Returns:
            List of configured Integration instances. Empty if none configured.
        """
        configured: List[Integration] = []

        for integration_class in cls._integration_classes:
            try:
                integration = integration_class(settings)  # type: ignore[call-arg]

                # Check for partial configuration and log warning
                warning = integration.validate_config()
                if warning:
                    log.warning(
                        "integration_partial_config",
                        integration=integration.name,
                        warning=warning,
                    )

                # Only include fully configured integrations
                if integration.is_configured():
                    configured.append(integration)
                    log.debug(
                        "integration_enabled",
                        integration=integration.name,
                    )

            except Exception as e:
                # Integration class instantiation failed - log and skip
                log.warning(
                    "integration_init_failed",
                    integration=getattr(integration_class, "__name__", str(integration_class)),
                    error=str(e),
                )

        return configured

    @classmethod
    def get_all(cls, settings: Any) -> List[Integration]:
        """Get all registered integrations regardless of configuration.

        Useful for validation, configuration display, or status reporting.
        Logs warnings for any instantiation failures.

        Args:
            settings: Application settings object passed to integration constructors.

        Returns:
            List of all Integration instances that could be instantiated.
        """
        all_integrations: List[Integration] = []

        for integration_class in cls._integration_classes:
            try:
                integration = integration_class(settings)  # type: ignore[call-arg]
                all_integrations.append(integration)
            except Exception as e:
                log.warning(
                    "integration_init_failed",
                    integration=getattr(integration_class, "__name__", str(integration_class)),
                    error=str(e),
                )

        return all_integrations

    @classmethod
    def clear(cls) -> None:
        """Clear all registered integrations.

        Primarily for testing purposes.
        """
        cls._integration_classes = []
