"""UniFi API client with device detection and site discovery.

The UnifiClient provides a high-level interface for connecting to UniFi
controllers, handling device type detection, authentication, and site selection
automatically.

Features:
- Automatic device type detection (UDM vs self-hosted)
- Session management with automatic re-authentication on 401
- Exponential backoff retry on connection failures
- Cookie-based session persistence

Example usage:
    from unifi_scanner.config import UnifiSettings
    from unifi_scanner.api import UnifiClient

    settings = UnifiSettings(host="192.168.1.1", username="admin", password="secret")

    with UnifiClient(settings) as client:
        sites = client.get_sites()
        print(f"Found {len(sites)} sites")
"""

from typing import Any, Dict, List, Optional

import httpx
import structlog

from unifi_scanner.config import UnifiSettings
from unifi_scanner.models import DeviceType

from .auth import authenticate, detect_device_type, logout
from .endpoints import get_api_prefix, get_endpoints
from .exceptions import (
    ConnectionError,
    MultipleSitesError,
    SiteNotFoundError,
    UnifiAPIError,
)
from .session import create_retry_decorator, request_with_session_check

logger = structlog.get_logger(__name__)


class UnifiClient:
    """Client for interacting with UniFi Controller API.

    Handles automatic device type detection, authentication, and site discovery.
    Works with both UDM-type devices (UDM Pro, UCG Ultra, Cloud Key Gen2+)
    and self-hosted UniFi Controller installations.

    Attributes:
        settings: UnifiSettings configuration object.
        device_type: Detected device type (set after connect).
        base_url: Base URL of the controller (set after connect).
        api_prefix: API prefix for site-specific endpoints (set after connect).

    Example:
        # As context manager (recommended)
        with UnifiClient(settings) as client:
            sites = client.get_sites()

        # Manual connection management
        client = UnifiClient(settings)
        client.connect()
        try:
            sites = client.get_sites()
        finally:
            client.disconnect()
    """

    def __init__(self, settings: UnifiSettings) -> None:
        """Initialize the UniFi client.

        Args:
            settings: Configuration settings for the UniFi connection.
        """
        self.settings = settings
        self._client: Optional[httpx.Client] = None
        self._authenticated: bool = False

        # These are set during connect()
        self.device_type: Optional[DeviceType] = None
        self.base_url: Optional[str] = None
        self.api_prefix: Optional[str] = None

        # Create retry decorator based on settings
        self._retry = create_retry_decorator(
            max_retries=settings.max_retries,
            min_wait=1,
            max_wait=60,
        )

    def connect(self) -> None:
        """Connect to the UniFi Controller.

        Performs device type detection, establishes connection, and authenticates.
        After successful connection, device_type, base_url, and api_prefix are set.

        Uses exponential backoff retry on connection failures (1s, 2s, 4s... max 60s).

        Raises:
            ConnectionError: Cannot connect to controller after all retries.
            DeviceDetectionError: Cannot determine device type.
            AuthenticationError: Authentication failed.
        """
        # Wrap the actual connect logic with retry decorator
        self._retry(self._connect_internal)()

    def _connect_internal(self) -> None:
        """Internal connection logic (wrapped with retry by connect())."""
        logger.info("connecting", host=self.settings.host)

        # Detect device type and port
        self.device_type, port = detect_device_type(
            host=self.settings.host,
            port=self.settings.port,
            verify_ssl=self.settings.verify_ssl,
            timeout=self.settings.connect_timeout,
        )

        self.base_url = f"https://{self.settings.host}:{port}"
        self.api_prefix = get_api_prefix(self.device_type)

        # Create HTTP client with cookie persistence
        self._client = httpx.Client(
            verify=self.settings.verify_ssl,
            timeout=self.settings.connect_timeout,
        )

        # Authenticate
        authenticate(
            client=self._client,
            base_url=self.base_url,
            device_type=self.device_type,
            username=self.settings.username,
            password=self.settings.password,
        )

        self._authenticated = True

        logger.info(
            "connected",
            device_type=self.device_type.value,
            base_url=self.base_url,
            api_prefix=self.api_prefix or "(none)",
        )

    def disconnect(self) -> None:
        """Disconnect from the UniFi Controller.

        Logs out (best-effort) and closes the HTTP client.
        Safe to call even if not connected.
        """
        if self._client is not None:
            if self._authenticated and self.base_url and self.device_type:
                logout(
                    client=self._client,
                    base_url=self.base_url,
                    device_type=self.device_type,
                )
            self._client.close()
            self._client = None

        self._authenticated = False
        logger.debug("disconnected")

    def get_sites(self) -> List[Dict[str, Any]]:
        """Get list of sites from the controller.

        Returns:
            List of site dictionaries, each containing 'name', 'desc', '_id'.

        Raises:
            UnifiAPIError: API request failed.
            RuntimeError: Not connected.

        Example:
            >>> sites = client.get_sites()
            >>> for site in sites:
            ...     print(f"{site['name']}: {site.get('desc', 'No description')}")
        """
        self._ensure_connected()
        assert self.device_type is not None  # For type checker

        endpoints = get_endpoints(self.device_type)
        response = self._request("GET", endpoints.sites)

        data = response.json()

        # UniFi API wraps data in {"meta": {...}, "data": [...]}
        if isinstance(data, dict) and "data" in data:
            sites = data["data"]
        else:
            sites = data if isinstance(data, list) else []

        logger.debug("sites_retrieved", count=len(sites))
        return sites

    def select_site(self, site_name: Optional[str] = None) -> str:
        """Select a site to use for subsequent operations.

        Args:
            site_name: Name of site to select. If None, auto-selects if only one site.

        Returns:
            Name of the selected site.

        Raises:
            SiteNotFoundError: Specified site does not exist.
            MultipleSitesError: Multiple sites exist but none specified.

        Example:
            >>> site = client.select_site()  # Auto-select if only one
            >>> site = client.select_site("default")  # Select specific site
        """
        sites = self.get_sites()

        if not sites:
            raise UnifiAPIError(
                message="No sites found on controller",
                hint="This is unusual. Check if the controller is properly configured.",
            )

        # Build list of site names for error messages
        site_names = [s.get("name", s.get("_id", "unknown")) for s in sites]

        if site_name:
            # User specified a site - find it
            for site in sites:
                if site.get("name") == site_name:
                    logger.info("site_selected", site=site_name, method="specified")
                    return site_name

            # Site not found
            raise SiteNotFoundError(site_name=site_name, available_sites=site_names)

        # No site specified - try to auto-select
        if len(sites) == 1:
            selected = site_names[0]
            logger.info("site_selected", site=selected, method="auto")
            return selected

        # Multiple sites and none specified
        raise MultipleSitesError(available_sites=site_names)

    def _raw_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a raw HTTP request without session handling.

        This method performs the actual HTTP request without checking for
        session expiration or handling 401 responses. Use _request() for
        automatic session management.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path.
            **kwargs: Additional arguments passed to httpx.request().

        Returns:
            Raw response object (may be 401 if session expired).

        Raises:
            ConnectionError: Network-level request failed.
            RuntimeError: Not connected.
        """
        self._ensure_connected()
        assert self._client is not None
        assert self.base_url is not None

        url = f"{self.base_url}{endpoint}"

        try:
            return self._client.request(method, url, **kwargs)
        except httpx.RequestError as e:
            raise ConnectionError(
                message=f"Request failed: {e}",
            )

    def _reauthenticate(self) -> None:
        """Re-authenticate with the controller.

        Called automatically when a 401 response is received, indicating
        the session has expired. Performs a fresh authentication using
        the stored credentials.

        Raises:
            AuthenticationError: Re-authentication failed.
            RuntimeError: Not connected or missing connection info.
        """
        if not self._client or not self.base_url or not self.device_type:
            raise RuntimeError("Cannot re-authenticate: not connected")

        logger.debug("reauthenticating", host=self.settings.host)

        authenticate(
            client=self._client,
            base_url=self.base_url,
            device_type=self.device_type,
            username=self.settings.username,
            password=self.settings.password,
        )

        self._authenticated = True
        logger.info("reauthenticated", host=self.settings.host)

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an API request with automatic session management.

        Uses request_with_session_check to handle 401 responses by
        re-authenticating and retrying the request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path.
            **kwargs: Additional arguments passed to httpx.request().

        Returns:
            Response object.

        Raises:
            UnifiAPIError: Request failed or session recovery failed.
            RuntimeError: Not connected.
        """
        self._ensure_connected()

        response = request_with_session_check(self, method, endpoint, **kwargs)

        # Handle common error codes (401 already handled by session check)
        if response.status_code == 401:
            # If we still get 401 after re-auth, it's a real auth failure
            raise UnifiAPIError(
                message="Session expired and re-authentication failed",
                hint="Check your credentials and try reconnecting.",
            )

        if response.status_code == 404:
            raise UnifiAPIError(
                message=f"Endpoint not found: {endpoint}",
                hint="This may indicate wrong device type detection.",
            )

        if response.status_code >= 400:
            raise UnifiAPIError(
                message=f"API error: {response.status_code} {response.reason_phrase}",
            )

        return response

    def _ensure_connected(self) -> None:
        """Ensure client is connected and authenticated.

        Raises:
            RuntimeError: Not connected.
        """
        if self._client is None or not self._authenticated:
            raise RuntimeError(
                "Not connected. Call connect() first or use as context manager."
            )

    def __enter__(self) -> "UnifiClient":
        """Enter context manager - connect to controller."""
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Exit context manager - disconnect from controller."""
        self.disconnect()
