"""File-based health check for Docker container monitoring.

This module provides health status management via a file that can be
checked by Docker's HEALTHCHECK command. The status file contains
JSON with the current health state and timestamp.

Docker HEALTHCHECK example:
    HEALTHCHECK --interval=30s --timeout=3s --retries=3 \\
        CMD python -c "import json; h=json.loads(open('/tmp/unifi-scanner-health').read()); exit(0 if h['status']=='healthy' else 1)"

Example usage:
    from unifi_scanner.health import update_health_status, HealthStatus

    # On successful connection
    update_health_status(HealthStatus.HEALTHY, {"site": "default"})

    # On startup
    update_health_status(HealthStatus.STARTING)

    # On error
    update_health_status(HealthStatus.UNHEALTHY, {"error": "Connection failed"})

    # On shutdown
    clear_health_status()
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

HEALTH_FILE = Path("/tmp/unifi-scanner-health")


class HealthStatus(Enum):
    """Health status values for the scanner service.

    These values are written to the health file and checked by
    Docker's HEALTHCHECK command.

    Values:
        STARTING: Service is initializing (not yet healthy or unhealthy)
        HEALTHY: Service is connected and operating normally
        UNHEALTHY: Service has encountered an error
    """

    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


def update_health_status(
    status: HealthStatus,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Write health status to file for Docker healthcheck.

    Creates or updates the health status file with the current status,
    timestamp, and optional details. This file is read by Docker's
    HEALTHCHECK to determine container health.

    Args:
        status: Current health status of the service.
        details: Optional dictionary with additional status information.

    Example:
        >>> update_health_status(HealthStatus.HEALTHY, {"site": "default", "polls": 42})
        >>> # File now contains:
        >>> # {"status": "healthy", "timestamp": "2024-01-15T12:30:00", "details": {"site": "default", "polls": 42}}
    """
    health_data = {
        "status": status.value,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {},
    }
    HEALTH_FILE.write_text(json.dumps(health_data))


def get_health_status() -> Optional[Dict[str, Any]]:
    """Read current health status from file.

    Returns:
        Dictionary with health status data, or None if file doesn't exist.

    Example:
        >>> status = get_health_status()
        >>> if status and status["status"] == "healthy":
        ...     print("Service is healthy")
    """
    if not HEALTH_FILE.exists():
        return None
    try:
        return json.loads(HEALTH_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_health_status() -> None:
    """Remove health file on shutdown.

    Safely removes the health status file. If the file doesn't exist
    or cannot be removed, no error is raised.

    Example:
        >>> # On service shutdown
        >>> clear_health_status()
    """
    HEALTH_FILE.unlink(missing_ok=True)
