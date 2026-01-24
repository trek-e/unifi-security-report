"""API-based log collector for UniFi controllers.

Wraps UnifiClient methods to retrieve events and alarms,
parsing them into LogEntry objects.
"""

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
    ) -> None:
        """Initialize API log collector.

        Args:
            client: Connected UnifiClient instance.
            site: Site name to collect logs from.
            history_hours: Hours of history to retrieve (default 720 = 30 days).
        """
        self.client = client
        self.site = site
        self.history_hours = history_hours
        self._parser = LogParser()

    def collect(
        self,
        include_events: bool = True,
        include_alarms: bool = True,
    ) -> List[LogEntry]:
        """Collect logs from the API.

        Retrieves events and/or alarms and parses into LogEntry objects.

        Args:
            include_events: Include event logs (default True).
            include_alarms: Include alarms (default True).

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
        )

        try:
            if include_events:
                events = self.client.get_events(
                    site=self.site,
                    history_hours=self.history_hours,
                )
                parsed_events = self._parser.parse_api_events(events)
                entries.extend(parsed_events)
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

        except Exception as e:
            raise APICollectionError(
                message=f"API collection failed: {e}",
                cause=e,
            ) from e

        logger.info(
            "api_collection_complete",
            site=self.site,
            total_entries=len(entries),
        )
        return entries
