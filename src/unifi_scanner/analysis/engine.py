"""Main analysis engine for processing UniFi logs."""

from typing import Any, Dict, List, Optional

import structlog

from unifi_scanner.models.enums import Category, Severity
from unifi_scanner.models.finding import Finding
from unifi_scanner.models.log_entry import LogEntry
from unifi_scanner.analysis.rules.base import Rule, RuleRegistry
from unifi_scanner.analysis.rules.wireless import rssi_to_quality, format_radio_band

logger = structlog.get_logger(__name__)


class AnalysisEngine:
    """Engine for analyzing LogEntry objects and producing Findings.

    Uses a RuleRegistry for dictionary dispatch based on event_type.
    Unknown event types are captured gracefully in the UNCATEGORIZED bucket.

    Usage:
        engine = AnalysisEngine()
        engine.register_rules(my_rules)
        findings = engine.analyze(log_entries)
    """

    def __init__(self, registry: Optional[RuleRegistry] = None):
        """Initialize the analysis engine.

        Args:
            registry: Optional pre-configured RuleRegistry.
                     Creates empty one if not provided.
        """
        self._registry = registry or RuleRegistry()
        self._unknown_event_types: Dict[str, int] = {}

    @property
    def registry(self) -> RuleRegistry:
        """Get the rule registry."""
        return self._registry

    @property
    def unknown_event_types(self) -> Dict[str, int]:
        """Get counts of unknown event types encountered."""
        return dict(self._unknown_event_types)

    def register_rule(self, rule: Rule) -> None:
        """Register a single rule.

        Args:
            rule: Rule to register
        """
        self._registry.register(rule)
        logger.debug("rule_registered", rule_name=rule.name, event_types=rule.event_types)

    def register_rules(self, rules: List[Rule]) -> None:
        """Register multiple rules.

        Args:
            rules: List of rules to register
        """
        for rule in rules:
            self.register_rule(rule)
        logger.info("rules_registered", count=len(rules))

    def analyze_entry(self, entry: LogEntry) -> Optional[Finding]:
        """Analyze a single log entry.

        Args:
            entry: LogEntry to analyze

        Returns:
            Finding if a rule matched, None for unmatched entries.
            Unknown event types are tracked but don't produce findings
            (they go in the UNCATEGORIZED bucket which is logged separately).
        """
        rule = self._registry.find_matching_rule(entry.event_type, entry.message)

        if rule is None:
            # Track unknown event type
            if not self._registry.is_known_event_type(entry.event_type):
                self._unknown_event_types[entry.event_type] = (
                    self._unknown_event_types.get(entry.event_type, 0) + 1
                )
                logger.debug(
                    "unknown_event_type",
                    event_type=entry.event_type,
                    count=self._unknown_event_types[entry.event_type],
                )
            return None

        # Create finding from rule template
        finding = self._create_finding(entry, rule)
        return finding

    def analyze(self, entries: List[LogEntry]) -> List[Finding]:
        """Analyze multiple log entries.

        Args:
            entries: List of LogEntry objects to analyze

        Returns:
            List of Finding objects (one per matched entry).
            Note: This does NOT deduplicate - use FindingStore for that.
        """
        findings = []
        roam_events_by_client: Dict[str, List[LogEntry]] = {}

        for entry in entries:
            finding = self.analyze_entry(entry)
            if finding:
                findings.append(finding)

            # Track roaming events for flapping detection (WIFI-06)
            if entry.event_type in ("EVT_WU_Roam", "EVT_WG_Roam"):
                client_mac = (entry.raw_data or {}).get("user", "unknown")
                if client_mac not in roam_events_by_client:
                    roam_events_by_client[client_mac] = []
                roam_events_by_client[client_mac].append(entry)

        # Detect flapping (WIFI-06): 5+ roams within analysis window
        flapping_findings = self._detect_flapping(roam_events_by_client, threshold=5)
        findings.extend(flapping_findings)

        logger.info(
            "analysis_complete",
            entries_processed=len(entries),
            findings_created=len(findings),
            flapping_clients=len(flapping_findings),
            unknown_types=len(self._unknown_event_types),
        )
        return findings

    def _create_finding(self, entry: LogEntry, rule: Rule) -> Finding:
        """Create a Finding from a LogEntry and matched Rule.

        Args:
            entry: The source LogEntry
            rule: The matched Rule with templates

        Returns:
            Finding with rendered templates
        """
        # Build template context from entry
        context = self._build_template_context(entry)

        # Render templates with safe formatting
        title = self._safe_format(rule.title_template, context)
        description = self._safe_format(rule.description_template, context)
        remediation = None
        if rule.remediation_template and rule.severity in (Severity.SEVERE, Severity.MEDIUM):
            remediation = self._safe_format(rule.remediation_template, context)

        return Finding(
            severity=rule.severity,
            category=rule.category,
            title=title,
            description=description,
            remediation=remediation,
            source_log_ids=[entry.id],
            first_seen=entry.timestamp,
            last_seen=entry.timestamp,
            device_mac=entry.device_mac,
            device_name=entry.device_name,
            metadata={
                "rule_name": rule.name,
                "event_type": entry.event_type,
            },
        )

    def _build_template_context(self, entry: LogEntry) -> Dict[str, Any]:
        """Build context dictionary for template rendering.

        Args:
            entry: LogEntry to extract context from

        Returns:
            Dict with common placeholders populated
        """
        # Device name with MAC fallback per user decision
        device_display = entry.device_name or entry.device_mac or "Unknown device"

        context = {
            "device_name": device_display,
            "device_mac": entry.device_mac or "Unknown",
            "event_type": entry.event_type,
            "message": entry.message,
            "timestamp": entry.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        # Extract common fields from raw_data
        raw = entry.raw_data or {}
        context["ip"] = raw.get("ip", raw.get("client_ip", raw.get("src_ip", "Unknown")))
        context["user"] = raw.get("admin", raw.get("user", raw.get("username", "Unknown")))
        context["subsystem"] = raw.get("subsystem", entry.metadata.get("subsystem", "Unknown"))

        # Wireless-specific fields (WIFI-05, WIFI-06)
        # Radio band translation (ng -> 2.4GHz, na -> 5GHz)
        context["radio_from"] = raw.get("radio_from")
        context["radio_to"] = raw.get("radio_to")
        context["radio_from_display"] = format_radio_band(raw.get("radio_from"))
        context["radio_to_display"] = format_radio_band(raw.get("radio_to"))

        # Channel information
        context["channel_from"] = raw.get("channel_from", "Unknown")
        context["channel_to"] = raw.get("channel_to", raw.get("channel", "Unknown"))

        # AP roaming fields
        context["ap_from"] = raw.get("ap_from", "Unknown")
        context["ap_to"] = raw.get("ap_to", "Unknown")
        # AP names from message if present
        context["ap_from_name"] = raw.get("ap_from_name", raw.get("ap_from", "Unknown"))
        context["ap_to_name"] = raw.get("ap_to_name", raw.get("ap_to", "Unknown"))

        # RSSI to quality translation
        rssi = raw.get("rssi") or raw.get("signal")
        if isinstance(rssi, (int, float)):
            context["rssi"] = int(rssi)
            context["rssi_quality"] = rssi_to_quality(int(rssi))
        else:
            context["rssi"] = None
            context["rssi_quality"] = "Unknown"

        # Client identifier for roaming
        context["client_mac"] = raw.get("user", raw.get("client", "Unknown"))
        context["ssid"] = raw.get("ssid", "Unknown")

        return context

    def _safe_format(self, template: str, context: Dict[str, Any]) -> str:
        """Safely format a template string with context.

        Missing keys are replaced with 'Unknown' instead of raising KeyError.

        Args:
            template: Template string with {placeholders}
            context: Dictionary of values

        Returns:
            Formatted string with placeholders replaced
        """
        # Use defaultdict-like behavior for missing keys
        class SafeDict(dict):
            def __missing__(self, key):
                logger.debug("template_missing_key", key=key)
                return "Unknown"

        safe_context = SafeDict(context)
        try:
            return template.format_map(safe_context)
        except Exception as e:
            logger.warning("template_format_error", template=template[:50], error=str(e))
            return template

    def clear_unknown_counts(self) -> None:
        """Clear the unknown event type counts."""
        self._unknown_event_types.clear()

    def _detect_flapping(
        self,
        roam_events_by_client: Dict[str, List[LogEntry]],
        threshold: int = 5,
    ) -> List[Finding]:
        """Detect clients with excessive roaming (flapping).

        WIFI-06: Creates MEDIUM severity finding when client roams
        more than threshold times within the analysis window.

        Args:
            roam_events_by_client: Dict mapping client MAC to roam events
            threshold: Minimum roams to trigger flapping warning (default: 5)

        Returns:
            List of flapping Finding objects
        """
        findings = []

        for client_mac, events in roam_events_by_client.items():
            if len(events) < threshold:
                continue

            # Get unique APs involved
            ap_names: set[str] = set()
            for event in events:
                raw = event.raw_data or {}
                ap_from = raw.get("ap_from_name", raw.get("ap_from", ""))
                ap_to = raw.get("ap_to_name", raw.get("ap_to", ""))
                if ap_from:
                    ap_names.add(ap_from)
                if ap_to:
                    ap_names.add(ap_to)

            ap_list = ", ".join(sorted(ap_names)) if ap_names else "multiple APs"

            finding = Finding(
                severity=Severity.MEDIUM,
                category=Category.WIRELESS,
                title=f"[Wireless] Client flapping detected ({len(events)} roams)",
                description=(
                    f"Client {client_mac} roamed {len(events)} times during this analysis period, "
                    f"which suggests unstable connectivity. The client moved between: {ap_list}. "
                    "Frequent roaming (flapping) typically indicates coverage gaps, interference, "
                    "or misconfigured roaming thresholds."
                ),
                remediation=(
                    "1. Check for coverage gaps between the APs - client may be in a dead zone\n"
                    "2. Verify AP power levels are balanced (not too high or low)\n"
                    "3. Check for interference sources causing signal fluctuation\n"
                    "4. Consider adjusting Min-RSSI settings if using BSS Transition\n"
                    "5. If client is stationary, it may have a faulty wireless adapter"
                ),
                source_log_ids=[e.id for e in events],
                first_seen=min(e.timestamp for e in events),
                last_seen=max(e.timestamp for e in events),
                device_mac=client_mac,
                device_name=client_mac,  # Client MAC as identifier
                metadata={
                    "rule_name": "client_flapping",
                    "event_type": "aggregation",
                    "roam_count": len(events),
                    "aps_involved": list(ap_names),
                },
            )
            findings.append(finding)
            logger.info(
                "flapping_detected",
                client=client_mac,
                roam_count=len(events),
                aps=list(ap_names),
            )

        return findings
