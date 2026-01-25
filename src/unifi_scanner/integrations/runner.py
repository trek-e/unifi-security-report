"""Integration runner with circuit breakers and parallel execution.

Executes integrations in parallel with:
- Per-integration circuit breakers (fail_max=3, reset_timeout=60s)
- 30-second timeout per integration
- Complete failure isolation (one failure doesn't affect others)

Example usage::

    from unifi_scanner.integrations import IntegrationRunner

    runner = IntegrationRunner(settings)
    results = await runner.run_all()
    # results.sections contains IntegrationSection for each integration
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict

import pybreaker
import structlog

from unifi_scanner.integrations.base import (
    Integration,
    IntegrationResult,
    IntegrationResults,
    IntegrationSection,
)
from unifi_scanner.integrations.registry import IntegrationRegistry

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# Module-level constants for circuit breaker and timeout configuration
INTEGRATION_TIMEOUT = 30  # seconds per integration
CIRCUIT_FAIL_MAX = 3  # open after 3 consecutive failures
CIRCUIT_RESET_TIMEOUT = 60  # try again after 60 seconds

# Cache of circuit breakers by integration name (in-memory, resets on restart)
_circuit_breakers: Dict[str, pybreaker.CircuitBreaker] = {}


class CircuitBreakerLoggingListener(pybreaker.CircuitBreakerListener):
    """Logs circuit breaker state changes.

    Per CONTEXT.md: Log once when tripped, not each skip.
    - WARNING when circuit opens (integration failing)
    - INFO when circuit closes (integration recovered)
    """

    def state_change(
        self,
        cb: pybreaker.CircuitBreaker,
        old_state: pybreaker.CircuitBreakerState,
        new_state: pybreaker.CircuitBreakerState,
    ) -> None:
        """Log state transitions for monitoring.

        Args:
            cb: The circuit breaker that changed state.
            old_state: Previous state before transition.
            new_state: New state after transition.
        """
        if new_state.name == "open":
            log.warning(
                "circuit_breaker_opened",
                integration=cb.name,
                failures=cb.fail_counter,
                reset_timeout=cb.reset_timeout,
                message=f"Circuit breaker opened for {cb.name}, will retry after {cb.reset_timeout}s",
            )
        elif new_state.name == "closed":
            log.info(
                "circuit_breaker_closed",
                integration=cb.name,
                message=f"Circuit breaker closed for {cb.name}, integration recovered",
            )


def create_circuit_breaker(name: str) -> pybreaker.CircuitBreaker:
    """Create a circuit breaker for an integration.

    Uses consistent configuration across all integrations:
    - fail_max=3: Open after 3 consecutive failures
    - reset_timeout=60: Try again after 60 seconds
    - Logging listener for state change monitoring

    Args:
        name: Integration name for logging context.

    Returns:
        Configured CircuitBreaker instance.
    """
    return pybreaker.CircuitBreaker(
        name=name,
        fail_max=CIRCUIT_FAIL_MAX,
        reset_timeout=CIRCUIT_RESET_TIMEOUT,
        listeners=[CircuitBreakerLoggingListener()],
    )


def get_circuit_breaker(name: str) -> pybreaker.CircuitBreaker:
    """Get or create a circuit breaker for an integration.

    Circuit breakers are cached by name to ensure consistent state
    across multiple calls within the same process lifetime.

    Args:
        name: Integration name for lookup/creation.

    Returns:
        Circuit breaker for the specified integration.
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = create_circuit_breaker(name)
    return _circuit_breakers[name]


class IntegrationRunner:
    """Runs integrations in parallel with circuit breakers and failure isolation.

    Each integration:
    - Has its own circuit breaker (not shared)
    - Runs with a 30-second timeout
    - Fails independently (doesn't affect other integrations)

    Example::

        runner = IntegrationRunner(settings)
        results = await runner.run_all()
        for section in results.sections:
            if section.success:
                print(f"{section.display_name}: {section.data}")
            else:
                print(f"{section.display_name}: {section.error_message}")
    """

    def __init__(self, settings: Any) -> None:
        """Initialize runner with settings.

        Args:
            settings: Application settings passed to integrations.
        """
        self._settings = settings

    async def run_all(self) -> IntegrationResults:
        """Run all configured integrations in parallel.

        Gets configured integrations from registry, runs them in parallel
        using asyncio.gather with return_exceptions=True for complete
        isolation (INTG-02).

        Returns:
            IntegrationResults with sections for all integrations.
            Empty sections list if no integrations configured.
        """
        integrations = IntegrationRegistry.get_configured(self._settings)

        if not integrations:
            # Silent skip when no integrations configured
            return IntegrationResults(sections=[])

        # Run all integrations in parallel with complete isolation
        results = await asyncio.gather(
            *[self._run_one(integration) for integration in integrations],
            return_exceptions=True,  # Critical for isolation (INTG-02)
        )

        # Convert results to sections
        sections = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Unexpected exception from gather itself
                integration = integrations[i]
                log.error(
                    "integration_unexpected_error",
                    integration=integration.name,
                    error=str(result),
                )
                sections.append(
                    IntegrationSection(
                        name=integration.name,
                        display_name=self._get_display_name(integration.name),
                        success=False,
                        error_message="Unable to fetch data",
                    )
                )
            else:
                sections.append(self._result_to_section(result))

        return IntegrationResults(sections=sections)

    async def _run_one(self, integration: Integration) -> IntegrationResult:
        """Run a single integration with circuit breaker and timeout.

        Wraps the integration fetch call with:
        - Circuit breaker protection (INTG-03)
        - 30-second timeout
        - Comprehensive exception handling

        Note: Uses pybreaker's calling() context manager instead of decorator
        because the @breaker decorator doesn't properly track failures for
        async functions in pybreaker 1.4.1.

        Args:
            integration: Integration to run.

        Returns:
            IntegrationResult with success/failure status.
        """
        breaker = get_circuit_breaker(integration.name)

        # Fast path: check if circuit is already open
        if breaker.current_state == pybreaker.STATE_OPEN:
            log.debug(
                "integration_circuit_open",
                integration=integration.name,
                message="Skipping integration due to open circuit",
            )
            return IntegrationResult(
                name=integration.name,
                success=False,
                error="circuit_open",
            )

        try:
            # Use calling() context manager for proper async support
            # The context manager tracks success/failure and updates circuit state
            with breaker.calling():
                result = await asyncio.wait_for(
                    integration.fetch(),
                    timeout=INTEGRATION_TIMEOUT,
                )
            return result

        except asyncio.TimeoutError:
            log.warning(
                "integration_timeout",
                integration=integration.name,
                timeout=INTEGRATION_TIMEOUT,
            )
            return IntegrationResult(
                name=integration.name,
                success=False,
                error="timeout",
            )
        except pybreaker.CircuitBreakerError:
            # Circuit just opened or is open - already logged by listener
            log.debug(
                "integration_circuit_breaker_error",
                integration=integration.name,
            )
            return IntegrationResult(
                name=integration.name,
                success=False,
                error="circuit_open",
            )
        except Exception as e:
            log.error(
                "integration_error",
                integration=integration.name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return IntegrationResult(
                name=integration.name,
                success=False,
                error=str(e),
            )

    def _result_to_section(self, result: IntegrationResult) -> IntegrationSection:
        """Convert IntegrationResult to IntegrationSection for report.

        Error messages include specific failure reason (timeout, circuit_open, etc.)
        for debugging, while templates can display user-friendly messages.

        Args:
            result: Result from integration fetch.

        Returns:
            IntegrationSection for template rendering.
        """
        # Build error message with specific reason if available
        error_message = None
        if not result.success:
            if result.error == "timeout":
                error_message = f"Unable to fetch data (timeout after {INTEGRATION_TIMEOUT}s)"
            elif result.error == "circuit_open":
                error_message = "Unable to fetch data (circuit breaker open)"
            elif result.error:
                error_message = f"Unable to fetch data ({result.error})"
            else:
                error_message = "Unable to fetch data"

        return IntegrationSection(
            name=result.name,
            display_name=self._get_display_name(result.name),
            success=result.success,
            data=result.data,
            error_message=error_message,
        )

    def _get_display_name(self, name: str) -> str:
        """Get human-readable display name for integration.

        Maps integration identifiers to display names for report headers.
        Can be extended as integrations are added.

        Args:
            name: Integration identifier.

        Returns:
            Human-readable display name.
        """
        # Display name mapping (can be extended for future integrations)
        display_names = {
            "cloudflare": "Cloudflare Security",
            "cybersecure": "Cybersecure",
        }
        return display_names.get(name, name.replace("_", " ").title())
