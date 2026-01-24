"""Custom exceptions for UniFi API operations.

All exceptions inherit from UnifiAPIError for consistent error handling.
Each exception includes helpful messages for non-expert users.
"""

from typing import List, Optional


class UnifiAPIError(Exception):
    """Base exception for all UniFi API errors.

    Attributes:
        message: Human-readable error message.
        hint: Optional troubleshooting hint for non-experts.
        exit_code: Suggested exit code for CLI applications.
    """

    exit_code: int = 1

    def __init__(
        self,
        message: str,
        hint: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        self.message = message
        self.hint = hint
        if exit_code is not None:
            self.exit_code = exit_code
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the exception message with optional hint."""
        if self.hint:
            return f"{self.message}\n\nHint: {self.hint}"
        return self.message


class AuthenticationError(UnifiAPIError):
    """Authentication failed with the UniFi Controller.

    This typically occurs when:
    - Using cloud/SSO credentials instead of local admin account
    - Incorrect username or password
    - Account is locked or disabled
    """

    exit_code: int = 3

    def __init__(
        self,
        message: str = "Authentication failed",
        hint: Optional[str] = None,
    ) -> None:
        if hint is None:
            hint = (
                "Ensure you're using a LOCAL admin account, not cloud SSO. "
                "Create a local admin in UniFi OS Console > Admins & Users."
            )
        super().__init__(message=message, hint=hint, exit_code=3)


class ConnectionError(UnifiAPIError):
    """Cannot reach the UniFi Controller.

    This typically occurs when:
    - Controller is not running
    - Incorrect hostname/IP address
    - Network connectivity issues
    - Firewall blocking the connection
    """

    exit_code: int = 2

    def __init__(
        self,
        message: str = "Cannot connect to UniFi Controller",
        hint: Optional[str] = None,
    ) -> None:
        if hint is None:
            hint = (
                "Is the UniFi Controller running? Check network connectivity. "
                "Common ports are 443 (UDM), 8443 (self-hosted), 11443 (UniFi OS Server)."
            )
        super().__init__(message=message, hint=hint, exit_code=2)


class DeviceDetectionError(UnifiAPIError):
    """Cannot determine the device type of the UniFi Controller.

    This typically occurs when:
    - None of the standard ports respond
    - Controller is running but /status endpoint is unavailable
    - Unexpected response format from controller
    """

    exit_code: int = 2

    def __init__(
        self,
        message: str = "Cannot determine UniFi device type",
        hint: Optional[str] = None,
    ) -> None:
        if hint is None:
            hint = (
                "Could not connect on ports 443, 8443, or 11443. "
                "Verify the controller is running and accessible from this host."
            )
        super().__init__(message=message, hint=hint, exit_code=2)


class SiteNotFoundError(UnifiAPIError):
    """Specified site does not exist on the controller.

    This typically occurs when:
    - Typo in site name configuration
    - Site was deleted from the controller
    """

    exit_code: int = 1

    def __init__(
        self,
        site_name: str,
        available_sites: Optional[List[str]] = None,
    ) -> None:
        message = f"Site '{site_name}' not found on controller"
        hint = None
        if available_sites:
            sites_list = ", ".join(available_sites)
            hint = f"Available sites: {sites_list}"
        super().__init__(message=message, hint=hint)


class MultipleSitesError(UnifiAPIError):
    """Multiple sites found but none specified in configuration.

    When a controller has multiple sites, you must specify which site
    to use via the UNIFI_SITE environment variable or config file.
    """

    exit_code: int = 1

    def __init__(
        self,
        available_sites: List[str],
    ) -> None:
        sites_list = ", ".join(available_sites)
        message = (
            f"Multiple sites found on controller: {sites_list}. "
            "Please specify which site to use."
        )
        hint = "Set UNIFI_SITE environment variable or 'site' in config file."
        super().__init__(message=message, hint=hint)
