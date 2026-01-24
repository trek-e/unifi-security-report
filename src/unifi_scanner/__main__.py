"""
Entry point for the unifi-scanner CLI.

Usage:
    unifi-scanner             Run the scanner service (scheduled)
    unifi-scanner --run-once  Run once immediately and exit
    unifi-scanner --test      Validate configuration and connection, then exit
    unifi-scanner --help      Show help message
    unifi-scanner --version   Show version and exit

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
from datetime import datetime, timedelta, timezone
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

  # Run once immediately (manual trigger)
  unifi-scanner --run-once

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
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run one report cycle immediately and exit (manual trigger)",
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


def run_report_job() -> None:
    """Execute one report generation and delivery cycle.

    This function is called by the scheduler on each scheduled run,
    or once in one-shot mode. It runs the complete pipeline:
    1. Connect to UniFi API
    2. Collect logs
    3. Analyze logs
    4. Generate report
    5. Deliver via configured channels
    """
    from unifi_scanner.analysis import AnalysisEngine
    from unifi_scanner.analysis.rules import get_default_registry
    from unifi_scanner.api import UnifiClient
    from unifi_scanner.config.loader import get_config
    from unifi_scanner.delivery import DeliveryManager, EmailDelivery, FileDelivery
    from unifi_scanner.health import HealthStatus, update_health_status
    from unifi_scanner.logging import get_logger
    from unifi_scanner.logs.collector import LogCollector
    from unifi_scanner.models.enums import DeviceType
    from unifi_scanner.models.report import Report
    from unifi_scanner.reports.generator import ReportGenerator

    log = get_logger()
    config = get_config()

    log.info("job_starting")
    update_health_status(HealthStatus.HEALTHY, {"last_run": "starting"})

    try:
        # Connect and collect logs
        with UnifiClient(config) as client:
            site = client.select_site(config.site)

            # Collect logs
            collector = LogCollector(
                client=client,
                settings=config,
                site=site,
            )
            log_entries = collector.collect()
            log.info("logs_collected", count=len(log_entries))

            # Analyze logs with default rules
            registry = get_default_registry()
            engine = AnalysisEngine(registry=registry)
            findings = engine.analyze(log_entries)
            log.info("analysis_complete", findings_count=len(findings))

            # Build report
            now = datetime.now(timezone.utc)
            report = Report(
                period_start=now - timedelta(hours=24),
                period_end=now,
                site_name=site,
                controller_type=client.device_type or DeviceType.UNKNOWN,
                findings=findings,
                log_entry_count=len(log_entries),
            )

            # Generate report content
            generator = ReportGenerator(
                display_timezone=config.schedule_timezone,
            )
            html_content = generator.generate_html(report)
            text_content = generator.generate_text(report)

            # Set up delivery
            email_delivery = None
            if config.email_enabled and config.smtp_host:
                email_delivery = EmailDelivery(
                    smtp_host=config.smtp_host,
                    smtp_port=config.smtp_port,
                    smtp_user=config.smtp_user,
                    smtp_password=config.smtp_password,
                    use_tls=config.smtp_use_tls,
                    from_addr=config.email_from,
                    timezone=config.schedule_timezone,
                )

            file_delivery = None
            if config.file_enabled and config.file_output_dir:
                file_delivery = FileDelivery(
                    output_dir=config.file_output_dir,
                    file_format=config.file_format,
                    retention_days=config.file_retention_days,
                    timezone=config.schedule_timezone,
                )

            # Deliver
            manager = DeliveryManager(
                email_delivery=email_delivery,
                file_delivery=file_delivery,
            )

            recipients = config.get_email_recipients()

            success = manager.deliver(
                report=report,
                html_content=html_content,
                text_content=text_content,
                email_recipients=recipients,
            )

            if success:
                log.info("job_complete", status="success")
                update_health_status(HealthStatus.HEALTHY, {"last_run": "success"})
            else:
                log.warning("job_complete", status="delivery_failed")
                update_health_status(HealthStatus.UNHEALTHY, {"last_run": "delivery_failed"})

    except Exception as e:
        log.error("job_failed", error=str(e))
        update_health_status(HealthStatus.UNHEALTHY, {"last_run": str(e)})


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
    from unifi_scanner.scheduler import ScheduledRunner

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

    # Run-once mode: execute one report cycle and exit
    if args.run_once:
        print_banner(config)
        log.info("run_once_mode", message="Running single report cycle")
        update_health_status(HealthStatus.STARTING)
        try:
            run_report_job()
            clear_health_status()
            return EXIT_SUCCESS
        except Exception as e:
            log.error("run_once_failed", error=str(e))
            print(f"\nReport generation failed: {e}", file=sys.stderr)
            clear_health_status()
            return EXIT_CONFIG_ERROR

    # Normal mode - print banner and start service
    print_banner(config)
    log.info("starting", version=__version__)
    update_health_status(HealthStatus.STARTING)

    # Set up signal handler for config reload (Unix only)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_sighup)

    # Initialize scheduler
    runner = ScheduledRunner(timezone=config.schedule_timezone)

    log.info(
        "service_starting",
        schedule_preset=config.schedule_preset,
        schedule_cron=config.schedule_cron,
        timezone=config.schedule_timezone,
    )

    try:
        runner.run(
            func=run_report_job,
            cron_expr=config.schedule_cron,
            preset=config.schedule_preset,
        )
        return EXIT_SUCCESS
    except KeyboardInterrupt:
        log.info("shutdown", reason="keyboard interrupt")
        print("\nShutdown requested, exiting...")
        runner.shutdown()
        clear_health_status()
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
