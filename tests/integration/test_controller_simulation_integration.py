"""Integration tests for controller and simulation manager interactions."""

from __future__ import annotations

import pytest

from controllers.traffic_light_controller import TrafficLightController
from safety.safety_checker import SafetyChecker
from simulation.simulation_manager import SimulationManager


pytestmark = pytest.mark.integration


def test_simulation_update_initializes_lights_and_advances_time() -> None:
    controller = TrafficLightController(SafetyChecker())
    simulation = SimulationManager(controller)

    start_time = simulation.elapsed_time
    simulation.update(0.1)

    assert simulation.elapsed_time > start_time
    assert set(simulation.traffic_lights.keys()) == {"north", "south", "east", "west"}


def test_simulation_reset_clears_runtime_state() -> None:
    controller = TrafficLightController(SafetyChecker())
    simulation = SimulationManager(controller)
    simulation.update(0.2)
    simulation.exited_vehicles = 3

    simulation.reset()

    assert simulation.elapsed_time == 0
    assert simulation.exited_vehicles == 0
    assert simulation.vehicles == []
