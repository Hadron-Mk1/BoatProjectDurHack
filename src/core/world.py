"""
World environment and ocean boundaries for FishSwarm.
"""
import pygame
from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, OCEAN_MARGIN

class OceanBounds:
    """Manages 2D ocean space boundaries and containment."""
    
    def __init__(self, width: float = OCEAN_WIDTH, height: float = OCEAN_HEIGHT, margin: float = OCEAN_MARGIN):
        self.width = float(width)
        self.height = float(height)
        self.margin = float(margin)
        self.rect = pygame.Rect(0, 0, int(self.width), int(self.height))
        self.usable_rect = pygame.Rect(
            int(self.margin),
            int(self.margin),
            int(self.width - 2 * self.margin),
            int(self.height - 2 * self.margin)
        )
    
    @property
    def min_x(self) -> float:
        return self.margin

    @property
    def max_x(self) -> float:
        return self.width - self.margin

    @property
    def min_y(self) -> float:
        return self.margin

    @property
    def max_y(self) -> float:
        return self.height - self.margin

    def is_inside(self, pos: pygame.Vector2 | tuple[float, float], use_margin: bool = True) -> bool:
        """Checks if a point is within ocean boundaries."""
        x, y = pos[0], pos[1]
        if use_margin:
            return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y
        return 0 <= x <= self.width and 0 <= y <= self.height

    def clamp(self, pos: pygame.Vector2 | tuple[float, float], use_margin: bool = True) -> pygame.Vector2:
        """Clamps a coordinate to the ocean boundaries."""
        x, y = pos[0], pos[1]
        if use_margin:
            clamped_x = max(self.min_x, min(x, self.max_x))
            clamped_y = max(self.min_y, min(y, self.max_y))
        else:
            clamped_x = max(0.0, min(x, self.width))
            clamped_y = max(0.0, min(y, self.height))
        return pygame.Vector2(clamped_x, clamped_y)
