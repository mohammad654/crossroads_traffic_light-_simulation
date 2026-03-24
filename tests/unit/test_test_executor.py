"""Unit tests for pytest subprocess execution wrapper."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest
import pytest_mock

from app.test_executor import TestExecutor as AppTestExecutor


pytestmark = pytest.mark.unit


def test_unit_test_command_build_and_success(mocker: pytest_mock.MockerFixture) -> None:
    run_mock = mocker.patch(
        "app.test_executor.subprocess.run", return_value=SimpleNamespace(returncode=0)
    )
    executor = AppTestExecutor(timeout_seconds=10)

    result = executor.run_unit_tests()

    assert result.succeeded is True
    assert result.exit_code == 0
    run_mock.assert_called_once()
    cmd = run_mock.call_args.args[0]
    assert "pytest" in cmd
    assert "-m" in cmd
    assert "unit" in cmd


def test_timeout_returns_exit_code_124(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "app.test_executor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=1),
    )
    executor = AppTestExecutor(timeout_seconds=1)

    result = executor.run_all_tests()

    assert result.exit_code == 124
    assert result.succeeded is False
