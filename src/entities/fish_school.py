"""
FishSchool entity for FishSwarm.
Represents a stationary biomass cluster with unique identity, single-operation
claim locking, combined harvesting, and clean depletion lifecycle.
"""
from typing import Optional
import math
import random
import pygame
from src.config import (
    DEFAULT_SCHOOL_POPULATION,
    BASE_HARVEST_RATE,
    FISH_POPULATION_SCALE,
    COLOR_FISH_DEPLETED,
    COLOR_TEXT,
    FISH_COLORS,
    normalize_fish_color,
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
        color: Optional[tuple[int, int, int] | str] = None,
    ):
        if school_id is not None:
            self.school_id = int(school_id)
            if self.school_id >= FishSchool._next_id:
                FishSchool._next_id = self.school_id + 1
        else:
            self.school_id = FishSchool._next_id
            FishSchool._next_id += 1

        self.position = pygame.Vector2(position[0], position[1])
        biomass_variation = random.uniform(0.65, 1.35) if population > 0 else 1.0
        self.initial_population = (float(max(0.0, population))
                                   * FISH_POPULATION_SCALE * biomass_variation)
        self.population = self.initial_population
        
        # Color initialization: random palette choice if None, otherwise normalized
        if color is None:
            self.color = random.choice(FISH_COLORS)
        else:
            self.color = normalize_fish_color(color)

        # Single active operation claim lock
        self.assigned_operation_id: Optional[str] = None
        self.is_depleted: bool = (self.population <= 0.0)
        self.radius = self._calculate_visual_radius()

    @classmethod
    def reset_id_counter(cls, start_id: int = 1):
        """Resets ID counter for deterministic testing."""
        cls._next_id = start_id

    def _calculate_visual_radius(self) -> float:
        """Scale pond size with its biomass and shrink it as fish are harvested."""
        if self.initial_population <= 0 or self.population <= 0:
            return 8.0
        ratio = max(0.0, min(1.0, self.population / self.initial_population))
        minimum_radius = 7.0 + self.initial_population * .07
        maximum_radius = min(38.0, 18.0 + self.initial_population * .32)
        return minimum_radius + (maximum_radius - minimum_radius) * ratio

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
        minimal: bool = False,
    ):
        """Render a softly moving cluster of individual fish silhouettes."""
        center = (int(self.position.x), int(self.position.y))
        school_radius = max(8.0, self.radius)
        population_ratio = (self.population / self.initial_population
                            if self.initial_population > 0 else 0.0)
        original_fish_count = (3 if self.is_depleted
                               else max(7, min(20, 7 + int(population_ratio * 13))))
        fish_count = original_fish_count
        source_fish_color = COLOR_FISH_DEPLETED if self.is_depleted else self.color
        spin_direction = -1 if self.school_id % 2 else 1
        spin_speed = .62 + (self.school_id % 5) * .055

        for index in range(fish_count):
            ring = index % 3
            ring_count = (fish_count + 2 - ring) // 3
            ring_slot = index // 3
            base_angle = (ring_slot / max(1, ring_count)) * math.tau + ring * .34
            angle = (base_angle + self.school_id * .71
                     + spin_direction * sim_time * spin_speed)
            orbit = school_radius * (.32 + ring * .26)
            radius = orbit + math.sin(sim_time * 1.3 + index * 1.9) * .65
            point = self.position + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
            depth = max(0.0, min(1.0, point.y / max(1, surface.get_height())))
            water_tint = (round(8 + 16 * depth), round(31 + 60 * depth),
                          round(51 + 60 * depth))
            fish_color = tuple(round((source_fish_color[channel] * .58
                                      + water_tint[channel] * .42)
                                     * (.84 + .08 * depth))
                                for channel in range(3))
            heading = angle + spin_direction * math.pi / 2
            heading += math.sin(sim_time * 1.1 + index) * .08
            forward = pygame.Vector2(math.cos(heading), math.sin(heading))
            side = pygame.Vector2(-forward.y, forward.x)
            base_size = 4.8 if self.is_depleted else 5.0 + min(1.4, population_ratio)
            size_variation = .78 + ((index * 5 + self.school_id * 3) % 8) * .06
            size = base_size * size_variation
            body = [
                point + forward * size,
                point + forward * (size * .66) + side * (size * .22),
                point + forward * (size * .24) + side * (size * .39),
                point - forward * (size * .30) + side * (size * .34),
                point - forward * (size * .58) + side * (size * .18),
                point - forward * (size * .58) - side * (size * .18),
                point - forward * (size * .30) - side * (size * .34),
                point + forward * (size * .24) - side * (size * .39),
                point + forward * (size * .66) - side * (size * .22),
            ]
            tail = [
                point - forward * (size * .46) + side * (size * .19),
                point - forward * (size * 1.02) + side * (size * .43),
                point - forward * (size * .84),
                point - forward * (size * 1.02) - side * (size * .43),
                point - forward * (size * .46) - side * (size * .19),
            ]
            outline = tuple(round(fish_color[channel] * .42 + water_tint[channel] * .58)
                            for channel in range(3))
            body_points = [(round(p.x), round(p.y)) for p in body]
            tail_points = [(round(p.x), round(p.y)) for p in tail]
            pygame.draw.polygon(surface, fish_color, body_points)
            pygame.draw.polygon(surface, outline, body_points, 1)
            pygame.draw.polygon(surface, fish_color, tail_points)
            pygame.draw.polygon(surface, outline, tail_points, 1)

            dorsal_fin = [
                point + forward * (size * .18) + side * (size * .34),
                point - forward * (size * .12) + side * (size * .59),
                point - forward * (size * .37) + side * (size * .31),
            ]
            fin_points = [(round(p.x), round(p.y)) for p in dorsal_fin]
            pygame.draw.polygon(surface, fish_color, fin_points)
            pygame.draw.polygon(surface, outline, fin_points, 1)
            pectoral_fin = [
                point + forward * (size * .04) + side * (size * .23),
                point - forward * (size * .20) + side * (size * .52),
                point - forward * (size * .32) + side * (size * .19),
            ]
            pectoral_points = [(round(p.x), round(p.y)) for p in pectoral_fin]
            pygame.draw.polygon(surface, fish_color, pectoral_points)
            pygame.draw.polygon(surface, outline, pectoral_points, 1)
            gill_outer = point + forward * (size * .45) + side * (size * .25)
            gill_inner = point + forward * (size * .33) - side * (size * .12)
            pygame.draw.line(surface, outline,
                             (round(gill_outer.x), round(gill_outer.y)),
                             (round(gill_inner.x), round(gill_inner.y)), 1)
            highlight_start = point + forward * (size * .42) + side * (size * .22)
            highlight_end = point - forward * (size * .16) + side * (size * .29)
            pygame.draw.line(surface, (117, 164, 171),
                             (round(highlight_start.x), round(highlight_start.y)),
                             (round(highlight_end.x), round(highlight_end.y)), 1)
        if font is not None and not minimal:
            pop_text = f"S{self.school_id}: {int(self.population)}"
            text_surf = font.render(pop_text, True, COLOR_TEXT)
            text_rect = text_surf.get_rect(center=(center[0], center[1] - round(school_radius) - 10))
            surface.blit(text_surf, text_rect)
