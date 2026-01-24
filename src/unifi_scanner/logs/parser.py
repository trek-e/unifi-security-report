"""Multi-format log parser for UniFi logs."""

import json
from typing import Any, Dict, List

import structlog

from unifi_scanner.models import LogEntry

logger = structlog.get_logger(__name__)


class LogParser:
    """Parser for multiple log formats (JSON, syslog).

    Automatically detects format and parses accordingly.
    Handles malformed data gracefully, logging warnings
    and skipping unparseable entries.

    Example:
        >>> parser = LogParser()
        >>> entries = parser.parse_api_events([{"time": 1705084800000, "key": "EVT_TEST", "msg": "Test"}])
        >>> len(entries)
        1
    """

    def parse_api_events(self, events: List[Dict[str, Any]]) -> List[LogEntry]:
        """Parse list of events from UniFi API.

        Args:
            events: List of event dictionaries from API response

        Returns:
            List of LogEntry objects (skips unparseable events)
        """
        entries: List[LogEntry] = []
        for i, event in enumerate(events):
            try:
                entry = LogEntry.from_unifi_event(event)
                entries.append(entry)
            except Exception as e:
                logger.warning(
                    "event_parse_failed",
                    index=i,
                    error=str(e),
                    event_key=event.get("key", "unknown"),
                )
        logger.debug("api_events_parsed", total=len(events), successful=len(entries))
        return entries

    def parse_syslog_lines(self, lines: str) -> List[LogEntry]:
        """Parse syslog-formatted log lines.

        Args:
            lines: Multi-line string of syslog entries

        Returns:
            List of LogEntry objects (skips unparseable lines)
        """
        entries: List[LogEntry] = []
        line_list = lines.strip().split("\n")
        for i, line in enumerate(line_list):
            line = line.strip()
            if not line:
                continue
            try:
                entry = LogEntry.from_syslog(line)
                entries.append(entry)
            except Exception as e:
                logger.warning(
                    "syslog_parse_failed",
                    line_num=i + 1,
                    error=str(e),
                    line_preview=line[:100],
                )
        logger.debug(
            "syslog_lines_parsed",
            total=len(line_list),
            successful=len(entries),
        )
        return entries

    def detect_and_parse(self, data: str) -> List[LogEntry]:
        """Auto-detect format and parse.

        Tries JSON first (API response), falls back to syslog.

        Args:
            data: Raw log data as string

        Returns:
            List of LogEntry objects
        """
        # Try JSON first
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                logger.debug("format_detected", format="json_array")
                return self.parse_api_events(parsed)
            elif isinstance(parsed, dict) and "data" in parsed:
                logger.debug("format_detected", format="json_wrapped")
                return self.parse_api_events(parsed["data"])
            elif isinstance(parsed, dict):
                # Single event
                logger.debug("format_detected", format="json_single")
                return self.parse_api_events([parsed])
        except json.JSONDecodeError:
            pass

        # Fall back to syslog
        logger.debug("format_detected", format="syslog")
        return self.parse_syslog_lines(data)
