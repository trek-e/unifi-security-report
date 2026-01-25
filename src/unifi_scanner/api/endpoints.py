"""API endpoint definitions for different UniFi controller types.

UniFi controllers have different API structures depending on device type:
- UDM Pro/UCG Ultra: Uses /api/auth/login and /proxy/network prefix
- Self-hosted: Uses /api/login with no prefix
"""

from dataclasses import dataclass
from typing import Dict

from unifi_scanner.models import DeviceType


@dataclass(frozen=True)
class Endpoints:
    """Collection of API endpoints for a UniFi controller type.

    Attributes:
        login: Authentication endpoint (POST)
        logout: Logout endpoint (POST)
        sites: Sites list endpoint (GET)
        self: Self/user info endpoint (GET)
        status: Status endpoint (GET, no auth required)
        events: Events retrieval endpoint (POST)
        alarms: Alarms retrieval endpoint (GET)
        ips_events: IDS/IPS events retrieval endpoint (POST)
        devices: Device statistics endpoint (GET)
    """

    login: str
    logout: str
    sites: str
    self: str
    status: str
    events: str
    alarms: str
    ips_events: str
    devices: str


# Endpoint definitions for UDM Pro, UDR, UCG Ultra, and Cloud Key Gen2+
# These devices run UniFi OS and use /api/auth/login with /proxy/network prefix
UDM_PRO_ENDPOINTS = Endpoints(
    login="/api/auth/login",
    logout="/api/auth/logout",
    sites="/proxy/network/api/self/sites",
    self="/proxy/network/api/self",
    status="/status",
    events="/proxy/network/api/s/{site}/stat/event",
    alarms="/proxy/network/api/s/{site}/list/alarm",
    ips_events="/proxy/network/api/s/{site}/stat/ips/event",
    devices="/proxy/network/api/s/{site}/stat/device",
)

# Endpoint definitions for self-hosted UniFi Controller
# These run on Linux/Windows/Mac and use /api/login with no prefix
SELF_HOSTED_ENDPOINTS = Endpoints(
    login="/api/login",
    logout="/api/logout",
    sites="/api/self/sites",
    self="/api/self",
    status="/status",
    events="/api/s/{site}/stat/event",
    alarms="/api/s/{site}/list/alarm",
    ips_events="/api/s/{site}/stat/ips/event",
    devices="/api/s/{site}/stat/device",
)

# API prefix required for site-specific endpoints
# UDM devices need /proxy/network prefix, self-hosted do not
API_PREFIXES: Dict[DeviceType, str] = {
    DeviceType.UDM_PRO: "/proxy/network",
    DeviceType.SELF_HOSTED: "",
}


def get_endpoints(device_type: DeviceType) -> Endpoints:
    """Get the API endpoints for a specific device type.

    Args:
        device_type: The type of UniFi controller.

    Returns:
        Endpoints dataclass with all API paths.

    Example:
        >>> endpoints = get_endpoints(DeviceType.UDM_PRO)
        >>> print(endpoints.login)
        /api/auth/login
    """
    if device_type == DeviceType.UDM_PRO:
        return UDM_PRO_ENDPOINTS
    return SELF_HOSTED_ENDPOINTS


def get_api_prefix(device_type: DeviceType) -> str:
    """Get the API prefix for site-specific endpoints.

    Args:
        device_type: The type of UniFi controller.

    Returns:
        API prefix string (e.g., '/proxy/network' for UDM, '' for self-hosted).

    Example:
        >>> prefix = get_api_prefix(DeviceType.UDM_PRO)
        >>> print(prefix)
        /proxy/network
    """
    return API_PREFIXES.get(device_type, "")
