import math
import os
import time
import pygame


class Slider:
    def __init__(self, min_value, max_value, value, label, step=0.01):
        self.min_value = min_value
        self.max_value = max_value
        self.value = value
        self.label = label
        self.step = step
        self.dragging = False
        self.editing = False
        self.input_text = f"{value:.2f}"
        self.track_rect = pygame.Rect(0, 0, 1, 1)
        self.input_rect = pygame.Rect(0, 0, 1, 1)
        self.tooltip = ""

    def knob_x(self):
        ratio = (self.value - self.min_value) / max(
            1e-6, (self.max_value - self.min_value)
        )
        return self.track_rect.x + int(self.track_rect.width * ratio)

    def set_from_x(self, x):
        ratio = (x - self.track_rect.x) / max(1, self.track_rect.width)
        ratio = max(0.0, min(1.0, ratio))
        raw_value = self.min_value + ratio * (self.max_value - self.min_value)
        self.value = round(raw_value / self.step) * self.step
        self.value = max(self.min_value, min(self.max_value, self.value))
        self.input_text = f"{self.value:.2f}"


class Renderer:
    def __init__(self, screen, simulation):
        self.screen = screen
        self.simulation = simulation
        self.width, self.height = screen.get_size()

        self.camera_offset = (0, 0)
        self.scale = 2.0
        self.panning = False
        self.pan_start = (0, 0)
        self.last_frame_time = 0.0

        self.adding_obstacle = False
        self.adding_road_closure = False
        self.obstacle_drag_start = None
        self.selected_manual_direction = None
        self.weather_particles = []
        self.dragging_obstacle_preview = None

        # Keep the junction centered at all times for stable navigation.
        self.recenter_camera()

        # ── Fonts ───────────────────────────────────────────────────────────
        for name in ("Segoe UI", "Arial", "sans-serif"):
            try:
                self.font = pygame.font.SysFont(name, 17)
                self.small_font = pygame.font.SysFont(name, 13)
                self.title_font = pygame.font.SysFont(name, 16, bold=True)
                self.large_font = pygame.font.SysFont(name, 22, bold=True)
                break
            except Exception:
                continue

        # ── Modern dark-light hybrid theme ───────────────────────────────────
        self.theme = {
            # Road-level background — deep asphalt grey-green
            "bg": (22, 28, 36),
            "bg_a": (24, 30, 38),
            "bg_b": (20, 26, 34),
            # Panel surfaces — clean near-white cards
            "panel": (245, 247, 252),
            "panel_2": (252, 254, 255),
            "panel_dark": (30, 38, 52),
            # Borders & shadows
            "border": (210, 218, 230),
            "border_dark": (55, 68, 88),
            "shadow": (6, 10, 20, 70),
            # Typography
            "text": (28, 36, 50),
            "text_inv": (235, 240, 248),
            "muted": (90, 105, 125),
            # Accent / state colours
            "accent": (56, 132, 255),
            "accent_soft": (210, 228, 255),
            "accent_dark": (36, 90, 180),
            "ok": (52, 185, 95),
            "ok_soft": (195, 240, 210),
            "warn": (240, 168, 48),
            "warn_soft": (255, 238, 195),
            "danger": (230, 72, 68),
            "danger_soft": (255, 215, 212),
        }

        self.day_night_cycle_seconds = 180.0
        self.active_tab = "Control"
        self.tabs = ["Control"]
        self.sidebar_expanded = True
        self.sidebar_anim = 1.0
        self.sidebar_width_expanded = 312
        self.sidebar_width_collapsed = 52
        self.sidebar_rect = pygame.Rect(
            10, 56, self.sidebar_width_expanded, self.height - 100
        )
        self.sidebar_toggle_rect = pygame.Rect(0, 0, 1, 1)
        self.fullscreen = False
        self.fast_forward = False

        self.toolbar_buttons = []
        self.notifications = []
        self.tooltip_map = {}
        self.hover_tooltip = None
        self.last_param_change = {}
        self.last_algorithm_change_time = 0.0
        self.focused_slider = None

        self.sliders = [
            Slider(
                0.2,
                4.0,
                self.simulation.simulation_speed_factor,
                "Simulation Speed",
                step=0.01,
            ),
            Slider(
                0.2,
                2.5,
                self.simulation.traffic_density_factor,
                "Traffic Density",
                step=0.05,
            ),
            Slider(
                10.0,
                60.0,
                self.simulation.traffic_controller.default_phase_durations[
                    "ns_green"
                ],
                "NS Green (s)",
                step=1.0,
            ),
            Slider(
                10.0,
                60.0,
                self.simulation.traffic_controller.default_phase_durations[
                    "ew_green"
                ],
                "EW Green (s)",
                step=1.0,
            ),
        ]
        self.sliders[0].tooltip = "Control simulation update speed multiplier"
        self.sliders[1].tooltip = "Adjust vehicle spawn pressure at all approaches"
        self.sliders[2].tooltip = "Adjust North/South green duration"
        self.sliders[3].tooltip = "Adjust East/West green duration"

        self.analytics_panel = {
            "rect": pygame.Rect(self.width - 500, 64, 480, 320),
            "dragging": False,
            "resizing": False,
            "drag_start": (0, 0),
            "resize_start": (0, 0),
            "min_w": 380,
            "min_h": 240,
            "visible": False,
        }
        self.analytics_content_rect = pygame.Rect(0, 0, 1, 1)
        self.analytics_cache_surface = None
        self.analytics_cache_stamp = -1
        self.analytics_panels_dirty = True
        self.chart_views = {
            "wait": {"zoom": 1.0, "pan": 0},
            "throughput": {"zoom": 1.0, "pan": 0},
            "speed": {"zoom": 1.0, "pan": 0},
            "comparison": {"zoom": 1.0, "pan": 0},
        }
        self.comparison_mode = True
        self.chart_dragging = None
        self.chart_drag_start = (0, 0)
        self.chart_rects = {}
        self.show_heatmap = True
        self.show_stats_card = True

        # Manual override direction selector
        self.manual_override_direction = (
            None  # None | "north" | "south" | "east" | "west"
        )
        self.manual_override_rects = {}
        self.scenario_preset_rects = {}

        self.simulation.traffic_controller.set_algorithm("time_based")
        self.algorithms = list(
            self.simulation.traffic_controller.available_algorithms
        )
        self.algorithm_descriptions = {
            "time_based": "Fixed cycle timing",
            "traffic_responsive": "Queue-responsive split",
            "adaptive": "Online adaptive bias",
            "ml_optimized": "Bandit-optimized green",
            "coordinated": "Green-wave coordination",
            "emergency": "Flashing emergency mode",
        }
        self.algorithm_toggle_rects = {}
        self.control_rects = {}
        self.setup_ui_metadata()

    def recenter_camera(self):
        cx, cy = self.simulation.intersection.center
        self.camera_offset = (
            self.width / 2 - cx * self.scale,
            self.height / 2 - cy * self.scale,
        )

    def setup_ui_metadata(self):
        self.tooltip_map = {
            "sidebar_toggle": "Collapse or expand the sidebar",
            "speed_slider": "Control simulation update speed multiplier",
            "density_slider": "Control global traffic demand",
            "ns_green_slider": "Tune NS green phase in seconds",
            "ew_green_slider": "Tune EW green phase in seconds",
            "toggle_analytics": "Show or hide analytics charts",
            "toggle_heatmap": "Show or hide congestion heat map",
            "toggle_stats": "Show or hide KPI stats card",
            "toggle_rush_hour": "Increase demand and adjust behavior for rush hour",
            "btn_play_pause": "Play or pause the simulation (Space)",
            "btn_reset": "Reset simulation to initial state (R)",
            "btn_record": "Start or stop recording simulation frames",
            "btn_playback": "Play back the last recording",
            "btn_obstacle": "Toggle obstacle placement tool (O)",
            "btn_closure": "Toggle road-closure placement tool (C)",
        }
        for algorithm in self.algorithms:
            self.tooltip_map[f"alg_{algorithm}"] = self.algorithm_descriptions.get(
                algorithm,
                "Traffic control algorithm",
            )

    def add_notification(self, message, kind="info", ttl=2.0):
        self.notifications.append(
            {"message": message, "kind": kind, "until": self.now() + ttl}
        )

    def now(self):
        return pygame.time.get_ticks() / 1000.0

    def format_algorithm_name(self, algorithm):
        return algorithm.replace("_", " ").title()

    def set_algorithm(self, algorithm):
        if algorithm != self.simulation.traffic_controller.algorithm:
            self.simulation.traffic_controller.set_algorithm(algorithm)
            self.last_algorithm_change_time = self.now()
            self.add_notification(
                f"Algorithm set: {self.format_algorithm_name(algorithm)}", "ok"
            )

    def toggle_rush_hour(self):
        self.simulation.set_rush_hour_mode(not self.simulation.rush_hour_mode)
        self.add_notification("Rush hour toggled", "ok")

    def toggle_pause(self):
        self.simulation.toggle_pause()
        label = "Paused" if self.simulation.paused else "Resumed"
        self.add_notification(label, "info")

    def reset_simulation(self):
        self.simulation.reset()
        self.sync_slider_values()
        self.add_notification("Simulation reset", "ok")

    def toggle_recording(self):
        if self.simulation.recording:
            self.simulation.stop_recording()
            self.add_notification(
                f"Recording stopped ({len(self.simulation.playback_frames)} frames)",
                "ok",
            )
        else:
            self.simulation.start_recording()
            self.add_notification("Recording started", "warn")

    def start_playback(self):
        if self.simulation.playback_frames:
            self.simulation.start_playback()
            self.add_notification("Playback started", "info")
        else:
            self.add_notification("No recording available", "warn")

    def toggle_obstacle_tool(self):
        self.adding_obstacle = not self.adding_obstacle
        if self.adding_obstacle:
            self.adding_road_closure = False
        self.obstacle_drag_start = None
        self.add_notification(
            "Obstacle tool " + ("enabled" if self.adding_obstacle else "disabled"),
            "info",
        )

    def toggle_road_closure_tool(self):
        self.adding_road_closure = not self.adding_road_closure
        if self.adding_road_closure:
            self.adding_obstacle = False
        self.obstacle_drag_start = None
        self.add_notification(
            "Road closure tool "
            + ("enabled" if self.adding_road_closure else "disabled"),
            "info",
        )

    def cycle_weather(self):
        weather_cycle = ["clear", "rain", "fog", "snow"]
        current = self.simulation.weather_mode
        idx = weather_cycle.index(current)
        next_weather = weather_cycle[(idx + 1) % len(weather_cycle)]
        self.simulation.set_weather_mode(next_weather)
        self.add_notification(f"Weather: {next_weather.title()}", "info")

    def screen_to_world(self, pos):
        x = (pos[0] - self.camera_offset[0]) / self.scale
        y = (pos[1] - self.camera_offset[1]) / self.scale
        return x, y

    def is_over_ui(self, pos):
        if self.sidebar_rect.collidepoint(pos):
            return True
        if self.analytics_panel["visible"] and self.analytics_panel[
            "rect"
        ].collidepoint(pos):
            return True
        if any(button["rect"].collidepoint(pos) for button in self.toolbar_buttons):
            return True
        return False

    def handle_hotkeys(self, event):
        if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.scale = min(6.0, self.scale * 1.08)
            self.recenter_camera()
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.scale = max(0.7, self.scale / 1.08)
            self.recenter_camera()
        elif event.key == pygame.K_a:
            self.toggle_analytics_visibility()
        elif event.key == pygame.K_g:
            self.show_heatmap = not self.show_heatmap
            self.add_notification(
                "Heat map " + ("shown" if self.show_heatmap else "hidden"), "info"
            )
        elif event.key == pygame.K_t:
            self.show_stats_card = not self.show_stats_card
            self.add_notification(
                "Stats card " + ("shown" if self.show_stats_card else "hidden"), "info"
            )
        elif event.key == pygame.K_w:
            self.cycle_weather()
        elif event.key == pygame.K_h:
            self.toggle_rush_hour()
        elif event.key == pygame.K_SPACE:
            self.toggle_pause()
        elif event.key == pygame.K_r:
            self.reset_simulation()
        elif event.key == pygame.K_f:
            self.toggle_fast_forward()
        elif event.key == pygame.K_F11:
            self.toggle_fullscreen()
        elif event.key == pygame.K_ESCAPE:
            if self.fullscreen:
                self.toggle_fullscreen()
        elif event.key == pygame.K_o:
            self.toggle_obstacle_tool()
        elif event.key == pygame.K_c:
            self.toggle_road_closure_tool()
        elif event.key in (
            pygame.K_1,
            pygame.K_2,
            pygame.K_3,
            pygame.K_4,
            pygame.K_5,
            pygame.K_6,
        ):
            idx = event.key - pygame.K_1
            if 0 <= idx < len(self.algorithms):
                self.set_algorithm(self.algorithms[idx])

    def sync_slider_values(self):
        self.sliders[0].value = self.simulation.simulation_speed_factor
        self.sliders[0].input_text = f"{self.sliders[0].value:.2f}"
        self.sliders[1].value = self.simulation.traffic_density_factor
        self.sliders[1].input_text = f"{self.sliders[1].value:.2f}"
        self.sliders[2].value = (
            self.simulation.traffic_controller.default_phase_durations["ns_green"]
        )
        self.sliders[2].input_text = f"{self.sliders[2].value:.2f}"
        self.sliders[3].value = (
            self.simulation.traffic_controller.default_phase_durations["ew_green"]
        )
        self.sliders[3].input_text = f"{self.sliders[3].value:.2f}"

    def apply_slider_value(self, slider):
        if slider.label == "Simulation Speed":
            self.simulation.set_simulation_speed_factor(slider.value)
            self.last_param_change["Simulation Speed"] = self.now()
            self.add_notification(
                f"Simulation Speed = {slider.value:.2f}", "ok", ttl=1.2
            )
        elif slider.label == "Traffic Density":
            self.simulation.set_traffic_density_factor(slider.value)
            self.last_param_change["Traffic Density"] = self.now()
            self.add_notification(
                f"Traffic Density = {slider.value:.2f}", "ok", ttl=1.2
            )
        elif slider.label == "NS Green (s)":
            self.simulation.traffic_controller.set_phase_durations(
                ns_green=slider.value
            )
            self.last_param_change["NS Green (s)"] = self.now()
            self.add_notification(f"NS Green = {slider.value:.0f}s", "ok", ttl=1.2)
        elif slider.label == "EW Green (s)":
            self.simulation.traffic_controller.set_phase_durations(
                ew_green=slider.value
            )
            self.last_param_change["EW Green (s)"] = self.now()
            self.add_notification(f"EW Green = {slider.value:.0f}s", "ok", ttl=1.2)
        self.analytics_panels_dirty = True

    def handle_slider_text_input(self, event):
        if not self.focused_slider:
            return False
        slider = self.focused_slider
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            try:
                parsed = float(slider.input_text)
            except ValueError:
                parsed = slider.value
            slider.value = max(slider.min_value, min(slider.max_value, parsed))
            slider.input_text = f"{slider.value:.2f}"
            slider.editing = False
            self.apply_slider_value(slider)
            self.focused_slider = None
            return True
        if event.key == pygame.K_ESCAPE:
            slider.editing = False
            slider.input_text = f"{slider.value:.2f}"
            self.focused_slider = None
            return True
        if event.key == pygame.K_BACKSPACE:
            slider.input_text = slider.input_text[:-1]
            return True
        allowed = "0123456789.-"
        if event.unicode and event.unicode in allowed and len(slider.input_text) < 8:
            slider.input_text += event.unicode
            return True
        return False

    def handle_toolbar_click(self, pos):
        for button in self.toolbar_buttons:
            if button["rect"].collidepoint(pos):
                button["action"]()
                return True
        return False

    def handle_sidebar_click(self, pos):
        if self.sidebar_toggle_rect.collidepoint(pos):
            self.sidebar_expanded = not self.sidebar_expanded
            self.add_notification(
                "Sidebar " + ("expanded" if self.sidebar_expanded else "collapsed"),
                "info",
            )
            return True

        if not self.sidebar_expanded and self.sidebar_anim < 0.95:
            return True

        for slider in self.sliders:
            knob_rect = pygame.Rect(
                slider.knob_x() - 8, slider.track_rect.y - 7, 16, 22
            )
            if knob_rect.collidepoint(pos) or slider.track_rect.collidepoint(pos):
                slider.dragging = True
                slider.editing = False
                self.focused_slider = None
                slider.set_from_x(pos[0])
                self.apply_slider_value(slider)
                return True
            if slider.input_rect.collidepoint(pos):
                slider.editing = True
                self.focused_slider = slider
                slider.input_text = ""
                if slider.label == "Simulation Speed":
                    self.control_rects["speed_slider"] = slider.track_rect
                elif slider.label == "Traffic Density":
                    self.control_rects["density_slider"] = slider.track_rect
                elif slider.label == "NS Green (s)":
                    self.control_rects["ns_green_slider"] = slider.track_rect
                elif slider.label == "EW Green (s)":
                    self.control_rects["ew_green_slider"] = slider.track_rect
                return True

        for algorithm, rect in self.algorithm_toggle_rects.items():
            if rect.collidepoint(pos):
                self.set_algorithm(algorithm)
                return True

        toggle_actions = {
            "toggle_analytics": self.toggle_analytics_visibility,
            "toggle_heatmap": lambda: self._toggle_flag("show_heatmap", "Heat map"),
            "toggle_stats": lambda: self._toggle_flag("show_stats_card", "Stats card"),
            "toggle_rush_hour": self.toggle_rush_hour,
        }
        for control_id, action in toggle_actions.items():
            rect = self.control_rects.get(control_id)
            if rect and rect.collidepoint(pos):
                action()
                return True

        # Scenario preset buttons
        for preset_key, rect in self.scenario_preset_rects.items():
            if rect.collidepoint(pos):
                self.simulation.apply_preconfigured_scenario(preset_key)
                self.sync_slider_values()
                self.add_notification(
                    f"Scenario: {preset_key.replace('_', ' ').title()}", "ok"
                )
                return True

        # Manual override direction buttons
        for direction, rect in self.manual_override_rects.items():
            if rect.collidepoint(pos):
                if direction == "clear":
                    self.manual_override_direction = None
                    self.simulation.traffic_controller.set_manual_override(None)
                    self.add_notification("Manual override cleared", "info")
                else:
                    if self.manual_override_direction == direction:
                        # Toggling same direction off
                        self.manual_override_direction = None
                        self.simulation.traffic_controller.set_manual_override(None)
                        self.add_notification("Manual override cleared", "info")
                    else:
                        self.manual_override_direction = direction
                        from simulation.traffic_light import LightState

                        self.simulation.traffic_controller.set_manual_override(
                            direction, LightState.GREEN
                        )
                        self.add_notification(
                            f"Override: {direction.title()} GREEN", "warn"
                        )
                return True

        return False

    def _toggle_flag(self, attr_name, label):
        current = getattr(self, attr_name)
        setattr(self, attr_name, not current)
        self.add_notification(
            label + " " + ("shown" if not current else "hidden"), "info"
        )

    def handle_analytics_panel_interaction(self, event):
        if not self.analytics_panel["visible"]:
            return False

        panel_rect = self.analytics_panel["rect"]
        # Close button (registered each frame in render_analytics_panel)
        close_rect = self.control_rects.get("analytics_close")
        if (
            close_rect
            and event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and close_rect.collidepoint(event.pos)
        ):
            self.toggle_analytics_visibility()
            return True

        header_rect = pygame.Rect(panel_rect.x, panel_rect.y, panel_rect.width, 36)
        resize_rect = pygame.Rect(panel_rect.right - 16, panel_rect.bottom - 16, 16, 16)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if resize_rect.collidepoint(event.pos):
                self.analytics_panel["resizing"] = True
                self.analytics_panel["resize_start"] = event.pos
                return True
            if header_rect.collidepoint(event.pos):
                self.analytics_panel["dragging"] = True
                self.analytics_panel["drag_start"] = event.pos
                return True
            for chart_id, chart_rect in self.chart_rects.items():
                if chart_rect.collidepoint(event.pos):
                    self.chart_dragging = chart_id
                    self.chart_drag_start = event.pos
                    return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.analytics_panel["dragging"] = False
            self.analytics_panel["resizing"] = False
            self.chart_dragging = None

        if event.type == pygame.MOUSEMOTION:
            if self.analytics_panel["dragging"]:
                dx = event.pos[0] - self.analytics_panel["drag_start"][0]
                dy = event.pos[1] - self.analytics_panel["drag_start"][1]
                rect = self.analytics_panel["rect"]
                rect.x += dx
                rect.y += dy
                rect.x = max(360, min(self.width - 120, rect.x))
                rect.y = max(50, min(self.height - 200, rect.y))
                self.analytics_panel["drag_start"] = event.pos
                return True

            if self.analytics_panel["resizing"]:
                dx = event.pos[0] - self.analytics_panel["resize_start"][0]
                dy = event.pos[1] - self.analytics_panel["resize_start"][1]
                rect = self.analytics_panel["rect"]
                rect.width = max(self.analytics_panel["min_w"], rect.width + dx)
                rect.height = max(self.analytics_panel["min_h"], rect.height + dy)
                rect.width = min(self.width - rect.x - 12, rect.width)
                rect.height = min(self.height - rect.y - 52, rect.height)
                self.analytics_panel["resize_start"] = event.pos
                self.analytics_panels_dirty = True
                return True

            if self.chart_dragging:
                dx = event.pos[0] - self.chart_drag_start[0]
                view = self.chart_views[self.chart_dragging]
                view["pan"] -= int(dx)
                self.chart_drag_start = event.pos
                self.analytics_panels_dirty = True
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            for chart_id, chart_rect in self.chart_rects.items():
                if chart_rect.collidepoint(event.pos):
                    view = self.chart_views[chart_id]
                    view["zoom"] *= 1.12 if event.button == 4 else 0.9
                    view["zoom"] = max(1.0, min(8.0, view["zoom"]))
                    self.analytics_panels_dirty = True
                    return True
        return False

    def handle_event(self, event):
        if self.handle_analytics_panel_interaction(event):
            return

        if event.type == pygame.KEYDOWN:
            if self.handle_slider_text_input(event):
                return
            self.handle_hotkeys(event)

        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()
            if event.button == 1:
                if self.handle_toolbar_click(pos):
                    return
                if self.handle_sidebar_click(pos):
                    return

            if event.button in (4, 5):
                self.scale *= 1.1 if event.button == 4 else 1 / 1.1
                self.scale = max(0.7, min(6.0, self.scale))
                self.recenter_camera()

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                for slider in self.sliders:
                    if slider.dragging:
                        slider.dragging = False

        elif event.type == pygame.MOUSEMOTION:
            self.update_hover_tooltip(event.pos)

            for slider in self.sliders:
                if slider.dragging:
                    slider.set_from_x(event.pos[0])
                    self.apply_slider_value(slider)
                    return

    def update_hover_tooltip(self, pos):
        self.hover_tooltip = None
        for key, rect in self.control_rects.items():
            if rect.collidepoint(pos) and key in self.tooltip_map:
                self.hover_tooltip = self.tooltip_map[key]
                return
        for algorithm, rect in self.algorithm_toggle_rects.items():
            if rect.collidepoint(pos):
                self.hover_tooltip = self.tooltip_map.get(f"alg_{algorithm}")
                return
        for slider in self.sliders:
            if slider.track_rect.collidepoint(pos) or slider.input_rect.collidepoint(
                pos
            ):
                self.hover_tooltip = slider.tooltip
                return
        for button in self.toolbar_buttons:
            if button["rect"].collidepoint(pos):
                self.hover_tooltip = self.tooltip_map.get(button["id"])
                return

    def _draw_toolbar_button(
        self, rect, label, active=False, danger=False, warn=False, icon_color=None
    ):
        """Render a single rounded toolbar button. Returns True if rendered."""
        if active:
            bg = self.theme["accent"]
            fg = (255, 255, 255)
            border = self.theme["accent_dark"]
        elif danger:
            bg = self.theme["danger"]
            fg = (255, 255, 255)
            border = (180, 40, 40)
        elif warn:
            bg = self.theme["warn"]
            fg = (255, 255, 255)
            border = (190, 120, 20)
        else:
            bg = self.theme["panel"]
            fg = self.theme["text"]
            border = self.theme["border"]
        shadow = pygame.Surface((rect.width + 4, rect.height + 4), pygame.SRCALPHA)
        pygame.draw.rect(
            shadow,
            (0, 0, 0, 28),
            pygame.Rect(2, 3, rect.width, rect.height),
            border_radius=9,
        )
        self.screen.blit(shadow, (rect.x - 2, rect.y - 1))
        pygame.draw.rect(self.screen, bg, rect, border_radius=9)
        pygame.draw.rect(self.screen, border, rect, 1, border_radius=9)
        txt = self.small_font.render(label, True, fg)
        self.screen.blit(txt, txt.get_rect(center=rect.center))

    def draw_section_header(self, x, y, w, label, accent_line=True):
        """Draw a section heading with a colored left accent bar."""
        if accent_line:
            pygame.draw.rect(
                self.screen,
                self.theme["accent"],
                pygame.Rect(x, y + 2, 3, 12),
                border_radius=2,
            )
        self.screen.blit(
            self.small_font.render(label.upper(), True, self.theme["muted"]), (x + 8, y)
        )
        pygame.draw.line(
            self.screen, self.theme["border"], (x + 8, y + 18), (x + w, y + 18), 1
        )
        return y + 24

    def draw_panel(self, rect, radius=12, dark=False):
        # Layered shadow for depth
        shadow = pygame.Surface((rect.width + 12, rect.height + 12), pygame.SRCALPHA)
        pygame.draw.rect(
            shadow,
            (0, 0, 0, 35),
            pygame.Rect(6, 7, rect.width, rect.height),
            border_radius=radius + 2,
        )
        pygame.draw.rect(
            shadow,
            (0, 0, 0, 20),
            pygame.Rect(3, 4, rect.width + 1, rect.height + 1),
            border_radius=radius + 1,
        )
        self.screen.blit(shadow, (rect.x - 6, rect.y - 4))
        bg = self.theme["panel_dark"] if dark else self.theme["panel"]
        border = self.theme["border_dark"] if dark else self.theme["border"]
        pygame.draw.rect(self.screen, bg, rect, border_radius=radius)
        pygame.draw.rect(self.screen, border, rect, 1, border_radius=radius)

    def draw_toggle_switch(self, rect, active, label, control_id):
        base = (202, 221, 248) if active else (218, 225, 235)
        pygame.draw.rect(self.screen, self.theme["panel_2"], rect, border_radius=10)
        pygame.draw.rect(self.screen, self.theme["border"], rect, 1, border_radius=10)
        pill = pygame.Rect(rect.right - 52, rect.y + 5, 40, rect.height - 10)
        pygame.draw.rect(self.screen, base, pill, border_radius=9)
        knob_x = pill.right - 10 if active else pill.x + 10
        knob_color = self.theme["accent"] if active else (143, 156, 173)
        pygame.draw.circle(self.screen, knob_color, (knob_x, pill.centery), 8)
        text = self.small_font.render(label, True, self.theme["text"])
        self.screen.blit(text, (rect.x + 10, rect.y + 8))
        self.control_rects[control_id] = rect

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode(
                (info.current_w, info.current_h), pygame.FULLSCREEN
            )
        else:
            self.screen = pygame.display.set_mode((1200, 800))
        self.width, self.height = self.screen.get_size()
        self.sidebar_rect = pygame.Rect(
            10, 56, self.sidebar_width_expanded, self.height - 100
        )
        self.analytics_panel["rect"] = pygame.Rect(self.width - 500, 64, 480, 320)
        self.add_notification(
            "Fullscreen " + ("on" if self.fullscreen else "off"), "info"
        )

    def toggle_fast_forward(self):
        self.fast_forward = not self.fast_forward
        factor = 4.0 if self.fast_forward else 1.0
        self.simulation.set_simulation_speed_factor(factor)
        self.sync_slider_values()
        self.add_notification(
            "Fast-forward " + ("ON (4×)" if self.fast_forward else "OFF"), "warn"
        )

    def draw_toolbar(self):
        # ── App title pill ─────────────────────────────────────────────────
        toolbar_rect = pygame.Rect(10, 10, 310, 38)
        pygame.draw.rect(
            self.screen, self.theme["panel_dark"], toolbar_rect, border_radius=10
        )
        pygame.draw.rect(
            self.screen, self.theme["border_dark"], toolbar_rect, 1, border_radius=10
        )
        # vertical accent stripe on left edge
        pygame.draw.rect(
            self.screen,
            self.theme["accent"],
            pygame.Rect(
                toolbar_rect.x, toolbar_rect.y + 8, 3, toolbar_rect.height - 16
            ),
            border_radius=2,
        )
        title = self.title_font.render(
            "Crossroads Traffic Simulation", True, self.theme["text_inv"]
        )
        self.screen.blit(title, (toolbar_rect.x + 14, toolbar_rect.y + 10))
        self.toolbar_buttons = []

        btn_h = toolbar_rect.height
        btn_y = toolbar_rect.y
        btn_x = toolbar_rect.right + 10

        def _add_btn(
            button_id, label, action, w=80, active=False, danger=False, warn=False
        ):
            nonlocal btn_x
            rect = pygame.Rect(btn_x, btn_y, w, btn_h)
            self._draw_toolbar_button(
                rect, label, active=active, danger=danger, warn=warn
            )
            self.toolbar_buttons.append(
                {"id": button_id, "rect": rect, "action": action}
            )
            self.control_rects[button_id] = rect
            btn_x += w + 5
            return rect

        def _divider():
            nonlocal btn_x
            pygame.draw.line(
                self.screen,
                self.theme["border"],
                (btn_x + 3, btn_y + 6),
                (btn_x + 3, btn_y + btn_h - 6),
                1,
            )
            btn_x += 10

        # ── GROUP 1: Playback control ───────────────────────────────────────
        is_running = not self.simulation.paused
        _add_btn(
            "btn_play_pause",
            "⏸ Pause" if is_running else "▶ Run",
            self.toggle_pause,
            w=82,
            active=is_running,
        )
        _add_btn("btn_reset", "↺ Reset", self.reset_simulation, w=72)
        _add_btn(
            "btn_fast_fwd",
            "⏩ 4×" if not self.fast_forward else "⏩ 1×",
            self.toggle_fast_forward,
            w=60,
            warn=self.fast_forward,
        )
        _divider()

        # ── GROUP 2: Recording ─────────────────────────────────────────────
        _add_btn(
            "btn_record",
            "⏹ Stop" if self.simulation.recording else "⏺ Rec",
            self.toggle_recording,
            w=72,
            danger=self.simulation.recording,
        )
        _add_btn("btn_playback", "▷ Play", self.start_playback, w=64)
        _divider()

        # ── GROUP 3: Tools ─────────────────────────────────────────────────
        _add_btn(
            "btn_obstacle",
            "✚ Obstacle",
            self.toggle_obstacle_tool,
            w=82,
            active=self.adding_obstacle,
        )
        _add_btn(
            "btn_closure",
            "⊘ Close",
            self.toggle_road_closure_tool,
            w=72,
            active=self.adding_road_closure,
        )
        _divider()

        # ── GROUP 4: Data / view ───────────────────────────────────────────
        _add_btn(
            "analytics",
            "📊 Charts",
            self.toggle_analytics_visibility,
            w=78,
            active=self.analytics_panel["visible"],
        )
        _add_btn("save", "💾 Save", self.save_scenario, w=64)
        _add_btn("load", "📂 Load", self.load_scenario, w=64)
        _add_btn("export", "⬇ Export", self.export_results, w=72)
        _add_btn(
            "btn_fullscreen",
            "⛶" if not self.fullscreen else "⛶ Exit",
            self.toggle_fullscreen,
            w=52,
            active=self.fullscreen,
        )
        _divider()

        # ── Safety / weather badge (right-anchored) ─────────────────────────
        safety_count = getattr(
            self.simulation.traffic_controller, "safety_violation_count", 0
        )
        weather_icons = {"clear": "☀", "rain": "☂", "fog": "≈", "snow": "❄"}
        w_icon = weather_icons.get(self.simulation.weather_mode, "")
        badge_label = (
            f"⚠ {safety_count} viol{'s' if safety_count != 1 else ''}"
            if safety_count > 0
            else f"✓ Safe  {w_icon} {self.simulation.weather_mode.title()}"
        )
        badge_color = self.theme["danger"] if safety_count > 0 else self.theme["ok"]
        badge_rect = pygame.Rect(self.width - 190, btn_y, 180, btn_h)
        pygame.draw.rect(self.screen, badge_color, badge_rect, border_radius=10)
        pygame.draw.rect(self.screen, (0, 0, 0, 40), badge_rect, 1, border_radius=10)
        badge_txt = self.small_font.render(badge_label, True, (255, 255, 255))
        self.screen.blit(badge_txt, badge_txt.get_rect(center=badge_rect.center))
        self.control_rects["weather_badge"] = badge_rect
        self.tooltip_map["weather_badge"] = (
            "W key cycles weather. Current: " + self.simulation.weather_mode
        )

    def reset_view(self):
        self.scale = 2.0
        self.recenter_camera()
        self.add_notification("Camera reset", "ok")

    def save_scenario(self):
        os.makedirs("data", exist_ok=True)
        self.simulation.save_scenario(os.path.join("data", "scenario_saved.json"))
        self.add_notification("Scenario saved", "ok")

    def load_scenario(self):
        path = os.path.join("data", "scenario_saved.json")
        if os.path.exists(path):
            self.simulation.load_scenario(path)
            self.sync_slider_values()
            self.add_notification("Scenario loaded", "ok")

    def export_results(self):
        os.makedirs("data", exist_ok=True)
        export_file = os.path.join(
            "data", f"simulation_results_{int(time.time())}.json"
        )
        self.simulation.export_results(export_file)
        self.add_notification(f"Exported: {os.path.basename(export_file)}", "ok")

    def toggle_analytics_visibility(self):
        self.analytics_panel["visible"] = not self.analytics_panel["visible"]
        self.add_notification(
            "Analytics panel "
            + ("shown" if self.analytics_panel["visible"] else "hidden"),
            "info",
        )

    def update_sidebar_animation(self):
        target = 1.0 if self.sidebar_expanded else 0.0
        speed = 0.16
        if abs(self.sidebar_anim - target) < 0.02:
            self.sidebar_anim = target
        else:
            self.sidebar_anim += (target - self.sidebar_anim) * speed

        width = int(
            self.sidebar_width_collapsed
            + (self.sidebar_width_expanded - self.sidebar_width_collapsed)
            * self.sidebar_anim
        )
        self.sidebar_rect = pygame.Rect(10, 56, width, self.height - 100)

    def draw_tabs(self, x, y):
        tab_count = max(1, len(self.tabs))
        tab_w = (self.sidebar_rect.width - 24) // tab_count
        for idx, tab in enumerate(self.tabs):
            rect = pygame.Rect(x + idx * tab_w, y, tab_w - 4, 26)
            active = tab == self.active_tab
            color = self.theme["accent_soft"] if active else self.theme["panel_2"]
            pygame.draw.rect(self.screen, color, rect, border_radius=7)
            pygame.draw.rect(
                self.screen, self.theme["border"], rect, 1, border_radius=7
            )
            self.screen.blit(
                self.small_font.render(tab, True, self.theme["text"]),
                (rect.x + 8, rect.y + 6),
            )
            self.control_rects[f"tab_{tab}"] = rect

    def draw_algorithm_toggles(self, x, y, available_w):
        self.algorithm_toggle_rects = {}
        current = self.simulation.traffic_controller.algorithm
        for i, algorithm in enumerate(self.algorithms):
            rect = pygame.Rect(x, y + i * 30, available_w, 26)
            active = algorithm == current
            label = self.format_algorithm_name(algorithm)

            pygame.draw.rect(self.screen, self.theme["panel_2"], rect, border_radius=8)
            pygame.draw.rect(
                self.screen, self.theme["border"], rect, 1, border_radius=8
            )
            text_color = self.theme["accent"] if active else self.theme["text"]
            self.screen.blit(
                self.small_font.render(label, True, text_color),
                (rect.x + 10, rect.y + 6),
            )

            switch_rect = pygame.Rect(rect.right - 44, rect.y + 6, 32, 14)
            pygame.draw.rect(self.screen, (205, 214, 228), switch_rect, border_radius=8)
            knob_x = switch_rect.right - 8 if active else switch_rect.x + 8
            pygame.draw.circle(
                self.screen,
                self.theme["accent"] if active else (134, 146, 164),
                (knob_x, switch_rect.centery),
                6,
            )
            if active:
                pulse = int(
                    70
                    + 40
                    * math.sin((self.now() - self.last_algorithm_change_time) * 10.0)
                )
                glow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                pygame.draw.rect(
                    glow,
                    (59, 130, 246, max(15, min(80, pulse))),
                    glow.get_rect(),
                    border_radius=8,
                )
                self.screen.blit(glow, rect.topleft)

            self.algorithm_toggle_rects[algorithm] = rect

    def draw_slider(self, slider, x, y, w):
        label = self.small_font.render(slider.label, True, self.theme["text"])
        self.screen.blit(label, (x, y))

        slider.track_rect = pygame.Rect(x, y + 20, w - 74, 8)
        slider.input_rect = pygame.Rect(x + w - 66, y + 10, 62, 26)

        pygame.draw.rect(
            self.screen, (212, 222, 236), slider.track_rect, border_radius=6
        )
        fill_width = int(
            (slider.value - slider.min_value)
            / max(1e-6, slider.max_value - slider.min_value)
            * slider.track_rect.width
        )
        fill_rect = pygame.Rect(
            slider.track_rect.x,
            slider.track_rect.y,
            max(2, fill_width),
            slider.track_rect.height,
        )
        pygame.draw.rect(self.screen, self.theme["accent"], fill_rect, border_radius=6)
        pygame.draw.circle(
            self.screen,
            (255, 255, 255),
            (slider.knob_x(), slider.track_rect.centery),
            8,
        )
        pygame.draw.circle(
            self.screen,
            self.theme["accent"],
            (slider.knob_x(), slider.track_rect.centery),
            8,
            2,
        )

        changed_recently = (
            self.now() - self.last_param_change.get(slider.label, -999) < 0.75
        )
        input_color = (
            self.theme["accent_soft"]
            if (slider.editing or changed_recently)
            else self.theme["panel_2"]
        )
        pygame.draw.rect(self.screen, input_color, slider.input_rect, border_radius=7)
        pygame.draw.rect(
            self.screen, self.theme["border"], slider.input_rect, 1, border_radius=7
        )
        text = slider.input_text if slider.editing else f"{slider.value:.2f}"
        self.screen.blit(
            self.small_font.render(text, True, self.theme["text"]),
            (slider.input_rect.x + 8, slider.input_rect.y + 6),
        )

    def draw_sidebar(self):
        self.update_sidebar_animation()
        self.draw_panel(self.sidebar_rect, radius=12)

        self.control_rects = {}

        # ── Collapse toggle ──────────────────────────────────────────────────
        self.sidebar_toggle_rect = pygame.Rect(
            self.sidebar_rect.right - 34, self.sidebar_rect.y + 10, 24, 24
        )
        pygame.draw.rect(
            self.screen,
            self.theme["panel_dark"],
            self.sidebar_toggle_rect,
            border_radius=7,
        )
        pygame.draw.rect(
            self.screen,
            self.theme["border_dark"],
            self.sidebar_toggle_rect,
            1,
            border_radius=7,
        )
        arrow = "◀" if self.sidebar_expanded else "▶"
        arrow_text = self.small_font.render(arrow, True, self.theme["text_inv"])
        self.screen.blit(
            arrow_text, arrow_text.get_rect(center=self.sidebar_toggle_rect.center)
        )
        self.control_rects["sidebar_toggle"] = self.sidebar_toggle_rect

        if self.sidebar_anim < 0.45:
            return

        x = self.sidebar_rect.x + 10
        content_w = self.sidebar_rect.width - 20

        # ── Header ──────────────────────────────────────────────────────────
        hdr_rect = pygame.Rect(x - 10, self.sidebar_rect.y, self.sidebar_rect.width, 40)
        pygame.draw.rect(
            self.screen,
            self.theme["panel_dark"],
            hdr_rect,
            border_top_left_radius=12,
            border_top_right_radius=12,
        )
        title = self.title_font.render("Control Center", True, self.theme["text_inv"])
        self.screen.blit(title, (x + 4, self.sidebar_rect.y + 11))
        # Accent strip at bottom of header
        pygame.draw.rect(
            self.screen,
            self.theme["accent"],
            pygame.Rect(hdr_rect.x, hdr_rect.bottom - 2, hdr_rect.width, 2),
        )

        content_y = self.sidebar_rect.y + 50

        # ── Phase badge ─────────────────────────────────────────────────────
        ctrl = self.simulation.traffic_controller
        phase_name = (
            ctrl.phase_sequence[ctrl.phase_index] if ctrl.phase_sequence else "unknown"
        )
        phase_remaining = max(
            0.0, ctrl._get_phase_duration(phase_name) - ctrl.phase_timer
        )
        phase_colors = {
            "ns_green": self.theme["ok"],
            "ew_green": self.theme["ok"],
            "ns_yellow": self.theme["warn"],
            "ew_yellow": self.theme["warn"],
        }
        phase_bg = phase_colors.get(phase_name, self.theme["danger"])
        phase_label = phase_name.replace("_", " ").upper()
        mode_name = self.format_algorithm_name(ctrl.algorithm)

        phase_rect = pygame.Rect(x, content_y, content_w, 46)
        pygame.draw.rect(
            self.screen, self.theme["panel_2"], phase_rect, border_radius=8
        )
        # Left accent bar
        pygame.draw.rect(
            self.screen,
            phase_bg,
            pygame.Rect(phase_rect.x, phase_rect.y + 4, 4, phase_rect.height - 8),
            border_radius=2,
        )
        pygame.draw.rect(self.screen, phase_bg, phase_rect, 1, border_radius=8)
        self.screen.blit(
            self.small_font.render(f"Mode: {mode_name}", True, self.theme["muted"]),
            (phase_rect.x + 12, phase_rect.y + 6),
        )
        self.screen.blit(
            self.small_font.render(
                f"{phase_label}  —  {phase_remaining:.1f}s", True, phase_bg
            ),
            (phase_rect.x + 12, phase_rect.y + 26),
        )
        # Phase progress bar at bottom
        total_dur = max(0.001, ctrl._get_phase_duration(phase_name))
        pbar_frac = 1.0 - min(1.0, phase_remaining / total_dur)
        pbar = pygame.Rect(
            phase_rect.x + 4, phase_rect.bottom - 4, phase_rect.width - 8, 3
        )
        pygame.draw.rect(self.screen, self.theme["border"], pbar, border_radius=2)
        pygame.draw.rect(
            self.screen,
            phase_bg,
            pygame.Rect(pbar.x, pbar.y, int(pbar.width * pbar_frac), pbar.height),
            border_radius=2,
        )
        content_y += 56

        # ── Section: Simulation Parameters ─────────────────────────────────
        content_y = self.draw_section_header(
            x, content_y, content_w, "Simulation Parameters"
        )
        slider_y = content_y
        for slider in self.sliders:
            self.draw_slider(slider, x, slider_y, content_w)
            if slider.label == "Simulation Speed":
                self.control_rects["speed_slider"] = slider.track_rect
            elif slider.label == "Traffic Density":
                self.control_rects["density_slider"] = slider.track_rect
            elif slider.label == "NS Green (s)":
                self.control_rects["ns_green_slider"] = slider.track_rect
            elif slider.label == "EW Green (s)":
                self.control_rects["ew_green_slider"] = slider.track_rect
            slider_y += 48
        content_y = slider_y + 4

        # ── Section: Algorithm ──────────────────────────────────────────────
        content_y = self.draw_section_header(
            x, content_y, content_w, "Traffic Algorithm"
        )
        self.draw_algorithm_toggles(x, content_y, content_w)
        content_y += len(self.algorithms) * 30 + 6

        # ── Section: View & Mode ─────────────────────────────────────────────
        content_y = self.draw_section_header(x, content_y, content_w, "View & Mode")
        toggle_height = 30
        toggle_items = [
            ("toggle_analytics", self.analytics_panel["visible"], "📊 Analytics Panel"),
            ("toggle_heatmap", self.show_heatmap, "🌡 Congestion Heat Map"),
            ("toggle_stats", self.show_stats_card, "📋 KPI Stats Card"),
            ("toggle_rush_hour", self.simulation.rush_hour_mode, "🚦 Rush Hour Mode"),
        ]
        for control_id, active, label in toggle_items:
            rect = pygame.Rect(x, content_y, content_w, toggle_height)
            self.draw_toggle_switch(rect, active, label, control_id)
            content_y += toggle_height + 4
        content_y += 4

        # ── Section: Scenarios ───────────────────────────────────────────────
        content_y = self.draw_section_header(
            x, content_y, content_w, "Scenario Presets"
        )
        self.scenario_preset_rects = {}
        presets = [
            ("normal_day", "🌤 Normal"),
            ("rush_hour", "🚗 Rush"),
            ("special_event", "🎪 Event"),
        ]
        btn_w = (content_w - 8) // 3
        for idx, (key, label) in enumerate(presets):
            rect = pygame.Rect(x + idx * (btn_w + 4), content_y, btn_w, 26)
            pygame.draw.rect(self.screen, self.theme["panel_2"], rect, border_radius=8)
            pygame.draw.rect(
                self.screen, self.theme["border"], rect, 1, border_radius=8
            )
            self.screen.blit(
                self.small_font.render(label, True, self.theme["text"]),
                self.small_font.render(label, True, self.theme["text"])
                .get_rect(center=rect.center)
                .topleft,
            )
            self.scenario_preset_rects[key] = rect
        content_y += 34

        # ── Section: Manual Override ─────────────────────────────────────────
        content_y = self.draw_section_header(x, content_y, content_w, "Manual Override")
        self.manual_override_rects = {}
        override_dirs = [
            ("north", "↑ N"),
            ("east", "→ E"),
            ("south", "↓ S"),
            ("west", "← W"),
        ]
        dir_w = (content_w - 12) // 4
        for idx, (direction, label) in enumerate(override_dirs):
            rect = pygame.Rect(x + idx * (dir_w + 4), content_y, dir_w, 26)
            active_override = self.manual_override_direction == direction
            bg = self.theme["accent"] if active_override else self.theme["panel_2"]
            fg = (255, 255, 255) if active_override else self.theme["text"]
            pygame.draw.rect(self.screen, bg, rect, border_radius=7)
            pygame.draw.rect(
                self.screen, self.theme["border"], rect, 1, border_radius=7
            )
            txt = self.small_font.render(label, True, fg)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
            self.manual_override_rects[direction] = rect
        content_y += 32
        # Clear button
        clear_rect = pygame.Rect(x, content_y, content_w, 22)
        pygame.draw.rect(
            self.screen, self.theme["panel_2"], clear_rect, border_radius=7
        )
        pygame.draw.rect(
            self.screen, self.theme["border"], clear_rect, 1, border_radius=7
        )
        clear_txt = self.small_font.render(
            "✕ Clear Override", True, self.theme["muted"]
        )
        self.screen.blit(clear_txt, clear_txt.get_rect(center=clear_rect.center))
        self.manual_override_rects["clear"] = clear_rect
        content_y += 28

        # ── Keyboard shortcuts footer ─────────────────────────────────────────
        footer_rect = pygame.Rect(
            x - 2, self.sidebar_rect.bottom - 90, content_w + 4, 78
        )
        pygame.draw.rect(
            self.screen,
            self.theme["panel_dark"],
            footer_rect,
            border_bottom_left_radius=12,
            border_bottom_right_radius=12,
        )
        pygame.draw.rect(
            self.screen,
            self.theme["border_dark"],
            footer_rect,
            1,
            border_bottom_left_radius=12,
            border_bottom_right_radius=12,
        )
        klines = [
            "Spc pause   R reset   F fast-fwd",
            "O obstacle  C closure  W weather",
            "H rush hour  1-6 algorithm  A charts",
            "= zoom-in   - zoom-out   Esc quit",
        ]
        for i, line in enumerate(klines):
            self.screen.blit(
                self.small_font.render(line, True, self.theme["border_dark"]),
                (footer_rect.x + 8, footer_rect.y + 6 + i * 17),
            )

    def get_chart_slice(self, values, view):
        if not values:
            return []
        max_visible = max(20, int(120 / view["zoom"]))
        pan = max(0, view["pan"])
        end = max(0, len(values) - pan)
        start = max(0, end - max_visible)
        return values[start:end]

    def draw_interactive_line_chart(
        self, surface, rect, values, color, label, chart_id
    ):
        pygame.draw.rect(surface, (252, 253, 255), rect, border_radius=8)
        pygame.draw.rect(surface, self.theme["border"], rect, 1, border_radius=8)

        view = self.chart_views[chart_id]
        series = self.get_chart_slice(values, view)
        if len(series) < 2:
            surface.blit(
                self.small_font.render(label, True, self.theme["muted"]),
                (rect.x + 8, rect.y + 8),
            )
            return

        max_v = max(series)
        min_v = min(series)
        span = max(0.001, max_v - min_v)
        points = []
        for i, value in enumerate(series):
            px = rect.x + int((i / max(1, len(series) - 1)) * (rect.width - 12)) + 6
            py = rect.bottom - int(((value - min_v) / span) * (rect.height - 24)) - 6
            points.append((px, py))
        pygame.draw.lines(surface, color, False, points, 2)
        surface.blit(
            self.small_font.render(
                f"{label}  z:{view['zoom']:.1f}", True, self.theme["muted"]
            ),
            (rect.x + 7, rect.y + 5),
        )

    def draw_comparison_chart(self, surface, rect):
        pygame.draw.rect(surface, (252, 253, 255), rect, border_radius=8)
        pygame.draw.rect(surface, self.theme["border"], rect, 1, border_radius=8)
        if not self.comparison_mode:
            surface.blit(
                self.small_font.render(
                    "Comparison mode disabled", True, self.theme["muted"]
                ),
                (rect.x + 8, rect.y + 8),
            )
            return

        datasets = [
            (self.simulation.wait_time_history, (224, 93, 86), "Wait"),
            (self.simulation.throughput_history, (64, 156, 90), "Throughput"),
            (self.simulation.avg_speed_history, (82, 116, 231), "Speed"),
        ]
        view = self.chart_views["comparison"]
        for values, color, label in datasets:
            series = self.get_chart_slice(values, view)
            if len(series) < 2:
                continue
            min_v, max_v = min(series), max(series)
            span = max(0.001, max_v - min_v)
            points = []
            for i, value in enumerate(series):
                px = rect.x + int((i / max(1, len(series) - 1)) * (rect.width - 12)) + 6
                py = (
                    rect.bottom - int(((value - min_v) / span) * (rect.height - 24)) - 6
                )
                points.append((px, py))
            pygame.draw.lines(surface, color, False, points, 2)

        legend_y = rect.y + 6
        for _, color, label in datasets:
            pygame.draw.circle(surface, color, (rect.right - 92, legend_y + 6), 4)
            surface.blit(
                self.small_font.render(label, True, self.theme["muted"]),
                (rect.right - 84, legend_y),
            )
            legend_y += 16

    def render_analytics_panel(self):
        if not self.analytics_panel["visible"]:
            return

        rect = self.analytics_panel["rect"]
        self.draw_panel(rect, radius=12)

        # Dark accent header
        header_rect = pygame.Rect(rect.x, rect.y, rect.width, 36)
        pygame.draw.rect(
            self.screen,
            self.theme["panel_dark"],
            header_rect,
            border_top_left_radius=12,
            border_top_right_radius=12,
        )
        pygame.draw.rect(
            self.screen,
            self.theme["accent"],
            pygame.Rect(header_rect.x, header_rect.bottom - 2, header_rect.width, 2),
        )
        # Chart icon + title
        self.screen.blit(
            self.title_font.render(
                "📊 Realtime Analytics", True, self.theme["text_inv"]
            ),
            (header_rect.x + 10, header_rect.y + 9),
        )
        # Close button
        close_rect = pygame.Rect(header_rect.right - 26, header_rect.y + 8, 18, 18)
        pygame.draw.rect(self.screen, self.theme["danger"], close_rect, border_radius=5)
        self.screen.blit(
            self.small_font.render("✕", True, (255, 255, 255)),
            close_rect.move(3, 1).topleft,
        )
        # Register close button
        self.control_rects["analytics_close"] = close_rect
        if "analytics_close" not in self.tooltip_map:
            self.tooltip_map["analytics_close"] = "Close analytics panel (A)"

        content_rect = pygame.Rect(
            rect.x + 10, rect.y + 46, rect.width - 20, rect.height - 58
        )
        self.analytics_content_rect = content_rect

        refresh_stamp = (
            len(self.simulation.wait_time_history)
            + len(self.simulation.throughput_history)
            + len(self.simulation.avg_speed_history)
        )
        need_refresh = (
            self.analytics_cache_surface is None
            or self.analytics_cache_surface.get_size()
            != (content_rect.width, content_rect.height)
            or refresh_stamp != self.analytics_cache_stamp
            or self.analytics_panels_dirty
        )

        if need_refresh:
            self.analytics_cache_surface = pygame.Surface(
                (content_rect.width, content_rect.height), pygame.SRCALPHA
            )
            self.analytics_cache_surface.fill((0, 0, 0, 0))

            chart_w = (content_rect.width - 10) // 2
            chart_h = (content_rect.height - 12) // 2
            wait_rect = pygame.Rect(0, 0, chart_w, chart_h)
            throughput_rect = pygame.Rect(
                chart_w + 10, 0, content_rect.width - chart_w - 10, chart_h
            )
            speed_rect = pygame.Rect(
                0, chart_h + 10, chart_w, content_rect.height - chart_h - 10
            )
            compare_rect = pygame.Rect(
                chart_w + 10,
                chart_h + 10,
                content_rect.width - chart_w - 10,
                content_rect.height - chart_h - 10,
            )

            self.draw_interactive_line_chart(
                self.analytics_cache_surface,
                wait_rect,
                self.simulation.wait_time_history,
                (224, 93, 86),
                "Wait",
                "wait",
            )
            self.draw_interactive_line_chart(
                self.analytics_cache_surface,
                throughput_rect,
                self.simulation.throughput_history,
                (64, 156, 90),
                "Throughput",
                "throughput",
            )
            self.draw_interactive_line_chart(
                self.analytics_cache_surface,
                speed_rect,
                self.simulation.avg_speed_history,
                (82, 116, 231),
                "Speed",
                "speed",
            )
            self.draw_comparison_chart(self.analytics_cache_surface, compare_rect)

            self.chart_rects = {
                "wait": wait_rect.move(content_rect.topleft),
                "throughput": throughput_rect.move(content_rect.topleft),
                "speed": speed_rect.move(content_rect.topleft),
                "comparison": compare_rect.move(content_rect.topleft),
            }

            self.analytics_cache_stamp = refresh_stamp
            self.analytics_panels_dirty = False

        self.screen.blit(self.analytics_cache_surface, content_rect.topleft)

        comparison = self.simulation.algorithm_comparison
        # Compute how many rows fit (18px each)
        table_h = max(44, min(18 * len(comparison) + 10, 100))
        table_rect = pygame.Rect(
            rect.x + 12, rect.bottom - table_h - 8, rect.width - 24, table_h
        )
        pygame.draw.rect(self.screen, (252, 253, 255), table_rect, border_radius=8)
        pygame.draw.rect(
            self.screen, self.theme["border"], table_rect, 1, border_radius=8
        )
        if comparison:
            header = self.small_font.render(
                "Algorithm        Queue  Delay  Thru", True, self.theme["muted"]
            )
            self.screen.blit(header, (table_rect.x + 8, table_rect.y + 4))
            current_alg = self.simulation.traffic_controller.algorithm
            for row_idx, (name, metrics) in enumerate(list(comparison.items())[:5]):
                row_y = table_rect.y + 20 + row_idx * 16
                if row_y + 14 > table_rect.bottom:
                    break
                is_active = name == current_alg
                color = self.theme["accent"] if is_active else self.theme["text"]
                row_txt = f"{name[:12]:<12}  {metrics['avg_queue']:>5.1f}  {metrics['avg_delay']:>5.1f}  {metrics['throughput']:>5.2f}"
                self.screen.blit(
                    self.small_font.render(row_txt, True, color),
                    (table_rect.x + 8, row_y),
                )
        else:
            self.screen.blit(
                self.small_font.render(
                    "Algorithm metrics collecting...", True, self.theme["muted"]
                ),
                (table_rect.x + 8, table_rect.y + 13),
            )

        resize_rect = pygame.Rect(rect.right - 16, rect.bottom - 16, 16, 16)
        pygame.draw.polygon(
            self.screen,
            self.theme["muted"],
            [
                (resize_rect.left + 4, resize_rect.bottom - 4),
                (resize_rect.right - 4, resize_rect.bottom - 4),
                (resize_rect.right - 4, resize_rect.top + 4),
            ],
            0,
        )

    def render_status_bar(self):
        rect = pygame.Rect(10, self.height - 34, self.width - 20, 26)
        pygame.draw.rect(self.screen, self.theme["panel_dark"], rect, border_radius=8)
        pygame.draw.rect(
            self.screen, self.theme["border_dark"], rect, 1, border_radius=8
        )

        alg_label = self.format_algorithm_name(
            self.simulation.traffic_controller.algorithm
        )
        mode_tags = []
        if self.simulation.paused:
            mode_tags.append("⏸ PAUSED")
        if self.fast_forward:
            mode_tags.append("⏩ 4×")
        if self.simulation.recording:
            mode_tags.append("⏺ REC")
        if self.simulation.playback_active:
            idx = self.simulation.playback_index
            total = len(self.simulation.playback_frames)
            mode_tags.append(f"▶ PLAYBACK {idx}/{total}")

        extras = "  ".join(mode_tags)
        state = (
            f"Alg: {alg_label}   "
            f"Speed: {self.simulation.simulation_speed_factor:.2f}×   "
            f"T: {self.simulation.elapsed_time:.1f}s"
            + (f"   {extras}" if extras else "")
        )
        self.screen.blit(
            self.small_font.render(state, True, self.theme["text_inv"]),
            (rect.x + 8, rect.y + 6),
        )

        # Recording/playback progress bar on the right
        if self.simulation.recording and self.simulation.recorded_frames:
            cap = 6000
            progress = min(1.0, len(self.simulation.recorded_frames) / cap)
            bar_w = 120
            bar_rect = pygame.Rect(rect.right - bar_w - 10, rect.y + 6, bar_w, 12)
            pygame.draw.rect(self.screen, (230, 80, 80), bar_rect, border_radius=4)
            fill = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_w * progress), 12)
            pygame.draw.rect(self.screen, (200, 40, 40), fill, border_radius=4)
        elif self.simulation.playback_active and self.simulation.playback_frames:
            total = max(1, len(self.simulation.playback_frames))
            progress = self.simulation.playback_index / total
            bar_w = 120
            bar_rect = pygame.Rect(rect.right - bar_w - 10, rect.y + 6, bar_w, 12)
            pygame.draw.rect(
                self.screen, self.theme["border"], bar_rect, border_radius=4
            )
            fill = pygame.Rect(bar_rect.x, bar_rect.y, int(bar_w * progress), 12)
            pygame.draw.rect(self.screen, self.theme["accent"], fill, border_radius=4)

    def render_notifications(self):
        now = self.now()
        self.notifications = [n for n in self.notifications if n["until"] > now]
        for idx, note in enumerate(self.notifications[-4:]):
            frac = min(1.0, (note["until"] - now) / 0.4)  # fade out last 0.4s
            alpha = int(255 * frac)
            rect = pygame.Rect(self.width - 370, 52 + idx * 30, 360, 26)
            if note["kind"] == "ok":
                bg, border, fg = (40, 168, 80), (30, 130, 60), (255, 255, 255)
            elif note["kind"] == "warn":
                bg, border, fg = (220, 145, 30), (180, 110, 20), (255, 255, 255)
            elif note["kind"] == "danger":
                bg, border, fg = (210, 60, 60), (160, 30, 30), (255, 255, 255)
            else:
                bg, border, fg = (
                    self.theme["panel_dark"],
                    self.theme["border_dark"],
                    self.theme["text_inv"],
                )
            notif_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(
                notif_surf, (*bg, alpha), notif_surf.get_rect(), border_radius=8
            )
            pygame.draw.rect(
                notif_surf, (*border, alpha), notif_surf.get_rect(), 1, border_radius=8
            )
            self.screen.blit(notif_surf, rect.topleft)
            txt = self.small_font.render(note["message"], True, fg)
            txt.set_alpha(alpha)
            self.screen.blit(txt, (rect.x + 10, rect.y + 6))

    def render_tooltip(self):
        if not self.hover_tooltip:
            return
        pos = pygame.mouse.get_pos()
        text = self.small_font.render(self.hover_tooltip, True, self.theme["text"])
        rect = pygame.Rect(
            pos[0] + 14, pos[1] + 14, text.get_width() + 12, text.get_height() + 8
        )
        if rect.right > self.width - 10:
            rect.x = self.width - rect.width - 10
        if rect.bottom > self.height - 10:
            rect.y = self.height - rect.height - 10
        pygame.draw.rect(self.screen, self.theme["panel_2"], rect, border_radius=7)
        pygame.draw.rect(self.screen, self.theme["border"], rect, 1, border_radius=7)
        self.screen.blit(text, (rect.x + 6, rect.y + 4))

    def render(self):
        self.recenter_camera()
        self.screen.fill(self.theme["bg"])
        self.last_frame_time = self.now()

        # Subtle city-block grid pattern at the background level
        tile = 64
        for ty in range(0, self.height, tile):
            for tx in range(0, self.width, tile):
                c = (
                    self.theme["bg_a"]
                    if ((tx // tile + ty // tile) % 2 == 0)
                    else self.theme["bg_b"]
                )
                pygame.draw.rect(self.screen, c, pygame.Rect(tx, ty, tile, tile))
        # Fine grid lines for a city-map feel
        grid_col = (28, 36, 48)
        for tx in range(0, self.width, tile):
            pygame.draw.line(self.screen, grid_col, (tx, 0), (tx, self.height), 1)
        for ty in range(0, self.height, tile):
            pygame.draw.line(self.screen, grid_col, (0, ty), (self.width, ty), 1)

        self.render_day_night_overlay()
        self.render_weather_effects()

        if self.show_heatmap:
            self.render_heatmap()

        self.simulation.intersection.draw(self.screen, self.camera_offset, self.scale)
        ordered_vehicles = sorted(
            self.simulation.vehicles,
            key=lambda vehicle: (vehicle.position[1], vehicle.position[0]),
        )
        for vehicle in ordered_vehicles:
            vehicle.draw(self.screen, self.camera_offset, self.scale)
        for light in self.simulation.traffic_lights.values():
            light.draw(self.screen, self.camera_offset, self.scale)

        self.render_pedestrian_signals()
        self.render_minimap()

        self.draw_toolbar()
        self.draw_sidebar()
        if self.show_stats_card:
            self.render_stats_card()
        self.render_analytics_panel()
        self.render_status_bar()
        self.render_notifications()
        self.render_tooltip()

    def render_stats_card(self):
        stats_x = self.sidebar_rect.right + 10
        stats_rect = pygame.Rect(stats_x, self.height - 300, 350, 262)
        self.draw_panel(stats_rect, radius=14)

        # Header band
        hdr = pygame.Rect(stats_rect.x, stats_rect.y, stats_rect.width, 32)
        pygame.draw.rect(self.screen, self.theme["accent"], hdr, border_radius=14)
        pygame.draw.rect(
            self.screen,
            self.theme["accent"],
            pygame.Rect(hdr.x, hdr.bottom - 14, hdr.width, 14),
        )
        self.screen.blit(
            self.title_font.render("Simulation Stats", True, (255, 255, 255)),
            (hdr.x + 12, hdr.y + 8),
        )

        dashboard = self.simulation.get_dashboard_metrics()
        active_lights = (
            ", ".join(
                [
                    d[0].upper()
                    for d, light in self.simulation.traffic_lights.items()
                    if light.state.name == "GREEN"
                ]
            )
            or "None"
        )

        weather_icons = {"clear": "☀", "rain": "☂", "fog": "~", "snow": "*"}
        weather_icon = weather_icons.get(dashboard["weather"], "")

        phase_name = dashboard.get("current_phase", "unknown").replace("_", " ").upper()
        phase_rem = dashboard.get("phase_remaining", 0.0)
        safety_count = dashboard.get("safety_violations", 0)
        safety_txt = (
            "Safety: OK"
            if safety_count == 0
            else f"Safety: {safety_count} violation(s)"
        )
        safety_color = self.theme["ok"] if safety_count == 0 else self.theme["danger"]

        queue = dashboard["queue_lengths"]
        mix = dashboard.get("vehicle_mix", {})
        mix_str = "  ".join(f"{k[0]}:{v}" for k, v in mix.items() if v > 0)

        lines = [
            (
                f"Vehicles: {dashboard['vehicles_total']}  Exited: {dashboard['exited_total']}",
                self.theme["text"],
            ),
            (f"Elapsed: {self.simulation.elapsed_time:.0f}s", self.theme["muted"]),
            (
                f"Avg Wait: {dashboard['avg_wait']:.2f}s   Throughput: {dashboard['throughput']:.2f}/s",
                self.theme["text"],
            ),
            (f"Queue  NS:{queue['ns']}  EW:{queue['ew']}", self.theme["text"]),
            (f"Avg Speed: {dashboard['avg_speed']:.1f} m/s", self.theme["muted"]),
            (
                f"Close Calls: {dashboard['close_calls']}   Pedestrians: {dashboard['pedestrians']}",
                (
                    self.theme["warn"]
                    if dashboard["close_calls"] > 0
                    else self.theme["muted"]
                ),
            ),
            (f"Green dirs: {active_lights}", self.theme["ok"]),
            (f"Phase: {phase_name}  {phase_rem:.1f}s left", self.theme["accent"]),
            (
                f"Weather: {weather_icon}{dashboard['weather'].title()}  Rush: {'ON' if dashboard['rush_hour'] else 'off'}",
                self.theme["muted"],
            ),
            (f"Mix: {mix_str}" if mix_str else "Mix: —", self.theme["muted"]),
        ]
        for idx, (line, color) in enumerate(lines):
            self.screen.blit(
                self.small_font.render(line, True, color),
                (stats_rect.x + 12, stats_rect.y + 40 + idx * 17),
            )

        # Safety status bar
        safety_bar = pygame.Rect(
            stats_rect.x + 8, stats_rect.bottom - 28, stats_rect.width - 16, 20
        )
        pygame.draw.rect(self.screen, safety_color, safety_bar, border_radius=7)
        self.screen.blit(
            self.small_font.render(safety_txt, True, (255, 255, 255)),
            (safety_bar.x + 10, safety_bar.y + 3),
        )

    def render_heatmap(self):
        if not self.simulation.congestion_heatmap:
            return
        max_intensity = max(self.simulation.congestion_heatmap.values())
        for (gx, gy), value in self.simulation.congestion_heatmap.items():
            intensity = value / max(1, max_intensity)
            alpha = int(40 + 120 * intensity)
            color = (255, int(170 - 130 * intensity), 40, alpha)
            wx = (gx * 4 + 2) * self.scale + self.camera_offset[0]
            wy = (gy * 4 + 2) * self.scale + self.camera_offset[1]
            radius = int(max(2, 2 + 6 * intensity))
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (radius, radius), radius)
            self.screen.blit(surf, (wx - radius, wy - radius))

    def render_day_night_overlay(self):
        phase = (
            self.simulation.elapsed_time % self.day_night_cycle_seconds
        ) / self.day_night_cycle_seconds
        daylight = 0.5 + 0.5 * math.sin((phase * 2 * math.pi) - math.pi / 2)
        darkness = int((1.0 - daylight) * 120)
        if darkness > 5:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((14, 24, 48, darkness))
            self.screen.blit(overlay, (0, 0))

    def render_weather_effects(self):
        weather = self.simulation.weather_mode
        if weather == "clear":
            self.weather_particles = []
            return

        max_particles = 90 if weather == "rain" else 65
        while len(self.weather_particles) < max_particles:
            self.weather_particles.append(
                {
                    "x": float(pygame.time.get_ticks() % max(1, self.width)),
                    "y": float((pygame.time.get_ticks() * 0.37) % max(1, self.height)),
                    "vx": -1.5 if weather == "rain" else -0.5,
                    "vy": 6.0 if weather == "rain" else 2.0,
                    "len": 10 if weather == "rain" else 3,
                }
            )

        for particle in self.weather_particles:
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]
            if particle["y"] > self.height + 4 or particle["x"] < -4:
                particle["x"] = float(
                    (pygame.time.get_ticks() * 0.13) % max(1, self.width)
                )
                particle["y"] = -5.0

            if weather == "rain":
                pygame.draw.line(
                    self.screen,
                    (170, 205, 255, 140),
                    (int(particle["x"]), int(particle["y"])),
                    (int(particle["x"] + 2), int(particle["y"] + particle["len"])),
                    1,
                )
            elif weather == "snow":
                pygame.draw.circle(
                    self.screen,
                    (245, 245, 255, 180),
                    (int(particle["x"]), int(particle["y"])),
                    2,
                )
            elif weather == "fog":
                fog = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                fog.fill((225, 228, 233, 45))
                self.screen.blit(fog, (0, 0))
                break

    def render_pedestrian_signals(self):
        signals = getattr(self.simulation, "pedestrian_signals", {})
        for signal in signals.values():
            sx = signal.position[0] * self.scale + self.camera_offset[0]
            sy = signal.position[1] * self.scale + self.camera_offset[1]
            housing = pygame.Rect(int(sx - 8), int(sy - 10), 16, 20)
            pygame.draw.rect(self.screen, (28, 30, 34), housing, border_radius=3)
            color = (70, 220, 90) if signal.walk else (220, 70, 70)
            pygame.draw.circle(self.screen, color, (int(sx), int(sy)), 4)

    def render_minimap(self):
        map_rect = pygame.Rect(self.width - 200, 392, 190, 190)
        self.draw_panel(map_rect, radius=10)
        title = self.small_font.render("Mini-map", True, self.theme["text"])
        self.screen.blit(title, (map_rect.x + 8, map_rect.y + 6))

        min_x, min_y, max_x, max_y = self.simulation.intersection.bounds
        w = max(1, max_x - min_x)
        h = max(1, max_y - min_y)

        def to_map(point):
            px = map_rect.x + 10 + int(((point[0] - min_x) / w) * (map_rect.width - 20))
            py = (
                map_rect.y + 24 + int(((point[1] - min_y) / h) * (map_rect.height - 34))
            )
            return px, py

        cx, cy = self.simulation.intersection.center
        rx1, ry1 = to_map((min_x, cy))
        rx2, ry2 = to_map((max_x, cy))
        pygame.draw.line(self.screen, (85, 88, 95), (rx1, ry1), (rx2, ry2), 5)
        vx1, vy1 = to_map((cx, min_y))
        vx2, vy2 = to_map((cx, max_y))
        pygame.draw.line(self.screen, (85, 88, 95), (vx1, vy1), (vx2, vy2), 5)

        for vehicle in self.simulation.vehicles:
            mx, my = to_map(vehicle.position)
            pygame.draw.circle(self.screen, (60, 120, 230), (mx, my), 2)

        for obstacle in self.simulation.obstacles:
            mx, my = to_map(obstacle["position"])
            pygame.draw.circle(self.screen, (240, 140, 45), (mx, my), 2)
