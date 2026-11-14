"""
WorldCoordinator for FishSwarm.
Manages ocean boundaries, entity registries, and shared exploration target reservations.
"""
from typing import Optional
import pygame
from src.core.world import OceanBounds
from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, OCEAN_MARGIN, EXPLORATION_CELL_SIZE

class WorldCoordinator:
    """
    Coordinates global ocean environment, bounds, and shared exploration cell reservations
    to prevent boats from unnecessary search overlap.
    """
    
    def __init__(self, width: float = OCEAN_WIDTH, height: float = OCEAN_HEIGHT, margin: float = OCEAN_MARGIN):
        self.bounds = OceanBounds(width, height, margin)
        # Mapping: boat_id -> (target_pos: pygame.Vector2, reservation_radius: float)
        self._target_reservations: dict[int, pygame.Vector2] = {}

    def is_target_reserved_by_other(
        self,
        boat_id: int,
        target_pos: pygame.Vector2,
        min_separation: float = EXPLORATION_CELL_SIZE * 0.75,
    ) -> bool:
        """
        Checks if target_pos is within min_separation of another boat's reserved target.
        """
        for other_id, other_target in self._target_reservations.items():
            if other_id != boat_id:
                if target_pos.distance_to(other_target) < min_separation:
                    return True
        return False

    def reserve_exploration_target(
        self,
        boat_id: int,
        target_pos: pygame.Vector2,
        min_separation: float = EXPLORATION_CELL_SIZE * 0.75,
    ) -> bool:
        """
        Attempts to reserve target_pos for boat_id.
        Fails if another boat already reserved a target within min_separation.
        """
        if self.is_target_reserved_by_other(boat_id, target_pos, min_separation):
            return False
        
        self._target_reservations[boat_id] = pygame.Vector2(target_pos)
        return True

    def release_exploration_target(self, boat_id: int):
        """Releases the target reservation held by boat_id."""
        self._target_reservations.pop(boat_id, None)

    def get_reserved_target(self, boat_id: int) -> Optional[pygame.Vector2]:
        """Returns the current target reserved by boat_id, if any."""
        return self._target_reservations.get(boat_id)

    def clear_all_reservations(self):
        """Clears all exploration target reservations."""
        self._target_reservations.clear()
