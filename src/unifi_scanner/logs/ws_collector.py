"""WebSocket-based log collector for UniFi controllers.

Converts WebSocket buffered events to LogEntry format, providing
a consistent interface with the existing API and SSH collectors.

This collector works with the WebSocketManager to retrieve buffered
events collected from the real-time WebSocket stream.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from unifi_scanner.models import LogEntry, LogSource

if TYPE_CHECKING:
    from unifi_scanner.api import BufferedEvent, WebSocketManager

logger = structlog.get_logger(__name__)

# Clock skew tolerance for timestamp filtering (matches API collector)
CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)

# Event type to message format mapping
EVENT_MESSAGE_FORMATS = {
    "wu.connected": "Client {mac} connected to {ap}",
    "wu.disconnected": "Client {mac} disconnected from {ap}",
    "wu.roam": "Client {mac} roamed from {ap} to {ap_to}",
    "wu.roam_radio": "Client {mac} switched radio on {ap}",
    "sta:sync": "Client {mac} state sync",
}

# Event type to log level mapping
EVENT_LEVELS = {
    "wu.connected": "INFO",
    "wu.disconnected": "INFO",
    "wu.roam": "INFO",
    "wu.roam_radio": "INFO",
    "sta:sync": "DEBUG",
}


class WSCollectionError(Exception):
    """Raised when WebSocket log collection fails."""

    def __init__(
        self,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        """Initialize the collection error.

        Args:
            message: Error description.
            cause: Underlying exception if any.
        """
        self.message = message
        self.cause = cause
        super().__init__(message)


class WSLogCollector:
    """Collects logs from WebSocket buffered events.

    Converts BufferedEvent objects from WebSocketManager into LogEntry
    format, consistent with APILogCollector and SSHLogCollector.

    Example:
        manager = WebSocketManager()
        manager.start(...)

        collector = WSLogCollector(manager, since_timestamp=last_run)
        entries = collector.collect()
    """

    def __init__(
        self,
        manager: WebSocketManager,
        since_timestamp: datetime | None = None,
    ) -> None:
        """Initialize the WebSocket log collector.

        Args:
            manager: WebSocketManager instance to drain events from.
            since_timestamp: Only include events newer than this timestamp (UTC).
                A 5-minute clock skew tolerance is applied.
        """
        self.manager = manager
        self.since_timestamp = since_timestamp

    def collect(self) -> list[LogEntry]:
        """Collect logs from WebSocket buffer.

        Drains all buffered events from the manager, filters by
        timestamp if configured, and converts to LogEntry format.

        Returns:
            List of LogEntry objects from WebSocket events.

        Raises:
            WSCollectionError: If collection fails.
        """
        try:
            # Drain events from manager buffer
            events = self.manager.drain_events()

            if not events:
                logger.debug("ws_collection_empty")
                return []

            # Filter by since_timestamp if provided
            if self.since_timestamp:
                effective_cutoff = self.since_timestamp - CLOCK_SKEW_TOLERANCE
                original_count = len(events)
                events = [
                    e for e in events
                    if e.timestamp > effective_cutoff
                ]
                logger.debug(
                    "ws_events_filtered",
                    before_filter=original_count,
                    after_filter=len(events),
                    since=self.since_timestamp.isoformat(),
                    effective_cutoff=effective_cutoff.isoformat(),
                )

            # Convert to LogEntry
            entries = [self._to_log_entry(e) for e in events]

            logger.info(
                "ws_collection_complete",
                events_collected=len(entries),
            )

            return entries

        except Exception as e:
            raise WSCollectionError(
                message=f"WebSocket collection failed: {e}",
                cause=e,
            ) from e

    def _to_log_entry(self, event: BufferedEvent) -> LogEntry:
        """Convert a BufferedEvent to LogEntry.

        Args:
            event: Buffered WebSocket event.

        Returns:
            LogEntry with mapped fields.
        """
        # Extract MAC address from event data
        mac = event.data.get("mac", "unknown")

        # Extract AP information
        ap = event.data.get("ap_name") or event.data.get("ap", "unknown")
        ap_to = event.data.get("ap_to_name") or event.data.get("ap_to", "")

        # Format message based on event type
        message_format = EVENT_MESSAGE_FORMATS.get(
            event.event_type,
            "{event_type}: {mac}",
        )
        message = message_format.format(
            mac=mac,
            ap=ap,
            ap_to=ap_to,
            event_type=event.event_type,
        )

        # Get log level for metadata
        level = EVENT_LEVELS.get(event.event_type, "INFO")

        # Build metadata
        metadata = {
            "level": level,
            "source_type": "websocket",
        }

        return LogEntry(
            timestamp=event.timestamp,
            source=LogSource.WEBSOCKET,
            device_mac=mac if mac != "unknown" else None,
            device_name=ap if ap != "unknown" else None,
            event_type=event.event_type,
            message=message,
            raw_data=event.data,
            metadata=metadata,
        )
