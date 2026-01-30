"""Tests for MongoDB IPS threat collector."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestMongoIPSCollector:
    """Test suite for MongoIPSCollector."""

    def test_normalize_alert_extracts_ips(self):
        """Test that IPs are correctly extracted from MongoDB alert."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        raw_alert = {
            "_id": "test123",
            "key": "THREAT_BLOCKED_V3",
            "time": 1769377254306,
            "status": "NEW",
            "severity": "HIGH",
            "site_id": "site123",
            "parameters": {
                "SRC_IP": {"name": "130.12.180.122", "target_id": "130.12.180.122"},
                "DST_IP": {"name": "192.168.0.26", "target_id": "192.168.0.26"},
                "DEVICE": {"name": "Dream Machine Pro", "model": "UDM-Pro"},
            },
        }

        normalized = collector._normalize_alert(raw_alert)

        assert normalized["src_ip"] == "130.12.180.122"
        assert normalized["dest_ip"] == "192.168.0.26"
        assert normalized["severity"] == 1  # HIGH maps to 1
        assert normalized["device_name"] == "Dream Machine Pro"
        assert normalized["action"] == "blocked"  # MongoDB alerts are always blocked threats

    def test_normalize_alert_handles_missing_fields(self):
        """Test that missing fields are handled gracefully."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        raw_alert = {
            "_id": "test456",
            "time": 1769377254306,
            "severity": "MEDIUM",
            "parameters": {},
        }

        normalized = collector._normalize_alert(raw_alert)

        assert normalized["src_ip"] == ""
        assert normalized["dest_ip"] == ""
        assert normalized["severity"] == 2  # MEDIUM maps to 2

    def test_convert_mongo_json_handles_objectid(self):
        """Test MongoDB JSON conversion for ObjectId."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        mongo_json = '{"_id": ObjectId("abc123"), "name": "test"}'
        result = collector._convert_mongo_json(mongo_json)

        assert result == '{"_id": "abc123", "name": "test"}'

    def test_convert_mongo_json_handles_numberlong(self):
        """Test MongoDB JSON conversion for NumberLong."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        mongo_json = '{"time": NumberLong(1769377254306)}'
        result = collector._convert_mongo_json(mongo_json)

        assert result == '{"time": 1769377254306}'

    def test_convert_mongo_json_handles_quoted_numberlong(self):
        """Test MongoDB JSON conversion for quoted NumberLong."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        mongo_json = '{"time": NumberLong("1769377254306")}'
        result = collector._convert_mongo_json(mongo_json)

        assert result == '{"time": 1769377254306}'

    def test_parse_mongo_output_single_doc(self):
        """Test parsing single MongoDB document."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        output = '{"_id": "test", "time": 12345}'
        result = collector._parse_mongo_output(output)

        assert len(result) == 1
        assert result[0]["_id"] == "test"
        assert result[0]["time"] == 12345

    def test_parse_mongo_output_multiple_docs(self):
        """Test parsing multiple MongoDB documents."""
        from unifi_scanner.logs.mongo_ips_collector import MongoIPSCollector

        collector = MongoIPSCollector(
            host="192.168.1.1",
            username="root",
            key_path="/path/to/key",
        )

        output = '{"_id": "1", "val": 1}\n{"_id": "2", "val": 2}'
        result = collector._parse_mongo_output(output)

        assert len(result) == 2
        assert result[0]["_id"] == "1"
        assert result[1]["_id"] == "2"


class TestIPSEventFromMongoDB:
    """Test IPSEvent.from_mongodb_alert factory method."""

    def test_creates_event_from_mongodb_alert(self):
        """Test that IPSEvent is created correctly from MongoDB alert."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        alert = {
            "_id": "test123",
            "timestamp": datetime(2025, 1, 25, 12, 0, 0, tzinfo=timezone.utc),
            "src_ip": "130.12.180.122",
            "dest_ip": "192.168.0.26",
            "severity": 1,
            "severity_str": "HIGH",
            "action": "blocked",
            "category_raw": "blocked",
            "signature": "Blocked Threat",
            "signature_id": 0,
            "proto": "",
            "src_port": None,
            "dest_port": None,
        }

        event = IPSEvent.from_mongodb_alert(alert)

        assert event.src_ip == "130.12.180.122"
        assert event.dest_ip == "192.168.0.26"
        assert event.severity == 1
        assert event.is_blocked is True
        # MongoDB alerts don't have Cybersecure signatures
        assert event.is_cybersecure is False

    def test_handles_timestamp_as_milliseconds(self):
        """Test that timestamp is handled when given as milliseconds."""
        from unifi_scanner.analysis.ips.models import IPSEvent

        alert = {
            "_id": "test456",
            "timestamp": 1769377254306,  # milliseconds
            "src_ip": "10.0.0.1",
            "dest_ip": "10.0.0.2",
            "severity": 2,
            "severity_str": "MEDIUM",
            "action": "blocked",
            "category_raw": "blocked",
            "signature_id": 0,
        }

        event = IPSEvent.from_mongodb_alert(alert)

        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
