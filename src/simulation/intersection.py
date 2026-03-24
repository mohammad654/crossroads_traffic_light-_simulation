# src/simulation/intersection.py
import math
import random


class Intersection:
    """
    Represents the intersection with its geometry and properties.
    """

    def __init__(self, width=40, height=40):
        self.width = width  # Width of the intersection in meters
        self.height = height  # Height of the intersection in meters
        self.center = (100, 100)  # Center position (x, y)
        self.lanes_per_direction = 2
        self.lane_width = 3.5
        self.road_width = self.lane_width * self.lanes_per_direction * 2

        # Define the simulation bounds
        self.bounds = (0, 0, 200, 200)  # (min_x, min_y, max_x, max_y)

        # Define entry/exit points
        self.setup_entry_exit_points()

    def setup_entry_exit_points(self):
        """Set up the entry and exit points for each direction."""
        half_width = self.width / 2
        half_height = self.height / 2
        min_x, min_y, max_x, max_y = self.bounds
        center_x, center_y = self.center

        inbound_offsets = {
            "north": [-1.5 * self.lane_width, -0.5 * self.lane_width],
            "south": [1.5 * self.lane_width, 0.5 * self.lane_width],
            "east": [-1.5 * self.lane_width, -0.5 * self.lane_width],
            "west": [1.5 * self.lane_width, 0.5 * self.lane_width],
        }

        outbound_offsets = {
            "north": [1.5 * self.lane_width, 0.5 * self.lane_width],
            "south": [-1.5 * self.lane_width, -0.5 * self.lane_width],
            "east": [1.5 * self.lane_width, 0.5 * self.lane_width],
            "west": [-1.5 * self.lane_width, -0.5 * self.lane_width],
        }

        self.entry_lanes = {
            "north": [
                (center_x + offset, max_y - 8) for offset in inbound_offsets["north"]
            ],
            "south": [
                (center_x + offset, min_y + 8) for offset in inbound_offsets["south"]
            ],
            "east": [
                (min_x + 8, center_y + offset) for offset in inbound_offsets["east"]
            ],
            "west": [
                (max_x - 8, center_y + offset) for offset in inbound_offsets["west"]
            ],
        }

        self.exit_lanes = {
            "north": [
                (center_x + offset, min_y - 5) for offset in outbound_offsets["north"]
            ],
            "south": [
                (center_x + offset, max_y + 5) for offset in outbound_offsets["south"]
            ],
            "east": [
                (max_x + 5, center_y + offset) for offset in outbound_offsets["east"]
            ],
            "west": [
                (min_x - 5, center_y + offset) for offset in outbound_offsets["west"]
            ],
        }

        self.turning_lane_index = {"north": 0, "south": 0, "east": 0, "west": 0}

        self.straight_lane_index = {"north": 1, "south": 1, "east": 1, "west": 1}

        self.entry_points = {
            direction: lanes[0] for direction, lanes in self.entry_lanes.items()
        }
        self.exit_points = {
            direction: lanes[0] for direction, lanes in self.exit_lanes.items()
        }

        # Stop line positions (where vehicles should stop on red)
        self.stop_lines = {
            "north": (center_x - self.lane_width, center_y + half_height + 2),
            "south": (center_x + self.lane_width, center_y - half_height - 2),
            "east": (center_x - half_width - 2, center_y - self.lane_width),
            "west": (center_x + half_width + 2, center_y + self.lane_width),
        }

        # Traffic light positions
        self.traffic_light_positions = {
            "north": (self.stop_lines["north"][0] + 4, self.stop_lines["north"][1]),
            "south": (self.stop_lines["south"][0] - 4, self.stop_lines["south"][1]),
            "east": (self.stop_lines["east"][0], self.stop_lines["east"][1] + 4),
            "west": (self.stop_lines["west"][0], self.stop_lines["west"][1] - 4),
        }

    def get_position(self, direction):
        """
        Get the position for a traffic light in the given direction.

        Args:
            direction: Direction of the traffic light

        Returns:
            (x, y) position tuple
        """
        if direction in self.traffic_light_positions:
            return self.traffic_light_positions[direction]
        return self.center

    def get_spawn_position(self, direction, lane_index=None, turning=False):
        """
        Get the spawn position for a vehicle in the given direction.

        Args:
            direction: Direction from which to spawn

        Returns:
            (x, y) position tuple
        """
        if direction in self.entry_lanes:
            lanes = self.entry_lanes[direction]
            if lane_index is None:
                lane_index = (
                    self.turning_lane_index[direction]
                    if turning
                    else random.randint(0, len(lanes) - 1)
                )
            lane_index = max(0, min(len(lanes) - 1, lane_index))
            return lanes[lane_index]
        return self.center

    def get_exit_position(self, direction, lane_index=None):
        """
        Get the exit position for a vehicle in the given direction.

        Args:
            direction: Direction in which to exit

        Returns:
            (x, y) position tuple
        """
        if direction in self.exit_lanes:
            lanes = self.exit_lanes[direction]
            if lane_index is None:
                lane_index = random.randint(0, len(lanes) - 1)
            lane_index = max(0, min(len(lanes) - 1, lane_index))
            return lanes[lane_index]
        return self.center

    def get_turning_lane_index(self, direction):
        return self.turning_lane_index.get(direction, 0)

    def get_straight_lane_index(self, direction):
        return self.straight_lane_index.get(direction, 1)

    def get_stop_line_position(self, direction):
        """Get stop line position for a heading direction."""
        return self.stop_lines.get(direction, self.center)

    def distance_to_stop_line(self, direction, position):
        """
        Signed distance to stop line in meters.
        Positive: vehicle is before the stop line.
        Negative: vehicle has crossed the stop line.
        """
        x, y = position
        stop_x, stop_y = self.get_stop_line_position(direction)

        if direction == "north":
            return y - stop_y
        if direction == "south":
            return stop_y - y
        if direction == "east":
            return stop_x - x
        if direction == "west":
            return x - stop_x
        return 0.0

    def is_in_bounds(self, position):
        """
        Check if a position is within the simulation bounds.

        Args:
            position: (x, y) position tuple

        Returns:
            True if in bounds, False otherwise
        """
        x, y = position
        min_x, min_y, max_x, max_y = self.bounds
        margin = 20
        return (min_x - margin <= x <= max_x + margin) and (
            min_y - margin <= y <= max_y + margin
        )

    def get_turn_path(self, entry_direction, exit_direction):
        """
        Get a path for turning from entry to exit direction.

        Args:
            entry_direction: Direction from which the vehicle entered
            exit_direction: Direction in which the vehicle will exit

        Returns:
            List of waypoints for the turn
        """
        entry_lane = self.get_turning_lane_index(entry_direction)
        exit_lane = self.get_turning_lane_index(exit_direction)
        entry = self.get_spawn_position(
            entry_direction, lane_index=entry_lane, turning=True
        )
        exit = self.get_exit_position(exit_direction, lane_index=exit_lane)

        cx, cy = self.center
        half_w = self.width / 2
        half_h = self.height / 2
        arc_margin = self.lane_width * 0.85

        corner_controls = {
            ("north", "east"): (cx + half_w - arc_margin, cy - half_h + arc_margin),
            ("east", "north"): (cx + half_w - arc_margin, cy - half_h + arc_margin),
            ("north", "west"): (cx - half_w + arc_margin, cy - half_h + arc_margin),
            ("west", "north"): (cx - half_w + arc_margin, cy - half_h + arc_margin),
            ("south", "east"): (cx + half_w - arc_margin, cy + half_h - arc_margin),
            ("east", "south"): (cx + half_w - arc_margin, cy + half_h - arc_margin),
            ("south", "west"): (cx - half_w + arc_margin, cy + half_h - arc_margin),
            ("west", "south"): (cx - half_w + arc_margin, cy + half_h - arc_margin),
        }

        control = corner_controls.get((entry_direction, exit_direction), (cx, cy))
        return [entry, control, exit]

    def draw(self, surface, camera_offset=(0, 0), scale=1.0):
        """
        Draw the intersection on the given surface.

        Args:
            surface: Pygame surface to draw on
            camera_offset: Offset for camera position
            scale: Scale factor for drawing
        """
        import pygame

        # Calculate screen positions
        center_x = self.center[0] * scale + camera_offset[0]
        center_y = self.center[1] * scale + camera_offset[1]
        width = self.width * scale
        height = self.height * scale
        road_width = self.road_width * scale

        # Draw sidewalks and environment
        sidewalk_color = (176, 178, 182)
        inner_sidewalk = pygame.Rect(
            center_x - self.width * scale / 2 - 28,
            center_y - self.height * scale / 2 - 28,
            self.width * scale + 56,
            self.height * scale + 56,
        )
        pygame.draw.rect(surface, sidewalk_color, inner_sidewalk, border_radius=14)

        for tx, ty in [
            (-56, -56),
            (56, -56),
            (-56, 56),
            (56, 56),
            (-80, 0),
            (80, 0),
            (0, -80),
            (0, 80),
        ]:
            tree_x = int(center_x + tx)
            tree_y = int(center_y + ty)
            pygame.draw.circle(surface, (58, 128, 73), (tree_x, tree_y), int(8 * scale))
            pygame.draw.circle(surface, (40, 92, 54), (tree_x, tree_y), int(4 * scale))

        # Draw the roads (horizontal and vertical)
        road_color = (54, 57, 63)
        shoulder_color = (45, 48, 54)

        # Horizontal road
        horizontal_road = pygame.Rect(
            camera_offset[0] + self.bounds[0] * scale,
            center_y - road_width / 2,
            (self.bounds[2] - self.bounds[0]) * scale,
            road_width,
        )
        pygame.draw.rect(
            surface, shoulder_color, horizontal_road.inflate(0, 6), border_radius=8
        )
        pygame.draw.rect(surface, road_color, horizontal_road)

        # Vertical road
        vertical_road = pygame.Rect(
            center_x - road_width / 2,
            camera_offset[1] + self.bounds[1] * scale,
            road_width,
            (self.bounds[3] - self.bounds[1]) * scale,
        )
        pygame.draw.rect(
            surface, shoulder_color, vertical_road.inflate(6, 0), border_radius=8
        )
        pygame.draw.rect(surface, road_color, vertical_road)

        marking_color = (252, 252, 252)
        dashed_color = (250, 250, 250)
        solid_color = (228, 228, 228)

        lane_step = self.lane_width * scale
        left_edge = center_x - road_width / 2
        top_edge = center_y - road_width / 2

        # Solid center separators between opposing directions
        pygame.draw.line(
            surface,
            solid_color,
            (camera_offset[0] + self.bounds[0] * scale, center_y),
            (camera_offset[0] + self.bounds[2] * scale, center_y),
            2,
        )
        pygame.draw.line(
            surface,
            solid_color,
            (center_x, camera_offset[1] + self.bounds[1] * scale),
            (center_x, camera_offset[1] + self.bounds[3] * scale),
            2,
        )

        # Dashed lane dividers within same direction
        dash_length = 12 * scale
        gap_length = 9 * scale
        divider_offsets = [-lane_step, lane_step]
        for lane_y in divider_offsets:
            y = center_y + lane_y
            for x in range(
                int(camera_offset[0] + self.bounds[0] * scale),
                int(camera_offset[0] + self.bounds[2] * scale),
                int(dash_length + gap_length),
            ):
                pygame.draw.line(surface, dashed_color, (x, y), (x + dash_length, y), 2)

        for lane_x in divider_offsets:
            x = center_x + lane_x
            for y in range(
                int(camera_offset[1] + self.bounds[1] * scale),
                int(camera_offset[1] + self.bounds[3] * scale),
                int(dash_length + gap_length),
            ):
                pygame.draw.line(surface, dashed_color, (x, y), (x, y + dash_length), 2)

        # Turning-lane guide markings near junction
        turn_mark_color = (242, 242, 242)
        for direction, lanes in self.entry_lanes.items():
            turning_lane = lanes[self.turning_lane_index[direction]]
            tx = turning_lane[0] * scale + camera_offset[0]
            ty = turning_lane[1] * scale + camera_offset[1]
            if direction in ["north", "south"]:
                pygame.draw.polygon(
                    surface,
                    turn_mark_color,
                    [
                        (tx - 4, ty),
                        (tx + 4, ty),
                        (tx, ty - 8 if direction == "north" else ty + 8),
                    ],
                )
            else:
                pygame.draw.polygon(
                    surface,
                    turn_mark_color,
                    [
                        (tx, ty - 4),
                        (tx, ty + 4),
                        (tx + 8 if direction == "east" else tx - 8, ty),
                    ],
                )

        # Zebra crosswalks
        zebra_color = (245, 245, 245)
        zebra_width = 4
        zebra_stripe_len = lane_step * 1.7
        stripe_count = 9
        stripe_gap = 3 * scale

        for i in range(stripe_count):
            offset = (i - stripe_count / 2) * (zebra_width + stripe_gap)
            # North/South
            pygame.draw.line(
                surface,
                zebra_color,
                (center_x + offset, center_y - height / 2 - 2 * scale),
                (center_x + offset, center_y - height / 2 - zebra_stripe_len),
                zebra_width,
            )
            pygame.draw.line(
                surface,
                zebra_color,
                (center_x + offset, center_y + height / 2 + 2 * scale),
                (center_x + offset, center_y + height / 2 + zebra_stripe_len),
                zebra_width,
            )
            # East/West
            pygame.draw.line(
                surface,
                zebra_color,
                (center_x + width / 2 + 2 * scale, center_y + offset),
                (center_x + width / 2 + zebra_stripe_len, center_y + offset),
                zebra_width,
            )
            pygame.draw.line(
                surface,
                zebra_color,
                (center_x - width / 2 - 2 * scale, center_y + offset),
                (center_x - width / 2 - zebra_stripe_len, center_y + offset),
                zebra_width,
            )

        # Draw stop lines for each approach
        stop_line_color = (245, 245, 245)
        stop_line_width = max(2, int(2 * scale))

        north_stop_y = self.stop_lines["north"][1] * scale + camera_offset[1]
        south_stop_y = self.stop_lines["south"][1] * scale + camera_offset[1]
        east_stop_x = self.stop_lines["east"][0] * scale + camera_offset[0]
        west_stop_x = self.stop_lines["west"][0] * scale + camera_offset[0]

        pygame.draw.line(
            surface,
            stop_line_color,
            (center_x - road_width / 2, north_stop_y),
            (center_x + road_width / 2, north_stop_y),
            stop_line_width,
        )
        pygame.draw.line(
            surface,
            stop_line_color,
            (center_x - road_width / 2, south_stop_y),
            (center_x + road_width / 2, south_stop_y),
            stop_line_width,
        )
        pygame.draw.line(
            surface,
            stop_line_color,
            (east_stop_x, center_y - road_width / 2),
            (east_stop_x, center_y + road_width / 2),
            stop_line_width,
        )
        pygame.draw.line(
            surface,
            stop_line_color,
            (west_stop_x, center_y - road_width / 2),
            (west_stop_x, center_y + road_width / 2),
            stop_line_width,
        )
