# src/controllers/traffic_light_controller.py
from collections import defaultdict
import logging

from simulation.traffic_light import LightState


LOGGER = logging.getLogger(__name__)


class TrafficLightController:
    """
    Controls the traffic lights at the intersection.
    Implements different control algorithms and ensures safety.
    """

    def __init__(self, safety_checker):
        self.safety_checker = safety_checker
        self.traffic_lights = {}
        self.elapsed_time = 0
        self.default_phase_durations = {
            "ns_green": 24.0,
            "ns_yellow": 4.0,
            "all_red": 2.0,
            "ew_green": 24.0,
            "ew_yellow": 4.0,
        }
        self.current_phase_durations = self.default_phase_durations.copy()
        self.phase_sequence = [
            "ns_green",
            "ns_yellow",
            "all_red_1",
            "ew_green",
            "ew_yellow",
            "all_red_2",
        ]
        self.phase_index = 0
        self.phase_timer = 0.0
        self.cycle_time = 60.0

        # Default to simple fixed-time signal control.
        self.algorithm = "time_based"
        self.available_algorithms = [
            "time_based",
            "traffic_responsive",
            "adaptive",
            "ml_optimized",
            "coordinated",
            "emergency",
        ]
        self.manual_override = None

        # Environment and strategy settings
        self.weather_mode = "clear"
        self.rush_hour_mode = False

        # Lightweight online-learning model (bandit-like)
        self.ml_candidate_greens = [18.0, 22.0, 26.0, 30.0]
        self.ml_scores = {duration: 0.0 for duration in self.ml_candidate_greens}
        self.ml_counts = {duration: 1 for duration in self.ml_candidate_greens}
        self.ml_last_duration = 24.0

        # Adaptive learning memory
        self.adaptive_memory = {"ns": 1.0, "ew": 1.0}
        self.adaptive_bias = {"ns": 0.0, "ew": 0.0}

        # Comparative metrics
        self.algorithm_metrics = defaultdict(
            lambda: {"cycles": 0, "avg_queue": 0.0, "avg_delay": 0.0, "throughput": 0.0}
        )

    def register_traffic_light(self, traffic_light):
        """
        Register a traffic light with the controller.

        Args:
            traffic_light: The traffic light to register
        """
        self.traffic_lights[traffic_light.direction] = traffic_light

    def update(self, dt, context=None):
        """
        Update all traffic lights based on the current algorithm.

        Args:
            dt: Delta time in seconds
            context: Optional context dictionary from simulation manager
        """
        self.elapsed_time += dt

        context = context or {}
        self.weather_mode = context.get("weather", self.weather_mode)
        self.rush_hour_mode = context.get("rush_hour", self.rush_hour_mode)

        # Highest-priority preemption
        priority = context.get("priority_request")
        if priority in ["north", "south", "east", "west"]:
            self.apply_priority_request(priority)
            return

        # Manual override pin
        if self.manual_override is not None:
            self.set_light_states(self.manual_override)
            return

        if self.algorithm == "time_based":
            self.update_time_based(dt, context)
        elif self.algorithm == "traffic_responsive":
            self.update_traffic_responsive(dt, context)
        elif self.algorithm == "adaptive":
            self.update_adaptive(dt, context)
        elif self.algorithm == "ml_optimized":
            self.update_ml_optimized(dt, context)
        elif self.algorithm == "coordinated":
            self.update_coordinated(dt, context)
        elif self.algorithm == "emergency":
            self.update_emergency(dt, context)

        self._update_algorithm_metrics(context)

    def _get_phase_duration(self, phase_name):
        weather_factor = {"clear": 1.0, "rain": 1.12, "fog": 1.15, "snow": 1.2}.get(
            self.weather_mode, 1.0
        )

        rush_factor = 0.93 if self.rush_hour_mode else 1.0

        if phase_name in ["all_red_1", "all_red_2"]:
            base = self.current_phase_durations["all_red"]
            return base * weather_factor

        base = self.current_phase_durations.get(phase_name, 4.0)
        return base * weather_factor * rush_factor

    def _phase_to_states(self, phase_name):
        if phase_name == "ns_green":
            return {
                "north": LightState.GREEN,
                "south": LightState.GREEN,
                "east": LightState.RED,
                "west": LightState.RED,
            }
        if phase_name == "ns_yellow":
            return {
                "north": LightState.YELLOW,
                "south": LightState.YELLOW,
                "east": LightState.RED,
                "west": LightState.RED,
            }
        if phase_name == "ew_green":
            return {
                "north": LightState.RED,
                "south": LightState.RED,
                "east": LightState.GREEN,
                "west": LightState.GREEN,
            }
        if phase_name == "ew_yellow":
            return {
                "north": LightState.RED,
                "south": LightState.RED,
                "east": LightState.YELLOW,
                "west": LightState.YELLOW,
            }
        return {
            "north": LightState.RED,
            "south": LightState.RED,
            "east": LightState.RED,
            "west": LightState.RED,
        }

    def _advance_phase_machine(self, dt):
        self.phase_timer += dt
        phase_name = self.phase_sequence[self.phase_index]
        phase_duration = self._get_phase_duration(phase_name)
        if self.phase_timer >= phase_duration:
            self.phase_timer = 0.0
            self.phase_index = (self.phase_index + 1) % len(self.phase_sequence)
            phase_name = self.phase_sequence[self.phase_index]
        self.set_light_states(self._phase_to_states(phase_name))
        self.cycle_time = (
            self._get_phase_duration("ns_green")
            + self._get_phase_duration("ns_yellow")
            + self._get_phase_duration("all_red_1")
            + self._get_phase_duration("ew_green")
            + self._get_phase_duration("ew_yellow")
            + self._get_phase_duration("all_red_2")
        )
        if self.phase_index == 0 and self.phase_timer < dt:
            self.algorithm_metrics[self.algorithm]["cycles"] += 1

    def update_time_based(self, dt, context=None):
        """
        Update traffic lights using a time-based algorithm.

        Args:
            dt: Delta time in seconds
        """
        self.current_phase_durations = self.default_phase_durations.copy()
        self._advance_phase_machine(dt)

    def update_traffic_responsive(self, dt, context=None):
        """
        Update traffic lights using a traffic-responsive algorithm.
        This would use data from traffic sensors to optimize light timing.

        Args:
            dt: Delta time in seconds
        """
        context = context or {}
        queue_lengths = context.get("queue_lengths", {"ns": 0, "ew": 0})
        ns_queue = queue_lengths.get("ns", 0)
        ew_queue = queue_lengths.get("ew", 0)

        self.current_phase_durations = self.default_phase_durations.copy()
        total = max(1, ns_queue + ew_queue)
        ns_ratio = ns_queue / total
        ew_ratio = ew_queue / total

        self.current_phase_durations["ns_green"] = 18.0 + 14.0 * ns_ratio
        self.current_phase_durations["ew_green"] = 18.0 + 14.0 * ew_ratio
        self._advance_phase_machine(dt)

    def update_adaptive(self, dt, context=None):
        """Adaptive timing using queue and weighted priority signals."""
        context = context or {}
        queue_lengths = context.get("queue_lengths", {"ns": 0, "ew": 0})
        queue_weighted = context.get("queue_weighted", queue_lengths)
        ns_score = float(queue_weighted.get("ns", 0))
        ew_score = float(queue_weighted.get("ew", 0))

        learning_rate = 0.035
        self.adaptive_memory["ns"] = (1 - learning_rate) * self.adaptive_memory[
            "ns"
        ] + learning_rate * ns_score
        self.adaptive_memory["ew"] = (1 - learning_rate) * self.adaptive_memory[
            "ew"
        ] + learning_rate * ew_score

        imbalance = self.adaptive_memory["ns"] - self.adaptive_memory["ew"]
        self.adaptive_bias["ns"] = max(-4.0, min(4.0, 0.55 * imbalance))
        self.adaptive_bias["ew"] = -self.adaptive_bias["ns"]

        ns_score += self.adaptive_bias["ns"]
        ew_score += self.adaptive_bias["ew"]
        total = max(1, ns_score + ew_score)

        self.current_phase_durations = self.default_phase_durations.copy()
        self.current_phase_durations["ns_green"] = max(
            14.0, min(34.0, 16.0 + 18.0 * (ns_score / total))
        )
        self.current_phase_durations["ew_green"] = max(
            14.0, min(34.0, 16.0 + 18.0 * (ew_score / total))
        )
        self._advance_phase_machine(dt)

    def get_pedestrian_walk_states(self):
        """Return pedestrian walk permissions for each crossing axis."""
        north = self.traffic_lights.get("north")
        south = self.traffic_lights.get("south")
        east = self.traffic_lights.get("east")
        west = self.traffic_lights.get("west")

        if not all([north, south, east, west]):
            return {"ns_cross": False, "ew_cross": False}

        ns_restrictive = north.state in [LightState.RED] and south.state in [
            LightState.RED
        ]
        ew_restrictive = east.state in [LightState.RED] and west.state in [
            LightState.RED
        ]
        return {"ns_cross": ns_restrictive, "ew_cross": ew_restrictive}

    def update_ml_optimized(self, dt, context=None):
        """Bandit-style green split optimization using observed delay/throughput reward."""
        context = context or {}
        if self.phase_index == 0 and self.phase_timer < dt:
            # Evaluate previous choice reward
            avg_delay = context.get("avg_wait_time", 0.0)
            throughput = context.get("throughput_last_window", 0.0)
            reward = throughput - 0.4 * avg_delay
            d = self.ml_last_duration
            self.ml_counts[d] += 1
            alpha = 1.0 / self.ml_counts[d]
            self.ml_scores[d] = (1 - alpha) * self.ml_scores[d] + alpha * reward

            # UCB-like choice
            exploration = max(1.0, sum(self.ml_counts.values()))
            best_duration = self.ml_candidate_greens[0]
            best_value = float("-inf")
            for candidate in self.ml_candidate_greens:
                bonus = (2.0 * (exploration**0.5)) / (
                    self.ml_counts[candidate] ** 0.5
                )
                value = self.ml_scores[candidate] + bonus
                if value > best_value:
                    best_value = value
                    best_duration = candidate
            self.ml_last_duration = best_duration

        self.current_phase_durations = self.default_phase_durations.copy()
        self.current_phase_durations["ns_green"] = self.ml_last_duration
        self.current_phase_durations["ew_green"] = max(
            16.0, 48.0 - self.ml_last_duration
        )
        self._advance_phase_machine(dt)

    def update_coordinated(self, dt, context=None):
        """Simple green-wave coordination with a virtual neighboring intersection offset."""
        context = context or {}
        phase_offset = context.get("coordination_offset", 5.0)
        self.current_phase_durations = self.default_phase_durations.copy()
        if int((self.elapsed_time + phase_offset) // 20) % 2 == 0:
            self.current_phase_durations["ns_green"] = 28.0
            self.current_phase_durations["ew_green"] = 20.0
        else:
            self.current_phase_durations["ns_green"] = 20.0
            self.current_phase_durations["ew_green"] = 28.0
        self._advance_phase_machine(dt)

    def update_emergency(self, dt, context=None):
        """
        Update traffic lights for emergency mode (all flashing yellow).

        Args:
            dt: Delta time in seconds
        """
        # In emergency mode, all lights flash yellow
        flash_period = 1.0  # 1 second flash period
        flash_state = int(self.elapsed_time / flash_period) % 2

        state = LightState.YELLOW if flash_state == 0 else LightState.RED

        for direction in self.traffic_lights:
            self.traffic_lights[direction].state = state

    def apply_priority_request(self, direction):
        """Grant immediate green to axis of emergency/public transport priority request."""
        if direction in ["north", "south"]:
            self.set_light_states(
                {
                    "north": LightState.GREEN,
                    "south": LightState.GREEN,
                    "east": LightState.RED,
                    "west": LightState.RED,
                }
            )
        else:
            self.set_light_states(
                {
                    "north": LightState.RED,
                    "south": LightState.RED,
                    "east": LightState.GREEN,
                    "west": LightState.GREEN,
                }
            )

    def set_manual_override(self, direction=None, state=None):
        """Manually pin a light state for user override; pass None to clear override."""
        if direction is None or state is None:
            self.manual_override = None
            return

        if direction in ["north", "south"]:
            ns_state = state
            ew_state = LightState.RED if state != LightState.RED else LightState.GREEN
            self.manual_override = {
                "north": ns_state,
                "south": ns_state,
                "east": ew_state,
                "west": ew_state,
            }
        elif direction in ["east", "west"]:
            ew_state = state
            ns_state = LightState.RED if state != LightState.RED else LightState.GREEN
            self.manual_override = {
                "north": ns_state,
                "south": ns_state,
                "east": ew_state,
                "west": ew_state,
            }

    def _update_algorithm_metrics(self, context):
        queue_lengths = context.get("queue_lengths", {"ns": 0, "ew": 0})
        avg_wait_time = context.get("avg_wait_time", 0.0)
        throughput = context.get("throughput_last_window", 0.0)

        queue_avg = 0.5 * (queue_lengths.get("ns", 0) + queue_lengths.get("ew", 0))
        metrics = self.algorithm_metrics[self.algorithm]
        alpha = 0.02
        metrics["avg_queue"] = (1 - alpha) * metrics["avg_queue"] + alpha * queue_avg
        metrics["avg_delay"] = (1 - alpha) * metrics[
            "avg_delay"
        ] + alpha * avg_wait_time
        metrics["throughput"] = (1 - alpha) * metrics["throughput"] + alpha * throughput

    def get_algorithm_metrics(self):
        return dict(self.algorithm_metrics)

    def set_light_states(self, states):
        """
        Set the states of traffic lights, checking safety first.

        Args:
            states: Dictionary mapping directions to light states
        """
        # Check if the requested states are safe
        if self.safety_checker.check_states(states):
            # Apply the states
            for direction, state in states.items():
                if direction in self.traffic_lights:
                    self.traffic_lights[direction].state = state
        else:
            # If not safe, switch to emergency mode and track violation
            self.safety_violation_count = getattr(self, "safety_violation_count", 0) + 1
            self.algorithm = "emergency"
            LOGGER.error("Safety violation detected; switching to emergency mode")

    def set_algorithm(self, algorithm):
        """
        Set the control algorithm to use.

        Args:
            algorithm: Name of the algorithm to use
        """
        if algorithm in self.available_algorithms:
            self.algorithm = algorithm
            self.elapsed_time = 0
            self.phase_timer = 0.0
            self.phase_index = 0
            LOGGER.info("Switched control algorithm", extra={"algorithm": algorithm})
        else:
            LOGGER.warning(
                "Unknown algorithm requested", extra={"algorithm": algorithm}
            )

    def set_phase_durations(
        self, ns_green=None, ew_green=None, ns_yellow=None, ew_yellow=None, all_red=None
    ):
        """Update default phase durations used by fixed and adaptive controllers."""
        updates = {
            "ns_green": ns_green,
            "ew_green": ew_green,
            "ns_yellow": ns_yellow,
            "ew_yellow": ew_yellow,
            "all_red": all_red,
        }
        for key, value in updates.items():
            if value is None:
                continue
            if key in ["ns_green", "ew_green"]:
                self.default_phase_durations[key] = max(10.0, min(60.0, float(value)))
            elif key in ["ns_yellow", "ew_yellow"]:
                self.default_phase_durations[key] = max(2.0, min(8.0, float(value)))
            elif key == "all_red":
                self.default_phase_durations[key] = max(1.0, min(6.0, float(value)))

        self.current_phase_durations = self.default_phase_durations.copy()
