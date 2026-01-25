"""Orchestrating log collector with fallback chain.

Tries WebSocket first (for WiFi events), then REST API, then falls back
to SSH if API fails or returns insufficient entries.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

import structlog

from unifi_scanner.api import UnifiClient
from unifi_scanner.config import UnifiSettings
from unifi_scanner.models import DeviceType, LogEntry

from .api_collector import APICollectionError, APILogCollector
from .ssh_collector import SSHCollectionError, SSHLogCollector
from .ws_collector import WSCollectionError, WSLogCollector

if TYPE_CHECKING:
    from unifi_scanner.api import WebSocketManager

logger = structlog.get_logger(__name__)


class LogCollectionError(Exception):
    """Raised when all log collection sources fail."""

    def __init__(
        self,
        message: str,
        api_error: Optional[Exception] = None,
        ssh_error: Optional[Exception] = None,
    ) -> None:
        self.message = message
        self.api_error = api_error
        self.ssh_error = ssh_error
        super().__init__(message)


class LogCollector:
    """Orchestrates log collection from multiple sources.

    Implements a fallback chain:
    1. Try API collection first (preferred, non-invasive)
    2. Fall back to SSH if API fails or returns too few entries
    3. Raise LogCollectionError if all sources fail

    Example:
        >>> with UnifiClient(settings) as client:
        ...     site = client.select_site()
        ...     collector = LogCollector(
        ...         client=client,
        ...         settings=settings,
        ...         site=site,
        ...     )
        ...     entries = collector.collect()
    """

    def __init__(
        self,
        client: UnifiClient,
        settings: UnifiSettings,
        site: str,
        device_type: Optional[DeviceType] = None,
        min_entries: int = 10,
        ws_manager: Optional["WebSocketManager"] = None,
    ) -> None:
        """Initialize the log collector.

        Args:
            client: Connected UnifiClient instance.
            settings: Configuration settings.
            site: Site name to collect logs from.
            device_type: Device type for SSH fallback (auto-detected if None).
            min_entries: Minimum entries required from API before fallback.
            ws_manager: WebSocket manager for real-time WiFi events (optional).
        """
        self.client = client
        self.settings = settings
        self.site = site
        self.device_type = device_type or client.device_type
        self.min_entries = min_entries
        self._ws_manager = ws_manager

    def collect(
        self,
        force_ssh: bool = False,
        history_hours: int = 720,
        since_timestamp: Optional[datetime] = None,
    ) -> list[LogEntry]:
        """Collect logs from available sources.

        Implements fallback chain: WS -> REST API -> SSH.

        Args:
            force_ssh: Skip WS and API, use SSH directly (default False).
            history_hours: Hours of history to retrieve via API.
            since_timestamp: Only include events newer than this timestamp (UTC).
                Client-side filtering is applied since UniFi API lacks
                timestamp filter support. A 5-minute clock skew tolerance
                is automatically applied.

        Returns:
            List of LogEntry objects.

        Raises:
            LogCollectionError: All collection sources failed.
        """
        api_error: Optional[Exception] = None
        ssh_error: Optional[Exception] = None
        ws_events: list[LogEntry] = []
        api_events: list[LogEntry] = []
        api_succeeded = False  # Track whether API collection succeeded (even with 0 results)
        sources: list[str] = []

        # Try WebSocket first (if manager provided and running)
        if not force_ssh and self._ws_manager is not None:
            try:
                if self._ws_manager.is_running():
                    ws_collector = WSLogCollector(
                        manager=self._ws_manager,
                        since_timestamp=since_timestamp,
                    )
                    ws_events = ws_collector.collect()

                    if ws_events:
                        sources.append("ws")
                        logger.info(
                            "websocket_events_collected",
                            count=len(ws_events),
                        )
                else:
                    logger.debug("websocket_manager_not_running")

            except WSCollectionError as e:
                logger.warning(
                    "ws_collection_failed",
                    error=str(e),
                )
                ws_events = []

        # Try REST API (unless forced to SSH)
        if not force_ssh:
            try:
                api_collector = APILogCollector(
                    client=self.client,
                    site=self.site,
                    history_hours=history_hours,
                    since_timestamp=since_timestamp,
                )
                api_events = api_collector.collect()
                api_succeeded = True  # API call succeeded, even if 0 entries

                if api_events:
                    sources.append("api")

            except APICollectionError as e:
                api_error = e
                logger.warning(
                    "api_collection_failed",
                    error=str(e),
                )
            except Exception as e:
                api_error = e
                logger.warning(
                    "api_collection_unexpected_error",
                    error=str(e),
                )

        # Merge WS + API events (deduplicate by timestamp + message)
        merged_events = self._merge_events(ws_events, api_events)

        # Check if we have enough entries (WS + API combined)
        if len(merged_events) >= self.min_entries or api_succeeded:
            # Don't try SSH if we have enough or API succeeded
            if len(merged_events) >= self.min_entries:
                logger.info(
                    "log_collection_complete",
                    sources=sources,
                    ws_count=len(ws_events),
                    api_count=len(api_events),
                    total=len(merged_events),
                )
                return merged_events

            # API succeeded but insufficient entries, try SSH if enabled
            if len(merged_events) < self.min_entries:
                logger.info(
                    "api_insufficient_entries",
                    entries=len(merged_events),
                    min_required=self.min_entries,
                )

        # Try SSH fallback if enabled
        if self.settings.ssh_enabled:
            try:
                ssh_entries = self._collect_via_ssh()

                # Filter SSH entries by since_timestamp (defensive, same as API)
                if since_timestamp:
                    unfiltered_count = len(ssh_entries)
                    effective_cutoff = since_timestamp - timedelta(minutes=5)
                    ssh_entries = [
                        e for e in ssh_entries if e.timestamp > effective_cutoff
                    ]
                    logger.debug(
                        "ssh_entries_filtered",
                        before_filter=unfiltered_count,
                        after_filter=len(ssh_entries),
                        since=since_timestamp.isoformat(),
                    )

                if ssh_entries:
                    sources.append("ssh")

                # Merge with WS + API entries
                merged_events = self._merge_events(merged_events, ssh_entries)

                logger.info(
                    "log_collection_complete",
                    sources=sources,
                    ws_count=len(ws_events),
                    api_count=len(api_events),
                    ssh_count=len(ssh_entries),
                    total=len(merged_events),
                )
                return merged_events

            except SSHCollectionError as e:
                ssh_error = e
                logger.warning(
                    "ssh_collection_failed",
                    error=str(e),
                )
            except Exception as e:
                ssh_error = e
                logger.warning(
                    "ssh_collection_unexpected_error",
                    error=str(e),
                )
        else:
            logger.debug("ssh_fallback_disabled")

        # If API succeeded (even with 0 entries), return what we got
        # 0 entries is valid - may just be no events in the time window
        if api_succeeded or ws_events:
            logger.info(
                "log_collection_partial",
                sources=sources,
                ws_count=len(ws_events),
                api_count=len(api_events),
                total=len(merged_events),
                note="SSH fallback unavailable or failed",
            )
            return merged_events

        # All sources failed (API threw exception and SSH failed/disabled)
        raise LogCollectionError(
            message="All log collection sources failed",
            api_error=api_error,
            ssh_error=ssh_error,
        )

    def _merge_events(
        self,
        events_a: list[LogEntry],
        events_b: list[LogEntry],
    ) -> list[LogEntry]:
        """Merge two lists of log entries, deduplicating by timestamp+message.

        Args:
            events_a: First list of events (preserved in conflicts).
            events_b: Second list of events (added if not duplicate).

        Returns:
            Merged list with duplicates removed.
        """
        if not events_a:
            return events_b
        if not events_b:
            return events_a

        # Use dict to deduplicate, preserving events_a in conflicts
        seen: dict[tuple[datetime, str], LogEntry] = {}
        for e in events_a:
            seen[(e.timestamp, e.message)] = e
        for e in events_b:
            key = (e.timestamp, e.message)
            if key not in seen:
                seen[key] = e

        return list(seen.values())

    def _collect_via_ssh(self) -> list[LogEntry]:
        """Collect logs via SSH fallback.

        Returns:
            List of LogEntry objects.

        Raises:
            SSHCollectionError: SSH collection failed.
        """
        # Use SSH credentials if provided, otherwise fall back to API credentials
        ssh_username = self.settings.ssh_username or self.settings.username
        ssh_password = self.settings.ssh_password or self.settings.password

        collector = SSHLogCollector(
            host=self.settings.host,
            username=ssh_username,
            password=ssh_password,
            device_type=self.device_type,
            timeout=self.settings.ssh_timeout,
        )

        return collector.collect()
