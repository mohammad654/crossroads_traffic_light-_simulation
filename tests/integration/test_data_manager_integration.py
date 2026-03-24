"""Integration tests for DataManager file operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from data.data_manager import DataManager


pytestmark = pytest.mark.integration


def test_save_and_load_scenario_round_trip(temp_data_dir: Path) -> None:
    manager = DataManager(data_dir=str(temp_data_dir))
    payload = {"algorithm": "adaptive", "weather": "clear"}

    manager.save_scenario("scenario_a", payload)
    loaded = manager.load_scenario("scenario_a")

    assert loaded == payload


def test_export_results_creates_file(temp_data_dir: Path) -> None:
    manager = DataManager(data_dir=str(temp_data_dir))
    output_file = manager.export_simulation_results("result.json", {"throughput": 10})

    assert Path(output_file).exists()
