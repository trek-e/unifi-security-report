"""MongoDB-based IPS threat collector for UniFi devices.

Connects to UniFi devices via SSH and queries the local MongoDB instance
for IPS threat alerts. This is a workaround for the UniFi Network API not
exposing IPS events through REST endpoints.

The MongoDB database on UDM Pro devices stores blocked threats in the
`ace.alert` collection with key `THREAT_BLOCKED_V3`.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import paramiko
import structlog

from .ssh_collector import SSHCollectionError, WarningHostKeyPolicy, _FingerprintVerifyPolicy

logger = structlog.get_logger(__name__)


class MongoIPSCollector:
    """Collects IPS threat alerts from UniFi device MongoDB via SSH.

    UniFi devices store blocked threat information in MongoDB but don't
    expose it via the Network API. This collector SSHs into the device
    and queries MongoDB directly.

    Note: MongoDB alerts contain limited information compared to what
    the UI shows. Signature names and categories are enriched by the UI
    from encrypted rule databases and are not stored in MongoDB.

    Available data:
    - Source IP
    - Destination IP
    - Severity (HIGH, MEDIUM, LOW)
    - Timestamp
    - Device info

    NOT available:
    - Signature ID
    - Signature name
    - Threat category
    - Protocol/port details

    Example:
        >>> collector = MongoIPSCollector(
        ...     host="192.168.1.1",
        ...     username="root",
        ...     key_path="~/.ssh/id_rsa",
        ... )
        >>> alerts = collector.collect(limit=100)
    """

    # MongoDB connection settings for UniFi devices
    MONGO_PORT = 27117
    MONGO_DB = "ace"
    MONGO_COLLECTION = "alert"
    THREAT_KEY = "THREAT_BLOCKED_V3"

    def __init__(
        self,
        host: str,
        username: str,
        password: Optional[str] = None,
        timeout: float = 30.0,
        port: int = 22,
        host_key_fingerprint: Optional[str] = None,
        key_path: Optional[str] = None,
        key_passphrase: Optional[str] = None,
    ) -> None:
        """Initialize MongoDB IPS collector.

        Args:
            host: Device hostname or IP address.
            username: SSH username (typically 'root' for UniFi).
            password: SSH password (optional if using key auth).
            timeout: Command execution timeout in seconds.
            port: SSH port (default 22).
            host_key_fingerprint: Expected host key fingerprint.
            key_path: Path to SSH private key file.
            key_passphrase: Passphrase for encrypted private key.
        """
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self.port = port
        self.host_key_fingerprint = host_key_fingerprint
        self.key_path = key_path
        self.key_passphrase = key_passphrase

    def collect(
        self,
        since_timestamp: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Collect IPS threat alerts from MongoDB.

        Args:
            since_timestamp: Only return alerts after this time (UTC).
            limit: Maximum number of alerts to return.

        Returns:
            List of alert dictionaries with normalized fields.

        Raises:
            SSHCollectionError: SSH connection or command failed.
        """
        logger.info(
            "mongo_ips_collection_starting",
            host=self.host,
            since=since_timestamp.isoformat() if since_timestamp else None,
            limit=limit,
        )

        try:
            client = self._connect()
            try:
                raw_alerts = self._query_alerts(client, since_timestamp, limit)
                normalized = [self._normalize_alert(a) for a in raw_alerts]

                logger.info(
                    "mongo_ips_collection_complete",
                    host=self.host,
                    count=len(normalized),
                )
                return normalized
            finally:
                client.close()
        except SSHCollectionError:
            raise
        except Exception as e:
            raise SSHCollectionError(
                message=f"MongoDB IPS collection failed: {e}",
                host=self.host,
                cause=e,
            ) from e

    def _connect(self) -> paramiko.SSHClient:
        """Establish SSH connection to the device."""
        client = paramiko.SSHClient()

        if self.host_key_fingerprint:
            client.set_missing_host_key_policy(
                _FingerprintVerifyPolicy(self.host_key_fingerprint)
            )
        else:
            client.set_missing_host_key_policy(WarningHostKeyPolicy())

        try:
            if self.key_path:
                logger.debug(
                    "mongo_ssh_connecting_with_key",
                    host=self.host,
                    key_path=self.key_path,
                )
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    key_filename=self.key_path,
                    passphrase=self.key_passphrase,
                    timeout=self.timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
            else:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
            logger.debug("mongo_ssh_connected", host=self.host)
            return client
        except paramiko.AuthenticationException as e:
            auth_method = "key" if self.key_path else "password"
            raise SSHCollectionError(
                message=f"SSH authentication failed ({auth_method})",
                host=self.host,
                cause=e,
            ) from e
        except Exception as e:
            raise SSHCollectionError(
                message=f"Failed to connect: {e}",
                host=self.host,
                cause=e,
            ) from e

    def _query_alerts(
        self,
        client: paramiko.SSHClient,
        since_timestamp: Optional[datetime],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Query MongoDB for threat alerts.

        Uses mongo shell to query the ace.alert collection for
        THREAT_BLOCKED_V3 documents.

        Args:
            client: Connected SSH client.
            since_timestamp: Filter alerts after this time.
            limit: Maximum alerts to return.

        Returns:
            List of raw alert documents from MongoDB.
        """
        # Build MongoDB query
        query_filter = f'{{"key": "{self.THREAT_KEY}"'

        if since_timestamp:
            # MongoDB stores time in milliseconds
            since_ms = int(since_timestamp.timestamp() * 1000)
            query_filter += f', "time": {{"$gte": NumberLong({since_ms})}}'

        query_filter += "}"

        # MongoDB shell command
        # Use printjson for each document to get valid JSON output
        mongo_cmd = (
            f'mongo --port {self.MONGO_PORT} --quiet {self.MONGO_DB} --eval \''
            f'db.{self.MONGO_COLLECTION}.find({query_filter})'
            f'.sort({{time: -1}}).limit({limit}).forEach(function(d) {{'
            f'printjson(d);'
            f'}});\''
        )

        logger.debug("mongo_query", command=mongo_cmd[:200])

        try:
            stdin, stdout, stderr = client.exec_command(mongo_cmd, timeout=self.timeout)
            channel = stdout.channel
            channel.settimeout(self.timeout)

            output = stdout.read().decode("utf-8", errors="replace")
            exit_status = channel.recv_exit_status()

            if exit_status != 0:
                error_output = stderr.read().decode("utf-8", errors="replace")
                logger.warning(
                    "mongo_query_error",
                    exit_status=exit_status,
                    stderr=error_output[:500],
                )
                return []

            # Parse JSON output (one document per printjson call)
            alerts = self._parse_mongo_output(output)
            logger.debug("mongo_query_results", count=len(alerts))
            return alerts

        except TimeoutError as e:
            raise SSHCollectionError(
                message=f"MongoDB query timed out after {self.timeout}s",
                host=self.host,
                cause=e,
            ) from e

    def _parse_mongo_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse MongoDB shell JSON output.

        MongoDB printjson outputs documents separated by newlines.
        Each document may span multiple lines.

        Args:
            output: Raw output from mongo shell.

        Returns:
            List of parsed documents.
        """
        if not output.strip():
            return []

        alerts = []
        current_doc = ""
        brace_count = 0

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Track brace nesting to find document boundaries
            for char in line:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1

            current_doc += line + " "

            if brace_count == 0 and current_doc.strip():
                try:
                    # Handle MongoDB extended JSON (ObjectId, NumberLong, etc.)
                    doc_str = self._convert_mongo_json(current_doc.strip())
                    doc = json.loads(doc_str)
                    alerts.append(doc)
                except json.JSONDecodeError as e:
                    logger.debug(
                        "mongo_json_parse_error",
                        error=str(e),
                        doc=current_doc[:200],
                    )
                current_doc = ""

        return alerts

    def _convert_mongo_json(self, mongo_json: str) -> str:
        """Convert MongoDB extended JSON to standard JSON.

        Handles MongoDB-specific types:
        - ObjectId("...") -> "..."
        - NumberLong(...) -> number
        - ISODate("...") -> "..."

        Args:
            mongo_json: MongoDB shell JSON output.

        Returns:
            Standard JSON string.
        """
        import re

        # ObjectId("...") -> "..."
        result = re.sub(r'ObjectId\("([^"]+)"\)', r'"\1"', mongo_json)

        # NumberLong(...) or NumberLong("...") -> number
        result = re.sub(r'NumberLong\((\d+)\)', r'\1', result)
        result = re.sub(r'NumberLong\("(\d+)"\)', r'\1', result)

        # ISODate("...") -> "..."
        result = re.sub(r'ISODate\("([^"]+)"\)', r'"\1"', result)

        return result

    def _normalize_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a MongoDB alert to a consistent format.

        Extracts relevant fields and converts timestamps.

        Args:
            alert: Raw MongoDB document.

        Returns:
            Normalized alert dictionary.
        """
        params = alert.get("parameters", {})

        # Extract source IP
        src_ip_data = params.get("SRC_IP", {})
        src_ip = src_ip_data.get("name") or src_ip_data.get("target_id", "")

        # Extract destination IP
        dst_ip_data = params.get("DST_IP", {})
        dst_ip = dst_ip_data.get("name") or dst_ip_data.get("target_id", "")

        # Extract device info
        device_data = params.get("DEVICE", {})
        device_name = device_data.get("name", "")
        device_model = device_data.get("model", "")

        # Convert timestamp (milliseconds to datetime)
        time_ms = alert.get("time", 0)
        if isinstance(time_ms, str):
            time_ms = int(time_ms)
        timestamp = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)

        # Map severity
        severity_str = alert.get("severity", "MEDIUM").upper()
        severity_map = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        severity_int = severity_map.get(severity_str, 2)

        return {
            "_id": str(alert.get("_id", "")),
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dest_ip": dst_ip,
            "severity": severity_int,
            "severity_str": severity_str,
            "device_name": device_name,
            "device_model": device_model,
            "site_id": alert.get("site_id", ""),
            "status": alert.get("status", ""),
            # These fields are not available in MongoDB
            "signature": "Blocked Threat (details unavailable via API)",
            "signature_id": 0,
            "category_raw": "blocked",
            "action": "blocked",
            "proto": "",
            "src_port": None,
            "dest_port": None,
        }
