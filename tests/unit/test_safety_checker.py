"""Unit tests for safety rules around conflicting traffic lights."""

from __future__ import annotations

import pytest

from safety.safety_checker import SafetyChecker
from simulation.traffic_light import LightState


pytestmark = pytest.mark.unit


def test_check_states_rejects_conflicting_green() -> None:
    checker = SafetyChecker()
    states = {
        "north": LightState.GREEN,
        "south": LightState.RED,
        "east": LightState.GREEN,
        "west": LightState.RED,
    }

    assert checker.check_states(states) is False


def test_check_states_accepts_safe_axis_split() -> None:
    checker = SafetyChecker()
    states = {
        "north": LightState.GREEN,
        "south": LightState.GREEN,
        "east": LightState.RED,
        "west": LightState.RED,
    }

    assert checker.check_states(states) is True


def test_transition_rejects_green_to_red_without_yellow() -> None:
    checker = SafetyChecker()

    current = {"north": LightState.GREEN}
    new = {"north": LightState.RED}

    assert checker.check_transition(current, new) is False
