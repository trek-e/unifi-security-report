"""Orchestrating log collector with fallback chain.

Tries API collection first, falls back to SSH if API fails
or returns insufficient entries.
"""

from datetime import datetime, timedelta
from typing import List, Optional

import structlog

from unifi_scanner.api import UnifiClient
from unifi_scanner.config import UnifiSettings
from unifi_scanner.models import DeviceType, LogEntry

from .api_collector import APICollectionError, APILogCollector
from .ssh_collector import SSHCollectionError, SSHLogCollector

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
    ) -> None:
        """Initialize the log collector.

        Args:
            client: Connected UnifiClient instance.
            settings: Configuration settings.
            site: Site name to collect logs from.
            device_type: Device type for SSH fallback (auto-detected if None).
            min_entries: Minimum entries required from API before fallback.
        """
        self.client = client
        self.settings = settings
        self.site = site
        self.device_type = device_type or client.device_type
        self.min_entries = min_entries

    def collect(
        self,
        force_ssh: bool = False,
        history_hours: int = 720,
        since_timestamp: Optional[datetime] = None,
    ) -> List[LogEntry]:
        """Collect logs from available sources.

        Tries API first, falls back to SSH if needed.

        Args:
            force_ssh: Skip API and use SSH directly (default False).
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
        entries: List[LogEntry] = []

        # Try API first unless forced to SSH
        if not force_ssh:
            try:
                api_collector = APILogCollector(
                    client=self.client,
                    site=self.site,
                    history_hours=history_hours,
                    since_timestamp=since_timestamp,
                )
                entries = api_collector.collect()

                # Check if we got enough entries
                if len(entries) >= self.min_entries:
                    logger.info(
                        "log_collection_complete",
                        source="api",
                        entries=len(entries),
                    )
                    return entries

                # Not enough entries, will try SSH fallback
                logger.info(
                    "api_insufficient_entries",
                    entries=len(entries),
                    min_required=self.min_entries,
                )

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

                # Merge with any API entries we got
                if entries:
                    # Deduplicate by message + timestamp (rough)
                    seen = {(e.timestamp, e.message) for e in entries}
                    for entry in ssh_entries:
                        if (entry.timestamp, entry.message) not in seen:
                            entries.append(entry)
                            seen.add((entry.timestamp, entry.message))
                else:
                    entries = ssh_entries

                logger.info(
                    "log_collection_complete",
                    source="ssh" if force_ssh else "api+ssh",
                    entries=len(entries),
                )
                return entries

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

        # If we have any entries from API, return them even if SSH failed
        if entries:
            logger.info(
                "log_collection_partial",
                source="api",
                entries=len(entries),
            )
            return entries

        # All sources failed
        raise LogCollectionError(
            message="All log collection sources failed",
            api_error=api_error,
            ssh_error=ssh_error,
        )

    def _collect_via_ssh(self) -> List[LogEntry]:
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
