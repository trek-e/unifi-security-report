"""Configuration loading with YAML, environment override, and Docker secrets support."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from unifi_scanner.config.settings import UnifiSettings


class ConfigurationError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""

    pass


# Thread-safe global config storage
_config: Optional[UnifiSettings] = None
_config_lock = threading.Lock()


def resolve_file_secrets() -> Dict[str, str]:
    """Resolve Docker secrets pattern (_FILE suffix) from environment.

    Scans environment for variables matching UNIFI_*_FILE pattern,
    reads the file contents, and returns a dict of the base variable
    names to their values.

    Example:
        UNIFI_PASSWORD_FILE=/run/secrets/unifi_password
        -> Returns {"PASSWORD": "<file contents>"}
    """
    secrets: Dict[str, str] = {}
    prefix = "UNIFI_"
    suffix = "_FILE"

    for key, filepath in os.environ.items():
        if key.startswith(prefix) and key.endswith(suffix):
            # Extract base name: UNIFI_PASSWORD_FILE -> PASSWORD
            base_name = key[len(prefix) : -len(suffix)]
            try:
                path = Path(filepath)
                if path.exists():
                    content = path.read_text().strip()
                    secrets[base_name] = content
                else:
                    # Log warning but don't fail - let validation catch missing password
                    import structlog

                    log = structlog.get_logger()
                    log.warning(
                        "secret_file_not_found",
                        env_var=key,
                        path=filepath,
                    )
            except PermissionError:
                raise ConfigurationError(
                    f"Cannot read secret file '{filepath}' specified by {key}: permission denied"
                )
            except Exception as e:
                raise ConfigurationError(
                    f"Error reading secret file '{filepath}' specified by {key}: {e}"
                )

    return secrets


def load_yaml_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file if specified.

    Args:
        config_path: Path to YAML config file. If None, checks CONFIG_PATH env var.

    Returns:
        Dict of configuration values from YAML, or empty dict if no file.
    """
    path = config_path or os.environ.get("CONFIG_PATH")

    if not path:
        return {}

    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        raise ConfigurationError(
            f"Configuration file not found: {path}\n"
            "Ensure CONFIG_PATH points to a valid YAML file, or remove it to use environment variables only."
        )
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in configuration file {path}: {e}")
    except PermissionError:
        raise ConfigurationError(f"Cannot read configuration file {path}: permission denied")


def format_validation_errors(errors: List[Dict[str, Any]]) -> List[str]:
    """Format Pydantic validation errors into user-friendly messages."""
    messages: List[str] = []
    for error in errors:
        loc = ".".join(str(part) for part in error.get("loc", []))
        msg = error.get("msg", "Invalid value")
        input_val = error.get("input")

        if "missing" in msg.lower() or "required" in msg.lower():
            hint = f"Set UNIFI_{loc.upper()} environment variable or add '{loc}:' to config file."
            messages.append(f"Configuration error: '{loc}' is required. {hint}")
        elif input_val is not None:
            messages.append(f"Configuration error: '{loc}' {msg}, got: {input_val}")
        else:
            messages.append(f"Configuration error: '{loc}' {msg}")

    return messages


def load_config(config_path: Optional[str] = None) -> UnifiSettings:
    """Load and validate configuration.

    Configuration is loaded with the following precedence:
    1. Environment variables (highest priority)
    2. Docker secrets (_FILE pattern)
    3. YAML configuration file
    4. Default values (lowest priority)

    Args:
        config_path: Optional path to YAML config file (sets CONFIG_PATH env).

    Returns:
        Validated UnifiSettings instance.

    Raises:
        ConfigurationError: If configuration file cannot be read.
        SystemExit: If validation fails (exits with code 1 after logging errors).
    """
    global _config

    # Set CONFIG_PATH if provided directly
    if config_path:
        os.environ["CONFIG_PATH"] = config_path

    # Validate YAML file exists and is readable (gives better errors)
    # The actual loading happens in the pydantic settings source
    _ = load_yaml_config()

    # Resolve Docker secrets and apply to environment
    secrets = resolve_file_secrets()
    for key, value in secrets.items():
        env_key = f"UNIFI_{key}"
        if env_key not in os.environ:
            os.environ[env_key] = value

    # Create settings - pydantic-settings handles source precedence
    try:
        _config = UnifiSettings()
        with _config_lock:
            pass  # Config already set above
        return _config
    except ValidationError as e:
        # Format all errors at once for fail-fast behavior
        error_messages = format_validation_errors(e.errors())
        for msg in error_messages:
            print(msg, file=sys.stderr)
        sys.exit(1)


def get_config() -> UnifiSettings:
    """Get the current configuration.

    Returns:
        Current UnifiSettings instance.

    Raises:
        ConfigurationError: If configuration has not been loaded.
    """
    with _config_lock:
        if _config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return _config


def reload_config() -> UnifiSettings:
    """Reload configuration from disk.

    Used by SIGHUP handler for hot reload.

    Returns:
        New UnifiSettings instance.
    """
    global _config
    with _config_lock:
        _config = None
    return load_config()
