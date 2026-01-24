"""Base rule definitions and registry for analysis engine."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern
import re

from unifi_scanner.models.enums import Category, Severity


@dataclass
class Rule:
    """Definition of a single analysis rule.

    Rules match LogEntry objects based on event_type and optional
    message pattern, then provide category, severity, and templates
    for generating findings.

    Attributes:
        name: Human-readable rule name for debugging
        event_types: List of event types this rule handles
        category: Finding category (Security, Connectivity, etc.)
        severity: Finding severity (low, medium, severe)
        title_template: Template for finding title with {placeholders}
        description_template: Plain English explanation with {placeholders}
        remediation_template: Step-by-step fix (SEVERE/MEDIUM only, None for LOW)
        pattern: Optional regex for additional message matching
    """

    name: str
    event_types: List[str]
    category: Category
    severity: Severity
    title_template: str
    description_template: str
    remediation_template: Optional[str] = None
    pattern: Optional[Pattern] = field(default=None, repr=False)

    def __post_init__(self):
        """Compile pattern string to regex if needed."""
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)

    def matches(self, event_type: str, message: str) -> bool:
        """Check if this rule applies to the given event.

        Args:
            event_type: The event_type from LogEntry
            message: The message from LogEntry

        Returns:
            True if rule matches (event_type in list AND pattern matches if set)
        """
        if event_type not in self.event_types:
            return False
        if self.pattern and not self.pattern.search(message):
            return False
        return True


class RuleRegistry:
    """Registry of rules with dictionary dispatch by event_type.

    Provides O(1) lookup of rules by event_type, with support for
    multiple rules per event_type and unknown event handling.
    """

    def __init__(self):
        self._rules: List[Rule] = []
        # Index: event_type -> list of rules that handle it
        self._index: Dict[str, List[Rule]] = {}

    def register(self, rule: Rule) -> None:
        """Register a rule in the registry.

        Args:
            rule: Rule instance to register
        """
        self._rules.append(rule)
        for event_type in rule.event_types:
            if event_type not in self._index:
                self._index[event_type] = []
            self._index[event_type].append(rule)

    def get_rules(self, event_type: str) -> List[Rule]:
        """Get all rules that might handle an event_type.

        Args:
            event_type: The event_type to look up

        Returns:
            List of matching Rule objects (empty if unknown event_type)
        """
        return self._index.get(event_type, [])

    def find_matching_rule(self, event_type: str, message: str) -> Optional[Rule]:
        """Find the first rule that matches event_type and message.

        Args:
            event_type: The event_type from LogEntry
            message: The message from LogEntry

        Returns:
            First matching Rule, or None if no match
        """
        for rule in self.get_rules(event_type):
            if rule.matches(event_type, message):
                return rule
        return None

    def is_known_event_type(self, event_type: str) -> bool:
        """Check if event_type has any registered rules.

        Args:
            event_type: The event_type to check

        Returns:
            True if at least one rule handles this event_type
        """
        return event_type in self._index

    @property
    def all_rules(self) -> List[Rule]:
        """Get all registered rules."""
        return list(self._rules)

    @property
    def known_event_types(self) -> List[str]:
        """Get all known event types."""
        return list(self._index.keys())
