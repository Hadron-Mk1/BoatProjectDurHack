"""
BoatAgent for FishSwarm.
Represents an autonomous fishing vessel with state-driven behaviors,
kinematics, 3x3 local grid exploration, sensor detection, fishing actions,
and collision/breakdown recovery.
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
    COLOR_BROKEN,
    COLOR_TOWING,
    COLOR_TOWING_BOAT,
    COLOR_CLEANING_BOAT,
    COLOR_TEXT,
    REGULAR_BOAT_FISH_CAPACITY,
    TOWING_BOAT_SPEED,
    CLEANING_BOAT_SPEED,
    TOWING_BOAT_FISH_CAPACITY,
    CLEANING_BOAT_FISH_CAPACITY,
)
from src.entities.exploration import LocalGrid
from src.entities.fish_school import FishSchool

class BoatState(Enum):
    IDLE = "EXPLORING"
    EXPLORING = "EXPLORING"
    RESERVED = "RESERVED"
    TRAVELING = "TRAVELING"
    FISHING = "FISHING"
    BROKEN = "BROKEN"
    MOVING_TO_SPILL = "MOVING_TO_SPILL"
    TOWING = "TOWING"
    MOVING_TO_TOW = "MOVING_TO_TOW"
    CLEANING = "CLEANING"


class BoatType(Enum):
    REGULAR = "REGULAR"
    TOWING = "TOWING"
    CLEANING = "CLEANING"

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
        boat_type: BoatType = BoatType.REGULAR,
        fish_capacity: Optional[float] = None,
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
        self.boat_type = boat_type
        capacities = {
            BoatType.REGULAR: REGULAR_BOAT_FISH_CAPACITY,
            BoatType.TOWING: TOWING_BOAT_FISH_CAPACITY,
            BoatType.CLEANING: CLEANING_BOAT_FISH_CAPACITY,
        }
        self.fish_capacity = float(fish_capacity if fish_capacity is not None else capacities[boat_type])
        self.fish_catch = 0.0
        self.oil_slow_remaining = 0.0
        self.oil_speed_multiplier = 1.0

        # State management
        self.state = BoatState.EXPLORING
        self.current_operation_id: Optional[str] = None
        self.assigned_school_id: Optional[int] = None
        self.assigned_school_pos: Optional[pygame.Vector2] = None

        # Exploration subsystem
        self.current_grid: Optional[LocalGrid] = None
        self.target_position: Optional[pygame.Vector2] = None
        self.target_spill = None
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
        """
        if self.state == new_state:
            return True

        if new_state == BoatState.BROKEN:
            return self.state in (BoatState.EXPLORING, BoatState.TRAVELING, BoatState.FISHING)

        if new_state == BoatState.TOWING:
            return self.boat_type == BoatType.TOWING and self.state == BoatState.MOVING_TO_TOW

        if new_state == BoatState.MOVING_TO_TOW:
            return self.boat_type == BoatType.TOWING and self.state in (
                BoatState.EXPLORING, BoatState.RESERVED, BoatState.TRAVELING, BoatState.FISHING
            )

        if new_state == BoatState.MOVING_TO_SPILL:
            return self.boat_type == BoatType.CLEANING and self.state in (
                BoatState.EXPLORING, BoatState.RESERVED, BoatState.TRAVELING, BoatState.FISHING
            )

        if new_state == BoatState.CLEANING:
            return self.boat_type == BoatType.CLEANING and self.state == BoatState.MOVING_TO_SPILL

        if self.state == BoatState.EXPLORING:
            return new_state in (
                BoatState.RESERVED,
                BoatState.TRAVELING,
                BoatState.FISHING,
            )

        if self.state == BoatState.RESERVED:
            return new_state in (BoatState.TRAVELING, BoatState.EXPLORING)

        if self.state == BoatState.TRAVELING:
            return new_state in (BoatState.FISHING, BoatState.EXPLORING)

        if self.state == BoatState.FISHING:
            return new_state in (BoatState.EXPLORING, BoatState.TRAVELING)

        if self.state == BoatState.BROKEN:
            return new_state == BoatState.EXPLORING

        if self.state == BoatState.TOWING:
            return new_state == BoatState.EXPLORING

        if self.state == BoatState.CLEANING:
            return new_state == BoatState.FISHING

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

        elif new_state == BoatState.BROKEN:
            self.velocity = pygame.Vector2(0, 0)
            self.current_operation_id = None
            self.assigned_school_id = None
            self.assigned_school_pos = None
            self.target_position = None
            self.current_cell_index = None

        elif new_state in (BoatState.MOVING_TO_TOW, BoatState.MOVING_TO_SPILL,
                           BoatState.TOWING, BoatState.CLEANING):
            self.velocity = pygame.Vector2(0, 0)
            self.current_operation_id = None
            self.assigned_school_id = None
            self.assigned_school_pos = None
            self.target_position = None
            self.current_cell_index = None
            if new_state not in (BoatState.MOVING_TO_SPILL, BoatState.CLEANING):
                self.target_spill = None

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
        self.target_spill = None
        self.current_cell_index = None
        self.fish_catch = 0.0
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
        # Full-speed steering has a minimum turning radius that can keep a boat
        # circling a close waypoint. Reduce speed near the target so it can settle.
        steering_speed = min(self.speed * self.oil_speed_multiplier, distance * self.turn_speed * 0.5)
        forward = pygame.Vector2(math.cos(self.heading), math.sin(self.heading))
        self.velocity = forward * steering_speed
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
        if self.oil_slow_remaining > 0.0:
            self.oil_slow_remaining = max(0.0, self.oil_slow_remaining - delta_time)
            if self.oil_slow_remaining == 0.0:
                self.oil_speed_multiplier = 1.0

        if (self.state in (BoatState.MOVING_TO_TOW, BoatState.TOWING)
                and self.boat_type != BoatType.TOWING):
            self.reset_to_exploring(world_coordinator)
        elif (self.state in (BoatState.MOVING_TO_SPILL, BoatState.CLEANING)
              and self.boat_type != BoatType.CLEANING):
            self.reset_to_exploring(world_coordinator)

        if self.state == BoatState.IDLE:
            self._update_exploring(delta_time, world_coordinator)

        elif self.state == BoatState.TRAVELING:
            self._update_traveling(delta_time, world_coordinator)

        elif self.state == BoatState.MOVING_TO_TOW:
            if self.boat_type == BoatType.TOWING and self.target_position is not None:
                self.steer_towards(self.target_position, delta_time, world_coordinator)
            else:
                self.velocity = pygame.Vector2(0, 0)

        elif self.state == BoatState.FISHING:
            self._update_fishing(delta_time, world_coordinator)

        elif self.state in (BoatState.RESERVED, BoatState.BROKEN, BoatState.MOVING_TO_SPILL,
                            BoatState.CLEANING, BoatState.MOVING_TO_TOW, BoatState.TOWING):
            self.velocity = pygame.Vector2(0, 0)

    @property
    def remaining_fish_capacity(self) -> float:
        return max(0.0, self.fish_capacity - self.fish_catch)

    def record_harvest(self, amount: float) -> float:
        stored = min(max(0.0, amount), self.remaining_fish_capacity)
        self.fish_catch += stored
        return stored

    def apply_oil_slow(self, duration: float, speed_multiplier: float):
        self.oil_slow_remaining = max(self.oil_slow_remaining, duration)
        self.oil_speed_multiplier = min(self.oil_speed_multiplier, speed_multiplier)

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
        """Draw a heading-aware hull and role-specific deck equipment."""
        pos = (int(self.position.x), int(self.position.y))
        role_styles = {
            BoatType.TOWING: {
                "length": BOAT_LENGTH * 1.55, "width": BOAT_WIDTH * 1.65,
                "hull": (48, 63, 69), "deck": (103, 113, 105),
                "accent": (224, 137, 44), "trim": (236, 192, 92),
            },
            BoatType.CLEANING: {
                "length": BOAT_LENGTH * 0.82, "width": BOAT_WIDTH * 0.78,
                "hull": (238, 113, 37), "deck": (255, 198, 75),
                "accent": (249, 238, 207), "trim": (255, 226, 73),
            },
            BoatType.REGULAR: {
                "length": BOAT_LENGTH, "width": BOAT_WIDTH,
                "hull": (49, 88, 101), "deck": (176, 135, 86),
                "accent": (226, 224, 198), "trim": (209, 81, 56),
            },
        }
        style = role_styles[self.boat_type]
        state_colors = {
            BoatState.EXPLORING: COLOR_EXPLORING,
            BoatState.RESERVED: COLOR_RESERVED,
            BoatState.TRAVELING: COLOR_TRAVELING,
            BoatState.FISHING: COLOR_FISHING,
            BoatState.MOVING_TO_SPILL: COLOR_CLEANING_BOAT,
            BoatState.MOVING_TO_TOW: COLOR_TOWING_BOAT,
        }
        debug_color = state_colors.get(self.state, style["accent"])
        length, width = style["length"], style["width"]
        half_length, half_width = length / 2, width / 2
        forward = pygame.Vector2(math.cos(self.heading), math.sin(self.heading))
        across = pygame.Vector2(-forward.y, forward.x)

        def world(longitudinal, lateral):
            return self.position + forward * longitudinal + across * lateral

        def polygon(local_points, color, outline=None, line_width=1):
            points = [world(x * length, y * width) for x, y in local_points]
            points = [(round(point.x), round(point.y)) for point in points]
            pygame.draw.polygon(surface, color, points)
            if outline is not None:
                pygame.draw.polygon(surface, outline, points, line_width)

        if self.boat_type == BoatType.TOWING:
            hull_shape = [(-.48, -.28), (-.39, -.48), (.25, -.5), (.45, -.32),
                          (.5, 0), (.45, .32), (.25, .5), (-.39, .48), (-.48, .28)]
            polygon(hull_shape, style["hull"], (208, 218, 204), 1)
            polygon([(-.33, -.33), (.25, -.34), (.39, -.2), (.42, 0),
                     (.39, .2), (.25, .34), (-.33, .33)], style["deck"])
            polygon([(-.08, -.22), (.2, -.22), (.29, -.13), (.29, .13),
                     (.2, .22), (-.08, .22)], style["accent"], (39, 54, 59))
            pygame.draw.line(surface, (178, 225, 226), world(.02 * length, -.17 * width),
                             world(.02 * length, .17 * width), 2)
            # Reinforced bow bumper and industrial deck rails.
            pygame.draw.line(surface, style["trim"], world(.46 * length, -.32 * width),
                             world(.52 * length, 0), 4)
            pygame.draw.line(surface, style["trim"], world(.52 * length, 0),
                             world(.46 * length, .32 * width), 4)
            for side in (-1, 1):
                pygame.draw.line(surface, (220, 164, 75), world(-.32 * length, side * .4 * width),
                                 world(.2 * length, side * .4 * width), 1)

        elif self.boat_type == BoatType.CLEANING:
            polygon([(-.48, -.2), (-.3, -.43), (.28, -.38), (.48, 0),
                     (.28, .38), (-.3, .43), (-.48, .2)], style["hull"], (255, 228, 165), 1)
            polygon([(-.28, -.27), (.22, -.27), (.37, 0), (.22, .27), (-.28, .27)], style["deck"])
            polygon([(-.2, -.19), (.02, -.19), (.1, -.1), (.1, .1),
                     (.02, .19), (-.2, .19)], style["accent"], (255, 255, 231))
            pygame.draw.line(surface, (156, 206, 209), world(-.12 * length, -.15 * width),
                             world(-.12 * length, .15 * width), 2)
            # Twin skimmer booms flare forward from the bow.
            for side in (-1, 1):
                hinge = world(.12 * length, side * .28 * width)
                tip = world(.58 * length, side * .85 * width)
                pygame.draw.line(surface, (255, 237, 113), hinge, tip, 3)
                pygame.draw.line(surface, (248, 250, 241), hinge, tip, 1)
                pygame.draw.circle(surface, (255, 247, 209), (round(tip.x), round(tip.y)), 2)

        else:
            polygon([(-.48, -.3), (-.36, -.48), (.27, -.46), (.48, -.23),
                     (.5, 0), (.48, .23), (.27, .46), (-.36, .48), (-.48, .3)],
                    style["hull"], (196, 213, 205), 1)
            polygon([(-.31, -.32), (.24, -.32), (.41, -.17), (.43, 0),
                     (.41, .17), (.24, .32), (-.31, .32)], style["deck"])
            polygon([(-.08, -.23), (.19, -.23), (.28, -.14), (.28, .14),
                     (.19, .23), (-.08, .23)], style["accent"], (45, 71, 80))
            pygame.draw.line(surface, (156, 205, 212), world(.03 * length, -.18 * width),
                             world(.03 * length, .18 * width), 2)
            # Aft trawl frame, net lines and paired buoys.
            pygame.draw.line(surface, style["trim"], world(-.35 * length, -.46 * width),
                             world(-.35 * length, .46 * width), 2)
            pygame.draw.line(surface, (230, 207, 150), world(-.35 * length, -.4 * width),
                             world(-.48 * length, -.5 * width), 1)
            pygame.draw.line(surface, (230, 207, 150), world(-.35 * length, .4 * width),
                             world(-.48 * length, .5 * width), 1)
            for side in (-1, 1):
                buoy = world(-.35 * length, side * .46 * width)
                pygame.draw.circle(surface, (244, 187, 77), (round(buoy.x), round(buoy.y)), 2)

        if self.state == BoatState.BROKEN:
            pygame.draw.circle(surface, (255, 50, 50), pos, 18, 2)
            pygame.draw.line(surface, (255, 50, 50), (pos[0] - 8, pos[1] - 8), (pos[0] + 8, pos[1] + 8), 2)
            pygame.draw.line(surface, (255, 50, 50), (pos[0] - 8, pos[1] + 8), (pos[0] + 8, pos[1] - 8), 2)

        if show_debug:
            if self.state == BoatState.EXPLORING:
                pygame.draw.circle(surface, (*debug_color, 40), pos, int(self.detection_radius), 1)
            if self.target_position is not None and self.state in (
                BoatState.EXPLORING, BoatState.MOVING_TO_SPILL, BoatState.MOVING_TO_TOW
            ):
                tgt = (int(self.target_position.x), int(self.target_position.y))
                pygame.draw.line(surface, debug_color, pos, tgt, 1)
                pygame.draw.circle(surface, debug_color, tgt, 3)

        if font is not None:
            lbl = f"B{self.boat_id} [{self.boat_type.value[:3]}:{self.state.value[:4]}]"
            surf = font.render(lbl, True, COLOR_TEXT)
            rect = surf.get_rect(center=(pos[0], pos[1] - 20))
            surface.blit(surf, rect)


class RegularBoat(BoatAgent):
    def __init__(self, position, **kwargs):
        kwargs.setdefault("boat_type", BoatType.REGULAR)
        super().__init__(position, **kwargs)


class TowingBoat(BoatAgent):
    def __init__(self, position, **kwargs):
        kwargs.setdefault("speed", TOWING_BOAT_SPEED)
        kwargs.setdefault("boat_type", BoatType.TOWING)
        kwargs.setdefault("fish_capacity", TOWING_BOAT_FISH_CAPACITY)
        super().__init__(position, **kwargs)


class CleaningBoat(BoatAgent):
    def __init__(self, position, **kwargs):
        kwargs.setdefault("speed", CLEANING_BOAT_SPEED)
        kwargs.setdefault("boat_type", BoatType.CLEANING)
        kwargs.setdefault("fish_capacity", CLEANING_BOAT_FISH_CAPACITY)
        super().__init__(position, **kwargs)
