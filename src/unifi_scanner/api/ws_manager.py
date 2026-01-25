"""WebSocket manager for background thread operation.

This module bridges async WebSocket operation with the synchronous scheduler.
The WebSocketManager runs the async WebSocket client in a daemon background
thread with its own event loop, while providing sync-friendly methods for
draining events.

Features:
- Background thread with isolated event loop
- Thread-safe event buffer accessible from sync context
- Graceful shutdown with timeout
- Automatic reconnection via UnifiWebSocketClient

Example usage:
    from unifi_scanner.api import WebSocketManager
    from unifi_scanner.models import DeviceType

    manager = WebSocketManager()
    manager.start(
        base_url="https://192.168.1.1",
        site="default",
        cookies={"TOKEN": "abc123"},
        device_type=DeviceType.UDM_PRO,
    )

    # From sync scheduler:
    events = manager.drain_events()

    # On shutdown:
    manager.stop()
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import structlog

from unifi_scanner.api.websocket import (
    BufferedEvent,
    UnifiWebSocketClient,
    WebSocketEventBuffer,
)
from unifi_scanner.models import DeviceType

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class WebSocketManager:
    """Manager for WebSocket client running in background thread.

    Bridges async WebSocket operation with synchronous scheduler context.
    Runs WebSocket in a daemon thread with its own event loop, buffering
    events that can be drained from the main thread.

    Attributes:
        _thread: Background thread running the event loop.
        _loop: Event loop for async WebSocket operations.
        _client: The WebSocket client instance.
        _buffer: Thread-safe buffer for events.
        _running: Flag to control shutdown.

    Example:
        manager = WebSocketManager()
        manager.start(
            base_url="https://192.168.1.1",
            site="default",
            cookies={"TOKEN": "abc123"},
            device_type=DeviceType.UDM_PRO,
        )

        # From sync context:
        events = manager.drain_events()

        # Shutdown:
        manager.stop()
    """

    def __init__(self) -> None:
        """Initialize the WebSocket manager.

        Constructor takes no args for lazy initialization.
        Call start() to begin WebSocket connection.
        """
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: UnifiWebSocketClient | None = None
        self._buffer: WebSocketEventBuffer = WebSocketEventBuffer()
        self._running: bool = False

    def start(
        self,
        base_url: str,
        site: str,
        cookies: dict[str, str],
        device_type: DeviceType,
        verify_ssl: bool = False,
    ) -> None:
        """Start the WebSocket client in a background thread.

        Creates UnifiWebSocketClient and starts background thread running
        the async event loop.

        Args:
            base_url: Base URL of the UniFi controller.
            site: Site name to connect to.
            cookies: Authentication cookies from REST session.
            device_type: Type of UniFi controller.
            verify_ssl: Whether to verify SSL certificates (default: False).
        """
        if self._running:
            logger.warning("websocket_manager_already_running")
            return

        # Create the WebSocket client
        self._client = UnifiWebSocketClient(
            base_url=base_url,
            site=site,
            cookies=cookies,
            device_type=device_type,
            verify_ssl=verify_ssl,
        )

        self._running = True

        # Create and start the background thread
        self._thread = threading.Thread(
            target=self._run_loop,
            name="websocket-manager",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "websocket_manager_started",
            base_url=base_url,
            site=site,
            device_type=device_type.value,
        )

    def _on_event(self, event: BufferedEvent) -> None:
        """Handle incoming WebSocket event.

        Callback passed to client.listen(). Adds parsed WiFi events
        to the thread-safe buffer.

        Args:
            event: Parsed WiFi event from WebSocket.
        """
        self._buffer.add(event)
        logger.debug(
            "websocket_event_buffered",
            event_type=event.event_type,
            buffer_size=len(self._buffer),
        )

    def _run_loop(self) -> None:
        """Run the async event loop in the background thread.

        Creates a new event loop for this thread and runs the WebSocket
        client's connect and listen methods.
        """
        # Create new event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            # Run the async main logic
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            logger.error(
                "websocket_manager_loop_error",
                error=str(e),
                error_type=type(e).__name__,
            )
        finally:
            # Clean up the loop
            self._loop.close()
            self._loop = None

    async def _async_main(self) -> None:
        """Main async logic for WebSocket operation.

        Connects to WebSocket and listens for events until stopped.
        """
        if self._client is None:
            return

        try:
            # Attempt connection
            connected = await self._client.connect()
            if not connected:
                logger.warning("websocket_manager_connection_failed")
                return

            # Listen for events (runs until stop() is called)
            await self._client.listen(self._on_event)

        except Exception as e:
            logger.error(
                "websocket_manager_error",
                error=str(e),
                error_type=type(e).__name__,
            )

    def drain_events(self) -> list[BufferedEvent]:
        """Drain and return all buffered events.

        Thread-safe method called from sync context (main thread).

        Returns:
            List of all buffered events. Empty list if not running.
        """
        if not self._running:
            return []

        return self._buffer.drain()

    def stop(self) -> None:
        """Stop the WebSocket manager gracefully.

        Stops the client, closes the event loop, and waits for the
        background thread to join.
        """
        if not self._running:
            return

        self._running = False

        # Schedule client stop in the background loop
        if self._loop is not None and self._client is not None:
            try:
                # Schedule stop coroutine from outside the loop
                asyncio.run_coroutine_threadsafe(
                    self._client.stop(),
                    self._loop,
                )
            except Exception as e:
                logger.debug(
                    "websocket_manager_stop_schedule_error",
                    error=str(e),
                )

        # Wait for thread to join with timeout
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("websocket_manager_thread_timeout")
            self._thread = None

        self._client = None

        logger.info("websocket_manager_stopped")

    def is_running(self) -> bool:
        """Check if the manager is running.

        Returns:
            True if background thread is alive and client is connected.
        """
        if self._thread is None or not self._thread.is_alive():
            return False

        if self._client is None:
            return False

        return self._client.is_connected()
