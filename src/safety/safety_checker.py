# src/safety/safety_checker.py
import logging

from simulation.traffic_light import LightState


LOGGER = logging.getLogger(__name__)

class SafetyChecker:
    """
    Checks traffic light states for safety violations.
    Ensures that conflicting directions don't have green lights simultaneously.
    """
    def __init__(self):
        # Define conflicting directions
        self.conflicts = {
            "north": ["east", "west"],
            "south": ["east", "west"],
            "east": ["north", "south"],
            "west": ["north", "south"]
        }
    
    def check_states(self, states):
        """
        Check if a set of traffic light states is safe.
        
        Args:
            states: Dictionary mapping directions to light states
            
        Returns:
            True if safe, False if unsafe
        """
        # Check for conflicting green or yellow lights
        for direction, state in states.items():
            if state in [LightState.GREEN, LightState.YELLOW]:
                # Check if any conflicting direction also has green or yellow
                for conflict in self.conflicts.get(direction, []):
                    if conflict in states and states[conflict] in [LightState.GREEN, LightState.YELLOW]:
                        LOGGER.warning(
                            "Safety violation: conflicting directions cannot both be green/yellow",
                            extra={"direction": direction, "conflict": conflict},
                        )
                        return False
        
        return True
    
    def check_transition(self, current_states, new_states):
        """
        Check if a transition between states is safe.
        
        Args:
            current_states: Dictionary of current light states
            new_states: Dictionary of new light states
            
        Returns:
            True if the transition is safe, False otherwise
        """
        # Check if the new states are safe
        if not self.check_states(new_states):
            return False
        
        # Check for unsafe transitions (e.g., skipping yellow)
        for direction, new_state in new_states.items():
            if direction in current_states:
                current = current_states[direction]
                
                # Cannot go directly from GREEN to RED (must go through YELLOW)
                if current == LightState.GREEN and new_state == LightState.RED:
                    LOGGER.warning(
                        "Safety violation: direct GREEN to RED transition",
                        extra={"direction": direction},
                    )
                    return False
        
        return True