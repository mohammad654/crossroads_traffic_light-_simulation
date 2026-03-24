"""Unit tests for vehicle initialization and heading logic."""

from __future__ import annotations

import pytest

from simulation.vehicle import Vehicle, VehicleType


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        ("north", 0.0),
        ("east", 90.0),
        ("south", 180.0),
        ("west", 270.0),
    ],
)
def test_vehicle_initial_rotation(direction: str, expected: float) -> None:
    vehicle = Vehicle(
        vehicle_type=VehicleType.CAR,
        position=(0.0, 0.0),
        direction=direction,
        target_direction="east",
    )

    assert vehicle.rotation == expected


def test_vehicle_sets_basic_attributes() -> None:
    vehicle = Vehicle(
        vehicle_type=VehicleType.CAR,
        position=(1.0, 2.0),
        direction="north",
        target_direction="east",
        lane_index=1,
    )

    assert vehicle.vehicle_type is VehicleType.CAR
    assert vehicle.position == (1.0, 2.0)
    assert vehicle.direction == "north"
    assert vehicle.target_direction == "east"
    assert vehicle.lane_index == 1
    assert vehicle.max_speed > 0
