"""FindingStore for time-window deduplication of analysis findings."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from ..models.enums import Category, Severity
from ..models.finding import Finding


class FindingStore:
    """Store for managing and deduplicating findings.

    Findings are deduplicated by event_type and device_mac within a configurable
    time window (default: 1 hour). Repeated events within the window are merged
    into a single finding with incremented occurrence count.

    Per user decision: "events within 1 hour are one incident"
    """

    DEFAULT_CLUSTER_WINDOW = timedelta(hours=1)

    def __init__(self, cluster_window: Optional[timedelta] = None) -> None:
        """Initialize the FindingStore.

        Args:
            cluster_window: Time window for deduplication. Events within this
                window are merged. Defaults to 1 hour.
        """
        self.cluster_window = cluster_window or self.DEFAULT_CLUSTER_WINDOW

        # Internal storage: key -> Finding
        # Key is (event_type, device_mac) tuple
        self._findings: Dict[Tuple[str, Optional[str]], Finding] = {}

        # Stats tracking
        self._total_merged = 0
        self._total_new = 0

    @property
    def stats(self) -> Dict[str, int]:
        """Get store statistics.

        Returns:
            Dict with total_findings, total_merged, and total_new counts
        """
        return {
            "total_findings": len(self._findings),
            "total_merged": self._total_merged,
            "total_new": self._total_new,
        }

    def _make_key(self, event_type: str, device_mac: Optional[str]) -> Tuple[str, Optional[str]]:
        """Create deduplication key from event_type and device_mac.

        Args:
            event_type: Type of event (e.g., "EVT_FAILED_LOGIN")
            device_mac: MAC address of device, or None for system events

        Returns:
            Tuple key for deduplication lookup
        """
        return (event_type, device_mac)

    def add_or_merge(
        self,
        event_type: str,
        finding: Finding,
        log_id: UUID,
        timestamp: datetime,
    ) -> Tuple[Finding, bool]:
        """Add a new finding or merge with existing if within time window.

        Deduplication is based on (event_type, device_mac). If an existing
        finding matches and the timestamp is within cluster_window of the
        existing finding's last_seen, the occurrence is merged.

        Args:
            event_type: Type of event for deduplication key
            finding: The Finding to add or merge
            log_id: UUID of the source log entry
            timestamp: When this occurrence was detected

        Returns:
            Tuple of (Finding, was_merged) where was_merged indicates if
            the finding was merged with an existing one
        """
        key = self._make_key(event_type, finding.device_mac)

        if key in self._findings:
            existing = self._findings[key]

            # Check if within time window
            time_diff = abs((timestamp - existing.last_seen).total_seconds())
            window_seconds = self.cluster_window.total_seconds()

            if time_diff <= window_seconds:
                # Merge: update existing finding
                existing.add_occurrence(log_id, timestamp)
                self._total_merged += 1
                return existing, True

        # Outside window or new key: store as new finding
        # Ensure the log_id is in source_log_ids
        if log_id not in finding.source_log_ids:
            finding.source_log_ids.append(log_id)

        self._findings[key] = finding
        self._total_new += 1
        return finding, False

    def get_all_findings(self) -> List[Finding]:
        """Get all findings in the store.

        Returns:
            List of all Finding objects, sorted by last_seen descending
        """
        return sorted(
            self._findings.values(),
            key=lambda f: f.last_seen,
            reverse=True,
        )

    def get_findings_by_severity(self, severity: Severity) -> List[Finding]:
        """Get findings filtered by severity level.

        Args:
            severity: Severity level to filter by

        Returns:
            List of Finding objects with matching severity
        """
        return [f for f in self._findings.values() if f.severity == severity]

    def get_findings_by_category(self, category: Category) -> List[Finding]:
        """Get findings filtered by category.

        Args:
            category: Category to filter by

        Returns:
            List of Finding objects with matching category
        """
        return [f for f in self._findings.values() if f.category == category]

    def get_recurring_findings(self) -> List[Finding]:
        """Get findings that are recurring (5+ occurrences).

        Returns:
            List of Finding objects where is_recurring is True
        """
        return [f for f in self._findings.values() if f.is_recurring]

    def get_summary(self) -> Dict[str, Dict[str, int]]:
        """Get summary counts by severity and category.

        Returns:
            Dict with 'by_severity' and 'by_category' sub-dicts containing counts
        """
        by_severity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for finding in self._findings.values():
            # Count by severity
            sev_key = finding.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1

            # Count by category
            cat_key = finding.category.value
            by_category[cat_key] = by_category.get(cat_key, 0) + 1

        return {
            "by_severity": by_severity,
            "by_category": by_category,
        }

    def clear(self) -> None:
        """Clear all findings and reset stats."""
        self._findings.clear()
        self._total_merged = 0
        self._total_new = 0
