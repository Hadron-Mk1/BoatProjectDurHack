"""
DebugOverlay for FishSwarm.
Draws visual aids:
- 3x3 local grid cells and current exploration targets.
- Detection ranges and fishing radius circles.
- Dynamic connection lines between Lead and Assisting boats in active operations.
"""
import pygame
from src.entities.boat_agent import BoatState

class DebugOverlay:
    """Renders visual debug overlays on top of the simulation."""

    @staticmethod
    def draw(surface: pygame.Surface, sim):
        """Draws all active debug indicators."""
        # 1. Draw 3x3 local grid waypoints for exploring boats
        for boat in sim.boats:
            if boat.state == BoatState.EXPLORING and boat.current_grid is not None:
                # Draw light markers for unvisited cells
                for idx in boat.current_grid.get_unvisited_indices():
                    cell_pos = boat.current_grid.get_cell_position(idx)
                    pygame.draw.circle(surface, (60, 110, 160), (int(cell_pos.x), int(cell_pos.y)), 3)

        # 2. Draw active operation connection rays (Lead -> Assisting boats -> School)
        for op in sim.operation_coordinator.operations.values():
            school = sim.get_school(op.school_id)
            if school is None:
                continue

            school_pt = (int(school.position.x), int(school.position.y))
            lead = next((b for b in sim.boats if b.boat_id == op.lead_boat_id), None)
            if lead is not None:
                lead_pt = (int(lead.position.x), int(lead.position.y))
                # Draw gold line from lead to school
                pygame.draw.line(surface, (255, 215, 0), lead_pt, school_pt, 2)

            for asst_id in op.confirmed_assistant_ids:
                asst = next((b for b in sim.boats if b.boat_id == asst_id), None)
                if asst is not None:
                    asst_pt = (int(asst.position.x), int(asst.position.y))
                    # Draw cyan line from assistant to school
                    pygame.draw.line(surface, (80, 200, 255), asst_pt, school_pt, 1)
