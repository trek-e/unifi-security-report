"""Tests for IPS event models and signature parser.

TDD tests for Phase 8: Enhanced Security Analysis.
Tests ET signature parsing, action classification, and IPSEvent model.
"""

import pytest
from datetime import datetime, timezone


class TestSignatureParser:
    """Tests for parse_signature_category function."""

    def test_parse_et_scan_signature(self):
        """ET SCAN signatures should return Reconnaissance category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET SCAN Nmap Scripting Engine")

        assert result == ("SCAN", "Reconnaissance", "Nmap Scripting Engine")

    def test_parse_et_malware_signature(self):
        """ET MALWARE signatures should return Malware Activity category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET MALWARE Win32/Agent.ABC")

        assert result == ("MALWARE", "Malware Activity", "Win32/Agent.ABC")

    def test_parse_et_policy_signature(self):
        """ET POLICY signatures should return Policy Violation category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET POLICY BitTorrent Traffic")

        assert result == ("POLICY", "Policy Violation", "BitTorrent Traffic")

    def test_parse_et_trojan_signature(self):
        """ET TROJAN signatures should map to Malware Activity (legacy mapping)."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET TROJAN Generic.Downloader")

        assert result == ("TROJAN", "Trojan Activity", "Generic.Downloader")

    def test_parse_et_exploit_signature(self):
        """ET EXPLOIT signatures should return Exploit Attempt category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET EXPLOIT Apache Struts RCE")

        assert result == ("EXPLOIT", "Exploit Attempt", "Apache Struts RCE")

    def test_parse_et_dos_signature(self):
        """ET DOS signatures should return Denial of Service category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET DOS Possible SYN Flood")

        assert result == ("DOS", "Denial of Service", "Possible SYN Flood")

    def test_parse_et_coinmining_signature(self):
        """ET COINMINING signatures should return Cryptocurrency Mining category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET COINMINING Stratum Protocol")

        assert result == ("COINMINING", "Cryptocurrency Mining", "Stratum Protocol")

    def test_parse_et_phishing_signature(self):
        """ET PHISHING signatures should return Phishing Attempt category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET PHISHING Credential Harvesting")

        assert result == ("PHISHING", "Phishing Attempt", "Credential Harvesting")

    def test_parse_et_tor_signature(self):
        """ET TOR signatures should return TOR Network Traffic category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET TOR Known Exit Node")

        assert result == ("TOR", "TOR Network Traffic", "Known Exit Node")

    def test_parse_et_p2p_signature(self):
        """ET P2P signatures should return Peer-to-Peer Traffic category."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET P2P BitTorrent DHT ping")

        assert result == ("P2P", "Peer-to-Peer Traffic", "BitTorrent DHT ping")

    def test_parse_non_et_signature(self):
        """Non-ET signatures should return UNKNOWN category with full string as description."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("GPL ATTACK_RESPONSE id check")

        assert result == ("UNKNOWN", "Security Event", "GPL ATTACK_RESPONSE id check")

    def test_parse_case_insensitive(self):
        """ET prefix matching should be case-insensitive."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("et scan Nmap Lower Case")

        assert result[0] == "SCAN"
        assert result[1] == "Reconnaissance"

    def test_parse_unknown_et_category(self):
        """Unknown ET categories should fall back to Security Event."""
        from unifi_scanner.analysis.ips.signature_parser import parse_signature_category

        result = parse_signature_category("ET NEWCATEGORY Something Unknown")

        assert result == ("NEWCATEGORY", "Security Event", "Something Unknown")

    def test_category_friendly_names_exported(self):
        """ET_CATEGORY_FRIENDLY_NAMES dict should be exported."""
        from unifi_scanner.analysis.ips.signature_parser import ET_CATEGORY_FRIENDLY_NAMES

        assert isinstance(ET_CATEGORY_FRIENDLY_NAMES, dict)
        assert "SCAN" in ET_CATEGORY_FRIENDLY_NAMES
        assert "MALWARE" in ET_CATEGORY_FRIENDLY_NAMES
        assert ET_CATEGORY_FRIENDLY_NAMES["SCAN"] == "Reconnaissance"


class TestActionClassification:
    """Tests for is_blocked classification."""

    def test_action_blocked_is_blocked(self):
        """Action 'blocked' should classify as blocked=True."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("blocked") is True

    def test_action_drop_is_blocked(self):
        """Action 'drop' should classify as blocked=True."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("drop") is True

    def test_action_reject_is_blocked(self):
        """Action 'reject' should classify as blocked=True."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("reject") is True

    def test_action_allowed_is_detected(self):
        """Action 'allowed' should classify as blocked=False (detection only)."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("allowed") is False

    def test_action_alert_is_detected(self):
        """Action 'alert' should classify as blocked=False (detection only)."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("alert") is False

    def test_action_pass_is_detected(self):
        """Action 'pass' should classify as blocked=False (detection only)."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("pass") is False

    def test_action_case_insensitive(self):
        """Action classification should be case-insensitive."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("BLOCKED") is True
        assert is_action_blocked("Blocked") is True
        assert is_action_blocked("ALLOWED") is False

    def test_action_unknown_defaults_to_detected(self):
        """Unknown actions should default to blocked=False for safety."""
        from unifi_scanner.analysis.ips.signature_parser import is_action_blocked

        assert is_action_blocked("unknown_action") is False


class TestIPSEventModel:
    """Tests for IPSEvent pydantic model."""

    def test_ips_event_from_api_with_inner_alert(self):
        """IPSEvent.from_api_event should handle nested inner_alert structure."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        raw_event = {
            "_id": "abc123",
            "timestamp": 1706189000000,  # milliseconds
            "src_ip": "192.168.1.100",
            "src_port": 54321,
            "dest_ip": "10.0.0.1",
            "dest_port": 443,
            "proto": "TCP",
            "inner_alert": {
                "signature": "ET SCAN Nmap Scripting Engine",
                "signature_id": 2009358,
                "category": "Attempted Information Leak",
                "severity": 2,
                "action": "blocked",
            },
        }

        event = IPSEvent.from_api_event(raw_event)

        assert event.id == "abc123"
        assert event.src_ip == "192.168.1.100"
        assert event.src_port == 54321
        assert event.dest_ip == "10.0.0.1"
        assert event.dest_port == 443
        assert event.proto == "TCP"
        assert event.signature == "ET SCAN Nmap Scripting Engine"
        assert event.signature_id == 2009358
        assert event.severity == 2
        assert event.action == "blocked"
        assert event.category_friendly == "Reconnaissance"
        assert event.is_blocked is True

    def test_ips_event_from_api_flat_structure(self):
        """IPSEvent.from_api_event should handle flat structure (no inner_alert)."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        raw_event = {
            "_id": "def456",
            "timestamp": 1706189000000,
            "src_ip": "203.0.113.50",
            "dest_ip": "192.168.1.1",
            "proto": "UDP",
            "signature": "ET MALWARE Trojan.Generic",
            "signature_id": 2800000,
            "category": "A Network Trojan was detected",
            "severity": 1,
            "action": "allowed",
        }

        event = IPSEvent.from_api_event(raw_event)

        assert event.id == "def456"
        assert event.src_ip == "203.0.113.50"
        assert event.dest_ip == "192.168.1.1"
        assert event.signature == "ET MALWARE Trojan.Generic"
        assert event.category_friendly == "Malware Activity"
        assert event.is_blocked is False

    def test_ips_event_timestamp_conversion(self):
        """IPSEvent should convert millisecond timestamps to datetime."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        raw_event = {
            "_id": "ts123",
            "timestamp": 1706189000000,  # 2024-01-25 10:43:20 UTC in ms
            "src_ip": "192.168.1.1",
            "dest_ip": "10.0.0.1",
            "proto": "TCP",
            "inner_alert": {
                "signature": "ET POLICY Test",
                "signature_id": 1,
                "category": "Test",
                "severity": 3,
                "action": "allowed",
            },
        }

        event = IPSEvent.from_api_event(raw_event)

        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.year == 2024
        assert event.timestamp.month == 1
        assert event.timestamp.day == 25

    def test_ips_event_missing_optional_ports(self):
        """IPSEvent should handle missing port fields."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        raw_event = {
            "_id": "noports",
            "timestamp": 1706189000000,
            "src_ip": "192.168.1.1",
            "dest_ip": "10.0.0.1",
            "proto": "ICMP",
            "inner_alert": {
                "signature": "ET DOS ICMP Flood",
                "signature_id": 1,
                "category": "DoS",
                "severity": 2,
                "action": "blocked",
            },
        }

        event = IPSEvent.from_api_event(raw_event)

        assert event.src_port is None
        assert event.dest_port is None

    def test_ips_event_severity_mapping(self):
        """IPSEvent should preserve severity from API."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        raw_event = {
            "_id": "sev1",
            "timestamp": 1706189000000,
            "src_ip": "1.2.3.4",
            "dest_ip": "5.6.7.8",
            "proto": "TCP",
            "inner_alert": {
                "signature": "ET MALWARE Critical",
                "signature_id": 1,
                "category": "Malware",
                "severity": 1,  # High severity
                "action": "blocked",
            },
        }

        event = IPSEvent.from_api_event(raw_event)

        assert event.severity == 1

    def test_ips_event_model_validation(self):
        """IPSEvent should validate required fields via pydantic."""
        from unifi_scanner.analysis.ips.models import IPSEvent
        from pydantic import ValidationError

        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError):
            IPSEvent(
                id="test",
                timestamp=datetime.now(timezone.utc),
                # Missing src_ip, dest_ip, proto, signature, etc.
            )


class TestCybersecureDetection:
    """Tests for Cybersecure (Proofpoint ET PRO) signature detection."""

    def test_is_cybersecure_boundary_min(self):
        """signature_id=2800000 (boundary min) should be is_cybersecure=True."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs1",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET PRO MALWARE Test",
            signature_id=2800000,
            category_raw="Malware",
            severity=1,
            action="blocked",
        )

        assert event.is_cybersecure is True

    def test_is_cybersecure_middle_range(self):
        """signature_id=2850000 (middle) should be is_cybersecure=True."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs2",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET PRO MALWARE Test",
            signature_id=2850000,
            category_raw="Malware",
            severity=1,
            action="blocked",
        )

        assert event.is_cybersecure is True

    def test_is_cybersecure_boundary_max(self):
        """signature_id=2899999 (boundary max) should be is_cybersecure=True."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs3",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET PRO MALWARE Test",
            signature_id=2899999,
            category_raw="Malware",
            severity=1,
            action="blocked",
        )

        assert event.is_cybersecure is True

    def test_is_cybersecure_just_below_range(self):
        """signature_id=2799999 (just below) should be is_cybersecure=False."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs4",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET MALWARE Test",
            signature_id=2799999,
            category_raw="Malware",
            severity=1,
            action="blocked",
        )

        assert event.is_cybersecure is False

    def test_is_cybersecure_just_above_range(self):
        """signature_id=2900000 (just above) should be is_cybersecure=False."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs5",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET MALWARE Test",
            signature_id=2900000,
            category_raw="Malware",
            severity=1,
            action="blocked",
        )

        assert event.is_cybersecure is False

    def test_is_cybersecure_et_open_range(self):
        """signature_id=2001000 (ET Open) should be is_cybersecure=False."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs6",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET SCAN Nmap",
            signature_id=2001000,
            category_raw="Scan",
            severity=2,
            action="allowed",
        )

        assert event.is_cybersecure is False

    def test_is_cybersecure_custom_rule(self):
        """signature_id=100 (custom) should be is_cybersecure=False."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs7",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="Custom Rule Test",
            signature_id=100,
            category_raw="Custom",
            severity=3,
            action="allowed",
        )

        assert event.is_cybersecure is False

    def test_is_cybersecure_serializes_to_dict(self):
        """is_cybersecure computed field should serialize to dict/JSON."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        event = IPSEvent(
            id="cs8",
            timestamp=datetime.now(timezone.utc),
            src_ip="192.168.1.1",
            dest_ip="10.0.0.1",
            proto="TCP",
            signature="ET PRO MALWARE Test",
            signature_id=2850000,
            category_raw="Malware",
            severity=1,
            action="blocked",
        )

        data = event.model_dump()
        assert "is_cybersecure" in data
        assert data["is_cybersecure"] is True


class TestCybersecureConstants:
    """Tests for ET PRO SID range constants."""

    def test_et_pro_sid_min_exported(self):
        """ET_PRO_SID_MIN constant should be exported from models."""
        from unifi_scanner.analysis.ips.models import ET_PRO_SID_MIN

        assert ET_PRO_SID_MIN == 2800000

    def test_et_pro_sid_max_exported(self):
        """ET_PRO_SID_MAX constant should be exported from models."""
        from unifi_scanner.analysis.ips.models import ET_PRO_SID_MAX

        assert ET_PRO_SID_MAX == 2899999


class TestModuleExports:
    """Tests for module-level exports."""

    def test_ips_module_exports_ips_event(self):
        """IPSEvent should be exported from ips module."""
        from unifi_scanner.analysis.ips import IPSEvent

        assert IPSEvent is not None

    def test_ips_module_exports_parse_signature_category(self):
        """parse_signature_category should be exported from ips module."""
        from unifi_scanner.analysis.ips import parse_signature_category

        assert callable(parse_signature_category)

    def test_ips_module_exports_is_action_blocked(self):
        """is_action_blocked should be exported from ips module."""
        from unifi_scanner.analysis.ips import is_action_blocked

        assert callable(is_action_blocked)
