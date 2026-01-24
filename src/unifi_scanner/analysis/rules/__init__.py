"""Rule definitions for analysis engine.

Aggregates all category rules and provides convenience functions.
"""

from typing import List

from unifi_scanner.analysis.rules.base import Rule, RuleRegistry
from unifi_scanner.analysis.rules.security import SECURITY_RULES
from unifi_scanner.analysis.rules.connectivity import CONNECTIVITY_RULES
from unifi_scanner.analysis.rules.performance import PERFORMANCE_RULES
from unifi_scanner.analysis.rules.system import SYSTEM_RULES


# Aggregate all rules from all categories
ALL_RULES: List[Rule] = (
    SECURITY_RULES
    + CONNECTIVITY_RULES
    + PERFORMANCE_RULES
    + SYSTEM_RULES
)


def get_default_registry() -> RuleRegistry:
    """Create a RuleRegistry pre-populated with all default rules.

    Returns:
        RuleRegistry with all rules from all categories registered.

    Usage:
        registry = get_default_registry()
        engine = AnalysisEngine(registry=registry)
    """
    registry = RuleRegistry()
    for rule in ALL_RULES:
        registry.register(rule)
    return registry


__all__ = [
    "Rule",
    "RuleRegistry",
    "SECURITY_RULES",
    "CONNECTIVITY_RULES",
    "PERFORMANCE_RULES",
    "SYSTEM_RULES",
    "ALL_RULES",
    "get_default_registry",
]
