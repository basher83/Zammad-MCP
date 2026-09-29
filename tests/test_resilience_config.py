"""Tests for environment-backed resilience configuration."""

import os
from unittest.mock import patch

import pytest
from zammad_py.exceptions import ConfigException

from mcp_zammad.resilience_config import ResilienceConfig

_FULL_ENV = {
    "ZAMMAD_RATE_LIMIT_ENABLED": "true",
    "ZAMMAD_RATE_LIMIT_REQUESTS": "120",
    "ZAMMAD_RATE_LIMIT_WINDOW": "30",
    "ZAMMAD_MAX_RETRIES": "5",
    "ZAMMAD_RETRY_BACKOFF_BASE": "0.5",
    "ZAMMAD_CIRCUIT_BREAKER_FAILURE_THRESHOLD": "8",
    "ZAMMAD_CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "45",
}


def test_defaults_keep_rate_limiting_disabled() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = ResilienceConfig.from_env()

    assert config == ResilienceConfig(
        rate_limit_enabled=False,
        rate_limit_requests=60,
        rate_limit_window=60.0,
        max_retries=3,
        retry_backoff_base=1.0,
        circuit_failure_threshold=5,
        circuit_recovery_timeout=30.0,
    )


def test_environment_values_are_parsed() -> None:
    with patch.dict(os.environ, _FULL_ENV, clear=True):
        config = ResilienceConfig.from_env()

    assert config.rate_limit_enabled is True
    assert config.rate_limit_requests == 120
    assert config.rate_limit_window == 30.0
    assert config.max_retries == 5
    assert config.retry_backoff_base == 0.5
    assert config.circuit_failure_threshold == 8
    assert config.circuit_recovery_timeout == 45.0


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_falsy_boolean_values_disable_rate_limiting(value: str) -> None:
    with patch.dict(os.environ, {"ZAMMAD_RATE_LIMIT_ENABLED": value}, clear=True):
        assert ResilienceConfig.from_env().rate_limit_enabled is False


def test_invalid_boolean_is_rejected() -> None:
    with (
        patch.dict(os.environ, {"ZAMMAD_RATE_LIMIT_ENABLED": "maybe"}, clear=True),
        pytest.raises(ConfigException, match="ZAMMAD_RATE_LIMIT_ENABLED"),
    ):
        ResilienceConfig.from_env()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ZAMMAD_RATE_LIMIT_REQUESTS", "0"),
        ("ZAMMAD_RATE_LIMIT_REQUESTS", "ten"),
        ("ZAMMAD_RATE_LIMIT_WINDOW", "-1"),
        ("ZAMMAD_MAX_RETRIES", "-1"),
        ("ZAMMAD_MAX_RETRIES", "2.5"),
        ("ZAMMAD_RETRY_BACKOFF_BASE", "0"),
        ("ZAMMAD_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "0"),
        ("ZAMMAD_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "abc"),
    ],
)
def test_invalid_numeric_values_are_rejected(name: str, value: str) -> None:
    with patch.dict(os.environ, {name: value}, clear=True), pytest.raises(ConfigException, match=name):
        ResilienceConfig.from_env()


def test_zero_retries_is_allowed() -> None:
    with patch.dict(os.environ, {"ZAMMAD_MAX_RETRIES": "0"}, clear=True):
        assert ResilienceConfig.from_env().max_retries == 0
