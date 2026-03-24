"""
Data Models Module

This module defines the data structures used throughout the simulation.
"""

from typing import Dict, List, Tuple


class CrossroadConfiguration:
    """
    Configuration for a crossroad in the simulation.
    """

    def __init__(self, name: str):
        self.name = name
        self.lanes: Dict[str, Dict[str, object]] = {}
        self.entry_lanes: List[str] = []
        self.exit_lanes: List[str] = []
        self.traffic_lights: Dict[str, Dict[str, Tuple[float, float]]] = {}
        self.lane_connections: Dict[str, set[str]] = {}
        self.light_controlled_lanes: Dict[str, set[str]] = {}

    def add_lane(
        self,
        lane_id: str,
        start_pos: Tuple[float, float],
        end_pos: Tuple[float, float],
        is_entry: bool,
        is_exit: bool,
    ) -> None:
        self.lanes[lane_id] = {
            "start_pos": start_pos,
            "end_pos": end_pos,
            "is_entry": is_entry,
            "is_exit": is_exit,
        }
        if is_entry:
            self.entry_lanes.append(lane_id)
        if is_exit:
            self.exit_lanes.append(lane_id)

    def add_traffic_light(self, light_id: str, position: Tuple[float, float]) -> None:
        self.traffic_lights[light_id] = {"position": position}
        self.light_controlled_lanes[light_id] = set()

    def connect_lanes(self, from_lane_id: str, to_lane_id: str) -> None:
        if from_lane_id not in self.lane_connections:
            self.lane_connections[from_lane_id] = set()
        self.lane_connections[from_lane_id].add(to_lane_id)

    def assign_light_to_lane(self, light_id: str, lane_id: str) -> None:
        if light_id in self.light_controlled_lanes:
            self.light_controlled_lanes[light_id].add(lane_id)

    def get_possible_destinations(self, lane_id: str) -> List[str]:
        destinations: List[str] = []
        visited: set[str] = set()
        to_visit = {lane_id}

        while to_visit:
            current_lane = to_visit.pop()
            visited.add(current_lane)
            if current_lane in self.lane_connections:
                for next_lane in self.lane_connections[current_lane]:
                    if next_lane not in visited:
                        if next_lane in self.exit_lanes:
                            destinations.append(next_lane)
                        else:
                            to_visit.add(next_lane)

        return destinations

    def get_lane_entry_position(self, lane_id: str) -> Tuple[float, float]:
        if lane_id in self.lanes:
            return self.lanes[lane_id]["start_pos"]
        return (0.0, 0.0)

    def get_lane_direction(self, lane_id: str) -> Tuple[float, float]:
        if lane_id in self.lanes:
            start = self.lanes[lane_id]["start_pos"]
            end = self.lanes[lane_id]["end_pos"]
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = (dx**2 + dy**2) ** 0.5
            if length > 0:
                return (dx / length, dy / length)
        return (1.0, 0.0)


class SimulationScenario:
    """
    Configuration for a simulation scenario.
    """

    def __init__(self, name: str, crossroad: CrossroadConfiguration):
        self.name = name
        self.crossroad = crossroad
        self.traffic_density = {lane_id: 10.0 for lane_id in crossroad.entry_lanes}
        self.vehicle_type_distribution = {"car": 0.8, "truck": 0.1, "motorcycle": 0.1}
        self.controller_type = "basic_clock"
        self.controller_params = {
            "green_time": 30.0,
            "yellow_time": 3.0,
            "all_red_time": 2.0,
        }

    def set_traffic_density(self, lane_id: str, vehicles_per_minute: float) -> None:
        if lane_id in self.traffic_density:
            self.traffic_density[lane_id] = max(0.0, vehicles_per_minute)

    def set_vehicle_distribution(self, vehicle_type: str, proportion: float) -> None:
        self.vehicle_type_distribution[vehicle_type] = max(0.0, min(1.0, proportion))
        total = sum(self.vehicle_type_distribution.values())
        if total > 0:
            for vtype in self.vehicle_type_distribution:
                self.vehicle_type_distribution[vtype] /= total

    def set_controller(self, controller_type: str, params: Dict) -> None:
        self.controller_type = controller_type
        self.controller_params = params
