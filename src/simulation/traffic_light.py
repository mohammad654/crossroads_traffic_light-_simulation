# src/simulation/traffic_light.py
from enum import Enum, auto


class LightState(Enum):
    """States for a traffic light."""

    RED = auto()
    YELLOW = auto()
    GREEN = auto()


class TrafficLight:
    """
    Represents a traffic light at an intersection.
    """

    def __init__(self, direction, position):
        self.direction = direction  # "north", "south", "east", "west"
        self.position = position  # (x, y) tuple
        self.state = LightState.RED
        self.timer = 0.0

        # Default timings (in seconds)
        self.green_duration = 30.0
        self.yellow_duration = 5.0
        self.red_duration = 35.0  # Should equal green + yellow of opposing direction

    def update(self, dt):
        """
        Update the traffic light state based on timer.

        Args:
            dt: Delta time in seconds
        """
        self.timer += dt

        if self.state == LightState.GREEN and self.timer >= self.green_duration:
            self.state = LightState.YELLOW
            self.timer = 0.0
        elif self.state == LightState.YELLOW and self.timer >= self.yellow_duration:
            self.state = LightState.RED
            self.timer = 0.0
        elif self.state == LightState.RED and self.timer >= self.red_duration:
            self.state = LightState.GREEN
            self.timer = 0.0

    def set_state(self, state):
        """
        Set the traffic light state.

        Args:
            state: The new state for the traffic light
        """
        self.state = state
        self.timer = 0.0

    def get_color(self):
        """
        Get the RGB color for the current state.

        Returns:
            Tuple of (R, G, B) values
        """
        if self.state == LightState.RED:
            return (255, 0, 0)
        elif self.state == LightState.YELLOW:
            return (255, 255, 0)
        elif self.state == LightState.GREEN:
            return (0, 255, 0)
        return (128, 128, 128)  # Gray for unknown state

    def draw(self, surface, camera_offset=(0, 0), scale=1.0):
        """
        Draw the traffic light on the given surface.

        Args:
            surface: Pygame surface to draw on
            camera_offset: Offset for camera position
            scale: Scale factor for drawing
        """
        import pygame

        # Calculate screen position
        screen_x = self.position[0] * scale + camera_offset[0]
        screen_y = self.position[1] * scale + camera_offset[1]

        # Draw traffic light housing
        housing_width = 11 * scale
        housing_height = 32 * scale
        housing_rect = pygame.Rect(
            screen_x - housing_width / 2,
            screen_y - housing_height / 2,
            housing_width,
            housing_height,
        )
        pygame.draw.rect(surface, (28, 30, 34), housing_rect, 0, 4)
        pygame.draw.rect(surface, (80, 84, 92), housing_rect, 1, 4)

        # Draw the active light
        light_radius = 3 * scale
        light_y_offset = 0

        if self.state == LightState.RED:
            light_y_offset = -housing_height / 3
        elif self.state == LightState.YELLOW:
            light_y_offset = 0
        elif self.state == LightState.GREEN:
            light_y_offset = housing_height / 3

        time_phase = pygame.time.get_ticks() / 1000.0
        pulse = (
            0.85 + 0.15 * (1 + pygame.math.Vector2(1, 0).rotate(time_phase * 180).x) / 2
        )
        glow_radius = int(max(3, light_radius * 2.2 * pulse))
        glow_surface = pygame.Surface(
            (glow_radius * 2, glow_radius * 2), pygame.SRCALPHA
        )
        pygame.draw.circle(
            glow_surface,
            (*self.get_color(), 75),
            (glow_radius, glow_radius),
            glow_radius,
        )
        surface.blit(
            glow_surface,
            (screen_x - glow_radius, screen_y + light_y_offset - glow_radius),
        )

        if self.state == LightState.YELLOW:
            ring_radius = int(max(4, light_radius * (2.0 + 0.4 * pulse)))
            pygame.draw.circle(
                surface, (255, 210, 90), (int(screen_x), int(screen_y)), ring_radius, 1
            )

        pygame.draw.circle(
            surface,
            self.get_color(),
            (screen_x, screen_y + light_y_offset),
            light_radius,
        )

        # Draw the other lights (dimmed)
        dim_red = (100, 0, 0)
        dim_yellow = (100, 100, 0)
        dim_green = (0, 100, 0)

        # Red light (dimmed if not active)
        if self.state != LightState.RED:
            pygame.draw.circle(
                surface,
                dim_red,
                (screen_x, screen_y - housing_height / 3),
                light_radius,
            )

        # Yellow light (dimmed if not active)
        if self.state != LightState.YELLOW:
            pygame.draw.circle(surface, dim_yellow, (screen_x, screen_y), light_radius)

        # Green light (dimmed if not active)
        if self.state != LightState.GREEN:
            pygame.draw.circle(
                surface,
                dim_green,
                (screen_x, screen_y + housing_height / 3),
                light_radius,
            )
