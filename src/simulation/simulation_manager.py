# src/simulation/simulation_manager.py
import random
import json
import time
import math
from simulation.vehicle import Vehicle, VehicleType
from simulation.traffic_light import TrafficLight, LightState
from simulation.intersection import Intersection


class Pedestrian:
    """Simple pedestrian entity for crosswalk traffic."""
    def __init__(self, position, direction):
        self.position = position
        self.direction = direction
        self.speed = random.uniform(1.0, 1.5)

    def update(self, dt):
        dx, dy = self.direction
        self.position = (self.position[0] + dx * self.speed * dt, self.position[1] + dy * self.speed * dt)


class PedestrianSignal:
    """Represents a pedestrian walk/don't-walk signal for one crossing axis."""
    def __init__(self, crossing, position):
        self.crossing = crossing
        self.position = position
        self.walk = False

    def set_walk(self, enabled):
        self.walk = bool(enabled)

    @property
    def state(self):
        return "WALK" if self.walk else "STOP"


class SimulationManager:
    """
    Manages the overall simulation, including vehicles, traffic lights,
    and their interactions at the intersection.
    """
    def __init__(self, traffic_controller):
        self.traffic_controller = traffic_controller
        self.intersection = Intersection()
        self.vehicles = []
        self.pedestrians = []
        self.obstacles = []
        self.elapsed_time = 0
        self.spawn_timer = 0
        self.spawn_interval = random.uniform(1.2, 2.4)
        self.pedestrian_timer = 0.0
        self.pedestrian_interval = random.uniform(3.0, 6.0)

        # Modes
        self.traffic_density_factor = 1.0
        self.simulation_speed_factor = 1.0
        self.rush_hour_mode = False
        self.weather_mode = "clear"
        self.random_events_enabled = True

        # Runtime events
        self.active_events = []
        self.last_event_time = 0.0

        # V2I and priority state
        self.v2i_messages = []
        self.priority_request = None

        # Analytics
        self.exited_vehicles = 0
        self.throughput_window_counter = 0
        self.throughput_last_window = 0.0
        self.window_timer = 0.0
        self.wait_time_history = []
        self.throughput_history = []
        self.congestion_heatmap = {}
        self.algorithm_comparison = {}
        self.last_algorithm = self.traffic_controller.algorithm
        self.close_proximity_count = 0
        self.avg_speed_history = []
        self.pedestrian_signals = {}

        # Playback state
        self.paused = False
        self.safety_violation_count = 0
        self.recording = False
        self.recorded_frames = []
        self.record_start_time = 0.0
        self.playback_frames = []
        self.playback_index = 0
        self.playback_active = False
        
        # Initialize traffic lights
        self.setup_traffic_lights()
        self.setup_pedestrian_signals()
        
    def setup_traffic_lights(self):
        """Set up the traffic lights at the intersection."""
        # Create traffic lights for each direction
        self.traffic_lights = {
            "north": TrafficLight("north", self.intersection.get_position("north")),
            "south": TrafficLight("south", self.intersection.get_position("south")),
            "east": TrafficLight("east", self.intersection.get_position("east")),
            "west": TrafficLight("west", self.intersection.get_position("west"))
        }
        
        # Register traffic lights with the controller
        for direction, light in self.traffic_lights.items():
            self.traffic_controller.register_traffic_light(light)

    def setup_pedestrian_signals(self):
        center_x, center_y = self.intersection.center
        half_w = self.intersection.width / 2
        half_h = self.intersection.height / 2
        self.pedestrian_signals = {
            "ns_cross": PedestrianSignal("ns_cross", (center_x, center_y - half_h - 8)),
            "ew_cross": PedestrianSignal("ew_cross", (center_x + half_w + 8, center_y))
        }
    
    def toggle_pause(self):
        """Toggle the paused state of the simulation."""
        self.paused = not self.paused

    def reset(self):
        """Reset the simulation to its initial state."""
        self.vehicles.clear()
        self.pedestrians.clear()
        self.obstacles.clear()
        self.elapsed_time = 0
        self.spawn_timer = 0
        self.spawn_interval = random.uniform(1.2, 2.4)
        self.pedestrian_timer = 0.0
        self.exited_vehicles = 0
        self.throughput_window_counter = 0
        self.throughput_last_window = 0.0
        self.window_timer = 0.0
        self.wait_time_history.clear()
        self.throughput_history.clear()
        self.congestion_heatmap.clear()
        self.avg_speed_history.clear()
        self.active_events.clear()
        self.close_proximity_count = 0
        self.safety_violation_count = 0
        self.recorded_frames.clear()
        self.recording = False
        self.playback_active = False
        self.playback_frames.clear()
        self.playback_index = 0
        self.traffic_controller.phase_index = 0
        self.traffic_controller.phase_timer = 0.0
        self.traffic_controller.elapsed_time = 0

    def start_recording(self):
        """Begin recording simulation frames."""
        self.recording = True
        self.recorded_frames = []
        self.record_start_time = self.elapsed_time

    def stop_recording(self):
        """Stop recording and store frames for playback."""
        self.recording = False
        self.playback_frames = list(self.recorded_frames)

    def start_playback(self):
        """Start replaying the last recording from the beginning."""
        if self.playback_frames:
            self.playback_active = True
            self.playback_index = 0

    def stop_playback(self):
        self.playback_active = False
        self.playback_index = 0

    def _record_frame(self):
        frame = {
            "t": self.elapsed_time - self.record_start_time,
            "vehicles": [(v.position, v.direction, v.velocity) for v in self.vehicles],
            "lights": {d: l.state.name for d, l in self.traffic_lights.items()},
        }
        self.recorded_frames.append(frame)
        if len(self.recorded_frames) > 6000:
            self.recorded_frames = self.recorded_frames[-6000:]

    def update(self, dt):
        """
        Update the simulation state.

        Args:
            dt: Delta time in seconds since the last update
        """
        if self.paused:
            return

        dt_scaled = dt * self.simulation_speed_factor
        self.elapsed_time += dt_scaled
        self.spawn_timer += dt_scaled
        self.pedestrian_timer += dt_scaled
        self.window_timer += dt_scaled

        self.update_random_events(dt_scaled)

        queue_lengths = self.compute_queue_lengths()
        queue_weighted = self.compute_weighted_queue_lengths()
        avg_wait = self.compute_avg_wait_time()
        self.priority_request = self.compute_priority_request()
        self.v2i_messages = [v.v2i_message for v in self.vehicles if v.v2i_message]
        
        # Update traffic lights
        self.traffic_controller.update(dt_scaled, {
            "queue_lengths": queue_lengths,
            "queue_weighted": queue_weighted,
            "avg_wait_time": avg_wait,
            "throughput_last_window": self.throughput_last_window,
            "weather": self.weather_mode,
            "rush_hour": self.rush_hour_mode,
            "priority_request": self.priority_request,
            "coordination_offset": 5.0 + 2.0 * math_sin_wave(self.elapsed_time, 40.0)
        })

        walk_states = self.traffic_controller.get_pedestrian_walk_states()
        for crossing, can_walk in walk_states.items():
            if crossing in self.pedestrian_signals:
                self.pedestrian_signals[crossing].set_walk(can_walk)
        
        # Spawn new vehicles
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer = 0
            self.spawn_vehicle()
            base_min, base_max = (1.0, 2.6)
            if self.rush_hour_mode:
                base_min, base_max = (0.45, 1.15)
            factor = max(0.2, self.traffic_density_factor)
            self.spawn_interval = random.uniform(base_min, base_max) / factor

        # Spawn pedestrians
        if self.pedestrian_timer >= self.pedestrian_interval:
            self.pedestrian_timer = 0.0
            self.spawn_pedestrian(walk_states)
            self.pedestrian_interval = random.uniform(2.5, 5.5)
        
        # Update vehicle positions and behaviors
        self.update_vehicles(dt_scaled)
        self.update_pedestrians(dt_scaled)
        self.update_heatmap()
        self.update_throughput_window(dt_scaled)
        self.update_proximity_metrics()
        self.capture_algorithm_comparison()

        # Record frame if recording is active (every ~0.5s worth of frames)
        if self.recording and len(self.recorded_frames) % 30 == 0:
            self._record_frame()

        # Check for vehicles that have left the simulation area
        self.remove_out_of_bounds_vehicles()
    
    def spawn_vehicle(self):
        """Spawn a new vehicle at one of the entry points."""
        directions = ["north", "south", "east", "west"]
        entry_direction = random.choice(directions)

        # Realistic traffic mix: mostly cars, occasional trucks/buses/motorcycles.
        vehicle_type = random.choices(
            [VehicleType.CAR, VehicleType.TRUCK, VehicleType.BUS, VehicleType.MOTORCYCLE],
            weights=[0.68, 0.12, 0.10, 0.10],
        )[0]

        target_direction = self.get_random_target_direction(entry_direction)
        going_straight = target_direction == entry_direction
        turning = not going_straight

        # Large vehicles (truck/bus) prefer the straight lane for safety.
        if vehicle_type in (VehicleType.TRUCK, VehicleType.BUS):
            lane_index = self.intersection.get_straight_lane_index(entry_direction)
        else:
            lane_index = (
                self.intersection.get_straight_lane_index(entry_direction)
                if going_straight
                else self.intersection.get_turning_lane_index(entry_direction)
            )
        spawn_position = self.intersection.get_spawn_position(entry_direction, lane_index=lane_index, turning=turning)
        
        vehicle = Vehicle(
            vehicle_type=vehicle_type,
            position=spawn_position,
            direction=entry_direction,
            target_direction=target_direction,
            lane_index=lane_index
        )

        if self.can_spawn_vehicle(vehicle):
            self.vehicles.append(vehicle)

    def can_spawn_vehicle(self, candidate_vehicle):
        """Check whether a new vehicle can be spawned without immediate overlap."""
        min_spawn_gap = max(11.0, candidate_vehicle.length * 2.4)

        for existing in self.vehicles:
            if existing.direction != candidate_vehicle.direction:
                continue

            if candidate_vehicle.direction in ["north", "south"]:
                lateral_offset = abs(existing.position[0] - candidate_vehicle.position[0])
            else:
                lateral_offset = abs(existing.position[1] - candidate_vehicle.position[1])

            if lateral_offset > 2.4:
                continue

            gap = math.hypot(
                existing.position[0] - candidate_vehicle.position[0],
                existing.position[1] - candidate_vehicle.position[1]
            )
            if gap < min_spawn_gap:
                return False

        return True

    def spawn_pedestrian(self, walk_states=None):
        walk_states = walk_states or {}
        center_x, center_y = self.intersection.center
        available = []
        if walk_states.get("ns_cross"):
            available.extend(["north", "south"])
        if walk_states.get("ew_cross"):
            available.extend(["east", "west"])
        if not available:
            return

        approach = random.choice(available)
        offset = random.uniform(-8.0, 8.0)
        if approach == "north":
            position = (center_x + offset, center_y + self.intersection.height / 2 + 7)
            direction = (0.0, -1.0)
        elif approach == "south":
            position = (center_x + offset, center_y - self.intersection.height / 2 - 7)
            direction = (0.0, 1.0)
        elif approach == "east":
            position = (center_x - self.intersection.width / 2 - 7, center_y + offset)
            direction = (1.0, 0.0)
        else:
            position = (center_x + self.intersection.width / 2 + 7, center_y + offset)
            direction = (-1.0, 0.0)

        self.pedestrians.append(Pedestrian(position, direction))
    
    def get_random_target_direction(self, entry_direction):
        """
        Get a destination direction for a spawned vehicle.
        Straight movement keeps the same heading label as entry_direction.
        
        Args:
            entry_direction: The direction from which the vehicle entered
            
        Returns:
            A target direction (straight or right-turn)
        """
        right_turn_direction = {
            "north": "east",
            "east": "south",
            "south": "west",
            "west": "north"
        }

        left_turn_direction = {
            "north": "west",
            "west": "south",
            "south": "east",
            "east": "north"
        }

        # Favor straight travel to keep the visualization readable and lane-stable.
        return random.choices(
            [entry_direction, right_turn_direction[entry_direction], left_turn_direction[entry_direction]],
            weights=[0.62, 0.24, 0.14]
        )[0]
    
    def update_vehicles(self, dt):
        """
        Update all vehicles in the simulation.
        
        Args:
            dt: Delta time in seconds
        """
        for vehicle in self.vehicles:
            # Get the traffic light state for the vehicle's direction
            light_state = self.get_relevant_traffic_light_state(vehicle)
            
            # Update the vehicle based on traffic light state and surroundings
            vehicle.update(
                dt,
                light_state,
                self.vehicles,
                self.intersection,
                weather=self.weather_mode,
                obstacles=[],
                pedestrian_blocks=self.compute_pedestrian_blocks_for_vehicles()
            )

    def compute_pedestrian_blocks_for_vehicles(self):
        blocks = []
        for crossing, signal in self.pedestrian_signals.items():
            if not signal.walk:
                continue
            if crossing == "ns_cross":
                blocks.extend([
                    {"direction": "north", "distance": 8.0},
                    {"direction": "south", "distance": 8.0}
                ])
            elif crossing == "ew_cross":
                blocks.extend([
                    {"direction": "east", "distance": 8.0},
                    {"direction": "west", "distance": 8.0}
                ])
        return blocks

    def update_pedestrians(self, dt):
        for pedestrian in self.pedestrians:
            pedestrian.update(dt)

        self.pedestrians = [
            p for p in self.pedestrians
            if self.intersection.is_in_bounds(p.position)
        ]
    
    def get_relevant_traffic_light_state(self, vehicle):
        """
        Get the state of the traffic light relevant to the vehicle.
        
        Args:
            vehicle: The vehicle to check
            
        Returns:
            The state of the relevant traffic light
        """
        # Determine which traffic light affects this vehicle
        direction = vehicle.direction
        if direction in self.traffic_lights:
            return self.traffic_lights[direction].state
        return LightState.RED  # Default to red if no relevant light
    
    def remove_out_of_bounds_vehicles(self):
        """Remove vehicles that have left the simulation area."""
        in_bounds = []
        for vehicle in self.vehicles:
            if self.intersection.is_in_bounds(vehicle.position):
                in_bounds.append(vehicle)
            else:
                self.exited_vehicles += 1
                self.throughput_window_counter += 1
        self.vehicles = in_bounds

    def compute_queue_lengths(self):
        queues = {"ns": 0, "ew": 0}
        for vehicle in self.vehicles:
            distance_to_line = self.intersection.distance_to_stop_line(vehicle.direction, vehicle.position)
            if 0 <= distance_to_line <= 20 and vehicle.velocity < 2.0:
                if vehicle.direction in ["north", "south"]:
                    queues["ns"] += 1
                else:
                    queues["ew"] += 1
        return queues

    def compute_weighted_queue_lengths(self):
        weighted = {"ns": 0.0, "ew": 0.0}
        for vehicle in self.vehicles:
            distance_to_line = self.intersection.distance_to_stop_line(vehicle.direction, vehicle.position)
            if 0 <= distance_to_line <= 25:
                weight = 1.0
                if vehicle.direction in ["north", "south"]:
                    weighted["ns"] += weight
                else:
                    weighted["ew"] += weight
        return weighted

    def compute_avg_wait_time(self):
        if not self.vehicles:
            return 0.0
        waits = [v.wait_time for v in self.vehicles]
        avg = sum(waits) / max(1, len(waits))
        self.wait_time_history.append(avg)
        if len(self.wait_time_history) > 300:
            self.wait_time_history = self.wait_time_history[-300:]
        return avg

    def compute_priority_request(self):
        # Car-only fleet: no special vehicle-priority requests.
        return None

    def update_heatmap(self):
        for vehicle in self.vehicles:
            if vehicle.velocity < 2.5:
                gx = int(vehicle.position[0] // 4)
                gy = int(vehicle.position[1] // 4)
                key = (gx, gy)
                self.congestion_heatmap[key] = self.congestion_heatmap.get(key, 0) + 1

        if len(self.congestion_heatmap) > 900:
            sorted_points = sorted(self.congestion_heatmap.items(), key=lambda item: item[1], reverse=True)
            self.congestion_heatmap = dict(sorted_points[:900])

    def update_proximity_metrics(self):
        for vehicle in self.vehicles:
            vehicle.too_close = False

        close_calls = 0
        for i in range(len(self.vehicles)):
            for j in range(i + 1, len(self.vehicles)):
                first = self.vehicles[i]
                second = self.vehicles[j]
                distance = math.hypot(first.position[0] - second.position[0], first.position[1] - second.position[1])
                dynamic_threshold = max(2.5, 0.45 * (first.length + second.length) + 0.25 * (first.velocity + second.velocity))
                if distance < dynamic_threshold:
                    close_calls += 1
                    first.too_close = True
                    second.too_close = True

        self.close_proximity_count = close_calls
        average_speed = sum(v.velocity for v in self.vehicles) / max(1, len(self.vehicles))
        self.avg_speed_history.append(average_speed)
        if len(self.avg_speed_history) > 300:
            self.avg_speed_history = self.avg_speed_history[-300:]

    def update_throughput_window(self, dt):
        if self.window_timer >= 8.0:
            self.throughput_last_window = self.throughput_window_counter / self.window_timer
            self.throughput_history.append(self.throughput_last_window)
            if len(self.throughput_history) > 300:
                self.throughput_history = self.throughput_history[-300:]
            self.window_timer = 0.0
            self.throughput_window_counter = 0

    def capture_algorithm_comparison(self):
        current_algorithm = self.traffic_controller.algorithm
        if self.last_algorithm != current_algorithm:
            self.last_algorithm = current_algorithm

        self.algorithm_comparison = self.traffic_controller.get_algorithm_metrics()

    def set_traffic_density_factor(self, value):
        self.traffic_density_factor = max(0.2, min(2.5, value))

    def set_simulation_speed_factor(self, value):
        self.simulation_speed_factor = max(0.2, min(4.0, value))

    def set_rush_hour_mode(self, enabled):
        self.rush_hour_mode = bool(enabled)

    def set_weather_mode(self, mode):
        if mode in ["clear", "rain", "fog", "snow"]:
            self.weather_mode = mode

    def add_obstacle(self, position, radius=6.0):
        self.obstacles.append({
            "position": position,
            "radius": max(2.0, radius),
            "kind": "obstacle",
            "created_at": self.elapsed_time
        })

    def clear_obstacles(self):
        self.obstacles = []

    def remove_nearest_obstacle(self, world_position, threshold=10.0):
        if not self.obstacles:
            return False

        best_index = None
        best_distance = float("inf")
        for idx, obstacle in enumerate(self.obstacles):
            ox, oy = obstacle.get("position", (0, 0))
            distance = math.hypot(world_position[0] - ox, world_position[1] - oy)
            if distance < best_distance:
                best_distance = distance
                best_index = idx

        if best_index is not None and best_distance <= threshold:
            self.obstacles.pop(best_index)
            return True
        return False

    def update_random_events(self, dt):
        if not self.random_events_enabled:
            return

        if self.elapsed_time - self.last_event_time < 20.0:
            return

        if random.random() < 0.05:
            self.last_event_time = self.elapsed_time
            event_type = random.choice(["accident", "road_closure", "weather_shift"])
            if event_type in ["accident", "road_closure"]:
                event_pos = (
                    self.intersection.center[0] + random.uniform(-20, 20),
                    self.intersection.center[1] + random.uniform(-20, 20)
                )
                radius = 7.0 if event_type == "accident" else 10.0
                self.add_obstacle(event_pos, radius)
            else:
                self.weather_mode = random.choice(["rain", "fog", "snow", "clear"])
            self.active_events.append({
                "type": event_type,
                "time": self.elapsed_time
            })

        self.active_events = [e for e in self.active_events if self.elapsed_time - e["time"] < 60.0]

    def get_dashboard_metrics(self):
        ctrl = self.traffic_controller
        phase_name = ctrl.phase_sequence[ctrl.phase_index] if ctrl.phase_sequence else "unknown"
        phase_remaining = max(0.0, ctrl._get_phase_duration(phase_name) - ctrl.phase_timer)
        return {
            "avg_wait": self.compute_avg_wait_time(),
            "throughput": self.throughput_last_window,
            "queue_lengths": self.compute_queue_lengths(),
            "vehicles_total": len(self.vehicles),
            "exited_total": self.exited_vehicles,
            "weather": self.weather_mode,
            "rush_hour": self.rush_hour_mode,
            "pedestrians": len(self.pedestrians),
            "close_calls": self.close_proximity_count,
            "avg_speed": self.avg_speed_history[-1] if self.avg_speed_history else 0.0,
            "vehicle_mix": self.get_vehicle_mix(),
            "pedestrian_signals": {k: v.state for k, v in self.pedestrian_signals.items()},
            "current_phase": phase_name,
            "phase_remaining": phase_remaining,
            "safety_violations": self.safety_violation_count,
            "recording": self.recording,
            "paused": self.paused,
            "playback_active": self.playback_active,
            "playback_total": len(self.playback_frames),
            "playback_index": self.playback_index,
        }

    def get_vehicle_mix(self):
        mix = {t.name: 0 for t in VehicleType}
        for vehicle in self.vehicles:
            mix[vehicle.vehicle_type.name] = mix.get(vehicle.vehicle_type.name, 0) + 1
        return mix

    def export_results(self, file_path):
        payload = {
            "timestamp": time.time(),
            "metrics": self.get_dashboard_metrics(),
            "wait_history": self.wait_time_history,
            "throughput_history": self.throughput_history,
            "algorithm_comparison": self.algorithm_comparison,
            "congestion_heatmap": [{"cell": [k[0], k[1]], "intensity": v} for k, v in self.congestion_heatmap.items()],
            "active_events": self.active_events,
            "v2i_message_count": len(self.v2i_messages)
        }
        with open(file_path, "w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, indent=2)

    def save_scenario(self, file_path):
        scenario = {
            "traffic_density_factor": self.traffic_density_factor,
            "simulation_speed_factor": self.simulation_speed_factor,
            "rush_hour_mode": self.rush_hour_mode,
            "weather_mode": self.weather_mode,
            "obstacles": self.obstacles,
            "algorithm": self.traffic_controller.algorithm,
            "manual_override_active": self.traffic_controller.manual_override is not None
        }
        with open(file_path, "w", encoding="utf-8") as scenario_file:
            json.dump(scenario, scenario_file, indent=2)

    def load_scenario(self, file_path):
        with open(file_path, "r", encoding="utf-8") as scenario_file:
            scenario = json.load(scenario_file)

        self.traffic_density_factor = scenario.get("traffic_density_factor", 1.0)
        self.simulation_speed_factor = scenario.get("simulation_speed_factor", 1.0)
        self.rush_hour_mode = scenario.get("rush_hour_mode", False)
        self.weather_mode = scenario.get("weather_mode", "clear")
        self.obstacles = scenario.get("obstacles", [])
        self.traffic_controller.set_algorithm(scenario.get("algorithm", "time_based"))

    def apply_preconfigured_scenario(self, name):
        presets = {
            "normal_day": {"traffic_density_factor": 1.0, "rush_hour_mode": False, "weather_mode": "clear"},
            "rush_hour": {"traffic_density_factor": 1.8, "rush_hour_mode": True, "weather_mode": "clear"},
            "special_event": {"traffic_density_factor": 2.2, "rush_hour_mode": True, "weather_mode": "rain"}
        }
        preset = presets.get(name)
        if not preset:
            return
        self.traffic_density_factor = preset["traffic_density_factor"]
        self.rush_hour_mode = preset["rush_hour_mode"]
        self.weather_mode = preset["weather_mode"]


def math_sin_wave(value, period):
    import math
    return math.sin((value / max(period, 1e-3)) * 2 * math.pi)