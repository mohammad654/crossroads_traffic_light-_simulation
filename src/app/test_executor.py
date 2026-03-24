"""Helpers for executing pytest suites with categorized markers."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Sequence

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TestResult:
    """Represents the outcome of a pytest invocation."""

    name: str
    exit_code: int
    duration_seconds: float
    command: Sequence[str]

    @property
    def succeeded(self) -> bool:
        """True when pytest returned success."""
        return self.exit_code == 0


class TestExecutor:
    """Executes selected test groups with rich reporting-friendly metadata."""

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def run_unit_tests(self) -> TestResult:
        """Run unit tests only."""
        return self._run("unit", ["-m", "unit"])

    def run_integration_tests(self) -> TestResult:
        """Run integration tests only."""
        return self._run("integration", ["-m", "integration"])

    def run_all_tests(self) -> TestResult:
        """Run the comprehensive suite."""
        return self._run("all", [])

    def _run(self, name: str, extra_args: list[str]) -> TestResult:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-ra",
            "--maxfail=1",
            "--durations=10",
            "--cov=src",
            "--cov-report=term-missing",
            "tests",
            *extra_args,
        ]

        LOGGER.info(
            "Starting test run", extra={"suite": name, "command": " ".join(cmd)}
        )
        start = time.perf_counter()

        try:
            completed = subprocess.run(cmd, check=False, timeout=self.timeout_seconds)
            code = completed.returncode
        except subprocess.TimeoutExpired:
            LOGGER.error(
                "Test run timed out",
                extra={"suite": name, "timeout": self.timeout_seconds},
            )
            code = 124

        duration = time.perf_counter() - start
        return TestResult(
            name=name, exit_code=code, duration_seconds=duration, command=tuple(cmd)
        )
