"""SSH-based log collector for UniFi devices.

Provides fallback log collection when API access is insufficient.
Connects to UniFi devices via SSH and reads log files directly.
"""

from typing import List, Optional

import paramiko
import structlog

from unifi_scanner.models import DeviceType, LogEntry

from .parser import LogParser

logger = structlog.get_logger(__name__)

# Log file paths by device type
LOG_PATHS = {
    DeviceType.UDM_PRO: [
        "/var/log/messages",
        "/mnt/data/log/daemon.log",
    ],
    DeviceType.SELF_HOSTED: [
        "/var/log/unifi/server.log",
        "/var/log/unifi/mongod.log",
    ],
}

# Default log paths when device type is unknown
DEFAULT_LOG_PATHS = [
    "/var/log/messages",
    "/var/log/syslog",
]


class SSHCollectionError(Exception):
    """Raised when SSH log collection fails."""

    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        self.message = message
        self.host = host
        self.cause = cause
        super().__init__(message)


class SSHLogCollector:
    """Collects logs from UniFi devices via SSH.

    Connects to the device, reads log files based on device type,
    and parses them into LogEntry objects.

    Example:
        >>> collector = SSHLogCollector(
        ...     host="192.168.1.1",
        ...     username="admin",
        ...     password="secret",
        ...     device_type=DeviceType.UDM_PRO,
        ... )
        >>> entries = collector.collect(max_lines=100)
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        device_type: Optional[DeviceType] = None,
        timeout: float = 30.0,
        port: int = 22,
    ) -> None:
        """Initialize SSH log collector.

        Args:
            host: Device hostname or IP address.
            username: SSH username.
            password: SSH password.
            device_type: Type of UniFi device (affects log paths).
            timeout: Command execution timeout in seconds.
            port: SSH port (default 22).
        """
        self.host = host
        self.username = username
        self.password = password
        self.device_type = device_type
        self.timeout = timeout
        self.port = port
        self._parser = LogParser()

    def collect(self, max_lines: int = 1000) -> List[LogEntry]:
        """Collect logs from the device via SSH.

        Connects to the device, reads log files, and parses entries.

        Args:
            max_lines: Maximum lines to read from each log file.

        Returns:
            List of LogEntry objects from all available log files.

        Raises:
            SSHCollectionError: Connection or command execution failed.
        """
        entries: List[LogEntry] = []
        log_paths = self._get_log_paths()

        logger.info(
            "ssh_collection_starting",
            host=self.host,
            device_type=self.device_type.value if self.device_type else "unknown",
            log_paths=log_paths,
        )

        try:
            client = self._connect()
            try:
                for path in log_paths:
                    try:
                        lines = self._read_log_file(client, path, max_lines)
                        if lines:
                            parsed = self._parser.parse_syslog_lines(lines)
                            entries.extend(parsed)
                            logger.debug(
                                "ssh_log_file_read",
                                path=path,
                                lines_read=len(lines.split("\n")),
                                entries_parsed=len(parsed),
                            )
                    except SSHCollectionError as e:
                        # Log file may not exist on this device type
                        logger.debug(
                            "ssh_log_file_skipped",
                            path=path,
                            reason=str(e),
                        )
            finally:
                client.close()

        except SSHCollectionError:
            raise
        except Exception as e:
            raise SSHCollectionError(
                message=f"SSH collection failed: {e}",
                host=self.host,
                cause=e,
            ) from e

        logger.info(
            "ssh_collection_complete",
            host=self.host,
            total_entries=len(entries),
        )
        return entries

    def _get_log_paths(self) -> List[str]:
        """Get log file paths based on device type."""
        if self.device_type and self.device_type in LOG_PATHS:
            return LOG_PATHS[self.device_type]
        return DEFAULT_LOG_PATHS

    def _connect(self) -> paramiko.SSHClient:
        """Establish SSH connection to the device.

        Returns:
            Connected SSH client.

        Raises:
            SSHCollectionError: Connection failed.
        """
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            logger.debug("ssh_connected", host=self.host, port=self.port)
            return client
        except paramiko.AuthenticationException as e:
            raise SSHCollectionError(
                message="SSH authentication failed",
                host=self.host,
                cause=e,
            ) from e
        except paramiko.SSHException as e:
            raise SSHCollectionError(
                message=f"SSH connection error: {e}",
                host=self.host,
                cause=e,
            ) from e
        except Exception as e:
            raise SSHCollectionError(
                message=f"Failed to connect: {e}",
                host=self.host,
                cause=e,
            ) from e

    def _read_log_file(
        self,
        client: paramiko.SSHClient,
        path: str,
        max_lines: int,
    ) -> str:
        """Read log file content via SSH with timeout.

        Uses tail to read the last N lines to avoid reading huge files.
        Implements channel timeout to prevent hanging.

        Args:
            client: Connected SSH client.
            path: Path to log file.
            max_lines: Maximum lines to read.

        Returns:
            Log file content as string.

        Raises:
            SSHCollectionError: Command execution failed or timed out.
        """
        command = f"tail -n {max_lines} {path} 2>/dev/null"

        try:
            # Use exec_command with explicit timeout via channel
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)

            # Set channel timeout to prevent blocking forever
            channel = stdout.channel
            channel.settimeout(self.timeout)

            try:
                output = stdout.read().decode("utf-8", errors="replace")
                exit_status = channel.recv_exit_status()

                if exit_status != 0:
                    error_output = stderr.read().decode("utf-8", errors="replace")
                    raise SSHCollectionError(
                        message=f"Command failed with exit {exit_status}: {error_output}",
                        host=self.host,
                    )

                return output

            except TimeoutError:
                raise SSHCollectionError(
                    message=f"Command timed out after {self.timeout}s: {command}",
                    host=self.host,
                )

        except SSHCollectionError:
            raise
        except Exception as e:
            raise SSHCollectionError(
                message=f"Failed to read {path}: {e}",
                host=self.host,
                cause=e,
            ) from e
