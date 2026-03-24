"""Unit tests for environment-based configuration validation."""

from __future__ import annotations


import pytest

from app.config import AppConfig
from app.exceptions import ConfigurationError


pytestmark = pytest.mark.unit


def test_config_loads_defaults_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_DATA_DIR", raising=False)
    monkeypatch.delenv("APP_LOG_LEVEL", raising=False)
    monkeypatch.delenv("TEST_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("ENABLE_REMOTE_METRICS", raising=False)

    config = AppConfig.from_env()

    assert config.app_env == "development"
    assert config.log_level == "INFO"
    assert config.test_timeout_seconds == 240
    assert config.enable_remote_metrics is False


def test_config_requires_telemetry_key_when_remote_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_REMOTE_METRICS", "true")
    monkeypatch.delenv("TELEMETRY_API_KEY", raising=False)

    with pytest.raises(ConfigurationError):
        AppConfig.from_env()


def test_config_rejects_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_LOG_LEVEL", "INVALID")

    with pytest.raises(ConfigurationError):
        AppConfig.from_env()


def test_safe_summary_redacts_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_REMOTE_METRICS", "true")
    monkeypatch.setenv("TELEMETRY_API_KEY", "secret")
    monkeypatch.setenv("DATABASE_PASSWORD", "db-secret")

    summary = AppConfig.from_env().safe_summary()

    assert summary["telemetry_api_key_configured"] is True
    assert summary["database_password_configured"] is True
    assert "secret" not in str(summary)
    assert "db-secret" not in str(summary)
