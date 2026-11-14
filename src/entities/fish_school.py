"""
FishSchool entity for FishSwarm.
Represents a stationary biomass cluster with unique identity, single-operation
claim locking, combined harvesting, and clean depletion lifecycle.
"""
from typing import Optional
import math
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

    def respawn(self) -> bool:
        """Restore a depleted school to its original population after its recovery delay."""
        if self.initial_population <= 0 or not self.is_depleted:
            return False
        self.population = self.initial_population
        self.is_depleted = False
        self.assigned_operation_id = None
        self.radius = self._calculate_visual_radius()
        return True

    def apply_harvest(
        self,
        operation_id: str,
        active_boat_count: int,
        delta_time: float,
        base_harvest_rate: float = BASE_HARVEST_RATE,
        harvest_limit: Optional[float] = None,
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
        if harvest_limit is not None:
            actual_harvest = min(actual_harvest, max(0.0, float(harvest_limit)))

        self.population = max(0.0, self.population - actual_harvest)
        self.radius = self._calculate_visual_radius()

        if self.population <= 0.0:
            self.is_depleted = True

        return actual_harvest

    def draw(
        self,
        surface: pygame.Surface,
        font: Optional[pygame.font.Font] = None,
        show_debug: bool = False,
        sim_time: float = 0.0,
    ):
        """Render a softly moving cluster of individual fish silhouettes."""
        center = (int(self.position.x), int(self.position.y))
        school_radius = max(5.0, self.radius * 0.78)
        population_ratio = (self.population / self.initial_population
                            if self.initial_population > 0 else 0.0)
        fish_count = 3 if self.is_depleted else max(7, min(20, 7 + int(population_ratio * 13)))
        fish_color = COLOR_FISH_DEPLETED if self.is_depleted else COLOR_FISH_SCHOOL

        for index in range(fish_count):
            base_angle = index * 2.399963 + self.school_id * 0.71
            orbit = school_radius * math.sqrt((index + 0.5) / fish_count)
            drift = sim_time * (0.32 + (index % 4) * 0.035) + index * 1.7
            angle = base_angle + math.sin(drift + self.school_id) * 0.12
            radius = orbit + math.sin(drift * 1.4) * 1.4
            point = self.position + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
            heading = angle + math.pi / 2 + math.sin(drift) * 0.18
            forward = pygame.Vector2(math.cos(heading), math.sin(heading))
            side = pygame.Vector2(-forward.y, forward.x)
            size = 4.2 if self.is_depleted else 4.4 + min(1.2, population_ratio)
            body = [point + forward * size,
                    point + forward * (size * 0.25) + side * (size * 0.48),
                    point - forward * (size * 0.58) + side * (size * 0.32),
                    point - forward * (size * 0.58) - side * (size * 0.32),
                    point + forward * (size * 0.25) - side * (size * 0.48)]
            tail = [point - forward * (size * 0.48),
                    point - forward * size - side * (size * 0.38),
                    point - forward * size + side * (size * 0.38)]
            pygame.draw.polygon(surface, fish_color,
                                [(round(p.x), round(p.y)) for p in body])
            pygame.draw.polygon(surface, fish_color,
                                [(round(p.x), round(p.y)) for p in tail])
            if not self.is_depleted:
                eye = point + forward * (size * 0.48) + side * (size * 0.12)
                pygame.draw.circle(surface, (255, 244, 206), (round(eye.x), round(eye.y)), 1)

        # A faint current ring helps show the school's changing density without
        # replacing its fish silhouettes with a static marker.
        halo_radius = max(7, round(self.radius + math.sin(sim_time * 1.7 + self.school_id) * 1.4))
        halo_color = (117, 144, 151) if self.is_depleted else (247, 204, 112)
        pygame.draw.circle(surface, halo_color, center, halo_radius, 1)

        if not self.is_depleted and (show_debug or self.assigned_operation_id is not None):
            pygame.draw.circle(surface, (255, 200, 50, 100), center, int(FISHING_RADIUS), 1)

        if font is not None:
            pop_text = f"S{self.school_id}: {int(self.population)}"
            text_surf = font.render(pop_text, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=(center[0], center[1] - halo_radius - 10))
            surface.blit(text_surf, text_rect)
