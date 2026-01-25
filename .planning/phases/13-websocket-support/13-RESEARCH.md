# Phase 13: WebSocket Support - Research

**Researched:** 2026-01-24
**Domain:** Python WebSocket client integration with UniFi Controller API
**Confidence:** HIGH

## Summary

This phase addresses a critical gap discovered during troubleshooting: UniFi Network 10.x+ deprecated the `/stat/event` REST endpoint for WiFi events (roaming, connections, disconnections). These events are now only available via WebSocket at `/proxy/network/wss/s/{site}/events`. The existing scanner gets 0 WiFi events on UniFi Network 10.x+ because it relies solely on REST API.

The research confirms that Python's `websockets` library (v16.0) is the standard choice for asyncio WebSocket clients. It provides built-in reconnection with exponential backoff, automatic ping/pong keepalive, and clean exception handling. The UniFi WebSocket uses cookie-based authentication from the existing REST session, making integration straightforward.

Key architecture decisions: Run WebSocket listener as a background asyncio task, buffer incoming events in an asyncio.Queue, and process the buffer when report generation triggers. The existing synchronous REST client (using httpx) can coexist with an async WebSocket listener by running the WebSocket in a dedicated thread with its own event loop.

**Primary recommendation:** Use the `websockets` library (asyncio API) with a dedicated WebSocket client class that shares authentication cookies from the existing REST session, buffers events in memory, and gracefully falls back to REST-only mode when WebSocket unavailable.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| websockets | 16.0 | Async WebSocket client | Pure Python, RFC 6455 compliant, built-in reconnection, production-ready, actively maintained |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Event loop, Queue, tasks | Already in Python stdlib, required for websockets |
| ssl | stdlib | TLS/certificate handling | Self-signed cert support for UniFi controllers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| websockets | httpx-ws | httpx-ws adds WebSocket to httpx but is less mature; websockets is the de-facto standard |
| websockets | websocket-client | websocket-client is sync-only; websockets supports both sync and async |
| websockets | aiounifi | aiounifi is full UniFi wrapper; too heavy when we only need WebSocket events |

**Installation:**
```bash
pip install websockets>=16.0
```

Note: The project requires Python 3.9+, but websockets 16.0 requires Python 3.10+. Either:
1. Use websockets 14.x for Python 3.9 compatibility
2. Bump minimum Python to 3.10 (recommended since 3.9 EOL is October 2025)

## Architecture Patterns

### Recommended Project Structure
```
src/unifi_scanner/
├── api/
│   ├── client.py           # Existing REST client (unchanged)
│   ├── websocket.py        # NEW: WebSocket client
│   └── endpoints.py        # Add WebSocket endpoint
├── logs/
│   ├── api_collector.py    # Existing REST collector
│   ├── ws_collector.py     # NEW: WebSocket event collector
│   └── collector.py        # Update fallback chain: WS -> REST -> SSH
└── models/
    └── events.py           # NEW: WebSocket event models (if needed)
```

### Pattern 1: Cookie Authentication Reuse
**What:** Share authentication cookies from REST client with WebSocket connection
**When to use:** Always - UniFi WebSocket requires same session cookies as REST
**Example:**
```python
# Source: https://github.com/uchkunrakhimow/unifi-best-practices
from websockets.sync.client import connect
import ssl

def create_websocket_connection(
    base_url: str,
    site: str,
    cookies: dict[str, str],
    verify_ssl: bool = False,
) -> ClientConnection:
    """Create WebSocket connection using REST session cookies."""
    # Convert https:// to wss://
    ws_url = base_url.replace("https://", "wss://")
    endpoint = f"{ws_url}/proxy/network/wss/s/{site}/events"

    # Format cookies as header
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

    # SSL context for self-signed certs
    ssl_context = ssl.create_default_context()
    if not verify_ssl:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    return connect(
        endpoint,
        additional_headers={"Cookie": cookie_header},
        ssl=ssl_context,
    )
```

### Pattern 2: Event Buffer with asyncio.Queue
**What:** Buffer WebSocket events in memory until report generation
**When to use:** When events arrive continuously but processing is periodic
**Example:**
```python
# Source: websockets docs + asyncio.Queue pattern
import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class BufferedEvent:
    timestamp: datetime
    event_type: str
    data: dict[str, Any]

class WebSocketEventBuffer:
    """Thread-safe buffer for WebSocket events."""

    def __init__(self, max_size: int = 10000):
        self._buffer: deque[BufferedEvent] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()

    async def add(self, event: BufferedEvent) -> None:
        async with self._lock:
            self._buffer.append(event)

    async def drain(self) -> list[BufferedEvent]:
        """Remove and return all buffered events."""
        async with self._lock:
            events = list(self._buffer)
            self._buffer.clear()
            return events
```

### Pattern 3: Automatic Reconnection with Backoff
**What:** Use websockets built-in reconnection pattern
**When to use:** For long-running WebSocket connections that must survive network issues
**Example:**
```python
# Source: https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html
import websockets
from websockets.asyncio.client import connect

async def listen_forever(uri: str, buffer: WebSocketEventBuffer):
    """Listen for events with automatic reconnection."""
    async for websocket in connect(uri):
        try:
            async for message in websocket:
                event = parse_event(message)
                if event:
                    await buffer.add(event)
        except websockets.exceptions.ConnectionClosed:
            # Reconnect automatically via iterator
            continue
```

### Pattern 4: Graceful Fallback
**What:** Detect WebSocket availability and fall back to REST-only
**When to use:** When supporting both UniFi 9.x (REST) and 10.x+ (WebSocket)
**Example:**
```python
class WebSocketClient:
    """WebSocket client with graceful fallback."""

    async def connect(self) -> bool:
        """Attempt WebSocket connection. Returns False if unavailable."""
        try:
            self._ws = await asyncio.wait_for(
                connect(self._endpoint, ...),
                timeout=10.0
            )
            return True
        except (OSError, asyncio.TimeoutError, websockets.InvalidStatusCode) as e:
            logger.info("websocket_unavailable", error=str(e))
            return False

    def is_available(self) -> bool:
        return self._ws is not None and self._ws.open
```

### Anti-Patterns to Avoid
- **Blocking the event loop:** Never use `time.sleep()` in async code; use `asyncio.sleep()`
- **Single recv() without loop:** WebSocket handlers must loop to receive multiple messages
- **Checking state instead of catching exceptions:** Use `try/except ConnectionClosed` not `if websocket.open`
- **Ignoring SSL in production:** Always handle self-signed certs explicitly, never silently disable

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reconnection logic | Custom retry loops | `async for ws in connect()` | Built-in exponential backoff (3s to 60s), handles all edge cases |
| Ping/pong keepalive | Manual ping frames | websockets defaults | Auto ping every 20s, closes if no pong in 20s |
| Message framing | Parse WebSocket frames | websockets.recv() | Handles fragmentation, continuation frames automatically |
| SSL/TLS setup | Manual cert handling | ssl.create_default_context() | Proper cert chain validation, hostname checking |
| Thread-safe buffer | Custom locking | asyncio.Queue | Designed for producer-consumer, handles backpressure |

**Key insight:** The websockets library handles RFC 6455 compliance, keepalive, reconnection, and backpressure. Focus implementation on UniFi-specific event parsing and integration with existing code.

## Common Pitfalls

### Pitfall 1: Connection Closes Immediately After Login
**What goes wrong:** WebSocket connects but closes within seconds
**Why it happens:** Missing or incorrect session cookies; UniFi expects same cookies as REST session
**How to avoid:** Extract cookies from httpx client after REST authentication:
```python
cookies = {c.name: c.value for c in client.cookies.jar}
```
**Warning signs:** ConnectionClosed with code 1008 (Policy Violation)

### Pitfall 2: No Events Received Despite Connected
**What goes wrong:** WebSocket stays open but recv() never returns
**Why it happens:** Wrong endpoint URL (missing `/proxy/network` prefix for UDM devices)
**How to avoid:** Use same device-type detection as REST API:
- UDM/UCG: `/proxy/network/wss/s/{site}/events`
- Self-hosted: `/wss/s/{site}/events`
**Warning signs:** Connection stays open indefinitely with no messages

### Pitfall 3: Memory Exhaustion from Event Buffer
**What goes wrong:** Service crashes with OOM after running for days
**Why it happens:** Events accumulate faster than they're processed; unbounded buffer
**How to avoid:** Use bounded deque or asyncio.Queue with maxsize; log when dropping events
**Warning signs:** Increasing memory usage over time; buffer size metrics growing

### Pitfall 4: Deadlock Between Sync REST and Async WebSocket
**What goes wrong:** Application hangs when trying to use both clients
**Why it happens:** Mixing sync httpx client with async websockets in same thread
**How to avoid:** Either:
1. Run WebSocket in separate thread with own event loop
2. Convert REST client to async (httpx.AsyncClient)
3. Use websockets.sync.client (threading API)
**Warning signs:** `RuntimeError: This event loop is already running`

### Pitfall 5: SSL Certificate Verification Failures
**What goes wrong:** WebSocket refuses to connect with SSL errors
**Why it happens:** UniFi controllers use self-signed certificates
**How to avoid:** Configure SSLContext to skip verification (dev) or pin certificate (prod):
```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # Or use cert pinning
```
**Warning signs:** `ssl.SSLCertVerificationError`

### Pitfall 6: Events Missing During Reconnection
**What goes wrong:** WiFi events lost during network blips
**Why it happens:** Gap between disconnect and reconnect; WebSocket doesn't replay history
**How to avoid:** Accept this limitation; document that WebSocket is for real-time only, REST provides historical data
**Warning signs:** Gaps in event timeline correlating with reconnection logs

## Code Examples

Verified patterns from official sources:

### UniFi WebSocket Event Parsing
```python
# Source: https://github.com/uchkunrakhimow/unifi-best-practices
import json
from datetime import datetime
from typing import Optional

def parse_unifi_event(raw_message: str) -> Optional[BufferedEvent]:
    """Parse UniFi WebSocket event message."""
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        return None

    # UniFi wraps events in {"meta": {...}, "data": [...]}
    meta = message.get("meta", {})
    event_type = meta.get("message", "unknown")
    data_list = message.get("data", [])

    # WiFi events we care about
    WIFI_EVENT_TYPES = {
        "sta:sync",      # Client connect/disconnect/update
        "wu.connected",  # Wireless user connected
        "wu.disconnected",
        "wu.roam",       # Wireless user roamed to different AP
        "wu.roam_radio", # Wireless user changed radio on same AP
    }

    if event_type not in WIFI_EVENT_TYPES:
        return None

    return BufferedEvent(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        data=data_list[0] if data_list else {},
    )
```

### Complete WebSocket Client Class
```python
# Source: websockets docs + project patterns
import asyncio
import ssl
from typing import Optional, Callable, Awaitable

import structlog
import websockets
from websockets.asyncio.client import connect, ClientConnection

logger = structlog.get_logger(__name__)

class UnifiWebSocketClient:
    """WebSocket client for UniFi event streaming."""

    def __init__(
        self,
        base_url: str,
        site: str,
        cookies: dict[str, str],
        verify_ssl: bool = False,
        on_event: Optional[Callable[[BufferedEvent], Awaitable[None]]] = None,
    ):
        self._base_url = base_url
        self._site = site
        self._cookies = cookies
        self._verify_ssl = verify_ssl
        self._on_event = on_event
        self._ws: Optional[ClientConnection] = None
        self._running = False

    @property
    def endpoint(self) -> str:
        ws_url = self._base_url.replace("https://", "wss://")
        return f"{ws_url}/proxy/network/wss/s/{self._site}/events"

    def _get_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        if not self._verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def start(self) -> None:
        """Start listening for events with auto-reconnection."""
        self._running = True
        cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())

        while self._running:
            try:
                async for websocket in connect(
                    self.endpoint,
                    additional_headers={"Cookie": cookie_header},
                    ssl=self._get_ssl_context(),
                ):
                    logger.info("websocket_connected", endpoint=self.endpoint)
                    self._ws = websocket
                    try:
                        async for message in websocket:
                            if not self._running:
                                break
                            event = parse_unifi_event(message)
                            if event and self._on_event:
                                await self._on_event(event)
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning(
                            "websocket_disconnected",
                            code=e.code,
                            reason=e.reason,
                        )
                        continue
            except Exception as e:
                logger.error("websocket_error", error=str(e))
                await asyncio.sleep(5)  # Back off before retry

    async def stop(self) -> None:
        """Stop the WebSocket client gracefully."""
        self._running = False
        if self._ws:
            await self._ws.close()
```

### Integration with Existing Sync Scheduler
```python
# Pattern for running async WebSocket alongside sync APScheduler
import threading
import asyncio

class WebSocketManager:
    """Manages WebSocket in background thread."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[UnifiWebSocketClient] = None
        self._buffer = WebSocketEventBuffer()

    def start(self, base_url: str, site: str, cookies: dict) -> None:
        """Start WebSocket listener in background thread."""
        self._client = UnifiWebSocketClient(
            base_url=base_url,
            site=site,
            cookies=cookies,
            on_event=self._buffer.add,
        )
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._client.start())

    def drain_events(self) -> list[BufferedEvent]:
        """Get all buffered events (called from sync context)."""
        if self._loop and self._client:
            future = asyncio.run_coroutine_threadsafe(
                self._buffer.drain(),
                self._loop
            )
            return future.result(timeout=5.0)
        return []

    def stop(self) -> None:
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.stop(),
                self._loop
            )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| REST `/stat/event` for WiFi events | WebSocket `/wss/s/{site}/events` | UniFi Network 10.x (2025) | REST returns 0 WiFi events; must use WebSocket |
| websockets 13.x | websockets 16.0 | Jan 2026 | Python 3.14 support; requires Python 3.10+ |
| websocket-client (sync only) | websockets (sync + async) | 2024 | websockets now has threading API too |

**Deprecated/outdated:**
- `/stat/event` REST endpoint: Still returns IPS/alarms but no longer returns WiFi events on UniFi 10.x+
- websockets.connect() with `async with`: Replaced by `async for` for auto-reconnection

## Open Questions

Things that couldn't be fully resolved:

1. **Exact UniFi version that deprecated WiFi REST events**
   - What we know: Confirmed broken in UniFi Network 10.x based on user troubleshooting
   - What's unclear: Exact version (10.0? 10.1?) and if there's a config to re-enable
   - Recommendation: Assume 10.x+ requires WebSocket; implement version detection if needed

2. **WebSocket event schema documentation**
   - What we know: Event types (sta:sync, wu.connected, etc.) and general structure
   - What's unclear: Complete field documentation; may vary by UniFi version
   - Recommendation: Parse defensively; log unknown fields for future schema expansion

3. **Certificate pinning for production**
   - What we know: Self-signed certs are common; disabling verification works
   - What's unclear: Best practice for pinning in long-running services
   - Recommendation: Start with verify_ssl=False (matching current REST behavior); add pinning later

## Sources

### Primary (HIGH confidence)
- [websockets 16.0 documentation](https://websockets.readthedocs.io/en/stable/) - Client API, reconnection patterns, exceptions
- [websockets PyPI](https://pypi.org/project/websockets/) - Version 16.0, Python requirements
- [websockets asyncio client reference](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html) - connect(), recv(), headers
- [websockets threading client reference](https://websockets.readthedocs.io/en/stable/reference/sync/client.html) - Sync API alternative

### Secondary (MEDIUM confidence)
- [unifi-best-practices](https://github.com/uchkunrakhimow/unifi-best-practices) - WebSocket endpoint, cookie auth, event types
- [unifi-events](https://github.com/oznu/unifi-events) - Event types (wu.connected, wu.roam, etc.)
- [aiounifi](https://github.com/Kane610/aiounifi) - Architecture patterns for UniFi WebSocket integration
- [unificontrol SSL docs](https://unificontrol.readthedocs.io/en/latest/ssl_self_signed.html) - Self-signed certificate handling

### Tertiary (LOW confidence)
- Community forum posts about UniFi 10.x REST API changes - Need validation against official Ubiquiti docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - websockets library is well-documented, actively maintained, de-facto standard
- Architecture: HIGH - Patterns verified from official docs and production libraries (aiounifi, Home Assistant)
- Pitfalls: MEDIUM - Based on community experience and library issue trackers
- UniFi-specific: MEDIUM - Based on reverse-engineered API, not official Ubiquiti documentation

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - websockets is stable; UniFi API may change)
