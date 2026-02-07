"""API-based log collector for UniFi controllers.

Wraps UnifiClient methods to retrieve events and alarms,
parsing them into LogEntry objects.
"""

from datetime import datetime, timedelta
from typing import List, Optional

import structlog

from unifi_scanner.api import UnifiClient
from unifi_scanner.models import LogEntry

from .parser import LogParser

logger = structlog.get_logger(__name__)


class APICollectionError(Exception):
    """Raised when API log collection fails."""

    def __init__(
        self,
        message: str,
        cause: Optional[Exception] = None,
    ) -> None:
        self.message = message
        self.cause = cause
        super().__init__(message)


class APILogCollector:
    """Collects logs from UniFi controller via API.

    Wraps UnifiClient.get_events() and get_alarms() methods,
    parsing results into LogEntry objects.

    Example:
        >>> with UnifiClient(settings) as client:
        ...     site = client.select_site()
        ...     collector = APILogCollector(client, site)
        ...     entries = collector.collect()
    """

    def __init__(
        self,
        client: UnifiClient,
        site: str,
        history_hours: int = 720,
        since_timestamp: Optional[datetime] = None,
    ) -> None:
        """Initialize API log collector.

        Args:
            client: Connected UnifiClient instance.
            site: Site name to collect logs from.
            history_hours: Hours of history to retrieve (default 720 = 30 days).
            since_timestamp: Only include events newer than this timestamp (UTC).
                The UniFi API doesn't support timestamp filtering, so this is
                applied client-side after fetching events.
        """
        self.client = client
        self.site = site
        self.history_hours = history_hours
        self.since_timestamp = since_timestamp
        self._parser = LogParser()
        self.raw_ips_events: list[dict] = []

    def collect(
        self,
        include_events: bool = True,
        include_alarms: bool = True,
        include_ips_events: bool = True,
    ) -> List[LogEntry]:
        """Collect logs from the API.

        Retrieves events, alarms, and IPS events and parses into LogEntry objects.

        Args:
            include_events: Include event logs (default True).
            include_alarms: Include alarms (default True).
            include_ips_events: Include IDS/IPS security events (default True).

        Returns:
            List of LogEntry objects from API.

        Raises:
            APICollectionError: API request failed.
        """
        entries: List[LogEntry] = []

        logger.info(
            "api_collection_starting",
            site=self.site,
            history_hours=self.history_hours,
            include_events=include_events,
            include_alarms=include_alarms,
            include_ips_events=include_ips_events,
        )

        try:
            if include_events:
                events = self.client.get_events(
                    site=self.site,
                    history_hours=self.history_hours,
                )
                parsed_events = self._parser.parse_api_events(events)
                entries.extend(parsed_events)
                # Log at INFO if no events found to help diagnose issues
                if len(events) == 0:
                    logger.info(
                        "api_events_empty",
                        site=self.site,
                        history_hours=self.history_hours,
                        hint="Controller may have no events, or API endpoint may differ",
                    )
                else:
                    logger.debug(
                        "api_events_collected",
                        raw_count=len(events),
                        parsed_count=len(parsed_events),
                    )

            if include_alarms:
                alarms = self.client.get_alarms(site=self.site)
                parsed_alarms = self._parser.parse_api_events(alarms)
                entries.extend(parsed_alarms)
                logger.debug(
                    "api_alarms_collected",
                    raw_count=len(alarms),
                    parsed_count=len(parsed_alarms),
                )

            if include_ips_events:
                # IPS events use start/end timestamps in ms, not history_hours
                # Calculate based on history_hours for consistency
                import time
                end_ms = int(time.time() * 1000)
                start_ms = end_ms - (self.history_hours * 60 * 60 * 1000)

                ips_events = self.client.get_ips_events(
                    site=self.site,
                    start=start_ms,
                    end=end_ms,
                )
                self.raw_ips_events = ips_events
                parsed_ips = self._parser.parse_api_events(ips_events)
                entries.extend(parsed_ips)
                # Log IPS events count at INFO level for visibility
                logger.info(
                    "api_ips_events_collected",
                    raw_count=len(ips_events),
                    parsed_count=len(parsed_ips),
                )

        except Exception as e:
            raise APICollectionError(
                message=f"API collection failed: {e}",
                cause=e,
            ) from e

        # Filter by since_timestamp if provided (client-side filtering)
        # UniFi API doesn't support timestamp filtering on events endpoint
        if self.since_timestamp:
            unfiltered_count = len(entries)
            # Apply 5-minute clock skew tolerance (STATE-07)
            effective_cutoff = self.since_timestamp - timedelta(minutes=5)
            entries = [e for e in entries if e.timestamp > effective_cutoff]
            logger.debug(
                "api_entries_filtered",
                before_filter=unfiltered_count,
                after_filter=len(entries),
                since=self.since_timestamp.isoformat(),
                effective_cutoff=effective_cutoff.isoformat(),
            )

        logger.info(
            "api_collection_complete",
            site=self.site,
            total_entries=len(entries),
        )
        return entries
