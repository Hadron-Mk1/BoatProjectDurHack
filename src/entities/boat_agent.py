"""
BoatAgent for FishSwarm.
Represents an autonomous fishing vessel with state-driven behaviors,
kinematics, 3x3 local grid exploration, sensor detection, and fishing actions.
"""
from enum import Enum
import math
from typing import Optional
import pygame

from src.config import (
    BOAT_CRUISE_SPEED,
    BOAT_TURN_SPEED,
    BOAT_LENGTH,
    BOAT_WIDTH,
    WAYPOINT_REACH_RADIUS,
    DETECTION_RADIUS,
    FISHING_RADIUS,
    COLOR_EXPLORING,
    COLOR_RESERVED,
    COLOR_TRAVELING,
    COLOR_FISHING,
    COLOR_TEXT,
)
from src.entities.exploration import LocalGrid
from src.entities.fish_school import FishSchool

class BoatState(Enum):
    EXPLORING = "EXPLORING"
    RESERVED = "RESERVED"
    TRAVELING = "TRAVELING"
    FISHING = "FISHING"

class BoatAgent:
    """
    Autonomous boat agent operating under a deterministic state machine.
    """
    _next_id = 1

    def __init__(
        self,
        position: tuple[float, float] | pygame.Vector2,
        boat_id: Optional[int] = None,
        speed: float = BOAT_CRUISE_SPEED,
        heading: float = 0.0,
    ):
        if boat_id is not None:
            self.boat_id = int(boat_id)
            if self.boat_id >= BoatAgent._next_id:
                BoatAgent._next_id = self.boat_id + 1
        else:
            self.boat_id = BoatAgent._next_id
            BoatAgent._next_id += 1

        self.position = pygame.Vector2(position[0], position[1])
        self.heading = float(heading)
        self.velocity = pygame.Vector2(0, 0)
        self.speed = float(speed)
        self.turn_speed = BOAT_TURN_SPEED

        # State management
        self.state = BoatState.EXPLORING
        self.current_operation_id: Optional[str] = None
        self.assigned_school_id: Optional[int] = None
        self.assigned_school_pos: Optional[pygame.Vector2] = None

        # Exploration subsystem
        self.current_grid: Optional[LocalGrid] = None
        self.target_position: Optional[pygame.Vector2] = None
        self.current_cell_index: Optional[int] = None

        # Sensor parameters
        self.detection_radius = DETECTION_RADIUS
        self.fishing_radius = FISHING_RADIUS

    @classmethod
    def reset_id_counter(cls, start_id: int = 1):
        """Resets ID counter for deterministic testing."""
        cls._next_id = start_id

    # ----------------- State Machine & Transitions -----------------

    def can_transition_to(self, new_state: BoatState) -> bool:
        """
        Validates if transition from current state to new_state is allowed.
        Allowed transitions:
        - EXPLORING -> RESERVED (recruited as assistant)
        - EXPLORING -> TRAVELING (discovering lead traveling to school)
        - EXPLORING -> FISHING (discovering lead already at school)
        - RESERVED  -> TRAVELING (recruitment confirmed)
        - RESERVED  -> EXPLORING (recruitment cancelled/expired)
        - TRAVELING -> FISHING (arrived at school)
        - TRAVELING -> EXPLORING (school depleted in transit or op cancelled)
        - FISHING   -> EXPLORING (school depleted or op completed)
        """
        if self.state == new_state:
            return True

        if self.state == BoatState.EXPLORING:
            return new_state in (BoatState.RESERVED, BoatState.TRAVELING, BoatState.FISHING)

        if self.state == BoatState.RESERVED:
            return new_state in (BoatState.TRAVELING, BoatState.EXPLORING)

        if self.state == BoatState.TRAVELING:
            return new_state in (BoatState.FISHING, BoatState.EXPLORING)

        if self.state == BoatState.FISHING:
            return new_state == BoatState.EXPLORING

        return False

    def transition_to(
        self,
        new_state: BoatState,
        operation_id: Optional[str] = None,
        school_id: Optional[int] = None,
        school_pos: Optional[pygame.Vector2] = None,
    ) -> bool:
        """
        Executes an authorized state transition.
        Updates operation/school references accordingly.
        """
        if not self.can_transition_to(new_state):
            return False

        self.state = new_state

        if new_state in (BoatState.RESERVED, BoatState.TRAVELING, BoatState.FISHING):
            if operation_id is not None:
                self.current_operation_id = str(operation_id)
            if school_id is not None:
                self.assigned_school_id = int(school_id)
            if school_pos is not None:
                self.assigned_school_pos = pygame.Vector2(school_pos)

        elif new_state == BoatState.EXPLORING:
            self.current_operation_id = None
            self.assigned_school_id = None
            self.assigned_school_pos = None

        return True

    def reset_to_exploring(self, world_coordinator=None):
        """
        Safely recovers boat to EXPLORING state, clearing all operation assignments
        and releasing any active exploration reservations.
        """
        self.state = BoatState.EXPLORING
        self.current_operation_id = None
        self.assigned_school_id = None
        self.assigned_school_pos = None
        self.target_position = None
        self.current_cell_index = None
        if world_coordinator is not None:
            world_coordinator.release_exploration_target(self.boat_id)

    # ----------------- Kinematics & Steering -----------------

    def steer_towards(self, target: pygame.Vector2, delta_time: float, world_coordinator):
        """
        Smoothly rotates heading towards target and advances position at cruise speed.
        Clamps position to ocean boundaries.
        """
        if delta_time <= 0.0:
            return

        direction = target - self.position
        distance = direction.length()
        if distance < 1e-4:
            self.velocity = pygame.Vector2(0, 0)
            return

        target_angle = math.atan2(direction.y, direction.x)
        angle_diff = (target_angle - self.heading + math.pi) % (2 * math.pi) - math.pi

        # Apply turn rate limit
        max_turn = self.turn_speed * delta_time
        if abs(angle_diff) <= max_turn:
            self.heading = target_angle
        else:
            self.heading += math.copysign(max_turn, angle_diff)

        # Normalize heading to [-pi, pi]
        self.heading = (self.heading + math.pi) % (2 * math.pi) - math.pi

        # Advance along heading
        forward = pygame.Vector2(math.cos(self.heading), math.sin(self.heading))
        self.velocity = forward * self.speed
        self.position += self.velocity * delta_time

        # Respect ocean boundaries
        self.position = world_coordinator.bounds.clamp(self.position, use_margin=True)

    # ----------------- Sensor Perception -----------------

    def detect_schools(self, schools: list[FishSchool]) -> list[FishSchool]:
        """
        Detects available, unassigned fish schools within detection_radius.
        """
        detected: list[FishSchool] = []
        for school in schools:
            if school.is_available():
                dist = self.position.distance_to(school.position)
                if dist <= self.detection_radius:
                    detected.append(school)
        return detected

    # ----------------- Simulation Update Loop -----------------

    def update(self, delta_time: float, world_coordinator):
        """
        Updates boat state and motion according to its active state.
        """
        if self.state == BoatState.EXPLORING:
            self._update_exploring(delta_time, world_coordinator)

        elif self.state == BoatState.TRAVELING:
            self._update_traveling(delta_time, world_coordinator)

        elif self.state == BoatState.FISHING:
            self._update_fishing(delta_time, world_coordinator)

        elif self.state == BoatState.RESERVED:
            # Idling; wait for assignment confirmation or timeout
            self.velocity = pygame.Vector2(0, 0)

    def _update_exploring(self, delta_time: float, world_coordinator):
        """Manages local 3x3 grid exploration and waypoint progression."""
        # Initialize grid if none exists or completed all 9 cells
        if self.current_grid is None or self.current_grid.is_complete():
            self.current_grid = LocalGrid(self.position, world_coordinator.bounds)
            self.target_position = None
            self.current_cell_index = None
            world_coordinator.release_exploration_target(self.boat_id)

        # If no active target, select an unvisited cell
        if self.target_position is None:
            selection = self.current_grid.select_next_cell(self.boat_id, world_coordinator)
            if selection is not None:
                self.current_cell_index, self.target_position = selection
                world_coordinator.reserve_exploration_target(self.boat_id, self.target_position)
            else:
                # All unvisited cells in this grid are reserved by peers:
                # Generate a new grid offset toward open ocean space
                step_offset = pygame.Vector2(
                    (1.0 if self.position.x < world_coordinator.bounds.width / 2 else -1.0) * 150.0,
                    (1.0 if self.position.y < world_coordinator.bounds.height / 2 else -1.0) * 150.0,
                )
                new_center = world_coordinator.bounds.clamp(self.position + step_offset, use_margin=True)
                self.current_grid = LocalGrid(new_center, world_coordinator.bounds)
                return

        # Navigate toward active waypoint
        self.steer_towards(self.target_position, delta_time, world_coordinator)

        # Check if waypoint reached
        if self.position.distance_to(self.target_position) <= WAYPOINT_REACH_RADIUS:
            if self.current_cell_index is not None:
                self.current_grid.mark_visited(self.current_cell_index)
            world_coordinator.release_exploration_target(self.boat_id)
            self.target_position = None
            self.current_cell_index = None

    def _update_traveling(self, delta_time: float, world_coordinator):
        """Travels directly to assigned fish school coordinates."""
        if self.assigned_school_pos is None:
            self.reset_to_exploring(world_coordinator)
            return

        self.steer_towards(self.assigned_school_pos, delta_time, world_coordinator)

        # Once inside fishing radius, commence fishing
        if self.position.distance_to(self.assigned_school_pos) <= self.fishing_radius:
            self.transition_to(BoatState.FISHING)
            self.velocity = pygame.Vector2(0, 0)

    def _update_fishing(self, delta_time: float, world_coordinator):
        """Station keeping around the school while fishing."""
        self.velocity = pygame.Vector2(0, 0)

    # ----------------- Rendering -----------------

    def draw(
        self,
        surface: pygame.Surface,
        font: Optional[pygame.font.Font] = None,
        show_debug: bool = False,
    ):
        """Renders boat agent with direction indicator and state-coded color."""
        pos = (int(self.position.x), int(self.position.y))

        # Color mapping by state
        colors = {
            BoatState.EXPLORING: COLOR_EXPLORING,
            BoatState.RESERVED: COLOR_RESERVED,
            BoatState.TRAVELING: COLOR_TRAVELING,
            BoatState.FISHING: COLOR_FISHING,
        }
        color = colors.get(self.state, COLOR_EXPLORING)

        # Draw boat as a directional triangle
        half_len = BOAT_LENGTH / 2.0
        half_wid = BOAT_WIDTH / 2.0
        
        nose = self.position + pygame.Vector2(math.cos(self.heading), math.sin(self.heading)) * half_len
        left_tail = self.position + pygame.Vector2(
            math.cos(self.heading + 2.5),
            math.sin(self.heading + 2.5)
        ) * half_len
        right_tail = self.position + pygame.Vector2(
            math.cos(self.heading - 2.5),
            math.sin(self.heading - 2.5)
        ) * half_len

        points = [(int(p.x), int(p.y)) for p in (nose, left_tail, right_tail)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, (255, 255, 255), points, 1)

        # Debug overlays
        if show_debug:
            # Draw detection radius
            pygame.draw.circle(surface, (color[0], color[1], color[2], 40), pos, int(self.detection_radius), 1)
            # Draw line to current target waypoint
            if self.target_position is not None and self.state == BoatState.EXPLORING:
                tgt = (int(self.target_position.x), int(self.target_position.y))
                pygame.draw.line(surface, color, pos, tgt, 1)
                pygame.draw.circle(surface, color, tgt, 3)

        # Boat text label
        if font is not None:
            lbl = f"B{self.boat_id} [{self.state.value[:4]}]"
            surf = font.render(lbl, True, COLOR_TEXT)
            rect = surf.get_rect(center=(pos[0], pos[1] - 16))
            surface.blit(surf, rect)
