"""Authentication and device detection for UniFi controllers.

This module handles:
- Auto-detection of device type (UDM vs self-hosted) by port probing
- Authentication with local admin credentials
- Logout for session cleanup
"""

import logging
from typing import Optional, Tuple

import httpx
import structlog

from unifi_scanner.models import DeviceType

from .endpoints import get_endpoints
from .exceptions import AuthenticationError, ConnectionError, DeviceDetectionError

logger = structlog.get_logger(__name__)

# Standard ports for UniFi controllers
# Order: UDM (443) first, then self-hosted (8443), then UniFi OS Server (11443)
DEFAULT_PORTS = [443, 8443, 11443]


def detect_device_type(
    host: str,
    port: Optional[int] = None,
    verify_ssl: bool = True,
    timeout: int = 10,
) -> Tuple[DeviceType, int]:
    """Detect the UniFi controller type by probing the status endpoint.

    Tries connecting to the /status endpoint (no auth required) on standard
    ports to determine if the controller is a UDM-type device or self-hosted.

    Args:
        host: Controller hostname or IP address.
        port: Specific port to try. If None, tries 443, 8443, 11443 in order.
        verify_ssl: Whether to verify SSL certificates.
        timeout: Connection timeout in seconds.

    Returns:
        Tuple of (DeviceType, detected_port).

    Raises:
        ConnectionError: Cannot connect to any port.
        DeviceDetectionError: Connected but cannot determine device type.

    Example:
        >>> device_type, port = detect_device_type("192.168.1.1")
        >>> print(f"Found {device_type.value} on port {port}")
        Found udm_pro on port 443
    """
    ports_to_try = [port] if port else DEFAULT_PORTS

    last_error: Optional[Exception] = None

    for try_port in ports_to_try:
        try:
            device_type = _probe_port(host, try_port, verify_ssl, timeout)
            logger.info(
                "device_detected",
                host=host,
                port=try_port,
                device_type=device_type.value,
            )
            return device_type, try_port
        except httpx.ConnectError as e:
            logger.debug(
                "port_connection_failed",
                host=host,
                port=try_port,
                error=str(e),
            )
            last_error = e
            continue
        except httpx.TimeoutException as e:
            logger.debug(
                "port_connection_timeout",
                host=host,
                port=try_port,
                error=str(e),
            )
            last_error = e
            continue
        except httpx.RequestError as e:
            logger.debug(
                "port_request_error",
                host=host,
                port=try_port,
                error=str(e),
            )
            last_error = e
            continue

    # All ports failed
    ports_tried = ", ".join(str(p) for p in ports_to_try)
    raise ConnectionError(
        message=f"Cannot connect to UniFi Controller at {host}",
        hint=f"Tried ports {ports_tried}. Is the controller running? Check network connectivity.",
    )


def _probe_port(
    host: str,
    port: int,
    verify_ssl: bool,
    timeout: int,
) -> DeviceType:
    """Probe a specific port to determine device type.

    Args:
        host: Controller hostname.
        port: Port to probe.
        verify_ssl: SSL verification flag.
        timeout: Timeout in seconds.

    Returns:
        Detected DeviceType.

    Raises:
        httpx.RequestError: Connection or request failed.
    """
    url = f"https://{host}:{port}/status"

    with httpx.Client(verify=verify_ssl, timeout=timeout) as client:
        response = client.get(url)

    # Port 443 is almost always UDM-type devices
    if port == 443:
        return DeviceType.UDM_PRO

    # Check response content for UDM indicators
    # UniFi OS devices often include version info or specific headers
    try:
        data = response.json()
        # Look for indicators of UniFi OS / UDM devices
        if any(
            key in str(data).lower()
            for key in ["unifi-os", "udm", "ucg", "unifi os"]
        ):
            return DeviceType.UDM_PRO
    except Exception:
        pass

    # Port 8443 and 11443 with no UDM indicators are self-hosted
    return DeviceType.SELF_HOSTED


def authenticate(
    client: httpx.Client,
    base_url: str,
    device_type: DeviceType,
    username: str,
    password: str,
) -> None:
    """Authenticate with the UniFi Controller.

    Sends credentials to the appropriate login endpoint based on device type.
    On success, the session cookie is stored in the client for subsequent requests.

    Args:
        client: httpx.Client instance (will store session cookie).
        base_url: Base URL of the controller (e.g., https://192.168.1.1:443).
        device_type: The type of UniFi controller.
        username: Local admin username.
        password: Admin password.

    Raises:
        AuthenticationError: Authentication failed (wrong credentials, cloud account, etc.)
        UnifiAPIError: Other API errors.

    Note:
        Password is never logged at any level. Username is logged at DEBUG only.
    """
    endpoints = get_endpoints(device_type)
    login_url = f"{base_url}{endpoints.login}"

    logger.debug("authenticating", username=username, device_type=device_type.value)

    try:
        response = client.post(
            login_url,
            json={"username": username, "password": password},
        )
    except httpx.RequestError as e:
        raise ConnectionError(
            message=f"Connection failed during authentication: {e}",
        )

    if response.status_code == 200:
        logger.info(
            "authentication_successful",
            device_type=device_type.value,
        )
        return

    if response.status_code in (401, 403):
        # Try to extract error message from response
        error_detail = ""
        try:
            data = response.json()
            error_detail = data.get("message", "") or data.get("error", "")
        except Exception:
            pass

        message = "Authentication failed"
        if error_detail:
            message = f"Authentication failed: {error_detail}"

        raise AuthenticationError(message=message)

    # Other error codes
    raise AuthenticationError(
        message=f"Authentication failed with status code {response.status_code}",
        hint="Check controller logs for more details.",
    )


def logout(
    client: httpx.Client,
    base_url: str,
    device_type: DeviceType,
) -> None:
    """Logout from the UniFi Controller (best-effort).

    This is a best-effort operation - errors are logged but not raised.
    The session will eventually expire on its own if logout fails.

    Args:
        client: httpx.Client instance with active session.
        base_url: Base URL of the controller.
        device_type: The type of UniFi controller.
    """
    endpoints = get_endpoints(device_type)
    logout_url = f"{base_url}{endpoints.logout}"

    try:
        response = client.post(logout_url)
        if response.status_code == 200:
            logger.debug("logout_successful")
        else:
            logger.debug(
                "logout_status",
                status_code=response.status_code,
            )
    except Exception as e:
        # Best-effort - don't raise on logout failure
        logger.debug("logout_failed", error=str(e))
