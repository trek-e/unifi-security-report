"""Main analysis engine for processing UniFi logs."""

from typing import Any, Dict, List, Optional

import structlog

from unifi_scanner.models.enums import Category, Severity
from unifi_scanner.models.finding import Finding
from unifi_scanner.models.log_entry import LogEntry
from unifi_scanner.analysis.rules.base import Rule, RuleRegistry

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
        for entry in entries:
            finding = self.analyze_entry(entry)
            if finding:
                findings.append(finding)

        logger.info(
            "analysis_complete",
            entries_processed=len(entries),
            findings_created=len(findings),
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
