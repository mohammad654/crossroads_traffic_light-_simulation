"""Security-focused checks around secret handling and source scanning."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import AppConfig


pytestmark = pytest.mark.security


SUSPICIOUS_PATTERNS = [
    'api_key = "',
    'password = "',
    'token = "',
    'secret = "',
]


def test_safe_summary_does_not_expose_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_REMOTE_METRICS", "true")
    monkeypatch.setenv("TELEMETRY_API_KEY", "top-secret-token")
    config = AppConfig.from_env()

    summary = str(config.safe_summary())

    assert "top-secret-token" not in summary


def test_no_obvious_hardcoded_secrets_in_source() -> None:
    src_dir = Path(__file__).resolve().parents[2] / "src"

    offenders: list[str] = []
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore").lower()
        if any(pattern in content for pattern in SUSPICIOUS_PATTERNS):
            offenders.append(str(py_file))

    assert offenders == []
