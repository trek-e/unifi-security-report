"""Tests for health rules (PoE disconnect and overload)."""

import pytest
from datetime import datetime, timezone

from unifi_scanner.analysis.rules import (
    HEALTH_RULES,
    ALL_RULES,
    get_default_registry,
)
from unifi_scanner.analysis import AnalysisEngine
from unifi_scanner.models.enums import Category, Severity, LogSource
from unifi_scanner.models.log_entry import LogEntry


class TestHealthRulesStructure:
    """Tests for health rules structure and count."""

    def test_health_rules_exist(self):
        """Verify HEALTH_RULES has 2 rules."""
        assert len(HEALTH_RULES) == 2

    def test_all_rules_have_system_category(self):
        """All health rules must have SYSTEM category."""
        for rule in HEALTH_RULES:
            assert rule.category == Category.SYSTEM, (
                f"Rule {rule.name} should have SYSTEM category"
            )

    def test_health_rules_have_unique_names(self):
        """All health rule names must be unique."""
        names = [r.name for r in HEALTH_RULES]
        assert len(names) == len(set(names)), "Rule names must be unique"

    def test_health_rules_in_all_rules(self):
        """Verify HEALTH_RULES are included in ALL_RULES."""
        for rule in HEALTH_RULES:
            assert rule in ALL_RULES, f"Rule {rule.name} should be in ALL_RULES"

    def test_poe_disconnect_is_first_rule(self):
        """Verify poe_disconnect is the first rule."""
        assert HEALTH_RULES[0].name == "poe_disconnect"

    def test_poe_overload_is_second_rule(self):
        """Verify poe_overload is the second rule."""
        assert HEALTH_RULES[1].name == "poe_overload"


class TestPoeDisconnectRule:
    """Tests for poe_disconnect rule."""

    @pytest.fixture
    def disconnect_rule(self):
        """Get the poe_disconnect rule."""
        for rule in HEALTH_RULES:
            if rule.name == "poe_disconnect":
                return rule
        pytest.fail("poe_disconnect rule not found")

    def test_poe_disconnect_matches_event(self, disconnect_rule):
        """Rule matches EVT_SW_PoeDisconnect event."""
        assert disconnect_rule.matches("EVT_SW_PoeDisconnect", "PoE device disconnected")

    def test_poe_disconnect_has_medium_severity(self, disconnect_rule):
        """PoE disconnect is MEDIUM severity."""
        assert disconnect_rule.severity == Severity.MEDIUM

    def test_poe_disconnect_has_system_category(self, disconnect_rule):
        """PoE disconnect is SYSTEM category."""
        assert disconnect_rule.category == Category.SYSTEM

    def test_poe_disconnect_has_remediation(self, disconnect_rule):
        """MEDIUM severity rules have remediation."""
        assert disconnect_rule.remediation_template is not None

    def test_poe_disconnect_remediation_has_5_steps(self, disconnect_rule):
        """Remediation has 5 steps."""
        steps = [s for s in disconnect_rule.remediation_template.split("\n") if s.strip()]
        assert len(steps) >= 5

    def test_poe_disconnect_title_has_port(self, disconnect_rule):
        """Title template includes port placeholder."""
        assert "{port}" in disconnect_rule.title_template
        assert "{device_name}" in disconnect_rule.title_template


class TestPoeOverloadRule:
    """Tests for poe_overload rule."""

    @pytest.fixture
    def overload_rule(self):
        """Get the poe_overload rule."""
        for rule in HEALTH_RULES:
            if rule.name == "poe_overload":
                return rule
        pytest.fail("poe_overload rule not found")

    def test_poe_overload_matches_overload_event(self, overload_rule):
        """Rule matches EVT_SW_PoeOverload event."""
        assert overload_rule.matches("EVT_SW_PoeOverload", "PoE overload detected")

    def test_poe_overload_matches_budget_exceeded_event(self, overload_rule):
        """Rule matches EVT_SW_PoeBudgetExceeded event."""
        assert overload_rule.matches("EVT_SW_PoeBudgetExceeded", "PoE budget exceeded")

    def test_poe_overload_has_severe_severity(self, overload_rule):
        """PoE overload is SEVERE severity."""
        assert overload_rule.severity == Severity.SEVERE

    def test_poe_overload_has_system_category(self, overload_rule):
        """PoE overload is SYSTEM category."""
        assert overload_rule.category == Category.SYSTEM

    def test_poe_overload_has_remediation(self, overload_rule):
        """SEVERE severity rules have remediation."""
        assert overload_rule.remediation_template is not None

    def test_poe_overload_remediation_has_6_steps(self, overload_rule):
        """Remediation has 6 steps."""
        steps = [s for s in overload_rule.remediation_template.split("\n") if s.strip()]
        assert len(steps) >= 6

    def test_poe_overload_description_mentions_immediate_attention(self, overload_rule):
        """Description emphasizes immediate attention."""
        assert "IMMEDIATE ATTENTION" in overload_rule.description_template


class TestRegistryIntegration:
    """Tests for health rules integration with default registry."""

    def test_health_rules_registered_in_default_registry(self):
        """get_default_registry() includes health rules."""
        registry = get_default_registry()

        # Check health event types are known
        assert registry.is_known_event_type("EVT_SW_PoeDisconnect")
        assert registry.is_known_event_type("EVT_SW_PoeOverload")
        assert registry.is_known_event_type("EVT_SW_PoeBudgetExceeded")

    def test_registry_finds_poe_disconnect_rule(self):
        """Registry can find matching rule for PoE disconnect event."""
        registry = get_default_registry()
        rule = registry.find_matching_rule("EVT_SW_PoeDisconnect", "PoE device disconnected")

        assert rule is not None
        assert rule.name == "poe_disconnect"
        assert rule.category == Category.SYSTEM

    def test_registry_finds_poe_overload_rule(self):
        """Registry can find matching rule for PoE overload event."""
        registry = get_default_registry()
        rule = registry.find_matching_rule("EVT_SW_PoeOverload", "PoE overload")

        assert rule is not None
        assert rule.name == "poe_overload"

    def test_registry_finds_poe_budget_exceeded_rule(self):
        """Registry can find matching rule for PoE budget exceeded event."""
        registry = get_default_registry()
        rule = registry.find_matching_rule("EVT_SW_PoeBudgetExceeded", "Budget exceeded")

        assert rule is not None
        assert rule.name == "poe_overload"


class TestEngineIntegration:
    """Tests for health rules with AnalysisEngine."""

    @pytest.fixture
    def engine(self):
        """Create engine with default registry."""
        return AnalysisEngine(registry=get_default_registry())

    def test_engine_processes_poe_disconnect_event(self, engine):
        """Engine creates finding from PoE disconnect event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_SW_PoeDisconnect",
            message="PoE device disconnected on port 5",
            device_name="Core-Switch",
            raw_data={"port": "5"},
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.SYSTEM
        assert finding.severity == Severity.MEDIUM
        assert "[Device Health]" in finding.title
        assert finding.remediation is not None

    def test_engine_processes_poe_overload_event(self, engine):
        """Engine creates finding from PoE overload event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_SW_PoeOverload",
            message="PoE power budget exceeded",
            device_name="Office-Switch",
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.SYSTEM
        assert finding.severity == Severity.SEVERE
        assert "[Device Health]" in finding.title
        assert finding.remediation is not None

    def test_engine_processes_poe_budget_exceeded_event(self, engine):
        """Engine creates finding from PoE budget exceeded event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_SW_PoeBudgetExceeded",
            message="PoE budget exceeded on switch",
            device_name="Access-Switch",
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.SYSTEM
        assert finding.severity == Severity.SEVERE
        assert finding.remediation is not None


class TestRemediation:
    """Tests for remediation templates."""

    def test_poe_disconnect_remediation_mentions_budget(self):
        """PoE disconnect remediation mentions power budget."""
        rule = HEALTH_RULES[0]  # poe_disconnect
        assert "budget" in rule.remediation_template.lower()

    def test_poe_disconnect_remediation_mentions_cable(self):
        """PoE disconnect remediation mentions cable check."""
        rule = HEALTH_RULES[0]  # poe_disconnect
        assert "cable" in rule.remediation_template.lower()

    def test_poe_overload_remediation_mentions_disconnect(self):
        """PoE overload remediation mentions disconnecting devices."""
        rule = HEALTH_RULES[1]  # poe_overload
        assert "disconnect" in rule.remediation_template.lower()

    def test_poe_overload_remediation_mentions_injectors(self):
        """PoE overload remediation mentions external injectors."""
        rule = HEALTH_RULES[1]  # poe_overload
        assert "injector" in rule.remediation_template.lower()
