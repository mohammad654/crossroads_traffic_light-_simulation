"""Configuration management with environment variable validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.exceptions import ConfigurationError

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - safe fallback if dependency is unavailable
    load_dotenv = None


_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    """Validated application configuration loaded from environment variables."""

    app_env: str
    data_dir: Path
    log_level: str
    test_timeout_seconds: int
    enable_remote_metrics: bool
    telemetry_api_key: Optional[str]
    database_password: Optional[str]

    @classmethod
    def from_env(cls, dotenv_path: str = ".env") -> "AppConfig":
        """Load and validate configuration from OS environment variables."""
        if load_dotenv is not None:
            load_dotenv(dotenv_path=dotenv_path, override=False)

        app_env = os.getenv("APP_ENV", "development").strip().lower()
        if app_env not in {"development", "test", "production"}:
            raise ConfigurationError(
                "APP_ENV must be one of: development, test, production."
            )

        data_dir = Path(os.getenv("APP_DATA_DIR", "data")).resolve()
        log_level = os.getenv("APP_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError(
                "APP_LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )

        timeout_str = os.getenv("TEST_TIMEOUT_SECONDS", "240").strip()
        if not timeout_str.isdigit() or int(timeout_str) <= 0:
            raise ConfigurationError("TEST_TIMEOUT_SECONDS must be a positive integer.")

        enable_remote_metrics = (
            os.getenv("ENABLE_REMOTE_METRICS", "false").strip().lower() in _TRUE_VALUES
        )
        telemetry_api_key = os.getenv("TELEMETRY_API_KEY")
        database_password = os.getenv("DATABASE_PASSWORD")

        if enable_remote_metrics and not telemetry_api_key:
            raise ConfigurationError(
                "TELEMETRY_API_KEY is required when ENABLE_REMOTE_METRICS=true."
            )

        return cls(
            app_env=app_env,
            data_dir=data_dir,
            log_level=log_level,
            test_timeout_seconds=int(timeout_str),
            enable_remote_metrics=enable_remote_metrics,
            telemetry_api_key=telemetry_api_key,
            database_password=database_password,
        )

    def safe_summary(self) -> dict[str, object]:
        """Return a redacted view of config values for logs and diagnostics."""
        return {
            "app_env": self.app_env,
            "data_dir": str(self.data_dir),
            "log_level": self.log_level,
            "test_timeout_seconds": self.test_timeout_seconds,
            "enable_remote_metrics": self.enable_remote_metrics,
            "telemetry_api_key_configured": bool(self.telemetry_api_key),
            "database_password_configured": bool(self.database_password),
        }
