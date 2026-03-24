"""Functional tests for high-level runner CLI orchestration paths."""

from __future__ import annotations

import pytest

from app.config import AppConfig
import runner


pytestmark = pytest.mark.functional


@pytest.fixture
def valid_config(tmp_path):
    return AppConfig(
        app_env="test",
        data_dir=tmp_path,
        log_level="INFO",
        test_timeout_seconds=30,
        enable_remote_metrics=False,
        telemetry_api_key=None,
        database_password=None,
    )


def test_main_runs_unit_mode_from_cli(
    monkeypatch: pytest.MonkeyPatch, valid_config: AppConfig
) -> None:
    monkeypatch.setattr(runner.AppConfig, "from_env", lambda: valid_config)
    monkeypatch.setattr(runner, "_run_unit", lambda executor: 0)

    code = runner.main(["--unit-tests"])

    assert code == 0


def test_main_rejects_multiple_noninteractive_modes(
    monkeypatch: pytest.MonkeyPatch, valid_config: AppConfig
) -> None:
    monkeypatch.setattr(runner.AppConfig, "from_env", lambda: valid_config)

    code = runner.main(["--unit-tests", "--all-tests"])

    assert code == 2
