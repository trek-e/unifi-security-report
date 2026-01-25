---
phase: 10-integration-infrastructure
plan: 02
subsystem: integrations
tags: [pybreaker, circuit-breaker, asyncio, parallel-execution]

# Dependency graph
requires:
  - phase: 10-01
    provides: Integration Protocol, IntegrationResult, IntegrationRegistry, base types
provides:
  - IntegrationRunner with parallel execution
  - Per-integration circuit breakers (fail_max=3, reset_timeout=60)
  - 30-second timeout per integration
  - Complete failure isolation between integrations
affects:
  - 10-03 (Integration tests and wiring)
  - 11-cloudflare-integration
  - 12-cybersecure-integration

# Tech tracking
tech-stack:
  added: []  # pybreaker already in dependencies
  patterns:
    - "calling() context manager for async circuit breaker support"
    - "asyncio.gather(return_exceptions=True) for parallel isolation"
    - "Per-integration circuit breaker caching"

key-files:
  created:
    - src/unifi_scanner/integrations/runner.py
  modified:
    - src/unifi_scanner/integrations/__init__.py

key-decisions:
  - "Use calling() context manager instead of @breaker decorator for async support"
  - "Circuit breaker fail_max=3 for quick failure detection"
  - "Circuit breaker reset_timeout=60 seconds for recovery testing"
  - "Error messages include specific reason for debugging"

patterns-established:
  - "calling() context manager: pybreaker decorator doesn't track async failures, use calling() instead"
  - "Failure isolation: asyncio.gather(return_exceptions=True) prevents one failure from affecting others"
  - "Circuit breaker caching: get_circuit_breaker() returns same instance for same integration name"

# Metrics
duration: 6min
completed: 2026-01-25
---

# Phase 10 Plan 02: IntegrationRunner Summary

**IntegrationRunner with per-integration circuit breakers (pybreaker) and asyncio.gather parallel execution with complete failure isolation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-25T15:53:41Z
- **Completed:** 2026-01-25T15:59:12Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- IntegrationRunner runs all configured integrations in parallel using asyncio.gather
- Per-integration circuit breakers prevent cascading failures (fail_max=3, reset_timeout=60)
- 30-second timeout per integration prevents slow integrations from blocking
- Complete failure isolation ensures one integration failing doesn't affect others

## Task Commits

Each task was committed atomically:

1. **Task 1: Create circuit breaker utilities** - `11ffefe` (feat)
2. **Task 2: Create IntegrationRunner with parallel execution** - `d68fb79` (feat)
3. **Fix: Use calling() context manager for async support** - `92b4a39` (fix)

## Files Created/Modified
- `src/unifi_scanner/integrations/runner.py` - IntegrationRunner, circuit breaker utilities, parallel execution
- `src/unifi_scanner/integrations/__init__.py` - Added IntegrationRunner to exports

## Decisions Made
- **calling() vs @breaker decorator:** The pybreaker @breaker decorator doesn't properly track failures for async functions. Discovered during testing that fail_counter stayed at 0. Switched to calling() context manager which correctly tracks async failures.
- **Error message format:** Error messages include specific failure reason (timeout, circuit_open, or exception message) in parentheses for debugging while maintaining "Unable to fetch data" prefix per CONTEXT.md.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created virtual environment for dependency installation**
- **Found during:** Initial setup
- **Issue:** pybreaker was in pyproject.toml but not installed (no active venv)
- **Fix:** Created .venv and installed project with dev dependencies
- **Files modified:** .venv/ (new)
- **Verification:** `import pybreaker` succeeds
- **Committed in:** N/A (development environment setup)

**2. [Rule 1 - Bug] Fixed async circuit breaker tracking**
- **Found during:** Test execution
- **Issue:** pybreaker @breaker decorator doesn't track failures for async functions - fail_counter stayed at 0
- **Fix:** Changed to use calling() context manager which properly supports async code
- **Files modified:** src/unifi_scanner/integrations/runner.py
- **Verification:** Circuit breaker tests pass, fail_counter increments correctly
- **Committed in:** 92b4a39

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correct operation. The calling() fix was essential for circuit breaker functionality.

## Issues Encountered
- pybreaker async support: The @breaker decorator silently fails to track async function failures. This is a known limitation in pybreaker 1.4.1. The calling() context manager works correctly for both sync and async code.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- IntegrationRunner ready for use by IntegrationOrchestrator (10-03)
- Circuit breaker infrastructure complete for future integrations
- All 30 integration tests passing

---
*Phase: 10-integration-infrastructure*
*Completed: 2026-01-25*
