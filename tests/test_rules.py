"""Tests for rule definitions across all categories."""

import pytest
from datetime import datetime, timezone

from unifi_scanner.analysis.rules import (
    Rule,
    RuleRegistry,
    SECURITY_RULES,
    CONNECTIVITY_RULES,
    PERFORMANCE_RULES,
    SYSTEM_RULES,
    WIRELESS_RULES,
    ALL_RULES,
    get_default_registry,
)
from unifi_scanner.analysis import AnalysisEngine
from unifi_scanner.models.enums import Category, Severity, LogSource
from unifi_scanner.models.log_entry import LogEntry


class TestRuleAggregation:
    """Tests for rule aggregation and counting."""

    def test_all_rules_count(self):
        """Verify total rule count is 27 (4 + 7 + 5 + 7 + 4)."""
        assert len(ALL_RULES) == 27, f"Expected 27 rules, got {len(ALL_RULES)}"

    def test_security_rules_count(self):
        """Verify security has 4 rules."""
        assert len(SECURITY_RULES) == 4

    def test_connectivity_rules_count(self):
        """Verify connectivity has 7 rules."""
        assert len(CONNECTIVITY_RULES) == 7

    def test_performance_rules_count(self):
        """Verify performance has 5 rules."""
        assert len(PERFORMANCE_RULES) == 5

    def test_system_rules_count(self):
        """Verify system has 7 rules."""
        assert len(SYSTEM_RULES) == 7

    def test_wireless_rules_count(self):
        """Verify wireless has 4 rules."""
        assert len(WIRELESS_RULES) == 4

    def test_all_rules_unique_names(self):
        """Verify all rule names are unique."""
        names = [r.name for r in ALL_RULES]
        assert len(names) == len(set(names)), "Rule names must be unique"


class TestRuleRequiredFields:
    """Tests for required fields on all rules."""

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_rule_has_name(self, rule):
        """Every rule must have a non-empty name."""
        assert rule.name, "Rule name cannot be empty"

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_rule_has_event_types(self, rule):
        """Every rule must have at least one event type."""
        assert len(rule.event_types) > 0, f"Rule {rule.name} needs event types"

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_rule_has_category(self, rule):
        """Every rule must have a valid category."""
        assert isinstance(rule.category, Category)

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_rule_has_severity(self, rule):
        """Every rule must have a valid severity."""
        assert isinstance(rule.severity, Severity)

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_rule_has_title_template(self, rule):
        """Every rule must have a title template."""
        assert rule.title_template, f"Rule {rule.name} needs title template"

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_rule_has_description_template(self, rule):
        """Every rule must have a description template."""
        assert rule.description_template, f"Rule {rule.name} needs description"


class TestRemediationPolicy:
    """Tests for remediation template policy.

    Per user decision: SEVERE and MEDIUM get remediation, LOW does not.
    """

    @pytest.mark.parametrize(
        "rule",
        [r for r in ALL_RULES if r.severity == Severity.SEVERE],
        ids=lambda r: r.name,
    )
    def test_severe_rules_have_remediation(self, rule):
        """SEVERE rules must have remediation guidance."""
        assert rule.remediation_template is not None, (
            f"SEVERE rule {rule.name} must have remediation_template"
        )

    @pytest.mark.parametrize(
        "rule",
        [r for r in ALL_RULES if r.severity == Severity.MEDIUM],
        ids=lambda r: r.name,
    )
    def test_medium_rules_have_remediation(self, rule):
        """MEDIUM rules must have remediation guidance."""
        assert rule.remediation_template is not None, (
            f"MEDIUM rule {rule.name} must have remediation_template"
        )

    @pytest.mark.parametrize(
        "rule",
        [r for r in ALL_RULES if r.severity == Severity.LOW],
        ids=lambda r: r.name,
    )
    def test_low_rules_no_remediation(self, rule):
        """LOW rules must NOT have remediation (per user decision)."""
        assert rule.remediation_template is None, (
            f"LOW rule {rule.name} should not have remediation_template"
        )


class TestTitleFormat:
    """Tests for title formatting conventions."""

    CATEGORY_PREFIXES = {
        Category.SECURITY: "[Security]",
        Category.CONNECTIVITY: "[Connectivity]",
        Category.PERFORMANCE: "[Performance]",
        Category.SYSTEM: "[System]",
        Category.WIRELESS: "[Wireless]",
    }

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_title_includes_category_prefix(self, rule):
        """All titles must include category prefix in brackets."""
        expected_prefix = self.CATEGORY_PREFIXES.get(rule.category)
        assert expected_prefix in rule.title_template, (
            f"Rule {rule.name} title must start with {expected_prefix}"
        )


class TestDescriptionFormat:
    """Tests for description formatting conventions."""

    @pytest.mark.parametrize("rule", ALL_RULES, ids=lambda r: r.name)
    def test_description_includes_event_type(self, rule):
        """All descriptions must include at least one event_type for searchability."""
        # Check if any event type appears in description (for Googling)
        has_event_type = any(
            evt in rule.description_template for evt in rule.event_types
        )
        # Or has a generic event type reference pattern
        has_generic_ref = (
            "EVT_" in rule.description_template
            or "{event_type}" in rule.description_template
        )
        assert has_event_type or has_generic_ref, (
            f"Rule {rule.name} description should include event type for searchability"
        )


class TestCategoryAssignment:
    """Tests for correct category assignment."""

    def test_security_rules_have_security_category(self):
        """All SECURITY_RULES must have Security category."""
        for rule in SECURITY_RULES:
            assert rule.category == Category.SECURITY, (
                f"Rule {rule.name} in SECURITY_RULES must have Security category"
            )

    def test_connectivity_rules_have_connectivity_category(self):
        """All CONNECTIVITY_RULES must have Connectivity category."""
        for rule in CONNECTIVITY_RULES:
            assert rule.category == Category.CONNECTIVITY, (
                f"Rule {rule.name} in CONNECTIVITY_RULES must have Connectivity category"
            )

    def test_performance_rules_have_performance_category(self):
        """All PERFORMANCE_RULES must have Performance category."""
        for rule in PERFORMANCE_RULES:
            assert rule.category == Category.PERFORMANCE, (
                f"Rule {rule.name} in PERFORMANCE_RULES must have Performance category"
            )

    def test_system_rules_have_system_category(self):
        """All SYSTEM_RULES must have System category."""
        for rule in SYSTEM_RULES:
            assert rule.category == Category.SYSTEM, (
                f"Rule {rule.name} in SYSTEM_RULES must have System category"
            )

    def test_wireless_rules_have_wireless_category(self):
        """All WIRELESS_RULES must have Wireless category."""
        for rule in WIRELESS_RULES:
            assert rule.category == Category.WIRELESS, (
                f"Rule {rule.name} in WIRELESS_RULES must have Wireless category"
            )


class TestGetDefaultRegistry:
    """Tests for get_default_registry helper."""

    def test_returns_populated_registry(self):
        """get_default_registry returns a registry with all rules."""
        registry = get_default_registry()
        assert len(registry.all_rules) == len(ALL_RULES)

    def test_registry_knows_all_event_types(self):
        """Registry has all event types indexed."""
        registry = get_default_registry()
        all_event_types = set()
        for rule in ALL_RULES:
            all_event_types.update(rule.event_types)

        for event_type in all_event_types:
            assert registry.is_known_event_type(event_type), (
                f"Registry missing event type: {event_type}"
            )


class TestEngineIntegration:
    """Tests for integration with AnalysisEngine."""

    @pytest.fixture
    def engine(self):
        """Create an engine with default registry."""
        return AnalysisEngine(registry=get_default_registry())

    def test_engine_processes_security_event(self, engine):
        """Engine creates finding from security event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AD_LOGIN_FAILED",
            message="Login failed from suspicious IP",
            raw_data={"ip": "10.0.0.1"},
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.SECURITY
        assert finding.severity == Severity.SEVERE
        assert "[Security]" in finding.title
        assert finding.remediation is not None

    def test_engine_processes_connectivity_event(self, engine):
        """Engine creates finding from connectivity event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AP_Lost_Contact",
            message="AP went offline",
            device_name="Office-AP",
            device_mac="aa:bb:cc:dd:ee:ff",
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.CONNECTIVITY
        assert finding.severity == Severity.SEVERE
        assert "Office-AP" in finding.title

    def test_engine_processes_performance_event(self, engine):
        """Engine creates finding from performance event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AP_Interference",
            message="Radar detected, switching channels",
            device_name="Lab-AP",
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.PERFORMANCE
        assert finding.severity == Severity.MEDIUM
        assert finding.remediation is not None

    def test_engine_processes_system_event(self, engine):
        """Engine creates finding from system event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AP_Upgraded",
            message="Firmware upgraded successfully",
            device_name="Gateway",
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.category == Category.SYSTEM
        assert finding.severity == Severity.LOW
        assert finding.remediation is None  # LOW severity

    def test_engine_handles_unknown_event(self, engine):
        """Engine tracks unknown event types gracefully."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_FUTURE_FEATURE",
            message="Some new feature",
        )

        finding = engine.analyze_entry(entry)

        assert finding is None
        assert "EVT_FUTURE_FEATURE" in engine.unknown_event_types

    def test_batch_analysis(self, engine):
        """Engine can analyze multiple entries."""
        entries = [
            LogEntry(
                timestamp=datetime.now(timezone.utc),
                source=LogSource.API,
                event_type="EVT_AD_LOGIN_FAILED",
                message="Failed login",
                raw_data={"ip": "1.1.1.1"},
            ),
            LogEntry(
                timestamp=datetime.now(timezone.utc),
                source=LogSource.API,
                event_type="EVT_AP_Lost_Contact",
                message="AP down",
                device_name="Test-AP",
            ),
            LogEntry(
                timestamp=datetime.now(timezone.utc),
                source=LogSource.API,
                event_type="EVT_UNKNOWN_TYPE",
                message="Unknown",
            ),
        ]

        findings = engine.analyze(entries)

        assert len(findings) == 2  # 2 matched, 1 unknown
        categories = {f.category for f in findings}
        assert Category.SECURITY in categories
        assert Category.CONNECTIVITY in categories
