# src/data/data_manager.py
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)

class DataManager:
    """
    Manages data persistence for the simulation.
    Handles saving and loading intersection layouts, simulation states, and recordings.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.scenario_dir = os.path.join(self.data_dir, "scenarios")
        self.export_dir = os.path.join(self.data_dir, "exports")
        self.ensure_data_directory()
        
        # Current recording data
        self.recording = False
        self.record_data: List[Dict[str, Any]] = []
        self.record_start_time = 0
    
    def ensure_data_directory(self) -> None:
        """Ensure the data directory exists."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            LOGGER.info("Created data directory", extra={"data_dir": self.data_dir})
        os.makedirs(self.scenario_dir, exist_ok=True)
        os.makedirs(self.export_dir, exist_ok=True)
    
    def save_intersection(self, intersection: Any, name: str) -> None:
        """
        Save an intersection layout to a file.
        
        Args:
            intersection: The intersection object to save
            name: Name for the saved intersection
        """
        # Create a dictionary with intersection properties
        data = {
            "width": intersection.width,
            "height": intersection.height,
            "center": intersection.center,
            "road_width": intersection.road_width,
            "bounds": intersection.bounds,
            "entry_points": intersection.entry_points,
            "exit_points": intersection.exit_points,
            "traffic_light_positions": intersection.traffic_light_positions
        }
        
        # Save to file
        filename = os.path.join(self.data_dir, f"intersection_{name}.json")
        with open(filename, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2)

        LOGGER.info("Saved intersection", extra={"file": filename})
    
    def load_intersection(self, name: str) -> Optional[Any]:
        """
        Load an intersection layout from a file.
        
        Args:
            name: Name of the intersection to load
            
        Returns:
            An Intersection object, or None if the file doesn't exist
        """
        from simulation.intersection import Intersection
        
        filename = os.path.join(self.data_dir, f"intersection_{name}.json")
        if not os.path.exists(filename):
            LOGGER.warning("Intersection file not found", extra={"file": filename})
            return None
        
        with open(filename, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        
        # Create a new intersection with the loaded properties
        intersection = Intersection(data["width"], data["height"])
        intersection.center = tuple(data["center"])
        intersection.road_width = data["road_width"]
        intersection.bounds = tuple(data["bounds"])
        
        # Convert string keys back to tuples where needed
        intersection.entry_points = {k: tuple(v) for k, v in data["entry_points"].items()}
        intersection.exit_points = {k: tuple(v) for k, v in data["exit_points"].items()}
        intersection.traffic_light_positions = {k: tuple(v) for k, v in data["traffic_light_positions"].items()}
        
        LOGGER.info("Loaded intersection", extra={"file": filename})
        return intersection
    
    def start_recording(self) -> None:
        """Start recording the simulation state."""
        self.recording = True
        self.record_data = []
        self.record_start_time = time.time()
        LOGGER.info("Started recording simulation")
    
    def stop_recording(self) -> List[Dict[str, Any]]:
        """Stop recording and return the recorded data."""
        self.recording = False
        LOGGER.info("Stopped recording", extra={"frames": len(self.record_data)})
        return self.record_data
    
    def record_frame(self, simulation: Any) -> None:
        """
        Record the current state of the simulation.
        
        Args:
            simulation: The simulation object to record
        """
        if not self.recording:
            return
        
        # Create a snapshot of the current state
        frame = {
            "timestamp": time.time() - self.record_start_time,
            "vehicles": [self._serialize_vehicle(v) for v in simulation.vehicles],
            "traffic_lights": {
                direction: light.state.name
                for direction, light in simulation.traffic_lights.items()
            }
        }
        
        self.record_data.append(frame)
    
    def _serialize_vehicle(self, vehicle: Any) -> Dict[str, Any]:
        """
        Convert a vehicle object to a serializable dictionary.
        
        Args:
            vehicle: The vehicle to serialize
            
        Returns:
            Dictionary representation of the vehicle
        """
        return {
            "id": id(vehicle),  # Use object ID as unique identifier
            "type": vehicle.vehicle_type.name,
            "position": vehicle.position,
            "direction": vehicle.direction,
            "target_direction": vehicle.target_direction,
            "velocity": vehicle.velocity,
            "rotation": vehicle.rotation
        }
    
    def save_recording(self, name: str) -> None:
        """
        Save the current recording to a file.
        
        Args:
            name: Name for the saved recording
        """
        if not self.record_data:
            LOGGER.warning("No recording data to save")
            return
        
        filename = os.path.join(self.data_dir, f"recording_{name}.json")
        with open(filename, "w", encoding="utf-8") as file_obj:
            json.dump(self.record_data, file_obj, indent=2)

        LOGGER.info("Saved recording", extra={"file": filename})
    
    def load_recording(self, name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load a recording from a file.
        
        Args:
            name: Name of the recording to load
            
        Returns:
            List of recorded frames, or None if the file doesn't exist
        """
        filename = os.path.join(self.data_dir, f"recording_{name}.json")
        if not os.path.exists(filename):
            LOGGER.warning("Recording file not found", extra={"file": filename})
            return None
        
        with open(filename, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)

        LOGGER.info("Loaded recording", extra={"file": filename, "frames": len(data)})
        return data

    def save_scenario(self, scenario_name: str, payload: Dict[str, Any]) -> str:
        """Save a simulation scenario payload."""
        path = os.path.join(self.scenario_dir, f"{scenario_name}.json")
        with open(path, "w", encoding="utf-8") as scenario_file:
            json.dump(payload, scenario_file, indent=2)
        return path

    def load_scenario(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """Load scenario payload by name."""
        path = os.path.join(self.scenario_dir, f"{scenario_name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as scenario_file:
            return json.load(scenario_file)

    def list_scenarios(self) -> List[str]:
        """List all available scenario names."""
        names = []
        for file_name in os.listdir(self.scenario_dir):
            if file_name.endswith(".json"):
                names.append(file_name[:-5])
        return sorted(names)

    def get_preconfigured_scenarios(self) -> Dict[str, Dict[str, Any]]:
        """Return built-in scenario templates."""
        return {
            "normal_day": {
                "traffic_density_factor": 1.0,
                "rush_hour_mode": False,
                "weather_mode": "clear",
                "algorithm": "adaptive"
            },
            "rush_hour": {
                "traffic_density_factor": 1.9,
                "rush_hour_mode": True,
                "weather_mode": "clear",
                "algorithm": "traffic_responsive"
            },
            "special_event": {
                "traffic_density_factor": 2.2,
                "rush_hour_mode": True,
                "weather_mode": "rain",
                "algorithm": "ml_optimized"
            }
        }

    def export_simulation_results(self, file_name: str, payload: Dict[str, Any]) -> str:
        """Write simulation analytics payload to export directory."""
        output_path = os.path.join(self.export_dir, file_name)
        with open(output_path, "w", encoding="utf-8") as export_file:
            json.dump(payload, export_file, indent=2)
        return output_path