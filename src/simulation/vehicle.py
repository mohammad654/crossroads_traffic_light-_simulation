import math
import random
import pygame
from enum import Enum, auto

from simulation.traffic_light import LightState


class VehicleType(Enum):
    """Legacy enum retained for compatibility with existing controls/stats."""

    CAR = auto()
    TRUCK = auto()
    MOTORCYCLE = auto()
    BUS = auto()
    EMERGENCY = auto()


class Vehicle:
    """Multi-type vehicle model with realistic physics and lane-stable movement."""

    # Per-type body colour palettes  (R, G, B)
    _PALETTES = {
        VehicleType.CAR: [
            (195, 60, 55),  # red
            (55, 120, 200),  # blue
            (60, 155, 75),  # green
            (230, 180, 40),  # yellow
            (130, 50, 180),  # purple
            (245, 115, 40),  # orange
            (220, 220, 225),  # silver
            (28, 30, 35),  # black
            (235, 235, 235),  # white
        ],
        VehicleType.TRUCK: [
            (195, 140, 60),  # sand
            (80, 90, 100),  # dark steel
            (190, 80, 60),  # brick red
            (60, 80, 60),  # army green
        ],
        VehicleType.BUS: [
            (240, 200, 40),  # yellow school
            (55, 130, 200),  # city blue
            (230, 80, 55),  # red bus
        ],
        VehicleType.MOTORCYCLE: [
            (28, 30, 35),  # black
            (195, 50, 50),  # sport red
            (60, 100, 180),  # sport blue
            (220, 220, 220),  # silver
        ],
        VehicleType.EMERGENCY: [
            (230, 40, 40),  # fire red
            (45, 100, 205),  # police blue
        ],
    }

    def __init__(
        self, vehicle_type, position, direction, target_direction, lane_index=0
    ):
        self.vehicle_type = vehicle_type
        self.position = position
        self.direction = direction
        self.target_direction = target_direction
        self.lane_index = lane_index
        self.exit_lane_index = 0

        self.setup_vehicle_properties()

        self.velocity = 0.0
        self.acceleration = 0.0
        self.rotation = self.get_initial_rotation()
        self.waiting_for_light = False
        self.wait_time = 0.0
        self.v2i_message = {}
        self.too_close = False

        self.turning = False
        self.turn_started = False
        self.path = []
        self.turn_progress = 0.0
        self.turn_distance = 0.0
        self.turn_length = 1.0

        self.desired_speed = 0.0
        self.speed_settle_rate = random.uniform(2.1, 2.8)
        self.driver_headway = random.uniform(1.05, 1.35)
        self.driver_reaction = random.uniform(0.45, 0.72)
        self.max_jerk = random.uniform(3.8, 5.1)
        self.behavior_phase = random.uniform(0.0, math.pi * 2.0)
        self.behavior_timer = random.uniform(0.0, 5.0)

        self.min_stopped_gap = 2.0
        self.min_moving_gap = 2.0 * self.length
        self.brake_lights_on = False
        self.last_light_state = None
        self.green_reaction_delay = random.uniform(0.5, 1.0)
        self.green_hold_timer = 0.0

    def setup_vehicle_properties(self):
        """Assign realistic size, speed, and dynamics per vehicle type."""
        vt = self.vehicle_type

        if vt == VehicleType.CAR:
            self.length = random.uniform(4.0, 4.9)
            self.width = random.uniform(1.75, 2.0)
            max_speed_kmh = random.uniform(45.0, 65.0)
            self.max_acceleration = random.uniform(2.5, 3.5)
            self.comfortable_deceleration = random.uniform(3.0, 4.2)
            self.max_deceleration = random.uniform(6.0, 8.0)

        elif vt == VehicleType.TRUCK:
            self.length = random.uniform(8.5, 13.0)
            self.width = random.uniform(2.4, 2.65)
            max_speed_kmh = random.uniform(35.0, 55.0)
            self.max_acceleration = random.uniform(0.9, 1.5)
            self.comfortable_deceleration = random.uniform(2.2, 3.0)
            self.max_deceleration = random.uniform(4.5, 6.0)

        elif vt == VehicleType.BUS:
            self.length = random.uniform(10.5, 14.0)
            self.width = random.uniform(2.5, 2.8)
            max_speed_kmh = random.uniform(30.0, 50.0)
            self.max_acceleration = random.uniform(0.8, 1.3)
            self.comfortable_deceleration = random.uniform(2.0, 2.8)
            self.max_deceleration = random.uniform(4.0, 5.5)

        elif vt == VehicleType.MOTORCYCLE:
            self.length = random.uniform(1.9, 2.4)
            self.width = random.uniform(0.75, 0.95)
            max_speed_kmh = random.uniform(50.0, 80.0)
            self.max_acceleration = random.uniform(3.5, 5.0)
            self.comfortable_deceleration = random.uniform(4.0, 5.5)
            self.max_deceleration = random.uniform(7.0, 9.5)

        elif vt == VehicleType.EMERGENCY:
            self.length = random.uniform(5.0, 6.5)
            self.width = random.uniform(2.0, 2.3)
            max_speed_kmh = random.uniform(70.0, 100.0)
            self.max_acceleration = random.uniform(4.0, 5.5)
            self.comfortable_deceleration = random.uniform(4.5, 6.0)
            self.max_deceleration = random.uniform(8.0, 10.0)

        else:  # fallback
            self.length = 4.5
            self.width = 1.9
            max_speed_kmh = 50.0
            self.max_acceleration = 2.8
            self.comfortable_deceleration = 3.5
            self.max_deceleration = 7.0

        self.max_speed = max_speed_kmh / 3.6
        self.cruise_speed = self.max_speed * random.uniform(0.82, 0.95)

        palette = self._PALETTES.get(vt, self._PALETTES[VehicleType.CAR])
        base = random.choice(palette)
        tint = random.randint(-10, 10)
        self.color = tuple(max(20, min(240, c + tint)) for c in base)

    def get_initial_rotation(self):
        return {
            "north": 0.0,
            "east": 90.0,
            "south": 180.0,
            "west": 270.0,
        }.get(self.direction, 0.0)

    def heading_vector(self):
        angle = math.radians(self.rotation)
        return math.sin(angle), -math.cos(angle)

    def update(
        self,
        dt,
        light_state,
        other_vehicles,
        intersection,
        weather="clear",
        obstacles=None,
        pedestrian_blocks=None,
    ):
        obstacles = obstacles or []
        pedestrian_blocks = pedestrian_blocks or []
        self.too_close = False
        self.behavior_timer += dt

        # Add realistic restart delay after red/yellow phases.
        if self.last_light_state is None:
            self.last_light_state = light_state
        if self.last_light_state != light_state:
            if (
                light_state == LightState.GREEN
                and self.velocity < 0.2
                and 0.0
                <= intersection.distance_to_stop_line(self.direction, self.position)
                <= 12.0
            ):
                self.green_hold_timer = self.green_reaction_delay
            self.last_light_state = light_state
        if self.green_hold_timer > 0.0:
            self.green_hold_timer = max(0.0, self.green_hold_timer - dt)

        weather_speed_factor = {
            "clear": 1.0,
            "rain": 0.88,
            "fog": 0.82,
            "snow": 0.74,
        }.get(weather, 1.0)

        # Lightly vary cruise speed over time to avoid robotic lockstep traffic.
        behavior_mod = 1.0 + 0.045 * math.sin(
            self.behavior_timer * 0.45 + self.behavior_phase
        )
        free_flow_target = self.cruise_speed * weather_speed_factor * behavior_mod

        signal_target = self.signal_target_speed(light_state, intersection)
        lead_target = self.lead_vehicle_target_speed(other_vehicles)
        block_target = self.blocked_box_target_speed(other_vehicles, intersection)
        conflict_target = self.intersection_conflict_target_speed(
            other_vehicles, intersection
        )
        obstacle_target = self.obstacle_target_speed(obstacles)
        crosswalk_target = self.crosswalk_target_speed(pedestrian_blocks)

        target_speed = min(
            free_flow_target,
            signal_target,
            lead_target,
            block_target,
            conflict_target,
            obstacle_target,
            crosswalk_target,
        )
        if self.turning:
            target_speed = min(target_speed, self.cruise_speed * 0.62)

        # First-order speed filter + jerk-limited acceleration for smoother longitudinal motion.
        settle = min(1.0, dt * self.speed_settle_rate)
        self.desired_speed += (target_speed - self.desired_speed) * settle
        desired_acc = (self.desired_speed - self.velocity) / max(
            self.driver_reaction, 1e-3
        )
        desired_acc = max(
            -self.max_deceleration, min(self.max_acceleration, desired_acc)
        )

        accel_delta = desired_acc - self.acceleration
        max_accel_delta = self.max_jerk * dt
        accel_delta = max(-max_accel_delta, min(max_accel_delta, accel_delta))
        self.acceleration += accel_delta
        self.acceleration = max(
            -self.max_deceleration, min(self.max_acceleration, self.acceleration)
        )

        self.velocity += self.acceleration * dt
        self.velocity = max(0.0, min(self.velocity, self.max_speed))
        self.brake_lights_on = self.acceleration < -0.45

        if self.waiting_for_light and self.velocity < 0.15:
            self.wait_time += dt

        if self.turning:
            self.update_turning(dt, intersection)
        else:
            hx, hy = self.heading_vector()
            self.position = (
                self.position[0] + hx * self.velocity * dt,
                self.position[1] + hy * self.velocity * dt,
            )
            self.enforce_stop_line(light_state, intersection)
            self.apply_lane_alignment(intersection, dt)

            if self.target_direction != self.direction and self.should_start_turn(
                intersection
            ):
                self.start_turning(intersection)

        self.v2i_message = {
            "vehicle_type": self.vehicle_type.name,
            "direction": self.direction,
            "eta_to_stop_line": self.estimate_eta_to_stop_line(intersection),
            "speed": self.velocity,
        }

    def should_start_turn(self, intersection):
        if self.turn_started or self.turning:
            return False
        if not self.is_inside_intersection(intersection):
            return False
        distance_to_line = intersection.distance_to_stop_line(
            self.direction, self.position
        )
        return distance_to_line <= -0.7

    def apply_lane_alignment(self, intersection, dt):
        if self.turning:
            return

        lane_positions = (
            intersection.exit_lanes.get(self.direction)
            if self.turn_started
            else intersection.entry_lanes.get(self.direction)
        )
        if not lane_positions:
            return

        lane_count = len(lane_positions)
        lane_index = self.exit_lane_index if self.turn_started else self.lane_index
        lane_index = max(0, min(max(0, lane_count - 1), lane_index))
        lane_center = lane_positions[lane_index]

        blend = min(1.0, dt * 10.0)
        if self.direction in ["north", "south"]:
            x = self.position[0] + (lane_center[0] - self.position[0]) * blend
            self.position = (x, self.position[1])
        else:
            y = self.position[1] + (lane_center[1] - self.position[1]) * blend
            self.position = (self.position[0], y)

    def enforce_stop_line(self, light_state, intersection):
        if self.turning:
            return
        if light_state not in [LightState.RED, LightState.YELLOW]:
            return

        stop_x, stop_y = intersection.get_stop_line_position(self.direction)
        stop_buffer = 0.25
        front_offset = self.length * 0.5
        x, y = self.position

        if self.direction == "north":
            min_center_y = stop_y + front_offset + stop_buffer
            if y < min_center_y:
                self.position = (x, min_center_y)
                self.velocity = 0.0
        elif self.direction == "south":
            max_center_y = stop_y - front_offset - stop_buffer
            if y > max_center_y:
                self.position = (x, max_center_y)
                self.velocity = 0.0
        elif self.direction == "east":
            max_center_x = stop_x - front_offset - stop_buffer
            if x > max_center_x:
                self.position = (max_center_x, y)
                self.velocity = 0.0
        elif self.direction == "west":
            min_center_x = stop_x + front_offset + stop_buffer
            if x < min_center_x:
                self.position = (min_center_x, y)
                self.velocity = 0.0

    def is_approaching_intersection(self, intersection):
        center = intersection.center
        distance = math.hypot(
            self.position[0] - center[0], self.position[1] - center[1]
        )
        return distance < 50.0 and not self.turning

    def is_inside_intersection(self, intersection):
        half_width = intersection.width / 2
        half_height = intersection.height / 2
        cx, cy = intersection.center
        x, y = self.position
        return (cx - half_width <= x <= cx + half_width) and (
            cy - half_height <= y <= cy + half_height
        )

    def react_to_traffic_light(self, light_state, intersection):
        return self.signal_target_speed(light_state, intersection) < 0.2

    def signal_target_speed(self, light_state, intersection):
        distance_to_line = intersection.distance_to_stop_line(
            self.direction, self.position
        )

        # Already past the stop line → always proceed at full speed.
        if distance_to_line < -0.45:
            self.waiting_for_light = False
            return self.max_speed

        if light_state == LightState.GREEN:
            # Honour the initial green-reaction delay (driver looks up, decides to go).
            if self.green_hold_timer > 0.0 and distance_to_line <= 12.0:
                self.waiting_for_light = True
                return 0.0
            self.waiting_for_light = False
            return self.max_speed

        # --- RED or YELLOW ---
        # Commit-or-stop decision for YELLOW:
        #   If the vehicle can come to a comfortable stop before the line → stop.
        #   If already too close to stop safely → proceed (run the yellow).
        stopping_distance = (self.velocity**2) / max(
            2.0 * self.comfortable_deceleration, 1e-3
        )
        commit_threshold = stopping_distance + max(2.5, self.velocity * 0.5)

        if light_state == LightState.YELLOW:
            if distance_to_line < commit_threshold:
                # Too close to stop safely — commit and proceed through.
                self.waiting_for_light = False
                return self.max_speed

        # Build a smooth deceleration profile so vehicles glide to a stop
        # exactly at the stop line rather than jamming on brakes.
        caution_start = max(14.0, commit_threshold + 8.0)

        if distance_to_line > caution_start:
            # Far away — keep driving normally, will re-evaluate next tick.
            self.waiting_for_light = False
            return self.max_speed

        if distance_to_line <= 0.5:
            # Right at the line — full stop.
            self.waiting_for_light = True
            return 0.0

        # Graduated braking: smooth power curve for natural deceleration feel.
        normalized = max(
            0.0, min(1.0, (distance_to_line - 0.2) / max(caution_start, 1e-3))
        )
        self.waiting_for_light = True
        return self.max_speed * (normalized**1.6)

    def estimate_eta_to_stop_line(self, intersection):
        distance = max(
            0.0, intersection.distance_to_stop_line(self.direction, self.position)
        )
        speed = max(0.5, self.velocity)
        return distance / speed

    def center_gap_to(self, other):
        return 0.5 * self.length + 0.5 * other.length + self.min_stopped_gap

    def moving_center_gap_to(self, other):
        moving_buffer = max(self.min_moving_gap, 2.0 * other.length)
        return 0.5 * self.length + 0.5 * other.length + moving_buffer

    def lead_vehicle_target_speed(self, other_vehicles):
        lane_tolerance = 0.9
        best_speed = self.max_speed

        for other in other_vehicles:
            if other is self:
                continue
            if other.direction != self.direction:
                continue

            if self.direction in ["north", "south"]:
                lateral_offset = abs(self.position[0] - other.position[0])
            else:
                lateral_offset = abs(self.position[1] - other.position[1])
            if lateral_offset > lane_tolerance:
                continue

            gap = self.longitudinal_progress(
                other.position
            ) - self.longitudinal_progress(self.position)
            if gap <= 0.0:
                continue

            min_gap = self.center_gap_to(other)
            moving_gap = self.moving_center_gap_to(other)
            dynamic_gap = moving_gap + max(0.0, self.velocity * self.driver_headway)

            if gap <= min_gap:
                return 0.0

            if gap < dynamic_gap:
                ratio = (gap - min_gap) / max(dynamic_gap - min_gap, 1e-3)
                constrained = other.velocity * max(0.0, min(1.0, ratio**1.5))
                best_speed = min(best_speed, constrained)

        return best_speed

    def blocked_box_target_speed(self, other_vehicles, intersection):
        distance_to_line = intersection.distance_to_stop_line(
            self.direction, self.position
        )
        if not (0.0 <= distance_to_line <= 7.5):
            return self.max_speed

        lane_tolerance = 0.95
        lookahead = 20.0

        for other in other_vehicles:
            if other is self:
                continue
            if other.direction != self.direction:
                continue

            if self.direction in ["north", "south"]:
                lateral_offset = abs(self.position[0] - other.position[0])
            else:
                lateral_offset = abs(self.position[1] - other.position[1])

            if lateral_offset > lane_tolerance:
                continue

            gap = self.longitudinal_progress(
                other.position
            ) - self.longitudinal_progress(self.position)
            if not (0.0 < gap < lookahead):
                continue

            if other.velocity < 1.0 and (
                other.is_inside_intersection(intersection)
                or intersection.distance_to_stop_line(other.direction, other.position)
                < -1.0
            ):
                return 0.0

        return self.max_speed

    def intersection_conflict_target_speed(self, other_vehicles, intersection):
        best_speed = self.max_speed
        center_x, center_y = intersection.center
        own_distance_to_line = intersection.distance_to_stop_line(
            self.direction, self.position
        )
        own_axis = "ns" if self.direction in ["north", "south"] else "ew"
        turning_now = self.target_direction != self.direction
        left_turning_now = self.is_left_turn(self.direction, self.target_direction)

        for other in other_vehicles:
            if other is self:
                continue

            distance = math.hypot(
                other.position[0] - self.position[0],
                other.position[1] - self.position[1],
            )
            safety_radius = max(3.8, 0.5 * (self.length + other.length))

            if self.is_inside_intersection(
                intersection
            ) and other.is_inside_intersection(intersection):
                if distance < safety_radius:
                    return 0.0
                if distance < safety_radius * 1.75:
                    best_speed = min(best_speed, self.cruise_speed * 0.35)

            if 0.0 <= own_distance_to_line <= 3.2:
                other_axis = "ns" if other.direction in ["north", "south"] else "ew"
                if own_axis == other_axis:
                    continue
                if not other.is_inside_intersection(intersection):
                    continue

                center_distance = math.hypot(
                    other.position[0] - center_x, other.position[1] - center_y
                )
                if (
                    center_distance
                    <= max(intersection.width, intersection.height) * 0.48
                ):
                    return 0.0

            # Turning vehicles yield to straight cross-traffic near the stop line.
            if turning_now and 0.0 <= own_distance_to_line <= 8.0:
                other_axis = "ns" if other.direction in ["north", "south"] else "ew"
                if other_axis != own_axis and other.target_direction == other.direction:
                    other_distance = intersection.distance_to_stop_line(
                        other.direction, other.position
                    )
                    if -2.5 <= other_distance <= 5.0:
                        if other.velocity > 0.8:
                            return min(best_speed, self.cruise_speed * 0.05)

            # Dedicated rule: left turns yield to opposing straight movement.
            if left_turning_now and 0.0 <= own_distance_to_line <= 12.0:
                opposing_direction = self.opposite_direction(self.direction)
                if (
                    other.direction == opposing_direction
                    and other.target_direction == other.direction
                ):
                    other_distance = intersection.distance_to_stop_line(
                        other.direction, other.position
                    )
                    if -4.0 <= other_distance <= 14.0 and other.velocity > 0.5:
                        return 0.0

        return best_speed

    def obstacle_target_speed(self, obstacles):
        if not obstacles:
            return self.max_speed

        best_speed = self.max_speed
        for obstacle in obstacles:
            ox, oy = obstacle.get("position", (0.0, 0.0))
            radius = float(obstacle.get("radius", 6.0))
            if obstacle.get("kind") == "closure":
                radius *= 1.45

            dist = math.hypot(ox - self.position[0], oy - self.position[1])
            if dist < radius + 18.0:
                ratio = max(0.0, (dist - radius) / 18.0)
                best_speed = min(best_speed, self.max_speed * ratio)
        return best_speed

    def crosswalk_target_speed(self, pedestrian_blocks):
        if not pedestrian_blocks:
            return self.max_speed

        best_speed = self.max_speed
        for block in pedestrian_blocks:
            if block.get("direction") != self.direction:
                continue
            distance = max(0.0, float(block.get("distance", 999.0)))
            caution_distance = 16.0
            if distance < caution_distance:
                ratio = max(0.0, distance / caution_distance)
                best_speed = min(best_speed, self.max_speed * ratio)
        return best_speed

    def longitudinal_progress(self, position):
        x, y = position
        if self.direction == "north":
            return -y
        if self.direction == "south":
            return y
        if self.direction == "east":
            return x
        if self.direction == "west":
            return -x
        return 0.0

    @staticmethod
    def is_left_turn(entry_direction, target_direction):
        left_turn_map = {
            "north": "west",
            "west": "south",
            "south": "east",
            "east": "north",
        }
        return left_turn_map.get(entry_direction) == target_direction

    @staticmethod
    def opposite_direction(direction):
        opposite = {
            "north": "south",
            "south": "north",
            "east": "west",
            "west": "east",
        }
        return opposite.get(direction)

    @staticmethod
    def bezier_point(start, control, end, t):
        omt = 1.0 - t
        return (
            (omt * omt) * start[0] + 2.0 * omt * t * control[0] + (t * t) * end[0],
            (omt * omt) * start[1] + 2.0 * omt * t * control[1] + (t * t) * end[1],
        )

    @staticmethod
    def bezier_tangent(start, control, end, t):
        return (
            2.0 * (1.0 - t) * (control[0] - start[0]) + 2.0 * t * (end[0] - control[0]),
            2.0 * (1.0 - t) * (control[1] - start[1]) + 2.0 * t * (end[1] - control[1]),
        )

    def estimate_turn_length(self, start, control, end):
        prev = start
        total = 0.0
        for i in range(1, 21):
            t = i / 20.0
            point = self.bezier_point(start, control, end, t)
            total += math.hypot(point[0] - prev[0], point[1] - prev[1])
            prev = point
        return max(0.1, total)

    def update_turning(self, dt, intersection):
        if len(self.path) < 3:
            self.turning = False
            return

        start, control, end = self.path
        self.turn_distance += max(0.0, self.velocity * dt)
        self.turn_progress = max(
            0.0, min(1.0, self.turn_distance / max(self.turn_length, 1e-3))
        )
        t = self.turn_progress

        self.position = self.bezier_point(start, control, end, t)
        tangent_x, tangent_y = self.bezier_tangent(start, control, end, t)
        if abs(tangent_x) > 1e-4 or abs(tangent_y) > 1e-4:
            self.rotation = (
                math.degrees(math.atan2(tangent_x, -tangent_y)) + 360.0
            ) % 360.0

        if t >= 1.0:
            self.turning = False
            self.turn_started = True
            self.turn_progress = 0.0
            self.turn_distance = 0.0
            self.direction = self.target_direction
            self.rotation = self.get_initial_rotation()
            self.apply_lane_alignment(intersection, 1.0)

    def start_turning(self, intersection):
        self.turning = True
        self.turn_started = True
        self.turn_progress = 0.0
        self.turn_distance = 0.0
        self.exit_lane_index = intersection.get_turning_lane_index(
            self.target_direction
        )
        self.path = intersection.get_turn_path(self.direction, self.target_direction)
        if self.path:
            self.path[0] = self.position
        if len(self.path) >= 3:
            self.turn_length = self.estimate_turn_length(
                self.path[0], self.path[1], self.path[2]
            )

    def draw(self, surface, camera_offset=(0, 0), scale=1.0):
        screen_x = self.position[0] * scale + camera_offset[0]
        screen_y = self.position[1] * scale + camera_offset[1]

        car_w = max(5, int(self.width * scale))
        car_l = max(8, int(self.length * scale))

        # ── Drop shadow ──────────────────────────────────────────────────────
        shadow_w = car_w + int(3 * scale)
        shadow_h = car_l + int(2 * scale)
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 55), shadow.get_rect())
        surface.blit(shadow, (screen_x - shadow_w * 0.5, screen_y - shadow_h * 0.48))

        # ── Build vehicle surface ─────────────────────────────────────────────
        surf_w = car_w + 6
        surf_h = car_l + 6
        car_surface = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)

        ox, oy = 3, 3  # drawing origin inside the surface

        body_color = self.color
        darker = tuple(max(12, c - 28) for c in body_color)
        brighter = tuple(min(255, c + 38) for c in body_color)
        wheel_color = (28, 30, 36)
        window_color = (168, 198, 228)
        window_dark = (130, 160, 190)

        vt = self.vehicle_type

        if vt == VehicleType.MOTORCYCLE:
            # — Slender profile —
            body_rect = pygame.Rect(ox + car_w // 4, oy, car_w // 2, car_l)
            pygame.draw.rect(
                car_surface, body_color, body_rect, border_radius=max(1, car_w // 4)
            )
            # wheels
            w_r = max(2, car_w // 3)
            pygame.draw.circle(
                car_surface, wheel_color, (ox + car_w // 2, oy + w_r), w_r
            )
            pygame.draw.circle(
                car_surface, wheel_color, (ox + car_w // 2, oy + car_l - w_r), w_r
            )
            # rider silhouette
            rider_rect = pygame.Rect(
                ox + car_w // 4 + 1,
                oy + int(car_l * 0.25),
                int(car_w * 0.5),
                int(car_l * 0.45),
            )
            pygame.draw.ellipse(car_surface, darker, rider_rect)

        elif vt in (VehicleType.BUS, VehicleType.TRUCK):
            # — Box / slab body —
            body_rect = pygame.Rect(ox, oy, car_w, car_l)
            pygame.draw.rect(
                car_surface,
                body_color,
                body_rect,
                border_radius=max(2, int(car_w * 0.12)),
            )
            # Roof stripe
            stripe = pygame.Rect(ox + 2, oy + 2, car_w - 4, max(3, int(car_l * 0.08)))
            pygame.draw.rect(car_surface, brighter, stripe, border_radius=2)
            # Windshield
            ws = pygame.Rect(
                ox + 2,
                oy + max(2, int(car_l * 0.06)),
                car_w - 4,
                max(3, int(car_l * 0.12)),
            )
            pygame.draw.rect(car_surface, window_color, ws, border_radius=2)
            # Rear window
            rw = pygame.Rect(
                ox + 2,
                oy + car_l - max(4, int(car_l * 0.12)),
                car_w - 4,
                max(3, int(car_l * 0.10)),
            )
            pygame.draw.rect(car_surface, window_dark, rw, border_radius=2)
            # Side windows (bus)
            if vt == VehicleType.BUS:
                win_h = max(3, int(car_l * 0.09))
                win_y_start = oy + int(car_l * 0.22)
                for wi in range(3):
                    wy = win_y_start + wi * (win_h + max(2, int(car_l * 0.07)))
                    pygame.draw.rect(
                        car_surface,
                        window_color,
                        pygame.Rect(ox + 1, wy, car_w - 2, win_h),
                        border_radius=1,
                    )
            # Wheels
            wheel_w = max(2, int(car_w * 0.16))
            wheel_l_front = max(3, int(car_l * 0.14))
            wheel_l_rear = max(3, int(car_l * 0.18))
            for wx_off in (0, car_w + 2 - wheel_w):
                pygame.draw.rect(
                    car_surface,
                    wheel_color,
                    pygame.Rect(ox - 1 + wx_off, oy + 4, wheel_w, wheel_l_front),
                    border_radius=1,
                )
                pygame.draw.rect(
                    car_surface,
                    wheel_color,
                    pygame.Rect(
                        ox - 1 + wx_off,
                        oy + car_l - 4 - wheel_l_rear,
                        wheel_w,
                        wheel_l_rear,
                    ),
                    border_radius=1,
                )

        else:
            # — Standard car / emergency — rounded sedan shape —
            body_rect = pygame.Rect(ox, oy, car_w, car_l)
            roof_rect = pygame.Rect(
                ox + int(car_w * 0.15),
                oy + int(car_l * 0.22),
                int(car_w * 0.70),
                int(car_l * 0.54),
            )
            windshield = pygame.Rect(
                ox + int(car_w * 0.18),
                oy + int(car_l * 0.12),
                int(car_w * 0.64),
                int(car_l * 0.14),
            )
            rear_window = pygame.Rect(
                ox + int(car_w * 0.18),
                oy + int(car_l * 0.73),
                int(car_w * 0.64),
                int(car_l * 0.11),
            )

            pygame.draw.rect(
                car_surface,
                body_color,
                body_rect,
                border_radius=max(2, int(car_w * 0.30)),
            )
            pygame.draw.rect(
                car_surface, darker, roof_rect, border_radius=max(2, int(car_w * 0.22))
            )
            pygame.draw.rect(car_surface, window_color, windshield, border_radius=2)
            pygame.draw.rect(car_surface, window_dark, rear_window, border_radius=2)

            # Wheels
            wheel_w = max(2, int(car_w * 0.17))
            wheel_l = max(3, int(car_l * 0.20))
            for wx_off in (0, car_w + 2 - wheel_w):
                pygame.draw.rect(
                    car_surface,
                    wheel_color,
                    pygame.Rect(ox - 1 + wx_off, oy + 3, wheel_w, wheel_l),
                    border_radius=1,
                )
                pygame.draw.rect(
                    car_surface,
                    wheel_color,
                    pygame.Rect(
                        ox - 1 + wx_off, oy + car_l - 3 - wheel_l, wheel_w, wheel_l
                    ),
                    border_radius=1,
                )

            # Emergency light bar
            if vt == VehicleType.EMERGENCY:
                bar_rect = pygame.Rect(
                    ox + int(car_w * 0.2),
                    oy + int(car_l * 0.18),
                    int(car_w * 0.6),
                    max(2, int(car_l * 0.06)),
                )
                flash = int(self.behavior_timer * 4) % 2 == 0
                pygame.draw.rect(
                    car_surface,
                    (240, 40, 40) if flash else (60, 60, 240),
                    bar_rect,
                    border_radius=1,
                )

        # Headlights & taillights
        light_w = max(2, int(car_w * 0.22))
        headlight = (248, 244, 200)
        taillight = (255, 55, 44) if self.brake_lights_on else (140, 28, 28)
        if vt != VehicleType.MOTORCYCLE:
            pygame.draw.rect(
                car_surface,
                headlight,
                pygame.Rect(ox + 1, oy + 1, light_w, max(2, int(car_l * 0.04))),
                border_radius=1,
            )
            pygame.draw.rect(
                car_surface,
                headlight,
                pygame.Rect(
                    ox + car_w - light_w - 1, oy + 1, light_w, max(2, int(car_l * 0.04))
                ),
                border_radius=1,
            )
            pygame.draw.rect(
                car_surface,
                taillight,
                pygame.Rect(
                    ox + 1,
                    oy + car_l - max(2, int(car_l * 0.04)) - 1,
                    light_w,
                    max(2, int(car_l * 0.04)),
                ),
                border_radius=1,
            )
            pygame.draw.rect(
                car_surface,
                taillight,
                pygame.Rect(
                    ox + car_w - light_w - 1,
                    oy + car_l - max(2, int(car_l * 0.04)) - 1,
                    light_w,
                    max(2, int(car_l * 0.04)),
                ),
                border_radius=1,
            )

        # ── Rotate and blit ──────────────────────────────────────────────────
        rotated = pygame.transform.rotate(car_surface, -self.rotation)
        rect = rotated.get_rect(center=(int(screen_x), int(screen_y)))
        surface.blit(rotated, rect.topleft)

        # Subtle dark overlay while stopped
        if self.velocity < 0.2 and vt != VehicleType.MOTORCYCLE:
            stopped_ov = pygame.Surface(rotated.get_size(), pygame.SRCALPHA)
            stopped_ov.fill((12, 16, 24, 30))
            surface.blit(stopped_ov, rect.topleft)
