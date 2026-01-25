# Phase 10: Integration Infrastructure - Research

**Researched:** 2026-01-25
**Domain:** Python integration infrastructure, circuit breakers, parallel async execution, graceful degradation
**Confidence:** HIGH

## Summary

This phase implements the framework for optional external integrations (Cloudflare, Cybersecure) that fail gracefully without affecting core UniFi report generation. The research focused on three key areas: (1) circuit breaker patterns for protecting against cascading failures, (2) parallel async execution with isolation for running integrations concurrently, and (3) integration interface patterns using Python's Protocol-based typing.

The existing codebase already uses `tenacity` for retry logic and `httpx` for HTTP clients, providing a solid foundation. For circuit breakers, `pybreaker` (v1.4.1, BSD license) is the standard choice - it's well-maintained, supports Python 3.9+, and offers simple decorator-based usage. Parallel execution should use `asyncio.gather()` with `return_exceptions=True` for complete isolation between integrations.

The integration infrastructure should follow the existing patterns in the codebase: dataclasses for models, `Protocol` for interface definitions (to enable static type checking without runtime overhead), and optional Pydantic settings fields for configuration.

**Primary recommendation:** Use `pybreaker` for circuit breakers with credentials-only detection (no ENABLED flags), `asyncio.gather(return_exceptions=True)` for parallel isolated execution, and a `Protocol`-based `Integration` interface that follows the existing `DeviceHealthAnalyzer` pattern.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pybreaker | 1.4.1 | Circuit breaker pattern | Well-maintained, BSD license, simple decorator API, supports Python 3.9+, in-memory state (matches decision), async support |
| asyncio (stdlib) | Python 3.9+ | Parallel execution with isolation | Built-in, `gather(return_exceptions=True)` provides complete isolation |
| tenacity | 8.3+ | Retry with backoff (already in project) | Already used in codebase, complements circuit breaker |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ | Async HTTP client (already in project) | Integration HTTP calls (AsyncClient for parallel) |
| pydantic-settings | 2.0+ | Environment variable configuration (already in project) | Integration credentials as optional fields |
| structlog | 25.5+ | Structured logging (already in project) | Integration status logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pybreaker | circuitbreaker | circuitbreaker has async support but pybreaker is more actively maintained (Sept 2025 release) |
| pybreaker | aiobreaker | aiobreaker is asyncio-native but pybreaker works in both sync and async contexts |
| asyncio.gather | asyncio.TaskGroup | TaskGroup (Python 3.11+) cancels all tasks on first failure, but project targets Python 3.9+ |

**Installation:**
```bash
pip install pybreaker
# Or add to pyproject.toml dependencies:
# "pybreaker>=1.4"
```

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── integrations/           # New module for integration infrastructure
│   ├── __init__.py         # Public exports
│   ├── base.py             # Protocol, registry, result models
│   ├── runner.py           # IntegrationRunner (parallel execution, circuit breakers)
│   └── registry.py         # IntegrationRegistry (manages available integrations)
├── config/
│   └── settings.py         # Add integration settings (CLOUDFLARE_*, CYBERSECURE_*)
└── ...
```

### Pattern 1: Protocol-Based Integration Interface
**What:** Define integration contract using `typing.Protocol` for static type checking without runtime overhead
**When to use:** For defining what integrations must implement
**Example:**
```python
# Source: PEP 544 (Python typing.Protocol)
from typing import Protocol, Optional
from dataclasses import dataclass

@dataclass
class IntegrationResult:
    """Result from an integration call."""
    name: str
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None  # Populated on failure

class Integration(Protocol):
    """Protocol for external integrations.

    Integrations must implement these methods. Using Protocol
    enables duck typing with static type checking.
    """

    @property
    def name(self) -> str:
        """Unique integration name (e.g., 'cloudflare', 'cybersecure')."""
        ...

    def is_configured(self) -> bool:
        """Check if integration has required credentials.

        Returns True only if ALL required env vars are set.
        Partial config (some vars but not all) returns False.
        """
        ...

    def validate_config(self) -> Optional[str]:
        """Validate configuration completeness.

        Returns None if fully configured.
        Returns warning message if partially configured (missing some vars).
        """
        ...

    async def fetch(self) -> IntegrationResult:
        """Fetch data from external service.

        May raise exceptions - caller handles circuit breaker and isolation.
        """
        ...
```

### Pattern 2: Circuit Breaker with Pybreaker
**What:** Protect against cascading failures by tracking failures and entering "open" state
**When to use:** Wrapping every external API call
**Example:**
```python
# Source: pybreaker documentation (https://github.com/danielfm/pybreaker)
import pybreaker

# Per-integration circuit breaker (in-memory, resets on restart)
cloudflare_breaker = pybreaker.CircuitBreaker(
    fail_max=3,           # Open after 3 failures (per CONTEXT.md Claude's discretion)
    reset_timeout=60,     # Try again after 60 seconds
)

@cloudflare_breaker
async def fetch_cloudflare_data():
    """Fetch data from Cloudflare API."""
    # Circuit breaker wraps the call
    # - CLOSED: requests pass through
    # - OPEN: immediately raises CircuitBreakerError
    # - HALF_OPEN: one request allowed to test recovery
    async with httpx.AsyncClient() as client:
        response = await client.get(...)
        return response.json()
```

### Pattern 3: Parallel Execution with Complete Isolation
**What:** Run integrations concurrently using `asyncio.gather(return_exceptions=True)`
**When to use:** Running all configured integrations in parallel with UniFi data collection
**Example:**
```python
# Source: Python asyncio documentation
import asyncio
from typing import List

async def run_integrations_parallel(
    integrations: List[Integration],
) -> List[IntegrationResult]:
    """Run all integrations in parallel with complete isolation.

    One integration failing does NOT affect others (per CONTEXT.md decision).
    """
    async def run_one(integration: Integration) -> IntegrationResult:
        try:
            return await integration.fetch()
        except pybreaker.CircuitBreakerError:
            # Circuit is open - skip silently or with brief log
            return IntegrationResult(
                name=integration.name,
                success=False,
                error="circuit_open",
            )
        except Exception as e:
            # Any other error - log and return failure result
            return IntegrationResult(
                name=integration.name,
                success=False,
                error=str(e),
            )

    # return_exceptions=True ensures one failure doesn't cancel others
    results = await asyncio.gather(
        *[run_one(i) for i in integrations],
        return_exceptions=True,  # Critical for isolation
    )

    # Handle any unexpected exceptions from gather itself
    return [
        r if isinstance(r, IntegrationResult)
        else IntegrationResult(name="unknown", success=False, error=str(r))
        for r in results
    ]
```

### Pattern 4: Credentials-Only Detection (No ENABLED Flags)
**What:** Detect integration availability by presence of ALL required credentials
**When to use:** Determining which integrations to run
**Example:**
```python
# Source: Existing codebase pattern (email_enabled + smtp_host validation)
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from typing import Optional

class UnifiSettings(BaseSettings):
    # Cloudflare integration (optional - all fields must be set to enable)
    cloudflare_api_key: Optional[str] = Field(
        default=None,
        description="Cloudflare API key (integration enabled when all cloudflare_* set)",
    )
    cloudflare_zone_id: Optional[str] = Field(
        default=None,
        description="Cloudflare Zone ID",
    )

    @model_validator(mode="after")
    def validate_cloudflare_config(self) -> "UnifiSettings":
        """Warn if Cloudflare is partially configured."""
        has_key = self.cloudflare_api_key is not None
        has_zone = self.cloudflare_zone_id is not None

        if has_key != has_zone:
            # Partial config - log warning at startup (not error)
            import structlog
            log = structlog.get_logger()
            log.warning(
                "cloudflare_partial_config",
                has_api_key=has_key,
                has_zone_id=has_zone,
                message="Cloudflare integration disabled due to incomplete config",
            )
        return self

    def is_cloudflare_configured(self) -> bool:
        """Check if Cloudflare integration is fully configured."""
        return bool(self.cloudflare_api_key and self.cloudflare_zone_id)
```

### Pattern 5: Integration Registry with Discovery
**What:** Registry that discovers and manages configured integrations
**When to use:** Centralized management of available integrations
**Example:**
```python
from typing import List, Type

class IntegrationRegistry:
    """Registry for available integrations.

    Uses hardcoded list (per CONTEXT.md - no dynamic plugin discovery).
    """

    # All known integration classes (hardcoded, not dynamic)
    _integration_classes: List[Type[Integration]] = []

    @classmethod
    def register(cls, integration_class: Type[Integration]) -> None:
        """Register an integration class (called at module import)."""
        cls._integration_classes.append(integration_class)

    @classmethod
    def get_configured(cls, settings) -> List[Integration]:
        """Get all integrations that are fully configured.

        Returns empty list if no integrations configured (silent skip).
        """
        configured = []
        for integration_class in cls._integration_classes:
            integration = integration_class(settings)
            if integration.is_configured():
                configured.append(integration)
        return configured
```

### Anti-Patterns to Avoid
- **Global exception handlers that swallow errors:** Each integration should handle its own errors and return structured results
- **Shared state between integrations:** Integrations should be completely independent
- **Synchronous execution for integrations:** Use async throughout for true parallelism
- **Single circuit breaker for all integrations:** Each integration needs its own breaker
- **Persisting circuit breaker state:** Per CONTEXT.md, state resets on restart

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circuit breaker | Custom failure counter + timer | pybreaker | State machine logic, race conditions, half-open state handling |
| Parallel async execution | Threading or manual coroutine management | asyncio.gather | Battle-tested, proper exception isolation with return_exceptions |
| Retry with backoff | Custom retry loops | tenacity (already in project) | Exponential backoff, jitter, proper exception filtering |
| HTTP client pooling | Manual connection management | httpx AsyncClient | Connection pooling, timeout handling, proper cleanup |

**Key insight:** The circuit breaker pattern looks simple (count failures, open when threshold exceeded) but has subtle complexity: thread safety, state transitions, half-open testing, and failure classification. Using pybreaker avoids these pitfalls.

## Common Pitfalls

### Pitfall 1: Blocking the Event Loop
**What goes wrong:** Using synchronous HTTP clients (requests) or blocking operations in async code
**Why it happens:** Mixing sync and async code without proper handling
**How to avoid:** Use httpx.AsyncClient for all integration HTTP calls, never use requests in async context
**Warning signs:** Slow report generation, timeouts, one slow integration blocking others

### Pitfall 2: Circuit Breaker Leakage
**What goes wrong:** Circuit breaker state persists across application restarts when it shouldn't
**Why it happens:** Using Redis/file-backed state storage instead of in-memory
**How to avoid:** Use default pybreaker (in-memory state), per CONTEXT.md decision to reset on restart
**Warning signs:** Integration skipped immediately after fresh restart

### Pitfall 3: Swallowed Exceptions Without Logging
**What goes wrong:** Integration failures are silently ignored with no trace
**Why it happens:** Over-aggressive try/except with pass
**How to avoid:** Always log at WARNING/ERROR level when integration fails, return structured error in IntegrationResult
**Warning signs:** Integrations silently missing from reports with no log entry

### Pitfall 4: Not Validating Partial Configuration
**What goes wrong:** Integration starts but fails due to missing second credential
**Why it happens:** Only checking for one of multiple required credentials
**How to avoid:** is_configured() checks ALL required credentials, validate_config() returns warning for partial
**Warning signs:** Runtime errors about missing config despite some vars being set

### Pitfall 5: Timeout Mismanagement
**What goes wrong:** One slow integration delays entire report generation indefinitely
**Why it happens:** No per-integration timeout
**How to avoid:** Set explicit timeout on httpx.AsyncClient (recommend 30s), wrap fetch in asyncio.wait_for
**Warning signs:** Reports delayed by minutes when external service is slow

### Pitfall 6: Not Handling CircuitBreakerError
**What goes wrong:** CircuitBreakerError propagates and crashes report generation
**Why it happens:** Only catching httpx exceptions, not circuit breaker exceptions
**How to avoid:** Explicit except pybreaker.CircuitBreakerError clause in runner
**Warning signs:** Reports failing after integration has repeated failures

## Code Examples

Verified patterns from official sources:

### Circuit Breaker Setup
```python
# Source: pybreaker GitHub (https://github.com/danielfm/pybreaker)
import pybreaker
import structlog

log = structlog.get_logger()

class CircuitBreakerLoggingListener(pybreaker.CircuitBreakerListener):
    """Log circuit breaker state changes (per CONTEXT.md - log once when tripped)."""

    def state_change(self, cb, old_state, new_state):
        if new_state.name == "open":
            log.warning(
                "circuit_breaker_opened",
                integration=cb.name,
                failures=cb.fail_counter,
                message=f"Circuit breaker opened for {cb.name}, will retry after {cb.reset_timeout}s",
            )
        elif new_state.name == "closed":
            log.info(
                "circuit_breaker_closed",
                integration=cb.name,
                message=f"Circuit breaker closed for {cb.name}, integration recovered",
            )

def create_circuit_breaker(name: str) -> pybreaker.CircuitBreaker:
    """Create a circuit breaker for an integration."""
    return pybreaker.CircuitBreaker(
        name=name,
        fail_max=3,  # Open after 3 consecutive failures
        reset_timeout=60,  # Try again after 60 seconds
        listeners=[CircuitBreakerLoggingListener()],
    )
```

### Async Parallel Execution with Timeout
```python
# Source: Python asyncio documentation
import asyncio
from typing import List

INTEGRATION_TIMEOUT = 30  # seconds per integration

async def run_integration_with_timeout(
    integration: Integration,
    breaker: pybreaker.CircuitBreaker,
) -> IntegrationResult:
    """Run a single integration with circuit breaker and timeout."""

    # Check circuit breaker state first (fast path)
    if breaker.current_state == "open":
        return IntegrationResult(
            name=integration.name,
            success=False,
            error="circuit_open",
        )

    try:
        # Wrap the fetch call with circuit breaker
        @breaker
        async def protected_fetch():
            return await asyncio.wait_for(
                integration.fetch(),
                timeout=INTEGRATION_TIMEOUT,
            )

        return await protected_fetch()

    except asyncio.TimeoutError:
        return IntegrationResult(
            name=integration.name,
            success=False,
            error=f"timeout_after_{INTEGRATION_TIMEOUT}s",
        )
    except pybreaker.CircuitBreakerError:
        return IntegrationResult(
            name=integration.name,
            success=False,
            error="circuit_open",
        )
    except Exception as e:
        return IntegrationResult(
            name=integration.name,
            success=False,
            error=str(e),
        )
```

### Integration Result for Report
```python
# Source: Existing codebase pattern (health_analysis in report)
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class IntegrationSection:
    """Section data for a single integration in the report."""
    name: str
    display_name: str  # "Cloudflare Security" for report header
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None  # "Unable to fetch data" if failed

@dataclass
class IntegrationResults:
    """Aggregated results from all integrations for report generation."""
    sections: List[IntegrationSection] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        """Check if any integration returned data."""
        return any(s.success and s.data for s in self.sections)

    def get_section(self, name: str) -> Optional[IntegrationSection]:
        """Get a specific integration's section by name."""
        for section in self.sections:
            if section.name == name:
                return section
        return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ABC + abstractmethod | typing.Protocol | Python 3.8+ | No runtime overhead, duck typing with static checking |
| asyncio.ensure_future | asyncio.create_task | Python 3.7+ | Clearer intent, better debugging |
| asyncio.gather only | asyncio.TaskGroup | Python 3.11+ | Better cancellation semantics (but we target 3.9+, so use gather) |
| pybreaker 1.0 | pybreaker 1.4.1 | Sept 2025 | success_threshold support, better async handling |

**Deprecated/outdated:**
- **Hystrix:** Netflix Hystrix is in maintenance mode; Python equivalents like pybreaker are preferred
- **asyncio.coroutine decorator:** Use async def instead
- **loop.run_until_complete:** Use asyncio.run() for Python 3.7+

## Open Questions

Things that couldn't be fully resolved:

1. **Integration Timeout Duration**
   - What we know: httpx default is 5s, but external APIs may need longer
   - What's unclear: Optimal timeout for Cloudflare/Cybersecure APIs specifically
   - Recommendation: Start with 30s (conservative), make configurable per integration

2. **Circuit Breaker Failure Threshold**
   - What we know: Common values are 3-5 consecutive failures
   - What's unclear: Whether 3 or 5 is better for these specific integrations
   - Recommendation: Use 3 (fail fast), can adjust based on real-world behavior

3. **Logging Level for Integration Failures**
   - What we know: CONTEXT.md mentions WARNING vs ERROR based on context
   - What's unclear: Exact criteria for each level
   - Recommendation: ERROR for unexpected exceptions, WARNING for circuit open/timeout

## Sources

### Primary (HIGH confidence)
- [Python asyncio documentation](https://docs.python.org/3/library/asyncio-task.html) - gather(), return_exceptions, TaskGroup
- [pybreaker PyPI](https://pypi.org/project/pybreaker/) - Version 1.4.1, Python 3.9+ requirement
- [pybreaker GitHub](https://github.com/danielfm/pybreaker) - Configuration options, listener support, state storage

### Secondary (MEDIUM confidence)
- [PEP 544 - Protocols](https://peps.python.org/pep-0544/) - Protocol-based interface pattern
- [pydantic-settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Optional field patterns
- [HTTPX Async Support](https://www.python-httpx.org/async/) - AsyncClient usage patterns

### Tertiary (LOW confidence)
- WebSearch results on circuit breaker best practices - general patterns verified against official docs
- WebSearch results on graceful degradation - general microservices patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pybreaker is well-documented, asyncio.gather is stdlib
- Architecture: HIGH - Patterns match existing codebase (DeviceHealthAnalyzer, tenacity usage)
- Pitfalls: HIGH - Derived from official documentation and common async patterns

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days - stable libraries, no rapid changes expected)
