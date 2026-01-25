"""WebSocket client for UniFi event streaming.

This module provides WebSocket connectivity for real-time event streaming from
UniFi controllers running UniFi Network 10.x+. In these versions, WiFi events
(roaming, connections, disconnections) are no longer available via the REST
`/stat/event` endpoint and must be collected via WebSocket.

Features:
- Cookie-based authentication (shares session with REST client)
- Self-signed certificate support
- Automatic reconnection with backoff
- Thread-safe event buffering

Example usage:
    from unifi_scanner.api import UnifiWebSocketClient, WebSocketEventBuffer

    buffer = WebSocketEventBuffer()
    client = UnifiWebSocketClient(
        base_url="https://192.168.1.1",
        site="default",
        cookies={"TOKEN": "abc123"},
        device_type=DeviceType.UDM_PRO,
        verify_ssl=False,
    )

    # In async context:
    connected = await client.connect()
    if connected:
        await client.listen(buffer.add)
"""

from __future__ import annotations

import contextlib
import json
import ssl
import threading
from collections import deque
from collections.abc import Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

import structlog

from unifi_scanner.models import DeviceType

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

logger = structlog.get_logger(__name__)

# WiFi event types we care about from WebSocket stream
WIFI_EVENT_TYPES = frozenset(
    {
        "sta:sync",  # Client connect/disconnect/update
        "wu.connected",  # Wireless user connected
        "wu.disconnected",  # Wireless user disconnected
        "wu.roam",  # Wireless user roamed to different AP
        "wu.roam_radio",  # Wireless user changed radio on same AP
    }
)


@dataclass
class BufferedEvent:
    """A parsed event from the UniFi WebSocket stream.

    Attributes:
        timestamp: When the event was received (UTC).
        event_type: Type of event (e.g., "wu.roam", "wu.connected").
        data: Raw event payload from UniFi.
    """

    timestamp: datetime
    event_type: str
    data: dict[str, Any] = field(default_factory=dict)


class WebSocketEventBuffer:
    """Thread-safe buffer for WebSocket events.

    Uses a bounded deque to prevent memory exhaustion during long-running
    operation. When buffer is full, oldest events are dropped.

    Uses threading.Lock (not asyncio.Lock) for cross-thread safety, enabling
    the WebSocket listener to run in a background thread while the main
    synchronous scheduler can drain events.

    Attributes:
        max_size: Maximum number of events to buffer (default: 10000).

    Example:
        buffer = WebSocketEventBuffer(max_size=5000)

        # From async WebSocket listener
        buffer.add(event)

        # From sync scheduler
        events = buffer.drain()
    """

    def __init__(self, max_size: int = 10000) -> None:
        """Initialize the event buffer.

        Args:
            max_size: Maximum number of events to store. Oldest events are
                dropped when limit is reached.
        """
        self._buffer: deque[BufferedEvent] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._max_size = max_size

    def add(self, event: BufferedEvent) -> None:
        """Add an event to the buffer.

        Thread-safe. If buffer is full, oldest event is dropped automatically.

        Args:
            event: The parsed event to buffer.
        """
        with self._lock:
            self._buffer.append(event)

    def drain(self) -> list[BufferedEvent]:
        """Remove and return all buffered events.

        Thread-safe. Returns an empty list if no events buffered.

        Returns:
            List of all buffered events in order received.
        """
        with self._lock:
            events = list(self._buffer)
            self._buffer.clear()
            return events

    def __len__(self) -> int:
        """Return the number of buffered events."""
        with self._lock:
            return len(self._buffer)


def parse_unifi_event(raw_message: str) -> BufferedEvent | None:
    """Parse a UniFi WebSocket event message.

    UniFi WebSocket messages are JSON with structure:
    {"meta": {"message": "event_type", ...}, "data": [{...}]}

    Only WiFi-related events are returned; other events return None.

    Args:
        raw_message: Raw JSON string from WebSocket.

    Returns:
        BufferedEvent if this is a WiFi event, None otherwise.
    """
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        logger.warning("websocket_invalid_json", message=raw_message[:100])
        return None

    meta = message.get("meta", {})
    event_type = meta.get("message", "unknown")
    data_list = message.get("data", [])

    # Filter for WiFi events only
    if event_type not in WIFI_EVENT_TYPES:
        return None

    return BufferedEvent(
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        data=data_list[0] if data_list else {},
    )


class UnifiWebSocketClient:
    """WebSocket client for UniFi event streaming.

    Connects to UniFi controller WebSocket endpoint using authentication
    cookies from an existing REST session. Supports both UDM-type devices
    (UDM Pro, UCG Ultra) and self-hosted controllers.

    Attributes:
        base_url: Base URL of the controller (e.g., "https://192.168.1.1:443").
        site: Site name (e.g., "default").
        device_type: Type of UniFi controller (UDM_PRO or SELF_HOSTED).
        verify_ssl: Whether to verify SSL certificates.

    Example:
        client = UnifiWebSocketClient(
            base_url="https://192.168.1.1",
            site="default",
            cookies={"TOKEN": "abc123"},
            device_type=DeviceType.UDM_PRO,
            verify_ssl=False,
        )

        async with client:
            await client.listen(on_event=handle_event)
    """

    def __init__(
        self,
        base_url: str,
        site: str,
        cookies: dict[str, str],
        device_type: DeviceType,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the WebSocket client.

        Args:
            base_url: Base URL of the UniFi controller.
            site: Site name to connect to.
            cookies: Authentication cookies from REST session.
            device_type: Type of UniFi controller.
            verify_ssl: Whether to verify SSL certificates (default: False).
        """
        self._base_url = base_url
        self._site = site
        self._cookies = cookies
        self._device_type = device_type
        self._verify_ssl = verify_ssl
        self._ws: ClientConnection | None = None
        self._running = False

    @property
    def endpoint(self) -> str:
        """Get the WebSocket endpoint URL.

        UDM devices use /proxy/network prefix, self-hosted do not.
        """
        # Strip trailing slash and convert https:// to wss://
        base = self._base_url.rstrip("/")
        ws_url = base.replace("https://", "wss://").replace("http://", "ws://")

        # Choose correct prefix based on device type
        if self._device_type == DeviceType.UDM_PRO:
            return f"{ws_url}/proxy/network/wss/s/{self._site}/events"
        return f"{ws_url}/wss/s/{self._site}/events"

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for WebSocket connection.

        Returns:
            SSLContext configured based on verify_ssl setting.
        """
        ctx = ssl.create_default_context()
        if not self._verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _get_cookie_header(self) -> str:
        """Format cookies as HTTP header value."""
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    async def connect(self) -> bool:
        """Attempt to establish WebSocket connection.

        Returns:
            True if connected successfully, False if WebSocket unavailable.
        """
        import asyncio

        import websockets

        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self.endpoint,
                    additional_headers={"Cookie": self._get_cookie_header()},
                    ssl=self._get_ssl_context(),
                ),
                timeout=10.0,
            )
            self._running = True
            logger.info(
                "websocket_connected",
                endpoint=self.endpoint,
                device_type=self._device_type.value,
            )
            return True

        except asyncio.TimeoutError:
            logger.warning("websocket_timeout", endpoint=self.endpoint)
            return False

        except websockets.exceptions.InvalidHandshake as e:
            logger.warning(
                "websocket_handshake_failed",
                endpoint=self.endpoint,
                error=str(e),
            )
            return False

        except OSError as e:
            logger.warning(
                "websocket_connection_error",
                endpoint=self.endpoint,
                error=str(e),
            )
            return False

    async def listen(
        self,
        on_event: Callable[[BufferedEvent], None]
        | Callable[[BufferedEvent], Coroutine[Any, Any, None]],
    ) -> None:
        """Listen for events with automatic reconnection.

        Loops indefinitely, receiving WebSocket messages and passing parsed
        WiFi events to the callback. Automatically reconnects on disconnect.

        Args:
            on_event: Callback invoked for each WiFi event. Can be sync or async.
        """
        import asyncio
        import inspect

        import websockets

        while self._running:
            if (self._ws is None or self._ws.state.name != "OPEN") and not await self.connect():
                # Connection failed, back off and retry
                await asyncio.sleep(5.0)
                continue

            try:
                assert self._ws is not None
                async for message in self._ws:
                    if not self._running:
                        break

                    event = parse_unifi_event(message)
                    if event:
                        # Support both sync and async callbacks
                        result = on_event(event)
                        if inspect.isawaitable(result):
                            await result

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(
                    "websocket_disconnected",
                    code=e.code,
                    reason=e.reason,
                )
                self._ws = None
                # Small backoff before reconnection attempt
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error("websocket_error", error=str(e), error_type=type(e).__name__)
                self._ws = None
                await asyncio.sleep(5.0)

    async def stop(self) -> None:
        """Stop the WebSocket client gracefully.

        Closes the connection and stops the listen loop.
        """
        self._running = False
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None
        logger.debug("websocket_stopped")

    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        return self._ws is not None and self._ws.state.name == "OPEN"

    async def __aenter__(self) -> UnifiWebSocketClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.stop()
