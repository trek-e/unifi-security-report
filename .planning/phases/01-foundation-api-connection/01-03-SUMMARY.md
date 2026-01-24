---
phase: 01-foundation-api-connection
plan: 03
subsystem: api
tags: [httpx, unifi-api, authentication, device-detection, session-management]

# Dependency graph
requires:
  - phase: 01-01
    provides: Configuration system with UnifiSettings
  - phase: 01-02
    provides: DeviceType enum
provides:
  - UnifiClient for connecting to UniFi controllers
  - Automatic device type detection (UDM vs self-hosted)
  - Authentication with session cookie management
  - Site discovery and auto-selection
  - Custom API exceptions with troubleshooting hints
affects: [01-04, 02-01, log-collection]

# Tech tracking
tech-stack:
  added: []
  patterns: [httpx-client-cookies, context-manager, device-detection-by-port]

key-files:
  created:
    - src/unifi_scanner/api/__init__.py
    - src/unifi_scanner/api/client.py
    - src/unifi_scanner/api/auth.py
    - src/unifi_scanner/api/endpoints.py
    - src/unifi_scanner/api/exceptions.py
  modified: []

key-decisions:
  - "Device detection probes /status endpoint on ports 443, 8443, 11443 in order"
  - "Port 443 indicates UDM-type device, 8443/11443 indicates self-hosted"
  - "Session cookies managed automatically by httpx.Client"
  - "Password never logged at any level, username at DEBUG only"
  - "Logout is best-effort - errors logged but not raised"

patterns-established:
  - "Context manager pattern for resource cleanup"
  - "Custom exceptions with hint attribute for user-friendly error messages"
  - "Endpoints dataclass for type-safe API path definitions"

# Metrics
duration: 4min
completed: 2026-01-24
---

# Phase 01 Plan 03: UniFi API Client Summary

**UnifiClient with auto-detect device type, authenticate with local credentials, and discover sites**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-24T15:38:25Z
- **Completed:** 2026-01-24T15:42:15Z
- **Tasks:** 3
- **Files created:** 5

## Accomplishments

- Created custom exceptions with helpful troubleshooting hints for non-experts
- AuthenticationError reminds users about LOCAL admin requirement vs cloud SSO
- ConnectionError lists common ports and suggests checking if controller is running
- MultipleSitesError includes list of available sites for easy configuration
- Device detection probes /status endpoint on ports 443, 8443, 11443
- UDM devices use /api/auth/login and /proxy/network prefix
- Self-hosted uses /api/login with no prefix
- UnifiClient works as context manager for clean resource handling
- Site auto-selection when only one site exists

## Task Commits

Each task was committed atomically:

1. **Task 1: Create API exceptions and endpoint definitions** - `32793fa` (feat)
2. **Task 2: Implement device detection and authentication** - `7fec3e3` (feat)
3. **Task 3: Implement UnifiClient with site discovery** - `2e5bc45` (feat)

## Files Created/Modified

- `src/unifi_scanner/api/__init__.py` - Module exports (UnifiClient, exceptions, endpoints)
- `src/unifi_scanner/api/exceptions.py` - Custom exceptions with exit codes and hints
- `src/unifi_scanner/api/endpoints.py` - Endpoint definitions for UDM and self-hosted
- `src/unifi_scanner/api/auth.py` - Device detection and authentication logic
- `src/unifi_scanner/api/client.py` - UnifiClient with site discovery

## Decisions Made

1. **Port detection order:** 443 (UDM), 8443 (self-hosted), 11443 (UniFi OS Server) - matches research findings

2. **Device type by port:** Port 443 is treated as UDM-type since only UDM devices serve on 443. Response content analyzed for 8443/11443.

3. **Best-effort logout:** logout() catches all exceptions to avoid masking real errors on disconnect.

4. **Exception inheritance:** All exceptions inherit from UnifiAPIError, allowing catch-all handling while preserving specific error types.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed successfully.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- UnifiClient provides foundation for all API operations
- Ready for Plan 04: Session management and auto re-authentication
- Client maintains session cookie for authenticated requests
- Site selection integrated, ready for site-specific API calls

---
*Phase: 01-foundation-api-connection*
*Completed: 2026-01-24*
