"""Application runtime entrypoint for launching the pygame simulation."""

from __future__ import annotations

import logging
import sys

import pygame

from controllers.traffic_light_controller import TrafficLightController
from data.data_manager import DataManager
from safety.safety_checker import SafetyChecker
from simulation.simulation_manager import SimulationManager
from visualization.renderer import Renderer

LOGGER = logging.getLogger(__name__)


def run_full_application() -> int:
    """Run the full traffic simulation and return an exit code."""
    pygame.init()

    try:
        screen_width, screen_height = 1200, 800
        screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption("Crossroads Traffic Light Simulation")

        data_manager = DataManager()
        safety_checker = SafetyChecker()
        traffic_controller = TrafficLightController(safety_checker)
        simulation = SimulationManager(traffic_controller)
        renderer = Renderer(screen, simulation)

        LOGGER.info("Simulation initialized", extra={"data_dir": data_manager.data_dir})

        clock = pygame.time.Clock()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                renderer.handle_event(event)

            dt = clock.tick(60) / 1000.0
            simulation.update(dt)
            renderer.render()
            pygame.display.flip()

        return 0
    except KeyboardInterrupt:
        LOGGER.warning("Simulation interrupted by user")
        return 130
    except Exception:
        LOGGER.exception("Unrecoverable runtime failure")
        return 1
    finally:
        pygame.quit()
        try:
            sys.stdout.flush()
        except Exception:
            LOGGER.debug("Unable to flush stdout on shutdown", exc_info=True)
