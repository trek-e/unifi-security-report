"""Pydantic settings models for UniFi Scanner configuration."""

from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional, Tuple, Type

import yaml
from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads values from a YAML file.

    The YAML file path is determined by the CONFIG_PATH environment variable.
    """

    def get_field_value(
        self, field: Any, field_name: str
    ) -> Tuple[Any, str, bool]:
        """Get field value from YAML config."""
        yaml_config = self._load_yaml_config()
        field_value = yaml_config.get(field_name)
        return field_value, field_name, False

    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        config_path = os.environ.get("CONFIG_PATH")
        if not config_path:
            return {}

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, yaml.YAMLError, PermissionError):
            # Errors will be handled by loader.py
            return {}

    def __call__(self) -> Dict[str, Any]:
        """Return the YAML config values."""
        return self._load_yaml_config()


class UnifiSettings(BaseSettings):
    """UniFi Scanner configuration settings.

    Configuration is loaded in the following precedence (highest to lowest):
    1. Environment variables (UNIFI_ prefix)
    2. Docker secrets (_FILE pattern, applied via env)
    3. YAML configuration file (via CONFIG_PATH)
    4. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix="UNIFI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required settings
    host: str = Field(
        ...,
        description="UniFi Controller hostname or IP address",
    )
    username: str = Field(
        ...,
        description="UniFi admin username (must be local account, not cloud SSO)",
    )
    password: str = Field(
        default="",
        description="UniFi admin password",
    )

    # Optional connection settings
    port: Optional[int] = Field(
        default=None,
        description="Controller port (auto-detected from 443, 8443, 11443 if not set)",
        ge=1,
        le=65535,
    )
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates (set to false for self-signed certs)",
    )
    site: Optional[str] = Field(
        default=None,
        description="UniFi site name (auto-discovered if not set)",
    )

    # Timeout and retry settings
    connect_timeout: int = Field(
        default=10,
        description="Connection timeout in seconds",
        gt=0,
    )
    max_retries: int = Field(
        default=5,
        description="Maximum number of retry attempts on connection failure",
        ge=0,
    )
    poll_interval: int = Field(
        default=300,
        description="Polling interval in seconds",
        gt=0,
    )

    # Logging settings
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format: json (production) or text (development)",
    )

    # SSH fallback settings
    ssh_username: Optional[str] = Field(
        default=None,
        description="SSH username for fallback (defaults to username if not set)",
    )
    ssh_password: Optional[str] = Field(
        default=None,
        description="SSH password for fallback (defaults to password if not set)",
    )
    ssh_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="SSH command timeout in seconds",
    )
    ssh_enabled: bool = Field(
        default=True,
        description="Enable SSH fallback when API is insufficient",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources to set precedence.

        Order (first = highest priority):
        1. init_settings (constructor arguments - rarely used)
        2. env_settings (environment variables with UNIFI_ prefix)
        3. dotenv_settings (.env file)
        4. yaml_settings (CONFIG_PATH YAML file)
        5. file_secret_settings (not used, handled by loader)
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate and normalize log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL"}
        normalized = v.upper()
        if normalized == "WARN":
            normalized = "WARNING"
        if normalized not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: DEBUG, INFO, WARNING, ERROR"
            )
        return normalized

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is not empty."""
        if not v or not v.strip():
            raise ValueError("Host cannot be empty")
        return v.strip()

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username is not empty."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()
