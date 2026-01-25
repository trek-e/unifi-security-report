"""Tests for integration infrastructure.

Tests the Protocol contract, IntegrationRegistry filtering, and IntegrationRunner
isolation/circuit breaker behavior (INTG-01, INTG-02, INTG-03 requirements).
"""

import pytest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from unifi_scanner.integrations.base import (
    Integration,
    IntegrationResult,
    IntegrationResults,
    IntegrationSection,
)
from unifi_scanner.integrations.registry import IntegrationRegistry


# =============================================================================
# Mock Integrations for Testing
# =============================================================================


class ConfiguredIntegration:
    """Mock integration that is fully configured and succeeds."""

    name = "configured_test"

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return True

    def validate_config(self) -> Optional[str]:
        return None

    async def fetch(self) -> IntegrationResult:
        return IntegrationResult(
            name=self.name,
            success=True,
            data={"test_key": "test_value"},
        )


class UnconfiguredIntegration:
    """Mock integration that is not configured."""

    name = "unconfigured_test"

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return False

    def validate_config(self) -> Optional[str]:
        return None

    async def fetch(self) -> IntegrationResult:
        # Should never be called since not configured
        raise RuntimeError("fetch() called on unconfigured integration")


class PartiallyConfiguredIntegration:
    """Mock integration with partial configuration (triggers warning)."""

    name = "partial_test"

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return False

    def validate_config(self) -> Optional[str]:
        return "Missing api_key (zone_id is set)"

    async def fetch(self) -> IntegrationResult:
        raise RuntimeError("fetch() called on partially configured integration")


class FailingIntegration:
    """Mock integration that is configured but throws on fetch()."""

    name = "failing_test"

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return True

    def validate_config(self) -> Optional[str]:
        return None

    async def fetch(self) -> IntegrationResult:
        raise ConnectionError("API connection failed")


class SlowIntegration:
    """Mock integration that takes longer than timeout."""

    name = "slow_test"

    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return True

    def validate_config(self) -> Optional[str]:
        return None

    async def fetch(self) -> IntegrationResult:
        import asyncio
        # Sleep for 60 seconds (longer than 30s timeout)
        await asyncio.sleep(60)
        return IntegrationResult(name=self.name, success=True, data={})


# =============================================================================
# Protocol/Dataclass Tests (INTG-01)
# =============================================================================


class TestIntegrationResult:
    """Tests for IntegrationResult dataclass."""

    def test_integration_result_dataclass(self):
        """Verify IntegrationResult has expected fields."""
        result = IntegrationResult(
            name="test",
            success=True,
            data={"key": "value"},
            error=None,
        )

        assert result.name == "test"
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_integration_result_failure(self):
        """Verify IntegrationResult can represent failures."""
        result = IntegrationResult(
            name="test",
            success=False,
            data=None,
            error="Connection timeout",
        )

        assert result.name == "test"
        assert result.success is False
        assert result.data is None
        assert result.error == "Connection timeout"

    def test_integration_result_defaults(self):
        """Verify IntegrationResult default values."""
        result = IntegrationResult(name="test", success=True)

        assert result.data is None
        assert result.error is None


class TestIntegrationSection:
    """Tests for IntegrationSection dataclass."""

    def test_integration_section_dataclass(self):
        """Verify IntegrationSection has expected fields."""
        section = IntegrationSection(
            name="cloudflare",
            display_name="Cloudflare Security",
            success=True,
            data={"firewall_events": 10},
            error_message=None,
        )

        assert section.name == "cloudflare"
        assert section.display_name == "Cloudflare Security"
        assert section.success is True
        assert section.data == {"firewall_events": 10}
        assert section.error_message is None

    def test_integration_section_failure(self):
        """Verify IntegrationSection can represent failures."""
        section = IntegrationSection(
            name="cloudflare",
            display_name="Cloudflare Security",
            success=False,
            data=None,
            error_message="Unable to fetch data",
        )

        assert section.success is False
        assert section.data is None
        assert section.error_message == "Unable to fetch data"

    def test_integration_section_defaults(self):
        """Verify IntegrationSection default values."""
        section = IntegrationSection(
            name="test",
            display_name="Test",
            success=True,
        )

        assert section.data is None
        assert section.error_message is None


class TestIntegrationResults:
    """Tests for IntegrationResults aggregate dataclass."""

    def test_integration_results_has_data_true(self):
        """has_data returns True when at least one section has data."""
        results = IntegrationResults(
            sections=[
                IntegrationSection(name="a", display_name="A", success=True, data={"x": 1}),
                IntegrationSection(name="b", display_name="B", success=False),
            ]
        )

        assert results.has_data is True

    def test_integration_results_has_data_false_no_sections(self):
        """has_data returns False when no sections exist."""
        results = IntegrationResults(sections=[])

        assert results.has_data is False

    def test_integration_results_has_data_false_all_failed(self):
        """has_data returns False when all sections failed."""
        results = IntegrationResults(
            sections=[
                IntegrationSection(name="a", display_name="A", success=False),
                IntegrationSection(name="b", display_name="B", success=False),
            ]
        )

        assert results.has_data is False

    def test_integration_results_has_data_false_success_but_empty(self):
        """has_data returns False when success=True but data is None/empty."""
        results = IntegrationResults(
            sections=[
                IntegrationSection(name="a", display_name="A", success=True, data=None),
            ]
        )

        assert results.has_data is False

    def test_integration_results_get_section_found(self):
        """get_section returns section when found."""
        section_a = IntegrationSection(name="a", display_name="A", success=True)
        section_b = IntegrationSection(name="b", display_name="B", success=True)
        results = IntegrationResults(sections=[section_a, section_b])

        found = results.get_section("b")

        assert found is section_b

    def test_integration_results_get_section_not_found(self):
        """get_section returns None when not found."""
        results = IntegrationResults(
            sections=[IntegrationSection(name="a", display_name="A", success=True)]
        )

        found = results.get_section("nonexistent")

        assert found is None

    def test_integration_results_default_empty(self):
        """IntegrationResults defaults to empty sections list."""
        results = IntegrationResults()

        assert results.sections == []
        assert results.has_data is False


# =============================================================================
# IntegrationRegistry Tests
# =============================================================================


class TestIntegrationRegistry:
    """Tests for IntegrationRegistry filtering behavior."""

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear registry before and after each test to avoid state leakage."""
        IntegrationRegistry.clear()
        yield
        IntegrationRegistry.clear()

    @pytest.fixture
    def mock_settings(self):
        """Create a mock settings object for testing."""
        return MagicMock()

    def test_registry_empty_when_no_integrations(self, mock_settings):
        """get_configured returns empty list when no integrations registered."""
        # Registry is cleared by fixture, so no integrations
        result = IntegrationRegistry.get_configured(mock_settings)

        assert result == []

    def test_registry_filters_unconfigured(self, mock_settings):
        """get_configured only returns configured integrations."""
        IntegrationRegistry.register(ConfiguredIntegration)
        IntegrationRegistry.register(UnconfiguredIntegration)

        result = IntegrationRegistry.get_configured(mock_settings)

        assert len(result) == 1
        assert result[0].name == "configured_test"

    def test_registry_logs_partial_config_warning(self, mock_settings, capsys):
        """Partial configuration triggers warning log."""
        IntegrationRegistry.register(PartiallyConfiguredIntegration)

        result = IntegrationRegistry.get_configured(mock_settings)

        # Partial config integration is not returned (not fully configured)
        assert len(result) == 0

        # Warning should be logged (structlog writes to stdout in dev mode)
        captured = capsys.readouterr()
        output = captured.out.lower()
        assert "warning" in output or "partial" in output
        assert "partial_test" in output or "missing" in output

    def test_registry_get_all_returns_all(self, mock_settings):
        """get_all returns all integrations regardless of configuration."""
        IntegrationRegistry.register(ConfiguredIntegration)
        IntegrationRegistry.register(UnconfiguredIntegration)

        result = IntegrationRegistry.get_all(mock_settings)

        assert len(result) == 2
        names = [i.name for i in result]
        assert "configured_test" in names
        assert "unconfigured_test" in names

    def test_registry_register_idempotent(self, mock_settings):
        """Registering the same class twice doesn't duplicate it."""
        IntegrationRegistry.register(ConfiguredIntegration)
        IntegrationRegistry.register(ConfiguredIntegration)

        result = IntegrationRegistry.get_all(mock_settings)

        assert len(result) == 1

    def test_registry_handles_init_failure(self, mock_settings):
        """Registry handles integration class that fails to instantiate."""

        class FailingInit:
            name = "failing_init"

            def __init__(self, settings):
                raise ValueError("Init failed")

        IntegrationRegistry.register(FailingInit)
        IntegrationRegistry.register(ConfiguredIntegration)

        # Should not raise, should return only successful init
        result = IntegrationRegistry.get_configured(mock_settings)

        assert len(result) == 1
        assert result[0].name == "configured_test"


# =============================================================================
# IntegrationRunner Tests (INTG-02, INTG-03)
# =============================================================================
# These tests require runner.py which is created in plan 10-02.
# Tests are designed to skip gracefully if runner module doesn't exist.


class TestIntegrationRunner:
    """Tests for IntegrationRunner parallel execution and isolation."""

    @pytest.fixture(autouse=True)
    def import_runner(self):
        """Import runner module, skip tests if not available."""
        try:
            from unifi_scanner.integrations import runner
            self.runner = runner
            self.IntegrationRunner = runner.IntegrationRunner
        except ImportError:
            pytest.skip("IntegrationRunner not yet implemented (plan 10-02)")

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear registry before and after each test."""
        IntegrationRegistry.clear()
        yield
        IntegrationRegistry.clear()

    @pytest.fixture
    def mock_settings(self):
        """Create a mock settings object for testing."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_runner_empty_when_no_integrations(self, mock_settings):
        """Returns empty IntegrationResults when no integrations configured."""
        runner = self.IntegrationRunner(mock_settings)

        result = await runner.run_all()

        assert isinstance(result, IntegrationResults)
        assert result.sections == []
        assert result.has_data is False

    @pytest.mark.asyncio
    async def test_runner_isolates_failures(self, mock_settings):
        """One failing integration doesn't prevent others from succeeding."""
        IntegrationRegistry.register(ConfiguredIntegration)
        IntegrationRegistry.register(FailingIntegration)

        runner = self.IntegrationRunner(mock_settings)
        result = await runner.run_all()

        # Should have results for both integrations
        assert len(result.sections) == 2

        # Find sections by name
        configured_section = result.get_section("configured_test")
        failing_section = result.get_section("failing_test")

        # Configured should succeed
        assert configured_section is not None
        assert configured_section.success is True

        # Failing should fail but not crash the runner
        assert failing_section is not None
        assert failing_section.success is False

    @pytest.mark.asyncio
    async def test_runner_returns_all_results(self, mock_settings):
        """Results include both success and failure."""
        IntegrationRegistry.register(ConfiguredIntegration)
        IntegrationRegistry.register(FailingIntegration)

        runner = self.IntegrationRunner(mock_settings)
        result = await runner.run_all()

        # Both should be present
        names = [s.name for s in result.sections]
        assert "configured_test" in names
        assert "failing_test" in names

    @pytest.mark.asyncio
    async def test_runner_converts_to_sections(self, mock_settings):
        """IntegrationResult converted to IntegrationSection."""
        IntegrationRegistry.register(ConfiguredIntegration)

        runner = self.IntegrationRunner(mock_settings)
        result = await runner.run_all()

        section = result.get_section("configured_test")
        assert section is not None
        assert isinstance(section, IntegrationSection)
        assert section.name == "configured_test"
        assert section.success is True

    @pytest.mark.asyncio
    async def test_runner_sets_error_message_on_failure(self, mock_settings):
        """Failed integrations have error_message set."""
        IntegrationRegistry.register(FailingIntegration)

        runner = self.IntegrationRunner(mock_settings)
        result = await runner.run_all()

        section = result.get_section("failing_test")
        assert section is not None
        assert section.success is False
        assert section.error_message is not None
        assert len(section.error_message) > 0


class TestIntegrationRunnerTimeout:
    """Tests for IntegrationRunner timeout behavior."""

    @pytest.fixture(autouse=True)
    def import_runner(self):
        """Import runner module, skip tests if not available."""
        try:
            from unifi_scanner.integrations import runner
            self.runner = runner
            self.IntegrationRunner = runner.IntegrationRunner
        except ImportError:
            pytest.skip("IntegrationRunner not yet implemented (plan 10-02)")

    @pytest.fixture(autouse=True)
    def clear_registry(self):
        """Clear registry before and after each test."""
        IntegrationRegistry.clear()
        yield
        IntegrationRegistry.clear()

    @pytest.fixture
    def mock_settings(self):
        """Create a mock settings object for testing."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_runner_timeout_returns_failure(self, mock_settings):
        """SlowIntegration returns timeout error."""
        from unittest.mock import patch

        IntegrationRegistry.register(SlowIntegration)

        # Clear any existing circuit breaker for this integration
        self.runner._circuit_breakers.pop("slow_test", None)

        # Patch the timeout constant to 0.1 seconds for fast testing
        with patch.object(self.runner, "INTEGRATION_TIMEOUT", 0.1):
            runner = self.IntegrationRunner(mock_settings)
            result = await runner.run_all()

        section = result.get_section("slow_test")
        assert section is not None
        assert section.success is False
        # Error message includes timeout info
        assert section.error_message is not None
        assert "timeout" in section.error_message.lower()


class TestCircuitBreaker:
    """Tests for circuit breaker behavior (INTG-03)."""

    @pytest.fixture(autouse=True)
    def import_runner(self):
        """Import runner module, skip tests if not available."""
        try:
            from unifi_scanner.integrations import runner
            self.runner = runner
            self.IntegrationRunner = runner.IntegrationRunner
            self.get_circuit_breaker = runner.get_circuit_breaker
        except ImportError:
            pytest.skip("IntegrationRunner not yet implemented (plan 10-02)")

    @pytest.fixture(autouse=True)
    def clear_registry_and_breakers(self):
        """Clear registry and circuit breakers before each test."""
        IntegrationRegistry.clear()
        # Reset circuit breakers
        if hasattr(self, "runner") and hasattr(self.runner, "_circuit_breakers"):
            self.runner._circuit_breakers.clear()
        yield
        IntegrationRegistry.clear()
        if hasattr(self, "runner") and hasattr(self.runner, "_circuit_breakers"):
            self.runner._circuit_breakers.clear()

    @pytest.fixture
    def mock_settings(self):
        """Create a mock settings object for testing."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, mock_settings):
        """After 3 failures, circuit opens."""
        # Clear any pre-existing circuit breaker for this integration
        self.runner._circuit_breakers.pop("failing_test", None)

        IntegrationRegistry.register(FailingIntegration)

        runner = self.IntegrationRunner(mock_settings)

        # Run 3 times to trip circuit breaker (fail_max=3)
        for i in range(3):
            await runner.run_all()

        # Get circuit breaker state
        cb = self.get_circuit_breaker("failing_test")
        assert cb.current_state == "open", f"Expected 'open' but got '{cb.current_state}'"

    @pytest.mark.asyncio
    async def test_circuit_breaker_returns_circuit_open_error(self, mock_settings):
        """When open, returns 'circuit_open' error."""
        # Clear any pre-existing circuit breaker for this integration
        self.runner._circuit_breakers.pop("failing_test", None)

        IntegrationRegistry.register(FailingIntegration)

        runner = self.IntegrationRunner(mock_settings)

        # Trip the circuit breaker (need 3 failures)
        for _ in range(3):
            await runner.run_all()

        # Verify circuit is open
        cb = self.get_circuit_breaker("failing_test")
        assert cb.current_state == "open"

        # Next call should return circuit_open error immediately
        result = await runner.run_all()
        section = result.get_section("failing_test")

        assert section is not None
        assert section.success is False
        assert section.error_message is not None
        assert "circuit" in section.error_message.lower()


# =============================================================================
# Integration Protocol Compliance Tests
# =============================================================================


class TestProtocolCompliance:
    """Verify mock integrations comply with Integration Protocol."""

    def test_configured_integration_is_protocol_compliant(self):
        """ConfiguredIntegration satisfies Integration Protocol."""
        integration = ConfiguredIntegration(MagicMock())

        # Has required attributes/methods
        assert hasattr(integration, "name")
        assert hasattr(integration, "is_configured")
        assert hasattr(integration, "validate_config")
        assert hasattr(integration, "fetch")

        # name is string
        assert isinstance(integration.name, str)

        # is_configured returns bool
        assert isinstance(integration.is_configured(), bool)

        # validate_config returns Optional[str]
        result = integration.validate_config()
        assert result is None or isinstance(result, str)

    def test_unconfigured_integration_is_protocol_compliant(self):
        """UnconfiguredIntegration satisfies Integration Protocol."""
        integration = UnconfiguredIntegration(MagicMock())

        assert hasattr(integration, "name")
        assert hasattr(integration, "is_configured")
        assert hasattr(integration, "validate_config")
        assert hasattr(integration, "fetch")

        assert integration.is_configured() is False

    def test_partially_configured_returns_warning(self):
        """PartiallyConfiguredIntegration returns warning from validate_config."""
        integration = PartiallyConfiguredIntegration(MagicMock())

        warning = integration.validate_config()

        assert warning is not None
        assert isinstance(warning, str)
        assert len(warning) > 0
