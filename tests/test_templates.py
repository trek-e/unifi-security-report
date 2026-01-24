"""Tests for explanation and remediation templates and FindingFormatter.

Tests verify:
- Template structure (title, description presence)
- User style decisions (category prefix, event type, absolute timestamps)
- Remediation policy (SEVERE=steps, MEDIUM=guidance, LOW=None)
- FindingFormatter timezone handling and output generation
"""

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from unifi_scanner.analysis.templates import (
    EXPLANATION_TEMPLATES,
    REMEDIATION_TEMPLATES,
    render_explanation,
    render_remediation,
)
from unifi_scanner.analysis.formatter import FindingFormatter
from unifi_scanner.models.enums import Category, Severity
from unifi_scanner.models.finding import Finding, RECURRING_THRESHOLD


class TestExplanationTemplates:
    """Tests for EXPLANATION_TEMPLATES structure and content."""

    def test_all_templates_have_title(self):
        """Every template must have a title field."""
        for key, template in EXPLANATION_TEMPLATES.items():
            assert "title" in template, f"Template '{key}' missing 'title'"
            assert template["title"], f"Template '{key}' has empty title"

    def test_all_templates_have_description(self):
        """Every template must have a description field."""
        for key, template in EXPLANATION_TEMPLATES.items():
            assert "description" in template, f"Template '{key}' missing 'description'"
            assert template["description"], f"Template '{key}' has empty description"

    def test_titles_include_category_prefix(self):
        """All titles must include category prefix in brackets."""
        valid_prefixes = ["[Security]", "[Connectivity]", "[Performance]", "[System]", "[Uncategorized]"]
        for key, template in EXPLANATION_TEMPLATES.items():
            title = template["title"]
            has_prefix = any(title.startswith(prefix) for prefix in valid_prefixes)
            assert has_prefix, f"Template '{key}' title '{title}' missing category prefix"

    def test_descriptions_include_event_type_placeholder(self):
        """All descriptions must include {event_type} for Googling."""
        for key, template in EXPLANATION_TEMPLATES.items():
            description = template["description"]
            assert "{event_type}" in description, (
                f"Template '{key}' description missing {{event_type}} placeholder"
            )

    def test_unknown_template_exists(self):
        """Fallback 'unknown' template must exist."""
        assert "unknown" in EXPLANATION_TEMPLATES
        assert EXPLANATION_TEMPLATES["unknown"]["title"] == "[Uncategorized] Network Event"

    def test_security_templates_exist(self):
        """Security templates must exist for key event types."""
        expected = ["admin_login_failed", "admin_login_success", "rogue_ap_detected", "ips_alert"]
        for key in expected:
            assert key in EXPLANATION_TEMPLATES, f"Missing security template: {key}"
            assert EXPLANATION_TEMPLATES[key]["title"].startswith("[Security]")

    def test_connectivity_templates_exist(self):
        """Connectivity templates must exist for key event types."""
        expected = ["ap_lost_contact", "switch_lost_contact", "gateway_wan_down", "ap_isolated"]
        for key in expected:
            assert key in EXPLANATION_TEMPLATES, f"Missing connectivity template: {key}"
            assert EXPLANATION_TEMPLATES[key]["title"].startswith("[Connectivity]")

    def test_performance_templates_exist(self):
        """Performance templates must exist for key event types."""
        expected = ["interference_detected", "high_cpu", "high_memory", "slow_speed", "channel_congestion"]
        for key in expected:
            assert key in EXPLANATION_TEMPLATES, f"Missing performance template: {key}"
            assert EXPLANATION_TEMPLATES[key]["title"].startswith("[Performance]")

    def test_system_templates_exist(self):
        """System templates must exist for key event types."""
        expected = [
            "firmware_upgraded", "device_restarted", "device_restarted_unexpected",
            "device_adopted", "config_changed", "backup_created", "update_available"
        ]
        for key in expected:
            assert key in EXPLANATION_TEMPLATES, f"Missing system template: {key}"
            assert EXPLANATION_TEMPLATES[key]["title"].startswith("[System]")


class TestRenderExplanation:
    """Tests for render_explanation function."""

    def test_basic_rendering(self):
        """render_explanation returns title and description with context."""
        result = render_explanation("admin_login_failed", {
            "event_type": "EVT_ADMIN_LOGIN_FAILED",
            "ip_address": "192.168.1.100",
        })
        assert "title" in result
        assert "description" in result
        assert "[Security]" in result["title"]
        assert "EVT_ADMIN_LOGIN_FAILED" in result["description"]
        assert "192.168.1.100" in result["description"]

    def test_missing_key_replaced_with_unknown(self):
        """Missing context keys should be replaced with 'Unknown'."""
        result = render_explanation("admin_login_failed", {
            "event_type": "EVT_ADMIN_LOGIN_FAILED",
            # ip_address intentionally missing
        })
        assert "Unknown" in result["description"]

    def test_fallback_to_unknown_template(self):
        """Unknown template keys should fall back to 'unknown' template."""
        result = render_explanation("nonexistent_template_key", {
            "event_type": "UNKNOWN_EVENT",
            "message": "Some log message",
        })
        assert "[Uncategorized]" in result["title"]
        assert "UNKNOWN_EVENT" in result["description"]

    def test_device_name_in_context(self):
        """Device name placeholder should be rendered."""
        result = render_explanation("ap_lost_contact", {
            "event_type": "EVT_AP_LOST_CONTACT",
            "device_name": "Living Room AP",
        })
        assert "Living Room AP" in result["description"]


class TestRemediationTemplates:
    """Tests for REMEDIATION_TEMPLATES structure and content."""

    def test_severe_templates_have_numbered_steps(self):
        """SEVERE remediation must have numbered steps (1., 2., etc.)."""
        for key, template in REMEDIATION_TEMPLATES.items():
            if "severe" in template:
                severe_text = template["severe"]
                assert "1." in severe_text, f"Template '{key}' severe missing step 1"
                assert "2." in severe_text, f"Template '{key}' severe missing step 2"

    def test_medium_templates_exist_for_severe_rules(self):
        """Rules with severe remediation may have medium alternative."""
        # Not all need both, but verify structure is correct when present
        for key, template in REMEDIATION_TEMPLATES.items():
            if "medium" in template:
                medium_text = template["medium"]
                assert medium_text, f"Template '{key}' has empty medium remediation"
                # Medium should not have strict numbering
                assert not medium_text.strip().startswith("1."), (
                    f"Template '{key}' medium should not have numbered steps"
                )

    def test_security_remediations_exist(self):
        """Security events should have remediation templates."""
        expected = ["admin_login_failed", "rogue_ap_detected", "ips_alert"]
        for key in expected:
            assert key in REMEDIATION_TEMPLATES, f"Missing remediation for security rule: {key}"

    def test_connectivity_remediations_exist(self):
        """Critical connectivity events should have remediation."""
        expected = ["ap_lost_contact", "switch_lost_contact", "gateway_wan_down"]
        for key in expected:
            assert key in REMEDIATION_TEMPLATES, f"Missing remediation for connectivity rule: {key}"


class TestRenderRemediation:
    """Tests for render_remediation function."""

    def test_severe_returns_numbered_steps(self):
        """SEVERE severity returns numbered steps."""
        result = render_remediation("admin_login_failed", Severity.SEVERE, {
            "ip_address": "192.168.1.100",
        })
        assert result is not None
        assert "1." in result
        assert "192.168.1.100" in result

    def test_medium_returns_guidance(self):
        """MEDIUM severity returns high-level guidance."""
        result = render_remediation("admin_login_failed", Severity.MEDIUM, {})
        assert result is not None
        # Medium should not start with numbered steps
        assert not result.strip().startswith("1.")

    def test_low_returns_none(self):
        """LOW severity returns None (no remediation)."""
        result = render_remediation("admin_login_failed", Severity.LOW, {})
        assert result is None

    def test_unknown_rule_returns_none(self):
        """Unknown rule key returns None."""
        result = render_remediation("nonexistent_rule", Severity.SEVERE, {})
        assert result is None

    def test_missing_severity_returns_none(self):
        """Rule without matching severity returns None."""
        # admin_login_success has only medium, not severe
        result = render_remediation("admin_login_success", Severity.SEVERE, {})
        assert result is None

    def test_context_placeholders_replaced(self):
        """Context placeholders in remediation are replaced."""
        result = render_remediation("ap_lost_contact", Severity.SEVERE, {
            "device_name": "Office AP",
        })
        assert result is not None
        assert "Office AP" in result


class TestFindingFormatter:
    """Tests for FindingFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create formatter with Eastern timezone."""
        return FindingFormatter("America/New_York")

    @pytest.fixture
    def utc_formatter(self):
        """Create formatter with UTC timezone."""
        return FindingFormatter("UTC")

    @pytest.fixture
    def sample_finding(self):
        """Create a sample finding for testing."""
        return Finding(
            severity=Severity.SEVERE,
            category=Category.SECURITY,
            title="[Security] Failed Admin Login",
            description="Someone tried to log in but failed.",
            remediation="1. Check logs\n2. Block IP",
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name="Main Gateway",
            first_seen=datetime(2026, 1, 24, 14, 30, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 14, 30, 0, tzinfo=ZoneInfo("UTC")),
            occurrence_count=1,
        )

    def test_timezone_initialization(self, formatter):
        """Formatter stores display timezone."""
        assert formatter.display_timezone == "America/New_York"

    def test_format_timestamp_absolute(self, formatter):
        """Timestamps are absolute, not relative."""
        dt = datetime(2026, 1, 24, 14, 30, 0, tzinfo=ZoneInfo("UTC"))
        result = formatter.format_timestamp(dt)
        # Should contain date parts, not "2 hours ago"
        assert "Jan" in result
        assert "24" in result
        assert "2026" in result
        # Should not contain relative time
        assert "ago" not in result.lower()
        assert "yesterday" not in result.lower()

    def test_format_timestamp_includes_timezone_abbreviation(self, formatter):
        """Timestamps include timezone abbreviation."""
        dt = datetime(2026, 1, 24, 14, 30, 0, tzinfo=ZoneInfo("UTC"))
        result = formatter.format_timestamp(dt)
        # Eastern timezone in January is EST
        assert "EST" in result

    def test_format_timestamp_converts_timezone(self, formatter):
        """Timestamps are converted to display timezone."""
        # 2:30 PM UTC = 9:30 AM EST
        dt = datetime(2026, 1, 24, 14, 30, 0, tzinfo=ZoneInfo("UTC"))
        result = formatter.format_timestamp(dt)
        assert "9:30 AM" in result

    def test_format_timestamp_handles_naive_datetime(self, utc_formatter):
        """Naive datetimes are assumed to be UTC."""
        dt = datetime(2026, 1, 24, 14, 30, 0)  # No timezone
        result = utc_formatter.format_timestamp(dt)
        assert "2:30 PM" in result

    def test_occurrence_summary_single(self, formatter, sample_finding):
        """Single occurrence shows 'Occurred 1 time at...'."""
        result = formatter.format_occurrence_summary(sample_finding)
        assert "Occurred 1 time at" in result
        assert "times" not in result

    def test_occurrence_summary_multiple(self, formatter):
        """Multiple occurrences show count with first/last times."""
        finding = Finding(
            severity=Severity.MEDIUM,
            category=Category.CONNECTIVITY,
            title="Test",
            description="Test description",
            first_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 16, 30, 0, tzinfo=ZoneInfo("UTC")),
            occurrence_count=3,
        )
        result = formatter.format_occurrence_summary(finding)
        assert "Occurred 3 times" in result
        assert "first:" in result
        assert "last:" in result

    def test_occurrence_summary_recurring_flag(self, formatter):
        """Recurring findings show [Recurring Issue] prefix."""
        finding = Finding(
            severity=Severity.LOW,
            category=Category.CONNECTIVITY,
            title="Test",
            description="Test description",
            first_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 16, 30, 0, tzinfo=ZoneInfo("UTC")),
            occurrence_count=RECURRING_THRESHOLD,  # Exactly threshold
        )
        result = formatter.format_occurrence_summary(finding)
        assert "[Recurring Issue]" in result

    def test_occurrence_summary_not_recurring_below_threshold(self, formatter):
        """Below threshold should not show recurring flag."""
        finding = Finding(
            severity=Severity.LOW,
            category=Category.CONNECTIVITY,
            title="Test",
            description="Test description",
            first_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 16, 30, 0, tzinfo=ZoneInfo("UTC")),
            occurrence_count=RECURRING_THRESHOLD - 1,  # Just below threshold
        )
        result = formatter.format_occurrence_summary(finding)
        assert "[Recurring Issue]" not in result

    def test_device_display_uses_name(self, formatter, sample_finding):
        """Device display prefers name over MAC."""
        result = formatter.format_device_display(sample_finding)
        assert result == "Main Gateway"

    def test_device_display_falls_back_to_mac(self, formatter):
        """Device display falls back to MAC when name is None."""
        finding = Finding(
            severity=Severity.LOW,
            category=Category.CONNECTIVITY,
            title="Test",
            description="Test description",
            device_mac="aa:bb:cc:dd:ee:ff",
            device_name=None,  # Explicit None
            first_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        result = formatter.format_device_display(finding)
        assert result == "aa:bb:cc:dd:ee:ff"

    def test_device_display_unknown_when_both_none(self, formatter):
        """Device display shows 'Unknown device' when both name and MAC are None."""
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Test",
            description="Test description",
            device_mac=None,
            device_name=None,
            first_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
        )
        result = formatter.format_device_display(finding)
        assert result == "Unknown device"

    def test_format_finding_returns_all_fields(self, formatter, sample_finding):
        """format_finding returns dict with all expected fields."""
        result = formatter.format_finding(sample_finding)
        expected_keys = [
            "id", "severity", "category", "title", "description",
            "remediation", "device_display", "first_seen", "last_seen",
            "occurrence_count", "occurrence_summary", "is_recurring",
            "is_actionable", "metadata"
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_format_finding_severity_is_string(self, formatter, sample_finding):
        """Severity in formatted output is string value."""
        result = formatter.format_finding(sample_finding)
        assert result["severity"] == "severe"
        assert isinstance(result["severity"], str)

    def test_format_findings_list(self, formatter, sample_finding):
        """format_findings handles list of findings."""
        findings = [sample_finding, sample_finding]
        result = formatter.format_findings(findings)
        assert len(result) == 2
        assert all("title" in f for f in result)

    def test_grouped_findings_by_severity(self, formatter):
        """format_grouped_findings groups by severity."""
        findings = [
            Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title="Low finding",
                description="Description",
                first_seen=datetime.now(ZoneInfo("UTC")),
                last_seen=datetime.now(ZoneInfo("UTC")),
            ),
            Finding(
                severity=Severity.SEVERE,
                category=Category.SECURITY,
                title="Severe finding",
                description="Description",
                first_seen=datetime.now(ZoneInfo("UTC")),
                last_seen=datetime.now(ZoneInfo("UTC")),
            ),
            Finding(
                severity=Severity.MEDIUM,
                category=Category.CONNECTIVITY,
                title="Medium finding",
                description="Description",
                first_seen=datetime.now(ZoneInfo("UTC")),
                last_seen=datetime.now(ZoneInfo("UTC")),
            ),
        ]
        result = formatter.format_grouped_findings(findings)

        assert "severe" in result
        assert "medium" in result
        assert "low" in result
        assert len(result["severe"]) == 1
        assert len(result["medium"]) == 1
        assert len(result["low"]) == 1

    def test_grouped_findings_empty_categories(self, formatter):
        """Empty severity categories return empty lists."""
        findings = [
            Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title="Low finding",
                description="Description",
                first_seen=datetime.now(ZoneInfo("UTC")),
                last_seen=datetime.now(ZoneInfo("UTC")),
            ),
        ]
        result = formatter.format_grouped_findings(findings)
        assert result["severe"] == []
        assert result["medium"] == []
        assert len(result["low"]) == 1

    def test_text_report_generation(self, formatter, sample_finding):
        """format_text_report generates readable text output."""
        findings = [sample_finding]
        result = formatter.format_text_report(findings, title="Test Report")

        # Check structure
        assert "Test Report" in result
        assert "SUMMARY" in result
        assert "Total Findings: 1" in result
        assert "SEVERE: 1" in result
        assert "End of Report" in result

        # Check finding content
        assert "[Security] Failed Admin Login" in result
        assert "Main Gateway" in result

    def test_text_report_severe_first(self, formatter):
        """Text report shows SEVERE findings before MEDIUM and LOW."""
        findings = [
            Finding(
                severity=Severity.LOW,
                category=Category.SYSTEM,
                title="Low",
                description="Description",
                first_seen=datetime.now(ZoneInfo("UTC")),
                last_seen=datetime.now(ZoneInfo("UTC")),
            ),
            Finding(
                severity=Severity.SEVERE,
                category=Category.SECURITY,
                title="Severe",
                description="Description",
                first_seen=datetime.now(ZoneInfo("UTC")),
                last_seen=datetime.now(ZoneInfo("UTC")),
            ),
        ]
        result = formatter.format_text_report(findings)

        # SEVERE section should appear before LOW section
        severe_pos = result.find("SEVERE FINDINGS")
        low_pos = result.find("LOW FINDINGS")
        assert severe_pos < low_pos, "SEVERE should appear before LOW in report"

    def test_text_report_low_no_remediation(self, formatter):
        """LOW findings in text report don't show remediation section."""
        finding = Finding(
            severity=Severity.LOW,
            category=Category.SYSTEM,
            title="Low finding",
            description="Description",
            remediation="Should not appear",  # Even if set, shouldn't show
            first_seen=datetime.now(ZoneInfo("UTC")),
            last_seen=datetime.now(ZoneInfo("UTC")),
        )
        result = formatter.format_text_report([finding])

        # The LOW section should not include remediation
        low_section_start = result.find("LOW FINDINGS")
        low_section = result[low_section_start:]

        # Check that "Recommended Actions" doesn't appear in LOW section
        assert "Recommended Actions:" not in low_section

    def test_text_report_includes_remediation_for_severe(self, formatter, sample_finding):
        """SEVERE findings in text report include remediation."""
        result = formatter.format_text_report([sample_finding])
        assert "Recommended Actions:" in result
        assert "1. Check logs" in result


class TestIntegration:
    """Integration tests combining templates and formatter."""

    def test_full_finding_workflow(self):
        """Test complete workflow: template rendering to formatted output."""
        # Render explanation
        explanation = render_explanation("ap_lost_contact", {
            "event_type": "EVT_AP_LOST_CONTACT",
            "device_name": "Living Room AP",
        })

        # Render remediation
        remediation = render_remediation("ap_lost_contact", Severity.SEVERE, {
            "device_name": "Living Room AP",
        })

        # Create finding
        finding = Finding(
            severity=Severity.SEVERE,
            category=Category.CONNECTIVITY,
            title=explanation["title"],
            description=explanation["description"],
            remediation=remediation,
            device_name="Living Room AP",
            device_mac="aa:bb:cc:dd:ee:ff",
            first_seen=datetime(2026, 1, 24, 14, 0, 0, tzinfo=ZoneInfo("UTC")),
            last_seen=datetime(2026, 1, 24, 15, 0, 0, tzinfo=ZoneInfo("UTC")),
            occurrence_count=3,
        )

        # Format for display
        formatter = FindingFormatter("America/New_York")
        formatted = formatter.format_finding(finding)

        # Verify complete workflow
        assert "[Connectivity]" in formatted["title"]
        assert "EVT_AP_LOST_CONTACT" in formatted["description"]
        assert "Living Room AP" in formatted["remediation"]
        assert "Living Room AP" == formatted["device_display"]
        assert formatted["occurrence_count"] == 3
        assert "Occurred 3 times" in formatted["occurrence_summary"]
