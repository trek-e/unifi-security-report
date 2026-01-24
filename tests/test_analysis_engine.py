"""Tests for the analysis engine."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from unifi_scanner.analysis import AnalysisEngine, Rule, RuleRegistry
from unifi_scanner.models.enums import Category, Severity, LogSource
from unifi_scanner.models.log_entry import LogEntry
from unifi_scanner.models.finding import Finding


@pytest.fixture
def sample_rule():
    """Create a sample rule for testing."""
    return Rule(
        name="test_failed_login",
        event_types=["EVT_AD_LOGIN_FAILED"],
        category=Category.SECURITY,
        severity=Severity.SEVERE,
        title_template="[Security] Failed login from {ip}",
        description_template=(
            "Someone attempted to log into your UniFi controller from {ip} "
            "but failed authentication ({event_type}). This could indicate "
            "someone trying to guess your password."
        ),
        remediation_template=(
            "1. Check if you recognize the IP address {ip}\n"
            "2. Consider blocking this IP in your firewall"
        ),
    )


@pytest.fixture
def sample_log_entry():
    """Create a sample log entry for testing."""
    return LogEntry(
        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        source=LogSource.API,
        event_type="EVT_AD_LOGIN_FAILED",
        message="Admin login failed",
        device_name="UDM-Pro",
        raw_data={"ip": "192.168.1.100", "admin": "admin"},
    )


@pytest.fixture
def engine(sample_rule):
    """Create an engine with sample rule registered."""
    engine = AnalysisEngine()
    engine.register_rule(sample_rule)
    return engine


class TestRuleRegistry:
    """Tests for RuleRegistry."""

    def test_register_and_lookup(self, sample_rule):
        """Test rule registration and lookup."""
        registry = RuleRegistry()
        registry.register(sample_rule)

        assert registry.is_known_event_type("EVT_AD_LOGIN_FAILED")
        assert not registry.is_known_event_type("EVT_UNKNOWN")

    def test_find_matching_rule(self, sample_rule):
        """Test finding matching rule."""
        registry = RuleRegistry()
        registry.register(sample_rule)

        rule = registry.find_matching_rule("EVT_AD_LOGIN_FAILED", "any message")
        assert rule is not None
        assert rule.name == "test_failed_login"

    def test_find_no_match(self, sample_rule):
        """Test no match for unknown event."""
        registry = RuleRegistry()
        registry.register(sample_rule)

        rule = registry.find_matching_rule("EVT_UNKNOWN", "any message")
        assert rule is None

    def test_pattern_matching(self):
        """Test rule with regex pattern."""
        rule = Rule(
            name="high_cpu",
            event_types=["EVT_AP_ALERT"],
            category=Category.PERFORMANCE,
            severity=Severity.MEDIUM,
            title_template="High CPU on {device_name}",
            description_template="CPU usage exceeded threshold",
            pattern=r"CPU.*\d+%",
        )
        registry = RuleRegistry()
        registry.register(rule)

        # Should match with pattern
        match = registry.find_matching_rule("EVT_AP_ALERT", "CPU usage at 95%")
        assert match is not None

        # Should not match without pattern
        no_match = registry.find_matching_rule("EVT_AP_ALERT", "Memory usage high")
        assert no_match is None

    def test_all_rules_property(self, sample_rule):
        """Test all_rules property returns all registered rules."""
        registry = RuleRegistry()
        registry.register(sample_rule)

        rules = registry.all_rules
        assert len(rules) == 1
        assert rules[0].name == "test_failed_login"

    def test_known_event_types_property(self, sample_rule):
        """Test known_event_types property returns all event types."""
        registry = RuleRegistry()
        registry.register(sample_rule)

        event_types = registry.known_event_types
        assert "EVT_AD_LOGIN_FAILED" in event_types


class TestAnalysisEngine:
    """Tests for AnalysisEngine."""

    def test_analyze_entry_creates_finding(self, engine, sample_log_entry):
        """Test that matching entry creates finding."""
        finding = engine.analyze_entry(sample_log_entry)

        assert finding is not None
        assert finding.severity == Severity.SEVERE
        assert finding.category == Category.SECURITY
        assert "192.168.1.100" in finding.title
        assert finding.remediation is not None
        assert sample_log_entry.id in finding.source_log_ids

    def test_analyze_entry_unknown_type(self, engine):
        """Test that unknown event type is tracked but returns None."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_UNKNOWN_NEW",
            message="Something new",
        )

        finding = engine.analyze_entry(entry)

        assert finding is None
        assert "EVT_UNKNOWN_NEW" in engine.unknown_event_types
        assert engine.unknown_event_types["EVT_UNKNOWN_NEW"] == 1

    def test_analyze_multiple_entries(self, engine, sample_log_entry):
        """Test analyzing multiple entries."""
        entries = [sample_log_entry, sample_log_entry]
        findings = engine.analyze(entries)

        assert len(findings) == 2

    def test_template_rendering_with_missing_key(self, engine):
        """Test template renders gracefully with missing key."""
        # Create entry without ip in raw_data
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AD_LOGIN_FAILED",
            message="Login failed",
            raw_data={},  # No ip key
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert "Unknown" in finding.title  # {ip} replaced with Unknown

    def test_device_name_fallback_to_mac(self, engine):
        """Test device name falls back to MAC address."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AD_LOGIN_FAILED",
            message="Login failed",
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name=None,
            raw_data={"ip": "10.0.0.1"},
        )

        finding = engine.analyze_entry(entry)

        # Context should use MAC as device_name
        assert finding.device_mac == "aa:bb:cc:dd:ee:ff"

    def test_remediation_only_for_severe_and_medium(self):
        """Test that LOW severity rules don't get remediation."""
        low_rule = Rule(
            name="admin_login",
            event_types=["EVT_AD_Login"],
            category=Category.SYSTEM,
            severity=Severity.LOW,
            title_template="Admin login",
            description_template="An admin logged in",
            remediation_template="This should not appear",  # Has template but LOW severity
        )

        engine = AnalysisEngine()
        engine.register_rule(low_rule)

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_AD_Login",
            message="Admin login",
        )

        finding = engine.analyze_entry(entry)

        assert finding is not None
        assert finding.remediation is None  # Should not have remediation for LOW

    def test_unknown_event_count_increments(self, engine):
        """Test that unknown event types are counted correctly."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_MYSTERY",
            message="Mystery event",
        )

        engine.analyze_entry(entry)
        engine.analyze_entry(entry)
        engine.analyze_entry(entry)

        assert engine.unknown_event_types["EVT_MYSTERY"] == 3

    def test_clear_unknown_counts(self, engine):
        """Test clearing unknown event counts."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=LogSource.API,
            event_type="EVT_MYSTERY",
            message="Mystery event",
        )

        engine.analyze_entry(entry)
        assert len(engine.unknown_event_types) > 0

        engine.clear_unknown_counts()
        assert len(engine.unknown_event_types) == 0

    def test_finding_metadata_includes_rule_info(self, engine, sample_log_entry):
        """Test that finding metadata includes rule name and event type."""
        finding = engine.analyze_entry(sample_log_entry)

        assert finding.metadata["rule_name"] == "test_failed_login"
        assert finding.metadata["event_type"] == "EVT_AD_LOGIN_FAILED"

    def test_register_rules_batch(self, sample_rule):
        """Test registering multiple rules at once."""
        engine = AnalysisEngine()

        rule2 = Rule(
            name="another_rule",
            event_types=["EVT_OTHER"],
            category=Category.SYSTEM,
            severity=Severity.LOW,
            title_template="Other",
            description_template="Desc",
        )

        engine.register_rules([sample_rule, rule2])

        assert engine.registry.is_known_event_type("EVT_AD_LOGIN_FAILED")
        assert engine.registry.is_known_event_type("EVT_OTHER")


class TestRuleDefinition:
    """Tests for Rule dataclass."""

    def test_rule_creation(self):
        """Test basic rule creation."""
        rule = Rule(
            name="test",
            event_types=["EVT_A", "EVT_B"],
            category=Category.SECURITY,
            severity=Severity.SEVERE,
            title_template="Title",
            description_template="Description",
        )

        assert rule.name == "test"
        assert len(rule.event_types) == 2
        assert rule.remediation_template is None

    def test_rule_with_string_pattern(self):
        """Test that string pattern gets compiled to regex."""
        rule = Rule(
            name="test",
            event_types=["EVT_A"],
            category=Category.SYSTEM,
            severity=Severity.LOW,
            title_template="Title",
            description_template="Desc",
            pattern=r"\d+",
        )

        assert rule.pattern is not None
        assert rule.pattern.search("test 123") is not None

    def test_rule_matches_event_type(self):
        """Test rule matching by event type."""
        rule = Rule(
            name="test",
            event_types=["EVT_A", "EVT_B"],
            category=Category.SYSTEM,
            severity=Severity.LOW,
            title_template="Title",
            description_template="Desc",
        )

        assert rule.matches("EVT_A", "any message") is True
        assert rule.matches("EVT_B", "any message") is True
        assert rule.matches("EVT_C", "any message") is False

    def test_rule_matches_with_pattern(self):
        """Test rule matching with pattern requirement."""
        rule = Rule(
            name="test",
            event_types=["EVT_A"],
            category=Category.SYSTEM,
            severity=Severity.LOW,
            title_template="Title",
            description_template="Desc",
            pattern=r"error",
        )

        assert rule.matches("EVT_A", "an error occurred") is True
        assert rule.matches("EVT_A", "success message") is False
