"""
FishSchool entity for FishSwarm.
Represents a stationary biomass cluster with unique identity, single-operation
claim locking, combined harvesting, and clean depletion lifecycle.
"""
from typing import Optional
import pygame
from src.config import (
    DEFAULT_SCHOOL_POPULATION,
    BASE_HARVEST_RATE,
    FISHING_RADIUS,
    COLOR_FISH_SCHOOL,
    COLOR_FISH_DEPLETED,
    COLOR_TEXT,
)

class FishSchool:
    """
    A stationary fish school with unique ID, population tracking,
    operation claim management, and safe cooperative harvesting.
    """
    _next_id = 1

    def __init__(
        self,
        position: tuple[float, float] | pygame.Vector2,
        population: float = DEFAULT_SCHOOL_POPULATION,
        school_id: Optional[int] = None,
    ):
        if school_id is not None:
            self.school_id = int(school_id)
            if self.school_id >= FishSchool._next_id:
                FishSchool._next_id = self.school_id + 1
        else:
            self.school_id = FishSchool._next_id
            FishSchool._next_id += 1

        self.position = pygame.Vector2(position[0], position[1])
        self.initial_population = float(max(0.0, population))
        self.population = self.initial_population
        
        # Single active operation claim lock
        self.assigned_operation_id: Optional[str] = None
        self.is_depleted: bool = (self.population <= 0.0)
        self.radius = self._calculate_visual_radius()

    @classmethod
    def reset_id_counter(cls, start_id: int = 1):
        """Resets ID counter for deterministic testing."""
        cls._next_id = start_id

    def _calculate_visual_radius(self) -> float:
        """Visual radius proportional to current population (10 to 30 pixels)."""
        if self.initial_population <= 0 or self.population <= 0:
            return 8.0
        ratio = max(0.0, min(1.0, self.population / self.initial_population))
        return 10.0 + 20.0 * ratio

    def claim(self, operation_id: str) -> bool:
        """
        Atomically claims this fish school for a specific fishing operation.
        Fails if already claimed by another operation or if depleted.
        """
        if self.is_depleted or self.population <= 0:
            return False
        if self.assigned_operation_id is not None:
            return self.assigned_operation_id == operation_id
        self.assigned_operation_id = str(operation_id)
        return True

    def release(self, operation_id: str) -> bool:
        """
        Releases the claim on this school if the calling operation holds it.
        """
        if self.assigned_operation_id == str(operation_id):
            self.assigned_operation_id = None
            return True
        return False

    def is_available(self) -> bool:
        """Returns True if the school is alive and unassigned."""
        return not self.is_depleted and self.assigned_operation_id is None and self.population > 0

    def apply_harvest(
        self,
        operation_id: str,
        active_boat_count: int,
        delta_time: float,
        base_harvest_rate: float = BASE_HARVEST_RATE,
    ) -> float:
        """
        Applies a combined harvest step from active fishing boats.
        Ensures:
        - Only the claimed operation can harvest.
        - Harvest amount = base_harvest_rate * active_boat_count * delta_time.
        - Population is clamped at 0.0 and never goes negative.
        - Marks school depleted when population hits 0.
        Returns the actual harvested amount.
        """
        # Reject unauthorized or invalid operations
        if self.is_depleted or self.population <= 0.0:
            self.is_depleted = True
            return 0.0
            
        if self.assigned_operation_id != str(operation_id):
            return 0.0

        if active_boat_count <= 0 or delta_time <= 0.0:
            return 0.0

        # Calculate combined harvest once per update
        potential_harvest = float(base_harvest_rate) * float(active_boat_count) * float(delta_time)
        actual_harvest = min(self.population, potential_harvest)

        self.population = max(0.0, self.population - actual_harvest)
        self.radius = self._calculate_visual_radius()

        if self.population <= 0.0:
            self.is_depleted = True

        return actual_harvest

    def draw(self, surface: pygame.Surface, font: Optional[pygame.font.Font] = None, show_debug: bool = False):
        """Renders the fish school."""
        center = (int(self.position.x), int(self.position.y))
        radius = int(self.radius)

        if self.is_depleted:
            pygame.draw.circle(surface, COLOR_FISH_DEPLETED, center, radius, 1)
        else:
            # Concentric rings to give a pulsing biological school appearance
            pygame.draw.circle(surface, COLOR_FISH_SCHOOL, center, radius)
            pygame.draw.circle(surface, (255, 230, 130), center, max(3, radius - 4))
            
            # Show fishing radius boundary if active
            if show_debug or self.assigned_operation_id is not None:
                pygame.draw.circle(surface, (255, 200, 50, 100), center, int(FISHING_RADIUS), 1)

        if font is not None:
            pop_text = f"S{self.school_id}: {int(self.population)}"
            text_surf = font.render(pop_text, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=(center[0], center[1] - radius - 10))
            surface.blit(text_surf, text_rect)
