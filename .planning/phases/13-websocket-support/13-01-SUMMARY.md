---
phase: 13-websocket-support
plan: 01
subsystem: api
tags: [websockets, async, real-time, events]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: API client architecture, DeviceType enum
provides:
  - UnifiWebSocketClient class for real-time event streaming
  - WebSocketEventBuffer for thread-safe event collection
  - BufferedEvent dataclass for parsed events
  - parse_unifi_event function for filtering WiFi events
affects: [13-02, 13-03, 13-04, logs-collection]

# Tech tracking
tech-stack:
  added: [websockets>=14.0]
  patterns: [async-websocket-client, thread-safe-buffer, cookie-auth-reuse]

key-files:
  created:
    - src/unifi_scanner/api/websocket.py
  modified:
    - pyproject.toml
    - src/unifi_scanner/api/__init__.py

key-decisions:
  - "websockets>=14.0 for Python 3.9 compatibility (16.x needs 3.10+)"
  - "threading.Lock instead of asyncio.Lock for cross-thread buffer safety"
  - "Device-type-aware endpoint selection (UDM vs self-hosted)"

patterns-established:
  - "Cookie header reuse from REST session for WebSocket auth"
  - "Bounded deque with maxlen for memory-safe buffering"

# Metrics
duration: 5min
completed: 2026-01-25
---

# Phase 13 Plan 01: Core WebSocket Client Summary

**WebSocket client infrastructure for UniFi Network 10.x+ real-time event streaming with cookie-based authentication and thread-safe buffering**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-25T03:47:26Z
- **Completed:** 2026-01-25T03:52:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added websockets>=14.0 dependency for async WebSocket client
- Created UnifiWebSocketClient with connect/listen/stop methods
- Created WebSocketEventBuffer for thread-safe event collection (max 10k events)
- Created BufferedEvent dataclass for parsed WiFi events
- Implemented parse_unifi_event for filtering relevant WiFi event types
- Support for both UDM and self-hosted controller WebSocket endpoints
- Self-signed certificate handling via configurable SSL context

## Task Commits

Each task was committed atomically:

1. **Task 1: Add websockets dependency** - `40b9e03` (chore)
2. **Task 2: Create WebSocket client** - `7f759df` (feat)

Note: Task 2 was implemented via TDD in plan 13-02 but satisfies 13-01 requirements.

## Files Created/Modified

- `pyproject.toml` - Added websockets>=14.0 dependency
- `src/unifi_scanner/api/websocket.py` - New WebSocket client module (388 lines)
- `src/unifi_scanner/api/__init__.py` - Export WebSocket classes

## Decisions Made

1. **websockets>=14.0 minimum** - Maintains Python 3.9 compatibility while allowing pip to install 16.x on Python 3.10+
2. **threading.Lock for buffer** - Enables WebSocket listener in background thread while sync scheduler drains events
3. **Device-type parameter** - Reuses DeviceType enum to select correct WebSocket endpoint prefix

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WebSocket client ready for integration with collector
- Plan 13-02 (TDD tests) already complete
- Ready for 13-03: Log collector fallback chain integration

---
*Phase: 13-websocket-support*
*Completed: 2026-01-25*
