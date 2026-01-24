"""
Entry point for the unifi-scanner CLI.

Usage:
    unifi-scanner           Run the scanner service
    unifi-scanner --test    Validate configuration and connection, then exit
    unifi-scanner --help    Show help message
    unifi-scanner --version Show version and exit

Exit Codes:
    0 - Success
    1 - Configuration error (invalid settings, missing required values)
    2 - Connection error (cannot reach UniFi Controller)
    3 - Authentication error (invalid credentials, wrong account type)
"""

from __future__ import annotations

import argparse
import signal
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from types import FrameType
    from unifi_scanner.api import UnifiClient
    from unifi_scanner.config import UnifiSettings

from unifi_scanner import __version__

# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_CONNECTION_ERROR = 2
EXIT_AUTH_ERROR = 3


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="unifi-scanner",
        description="Translate cryptic UniFi logs into understandable findings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0   Success
  1   Configuration error
  2   Connection error (cannot reach controller)
  3   Authentication error (invalid credentials)

Environment Variables:
  CONFIG_PATH           Path to YAML configuration file
  UNIFI_HOST            UniFi Controller hostname or IP
  UNIFI_USERNAME        UniFi admin username
  UNIFI_PASSWORD        UniFi admin password
  UNIFI_PASSWORD_FILE   Path to file containing password (Docker secrets)
  UNIFI_PORT            Controller port (auto-detected if not set)
  UNIFI_SITE            Site name (auto-selected if only one site)
  UNIFI_VERIFY_SSL      Enable SSL verification (default: true)
  UNIFI_POLL_INTERVAL   Poll interval in seconds (default: 300)
  UNIFI_LOG_LEVEL       Logging level: DEBUG, INFO, WARNING, ERROR
  UNIFI_LOG_FORMAT      Log format: json or text

Examples:
  # Run with config file
  CONFIG_PATH=/etc/unifi-scanner/config.yaml unifi-scanner

  # Test configuration and connection
  unifi-scanner --test

  # Run with environment variables only
  UNIFI_HOST=192.168.1.1 UNIFI_USERNAME=admin UNIFI_PASSWORD=secret unifi-scanner
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test configuration and connection, then exit",
    )
    return parser.parse_args()


def handle_sighup(signum: int, frame: Optional[FrameType]) -> None:
    """Handle SIGHUP signal for configuration reload."""
    from unifi_scanner.config.loader import reload_config
    from unifi_scanner.logging import get_logger

    log = get_logger()
    log.info("received_sighup", action="reloading configuration")
    try:
        reload_config()
        log.info("config_reloaded", status="success")
    except Exception as e:
        log.error("config_reload_failed", error=str(e))


def print_banner(
    config: "UnifiSettings",
    client: Optional["UnifiClient"] = None,
) -> None:
    """Print startup banner with version and configuration summary.

    Displays a professional banner showing the service version,
    detected controller type, site, poll interval, and log settings.

    Args:
        config: Configuration settings object.
        client: Optional connected UnifiClient for device type info.
    """
    lines = [
        "",
        f"UniFi Scanner v{__version__}",
        "=" * 40,
    ]

    if client and client.device_type:
        lines.append(f"Controller: {client.device_type.value}")
        lines.append(f"Base URL:   {client.base_url}")

    lines.extend([
        f"Poll Interval: {config.poll_interval}s",
        f"Log Level:     {config.log_level}",
        f"Log Format:    {config.log_format}",
        "=" * 40,
        "",
    ])

    for line in lines:
        print(line)


def main() -> int:
    """Main entry point for unifi-scanner.

    Returns:
        Exit code (0=success, 1=config error, 2=connection error, 3=auth error)
    """
    args = parse_args()

    # Import here to avoid circular imports and allow --help without dependencies
    from unifi_scanner.api import UnifiClient
    from unifi_scanner.api.exceptions import AuthenticationError, ConnectionError
    from unifi_scanner.config.loader import ConfigurationError, load_config
    from unifi_scanner.health import HealthStatus, clear_health_status, update_health_status
    from unifi_scanner.logging import configure_logging, get_logger

    # Load configuration
    try:
        config = load_config()
    except ConfigurationError as e:
        # Configuration errors are already logged by loader
        print(f"Configuration error: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except SystemExit as e:
        # Validation errors cause sys.exit(1) in loader
        return e.code if isinstance(e.code, int) else EXIT_CONFIG_ERROR

    # Configure logging based on settings
    configure_logging(log_format=config.log_format, log_level=config.log_level)
    log = get_logger()

    # Test mode: verify config and connection, then exit
    if args.test:
        update_health_status(HealthStatus.STARTING)
        try:
            with UnifiClient(config) as client:
                site = client.select_site(config.site)
                print_banner(config, client)
                print(f"Site: {site}")
                print("Configuration and connection: OK")
                update_health_status(HealthStatus.HEALTHY, {"site": site})
                return EXIT_SUCCESS
        except ConnectionError as e:
            log.error("connection_failed", error=str(e))
            print(f"\nConnection error: {e}", file=sys.stderr)
            update_health_status(HealthStatus.UNHEALTHY, {"error": str(e)})
            return EXIT_CONNECTION_ERROR
        except AuthenticationError as e:
            log.error("authentication_failed", error=str(e))
            print(f"\nAuthentication error: {e}", file=sys.stderr)
            update_health_status(HealthStatus.UNHEALTHY, {"error": str(e)})
            return EXIT_AUTH_ERROR
        except Exception as e:
            log.error("test_failed", error=str(e))
            print(f"\nTest failed: {e}", file=sys.stderr)
            update_health_status(HealthStatus.UNHEALTHY, {"error": str(e)})
            return EXIT_CONFIG_ERROR
        finally:
            clear_health_status()

    # Normal mode - print banner and start service
    print_banner(config)
    log.info("starting", version=__version__)
    update_health_status(HealthStatus.STARTING)

    # Set up signal handler for config reload (Unix only)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_sighup)

    # Main service loop (placeholder for Phase 5 - scheduling)
    log.info("service_starting", poll_interval=config.poll_interval)
    try:
        # TODO: Phase 5 will add scheduling loop here
        log.info(
            "service_ready",
            message="UniFi Scanner ready. Scheduling not yet implemented.",
        )
        update_health_status(HealthStatus.HEALTHY, {"poll_interval": config.poll_interval})
        # For now, just exit cleanly
        return EXIT_SUCCESS
    except KeyboardInterrupt:
        log.info("shutdown", reason="keyboard interrupt")
        print("\nShutdown requested, exiting...")
        clear_health_status()
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
