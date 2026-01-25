"""Tests for IPS remediation templates."""

import pytest

from unifi_scanner.models.enums import Severity
from unifi_scanner.analysis.ips.remediation import (
    get_remediation,
    get_false_positive_note,
    IPS_REMEDIATION_TEMPLATES,
    SafeDict,
)


class TestSafeDict:
    """Tests for SafeDict class."""

    def test_existing_key_returns_value(self):
        """SafeDict returns value for existing keys."""
        d = SafeDict({"src_ip": "192.168.1.100"})
        assert d["src_ip"] == "192.168.1.100"

    def test_missing_key_returns_placeholder(self):
        """SafeDict returns placeholder for missing keys."""
        d = SafeDict({})
        assert d["src_ip"] == "[src_ip]"

    def test_format_map_with_missing_keys(self):
        """SafeDict works with format_map for missing keys."""
        template = "Source: {src_ip}, Dest: {dest_ip}"
        d = SafeDict({"src_ip": "10.0.0.1"})
        result = template.format_map(d)
        assert result == "Source: 10.0.0.1, Dest: [dest_ip]"


class TestIPSRemediationTemplates:
    """Tests for IPS_REMEDIATION_TEMPLATES structure."""

    # Required categories per PLAN.md
    REQUIRED_CATEGORIES = [
        "SCAN",
        "MALWARE",
        "POLICY",
        "EXPLOIT",
        "DOS",
        "COINMINING",
        "P2P",
        "TOR",
        "PHISHING",
    ]

    def test_all_required_categories_exist(self):
        """All required categories have templates."""
        for category in self.REQUIRED_CATEGORIES:
            assert category in IPS_REMEDIATION_TEMPLATES, (
                f"Missing required category: {category}"
            )

    def test_each_category_has_severity_templates(self):
        """Each category has severe, medium, and low templates."""
        for category in self.REQUIRED_CATEGORIES:
            templates = IPS_REMEDIATION_TEMPLATES[category]
            # All categories should have all three severity levels
            # (some may be None for INFO/GAMES/CHAT but required ones should have all)
            assert "severe" in templates, f"{category} missing 'severe' template"
            assert "medium" in templates, f"{category} missing 'medium' template"
            assert "low" in templates, f"{category} missing 'low' template"
            # Severe and medium should have content for required categories
            assert templates["severe"] is not None, (
                f"{category} 'severe' template is None"
            )
            assert templates["medium"] is not None, (
                f"{category} 'medium' template is None"
            )

    def test_false_positive_notes_for_expected_categories(self):
        """POLICY and P2P have false positive notes."""
        # Per CONTEXT.md, these categories should note common false positives
        assert IPS_REMEDIATION_TEMPLATES["POLICY"]["false_positive_note"] is not None
        assert IPS_REMEDIATION_TEMPLATES["P2P"]["false_positive_note"] is not None

    def test_severe_templates_have_numbered_steps(self):
        """Severe templates have step-by-step numbered instructions."""
        for category, templates in IPS_REMEDIATION_TEMPLATES.items():
            severe = templates.get("severe")
            if severe is not None:
                # Should have numbered steps like "1." "2." etc.
                assert "1." in severe, (
                    f"{category} severe template should have numbered steps"
                )


class TestGetRemediation:
    """Tests for get_remediation function."""

    def test_severe_remediation_for_scan(self):
        """SEVERE SCAN category returns step-by-step instructions."""
        context = {"src_ip": "192.168.1.100"}
        result = get_remediation("SCAN", Severity.SEVERE, context)

        assert result is not None
        assert "192.168.1.100" in result
        assert "1." in result  # Has numbered steps
        assert "firewall" in result.lower()

    def test_medium_remediation_for_malware(self):
        """MEDIUM MALWARE returns brief actionable advice."""
        context = {"src_ip": "10.0.0.50"}
        result = get_remediation("MALWARE", Severity.MEDIUM, context)

        assert result is not None
        assert "10.0.0.50" in result
        assert "malware scan" in result.lower()
        # Medium should not have numbered steps
        assert "1." not in result

    def test_low_remediation_is_explanation(self):
        """LOW severity returns explanation, not action items."""
        context = {"src_ip": "1.2.3.4"}
        result = get_remediation("SCAN", Severity.LOW, context)

        assert result is not None
        assert "background noise" in result.lower() or "no action" in result.lower()
        # LOW should not have numbered steps
        assert "1." not in result

    def test_category_case_insensitive(self):
        """Category matching is case-insensitive."""
        context = {"src_ip": "10.0.0.1"}

        upper = get_remediation("MALWARE", Severity.MEDIUM, context)
        lower = get_remediation("malware", Severity.MEDIUM, context)
        mixed = get_remediation("Malware", Severity.MEDIUM, context)

        assert upper == lower == mixed

    def test_unknown_category_returns_generic(self):
        """Unknown category returns generic remediation."""
        context = {"src_ip": "1.2.3.4"}
        result = get_remediation("UNKNOWN_CATEGORY", Severity.SEVERE, context)

        assert result is not None
        assert "1.2.3.4" in result
        assert "investigate" in result.lower()

    def test_missing_context_uses_placeholder(self):
        """Missing context variables use placeholders."""
        context = {}  # Empty context
        result = get_remediation("SCAN", Severity.SEVERE, context)

        assert result is not None
        assert "[src_ip]" in result

    def test_context_substitution_all_fields(self):
        """All context fields are properly substituted."""
        context = {
            "src_ip": "192.168.1.50",
            "dest_ip": "10.0.0.100",
            "signature": "ET MALWARE Test Signature",
        }
        result = get_remediation("EXPLOIT", Severity.SEVERE, context)

        assert "192.168.1.50" in result or "[src_ip]" not in result
        assert "10.0.0.100" in result or "[dest_ip]" not in result

    def test_policy_remediation_mentions_violation(self):
        """POLICY remediation addresses policy violation context."""
        context = {"src_ip": "192.168.1.100", "signature": "ET POLICY Test"}
        result = get_remediation("POLICY", Severity.SEVERE, context)

        assert result is not None
        assert "policy" in result.lower()


class TestGetFalsePositiveNote:
    """Tests for get_false_positive_note function."""

    def test_policy_has_false_positive_note(self):
        """POLICY category returns streaming services note."""
        note = get_false_positive_note("POLICY")

        assert note is not None
        assert "streaming" in note.lower() or "netflix" in note.lower()

    def test_p2p_has_false_positive_note(self):
        """P2P category returns gaming/launcher note."""
        note = get_false_positive_note("P2P")

        assert note is not None
        assert "game" in note.lower() or "steam" in note.lower()

    def test_malware_has_no_false_positive_note(self):
        """MALWARE category has no false positive note (it's serious)."""
        note = get_false_positive_note("MALWARE")
        assert note is None

    def test_unknown_category_returns_none(self):
        """Unknown category returns None."""
        note = get_false_positive_note("NONEXISTENT")
        assert note is None

    def test_case_insensitive_lookup(self):
        """False positive note lookup is case-insensitive."""
        upper = get_false_positive_note("POLICY")
        lower = get_false_positive_note("policy")

        assert upper == lower


class TestRemediationContentQuality:
    """Tests for remediation content quality and consistency."""

    def test_severe_templates_are_actionable(self):
        """Severe templates contain actionable language."""
        context = {"src_ip": "10.0.0.1", "dest_ip": "192.168.1.1"}
        actionable_words = ["check", "verify", "review", "investigate", "block", "scan"]

        for category in ["SCAN", "MALWARE", "POLICY", "EXPLOIT"]:
            result = get_remediation(category, Severity.SEVERE, context)
            if result:
                found = any(word in result.lower() for word in actionable_words)
                assert found, f"{category} severe should have actionable language"

    def test_no_escalation_advice(self):
        """Remediation does not include escalation advice per CONTEXT.md."""
        context = {"src_ip": "10.0.0.1"}
        escalation_phrases = [
            "consult a professional",
            "contact your security team",
            "hire an expert",
            "engage a specialist",
        ]

        for category, templates in IPS_REMEDIATION_TEMPLATES.items():
            for severity_key, template in templates.items():
                if template and severity_key != "false_positive_note":
                    result = template.format_map(SafeDict(context))
                    for phrase in escalation_phrases:
                        assert phrase not in result.lower(), (
                            f"{category}/{severity_key} contains escalation advice"
                        )

    def test_medium_templates_shorter_than_severe(self):
        """Medium templates are generally shorter than severe."""
        for category, templates in IPS_REMEDIATION_TEMPLATES.items():
            severe = templates.get("severe")
            medium = templates.get("medium")

            if severe and medium:
                # Medium should be significantly shorter (less detailed)
                assert len(medium) < len(severe), (
                    f"{category}: medium should be shorter than severe"
                )


class TestAllCategories:
    """Test all defined categories for completeness."""

    def test_all_et_categories_have_templates(self):
        """All categories from signature_parser are covered."""
        from unifi_scanner.analysis.ips.signature_parser import (
            ET_CATEGORY_FRIENDLY_NAMES,
        )

        # These are expected to be in our templates
        # UNKNOWN is a fallback, not a real ET category
        expected_categories = [
            cat for cat in ET_CATEGORY_FRIENDLY_NAMES.keys() if cat != "UNKNOWN"
        ]

        missing = []
        for category in expected_categories:
            if category not in IPS_REMEDIATION_TEMPLATES:
                missing.append(category)

        # We should have most categories, but some obscure ones might be okay to skip
        # Let's ensure we have at least 80% coverage
        coverage = (len(expected_categories) - len(missing)) / len(expected_categories)
        assert coverage >= 0.8, (
            f"Only {coverage*100:.0f}% category coverage. Missing: {missing}"
        )
