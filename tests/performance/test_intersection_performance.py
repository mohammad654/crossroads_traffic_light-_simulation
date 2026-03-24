"""Performance checks for critical geometry helpers."""

from __future__ import annotations

import time

import pytest

from simulation.intersection import Intersection


pytestmark = pytest.mark.performance


def test_distance_to_stop_line_bulk_runtime() -> None:
    intersection = Intersection()

    start = time.perf_counter()
    for _ in range(10000):
        intersection.distance_to_stop_line("north", (100.0, 150.0))
        intersection.distance_to_stop_line("south", (100.0, 50.0))
        intersection.distance_to_stop_line("east", (50.0, 100.0))
        intersection.distance_to_stop_line("west", (150.0, 100.0))
    duration = time.perf_counter() - start

    # Lenient threshold to avoid flaky failures in CI while still catching regressions.
    assert duration < 0.35
