"""Finding formatter for display-ready output.

Converts Finding objects to formatted dictionaries and text reports
with timezone-aware timestamps, occurrence summaries, and grouped output.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from unifi_scanner.models.enums import Severity
from unifi_scanner.models.finding import Finding, RECURRING_THRESHOLD


class FindingFormatter:
    """Formatter for converting findings to display-ready output.

    Handles timezone conversion, occurrence summaries, severity grouping,
    and plain text report generation.

    Attributes:
        display_timezone: Timezone name for timestamp display (e.g., 'America/New_York')
        _tz: ZoneInfo object for the display timezone
    """

    def __init__(self, display_timezone: str = "UTC"):
        """Initialize formatter with display timezone.

        Args:
            display_timezone: IANA timezone name (e.g., 'America/New_York', 'Europe/London')
                            Defaults to 'UTC' if not specified.
        """
        self.display_timezone = display_timezone
        self._tz = ZoneInfo(display_timezone)

    def format_timestamp(self, dt: datetime) -> str:
        """Format a datetime for display with timezone abbreviation.

        Converts to the display timezone and formats with absolute time.
        Uses 12-hour format with AM/PM for readability.

        Args:
            dt: Datetime to format (assumed UTC if naive)

        Returns:
            Formatted string like "Jan 24, 2026 at 2:30 PM EST"
        """
        # Ensure datetime is timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        # Convert to display timezone
        local_dt = dt.astimezone(self._tz)

        # Format: "Jan 24, 2026 at 2:30 PM EST"
        # Get timezone abbreviation
        tz_abbrev = local_dt.strftime("%Z")

        # Format the datetime
        formatted = local_dt.strftime("%b %-d, %Y at %-I:%M %p")
        return f"{formatted} {tz_abbrev}"

    def format_occurrence_summary(self, finding: Finding) -> str:
        """Format an occurrence summary for display.

        Shows count, first/last times, and recurring flag if applicable.
        Uses the display timezone for time formatting.

        Args:
            finding: Finding to summarize

        Returns:
            String like "Occurred 5 times (first: Jan 24 at 2:00 PM, last: Jan 24 at 4:30 PM)"
            or "Occurred 1 time at Jan 24 at 3:15 PM"
            Adds "[Recurring Issue]" prefix for 5+ occurrences.
        """
        # Format times in display timezone
        first_dt = finding.first_seen
        last_dt = finding.last_seen

        if first_dt.tzinfo is None:
            first_dt = first_dt.replace(tzinfo=ZoneInfo("UTC"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=ZoneInfo("UTC"))

        first_local = first_dt.astimezone(self._tz)
        last_local = last_dt.astimezone(self._tz)

        # Short time format for summaries
        first_time = first_local.strftime("%b %-d at %-I:%M %p")
        last_time = last_local.strftime("%b %-d at %-I:%M %p")

        if finding.occurrence_count == 1:
            return f"Occurred 1 time at {first_time}"

        summary = f"Occurred {finding.occurrence_count} times (first: {first_time}, last: {last_time})"

        if finding.is_recurring:
            summary = f"[Recurring Issue] {summary}"

        return summary

    def format_device_display(self, finding: Finding) -> str:
        """Format device display name with MAC fallback.

        Args:
            finding: Finding with device info

        Returns:
            Device name if available, otherwise MAC address, or 'Unknown device'
        """
        if finding.device_name:
            return finding.device_name
        if finding.device_mac:
            return finding.device_mac
        return "Unknown device"

    def format_finding(self, finding: Finding) -> Dict[str, Any]:
        """Format a single finding for display.

        Converts a Finding to a dictionary with all fields ready for display,
        including formatted timestamps, occurrence summary, and device name.

        Args:
            finding: Finding to format

        Returns:
            Dictionary with display-ready fields:
            - id: UUID string
            - severity: Severity value
            - category: Category value
            - title: Finding title
            - description: Finding description
            - remediation: Remediation text or None
            - device_display: Device name with MAC fallback
            - first_seen: Formatted timestamp
            - last_seen: Formatted timestamp
            - occurrence_count: Integer count
            - occurrence_summary: Human-readable summary
            - is_recurring: Boolean
            - is_actionable: Boolean
            - metadata: Original metadata dict
        """
        return {
            "id": str(finding.id),
            "severity": finding.severity.value,
            "category": finding.category.value,
            "title": finding.title,
            "description": finding.description,
            "remediation": finding.remediation,
            "device_display": self.format_device_display(finding),
            "first_seen": self.format_timestamp(finding.first_seen),
            "last_seen": self.format_timestamp(finding.last_seen),
            "occurrence_count": finding.occurrence_count,
            "occurrence_summary": self.format_occurrence_summary(finding),
            "is_recurring": finding.is_recurring,
            "is_actionable": finding.is_actionable,
            "metadata": finding.metadata,
        }

    def format_findings(self, findings: List[Finding]) -> List[Dict[str, Any]]:
        """Format a list of findings for display.

        Args:
            findings: List of findings to format

        Returns:
            List of formatted finding dictionaries
        """
        return [self.format_finding(f) for f in findings]

    def format_grouped_findings(
        self, findings: List[Finding]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group and format findings by severity.

        Groups findings into SEVERE, MEDIUM, and LOW categories,
        with SEVERE first for urgency.

        Args:
            findings: List of findings to group and format

        Returns:
            Dictionary with keys 'severe', 'medium', 'low', each containing
            a list of formatted finding dictionaries. Empty lists for
            severities with no findings.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {
            "severe": [],
            "medium": [],
            "low": [],
        }

        for finding in findings:
            formatted = self.format_finding(finding)
            grouped[finding.severity.value].append(formatted)

        return grouped

    def format_text_report(
        self,
        findings: List[Finding],
        title: str = "Network Analysis Report",
        include_timestamp: bool = True,
    ) -> str:
        """Generate a plain text report from findings.

        Creates a human-readable text report with severity sections,
        finding details, and remediation guidance.

        Args:
            findings: List of findings to include
            title: Report title
            include_timestamp: Whether to include generation timestamp

        Returns:
            Plain text report string
        """
        lines: List[str] = []

        # Header
        lines.append("=" * 60)
        lines.append(title.center(60))
        lines.append("=" * 60)

        if include_timestamp:
            now = datetime.now(self._tz)
            lines.append(f"Generated: {self.format_timestamp(now)}")
            lines.append("")

        # Group by severity
        grouped = self.format_grouped_findings(findings)

        # Summary counts
        total = len(findings)
        severe_count = len(grouped["severe"])
        medium_count = len(grouped["medium"])
        low_count = len(grouped["low"])

        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Findings: {total}")
        lines.append(f"  SEVERE: {severe_count}")
        lines.append(f"  MEDIUM: {medium_count}")
        lines.append(f"  LOW:    {low_count}")
        lines.append("")

        # SEVERE findings (most urgent first)
        if grouped["severe"]:
            lines.append("")
            lines.append("=" * 60)
            lines.append("SEVERE FINDINGS - Require Immediate Attention")
            lines.append("=" * 60)
            for finding in grouped["severe"]:
                lines.extend(self._format_finding_text(finding))

        # MEDIUM findings
        if grouped["medium"]:
            lines.append("")
            lines.append("=" * 60)
            lines.append("MEDIUM FINDINGS - Should Be Addressed")
            lines.append("=" * 60)
            for finding in grouped["medium"]:
                lines.extend(self._format_finding_text(finding))

        # LOW findings
        if grouped["low"]:
            lines.append("")
            lines.append("=" * 60)
            lines.append("LOW FINDINGS - Informational")
            lines.append("=" * 60)
            for finding in grouped["low"]:
                lines.extend(self._format_finding_text(finding, include_remediation=False))

        lines.append("")
        lines.append("=" * 60)
        lines.append("End of Report")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _format_finding_text(
        self, finding: Dict[str, Any], include_remediation: bool = True
    ) -> List[str]:
        """Format a single finding as text lines.

        Args:
            finding: Formatted finding dictionary
            include_remediation: Whether to include remediation section

        Returns:
            List of text lines for the finding
        """
        lines: List[str] = []
        lines.append("")
        lines.append("-" * 40)
        lines.append(f"{finding['title']}")
        lines.append(f"Device: {finding['device_display']}")
        lines.append(f"First seen: {finding['first_seen']}")
        lines.append(f"Last seen: {finding['last_seen']}")
        lines.append(f"{finding['occurrence_summary']}")
        lines.append("")
        lines.append(finding["description"])

        if include_remediation and finding.get("remediation"):
            lines.append("")
            lines.append("Recommended Actions:")
            lines.append(finding["remediation"])

        return lines
