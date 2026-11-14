"""
Local 3x3 exploration system for FishSwarm.
Generates a randomized 3x3 grid around a search center, tracks visited cells,
respects ocean boundaries, and cooperates with WorldCoordinator to avoid overlap.
"""
import random
from typing import Optional
import pygame
from src.config import EXPLORATION_CELL_SIZE
from src.core.world import OceanBounds

class LocalGrid:
    """
    Represents a 3x3 exploration grid with exactly 9 cells centered on a search point.
    """
    
    def __init__(
        self,
        center: pygame.Vector2 | tuple[float, float],
        bounds: OceanBounds,
        cell_size: float = EXPLORATION_CELL_SIZE,
    ):
        self.center = pygame.Vector2(center[0], center[1])
        self.cell_size = float(cell_size)
        self.bounds = bounds
        self.visited_cells: set[int] = set()
        
        # Precompute the 9 cell center positions (indices 0..8)
        # Layout:
        # 0: (-1, -1)   1: (0, -1)   2: (1, -1)
        # 3: (-1,  0)   4: (0,  0)   5: (1,  0)
        # 6: (-1,  1)   7: (0,  1)   8: (1,  1)
        self.cells: list[pygame.Vector2] = []
        for row in range(-1, 2):
            for col in range(-1, 2):
                raw_x = self.center.x + col * self.cell_size
                raw_y = self.center.y + row * self.cell_size
                clamped_pos = self.bounds.clamp(pygame.Vector2(raw_x, raw_y), use_margin=True)
                self.cells.append(clamped_pos)

    @property
    def total_cells(self) -> int:
        return 9

    def is_complete(self) -> bool:
        """Returns True if all 9 cells have been visited."""
        return len(self.visited_cells) >= self.total_cells

    def get_unvisited_indices(self) -> list[int]:
        """Returns list of cell indices that have not yet been visited."""
        return [i for i in range(self.total_cells) if i not in self.visited_cells]

    def get_cell_position(self, index: int) -> pygame.Vector2:
        """Returns the center coordinate of cell at index."""
        return pygame.Vector2(self.cells[index])

    def mark_visited(self, index: int):
        """Marks the cell at index as visited."""
        if 0 <= index < self.total_cells:
            self.visited_cells.add(index)

    def select_next_cell(
        self,
        boat_id: int,
        world_coordinator,
        rng: Optional[random.Random] = None,
    ) -> Optional[tuple[int, pygame.Vector2]]:
        """
        Randomly selects an unvisited cell that is not reserved by another boat.
        Returns (cell_index, cell_position), or None if all unvisited cells are reserved.
        """
        unvisited = self.get_unvisited_indices()
        if not unvisited:
            return None
        
        if rng is None:
            shuffled = list(unvisited)
            random.shuffle(shuffled)
        else:
            shuffled = list(unvisited)
            rng.shuffle(shuffled)

        # Find first unvisited cell that passes reservation check
        for idx in shuffled:
            candidate_pos = self.cells[idx]
            if not world_coordinator.is_target_reserved_by_other(boat_id, candidate_pos):
                return idx, candidate_pos

        return None
