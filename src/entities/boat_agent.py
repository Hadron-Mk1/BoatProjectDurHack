"""
BoatAgent for FishSwarm.
Represents an autonomous fishing vessel with state-driven behaviors,
kinematics, 3x3 local grid exploration, sensor detection, fishing actions,
and collision/breakdown recovery.
"""
from enum import Enum
import math
import random
from typing import Optional
import pygame

from src.config import (
    BOAT_CRUISE_SPEED,
    BOAT_TURN_SPEED,
    BOAT_LENGTH,
    BOAT_WIDTH,
    BOAT_AVOIDANCE_RADIUS,
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
    normalize_fish_color,
    FISH_COLORS,
    SONAR_DETECTION_RADIUS,
    SONAR_BOAT_SPEED,
    SONAR_PULSE_RADIUS,
    SONAR_PULSE_INTERVAL,
    SONAR_PULSE_DURATION,
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
    DUMPING = "DUMPING"
    RETURNING = "RETURNING"
    WHIRLPOOL = "WHIRLPOOL"


class BoatType(Enum):
    REGULAR = "REGULAR"
    TOWING = "TOWING"
    CLEANING = "CLEANING"
    SONAR = "SONAR"

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
        target_color: Optional[tuple[int, int, int] | str] = None,
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
        self.avoidance_positions: list[pygame.Vector2] = []
        self.collision_avoidance_enabled = True
        self.speed = float(speed)
        self.turn_speed = BOAT_TURN_SPEED
        self.boat_type = boat_type
        if target_color is None and boat_type != BoatType.SONAR:
            target_color = random.choice(FISH_COLORS)
        self.target_color: Optional[tuple[int, int, int]] = normalize_fish_color(target_color)
        capacities = {
            BoatType.REGULAR: REGULAR_BOAT_FISH_CAPACITY,
            BoatType.TOWING: TOWING_BOAT_FISH_CAPACITY,
            BoatType.CLEANING: CLEANING_BOAT_FISH_CAPACITY,
            BoatType.SONAR: 0.0,
        }
        self.fish_capacity = float(fish_capacity if fish_capacity is not None else capacities[boat_type])
        self.fish_catch = 0.0
        self.mission = None
        self.deposit_glow_remaining = 0.0
        self.oil_slow_remaining = 0.0
        self.oil_speed_multiplier = 1.0

        # State management
        self.state = BoatState.EXPLORING
        self.current_operation_id: Optional[str] = None
        self.assigned_school_id: Optional[int] = None
        self.assigned_school_pos: Optional[pygame.Vector2] = None

        # Rescue subsystem
        self.needs_rescue: bool = False
        self.claimed_rescue: Optional["BoatAgent"] = None

        # Exploration subsystem
        self.current_grid: Optional[LocalGrid] = None
        self.target_position: Optional[pygame.Vector2] = None
        self.target_spill = None
        self.current_cell_index: Optional[int] = None

        # Whirlpool subsystem
        self.suspended_task: Optional[dict] = None

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

        if new_state == BoatState.WHIRLPOOL:
            # Active boats can be pulled into a whirlpool; broken boats are strictly excluded
            return self.state != BoatState.BROKEN and not getattr(self, "needs_rescue", False)

        if self.state == BoatState.WHIRLPOOL:
            # Whirpool state can transition back when resumed
            return True

        if new_state == BoatState.BROKEN:
            return self.state in (BoatState.EXPLORING, BoatState.RESERVED, BoatState.TRAVELING,
                                  BoatState.FISHING, BoatState.WHIRLPOOL)

        if new_state == BoatState.TOWING:
            return self.boat_type == BoatType.TOWING and self.state == BoatState.MOVING_TO_TOW

        if new_state == BoatState.MOVING_TO_TOW:
            return self.boat_type == BoatType.TOWING and self.state in (
                BoatState.EXPLORING, BoatState.RESERVED, BoatState.TRAVELING,
                BoatState.FISHING, BoatState.DUMPING
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
            self.needs_rescue = True
            self.velocity = pygame.Vector2(0, 0)
            self.current_operation_id = None
            self.assigned_school_id = None
            self.assigned_school_pos = None
            self.target_position = None
            self.current_cell_index = None
            self.suspended_task = None

        elif new_state in (BoatState.MOVING_TO_TOW, BoatState.MOVING_TO_SPILL,
                           BoatState.TOWING, BoatState.CLEANING):
            self.velocity = pygame.Vector2(0, 0)
            self.current_operation_id = None
            self.assigned_school_id = None
            self.assigned_school_pos = None
            self.target_position = None
            self.current_cell_index = None
            self.current_grid = None
            if new_state not in (BoatState.MOVING_TO_SPILL, BoatState.CLEANING):
                self.target_spill = None
            if new_state not in (BoatState.MOVING_TO_TOW, BoatState.TOWING):
                self.claimed_rescue = None

        elif new_state == BoatState.WHIRLPOOL:
            self.velocity = pygame.Vector2(0, 0)

        elif new_state == BoatState.EXPLORING:
            self.needs_rescue = False
            self.claimed_rescue = None
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
        self.needs_rescue = False
        self.claimed_rescue = None
        self.current_operation_id = None
        self.assigned_school_id = None
        self.assigned_school_pos = None
        self.target_position = None
        self.target_spill = None
        self.current_cell_index = None
        if world_coordinator is not None:
            world_coordinator.release_exploration_target(self.boat_id)

    def suspend_task(self):
        """
        Suspends the active boat's current task state and transitions it to WHIRLPOOL.
        """
        self.suspended_task = {
            "state": self.state,
            "current_operation_id": self.current_operation_id,
            "assigned_school_id": self.assigned_school_id,
            "assigned_school_pos": self.assigned_school_pos.copy() if self.assigned_school_pos is not None else None,
            "target_position": self.target_position.copy() if self.target_position is not None else None,
            "target_spill": self.target_spill,
            "current_grid": self.current_grid,
            "current_cell_index": self.current_cell_index,
            "velocity": self.velocity.copy(),
            "heading": self.heading,
            "claimed_rescue": self.claimed_rescue,
            "mission": self.mission,
            "collision_avoidance_enabled": self.collision_avoidance_enabled,
            "oil_slow_remaining": self.oil_slow_remaining,
            "oil_speed_multiplier": self.oil_speed_multiplier,
            "deposit_glow_remaining": self.deposit_glow_remaining,
            "pulse_timer": getattr(self, "pulse_timer", None),
            "active_pulses": list(getattr(self, "active_pulses", [])),
        }
        self.state = BoatState.WHIRLPOOL
        self.velocity = pygame.Vector2(0, 0)

    def resume_task(self):
        """
        Restores the previously suspended task state seamlessly.
        """
        if not hasattr(self, "suspended_task") or self.suspended_task is None:
            self.state = BoatState.EXPLORING
            return

        task = self.suspended_task
        self.state = task["state"]
        self.current_operation_id = task["current_operation_id"]
        self.assigned_school_id = task["assigned_school_id"]
        self.assigned_school_pos = task["assigned_school_pos"]
        self.target_position = task["target_position"]
        self.target_spill = task["target_spill"]
        self.current_grid = task["current_grid"]
        self.current_cell_index = task["current_cell_index"]
        self.velocity = task["velocity"]
        self.heading = task["heading"]
        self.claimed_rescue = task["claimed_rescue"]
        self.mission = task["mission"]
        self.collision_avoidance_enabled = task["collision_avoidance_enabled"]
        self.oil_slow_remaining = task["oil_slow_remaining"]
        self.oil_speed_multiplier = task["oil_speed_multiplier"]
        self.deposit_glow_remaining = task["deposit_glow_remaining"]
        if task["pulse_timer"] is not None:
            self.pulse_timer = task["pulse_timer"]
            self.active_pulses = task["active_pulses"]
        self.suspended_task = None


    # ----------------- Kinematics & Steering -----------------

    def steer_towards(
        self,
        target: pygame.Vector2,
        delta_time: float,
        world_coordinator,
        max_speed: Optional[float] = None,
    ):
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

        steering_direction = direction.copy()
        if self.collision_avoidance_enabled:
            avoidance = pygame.Vector2()
            for other_position in self.avoidance_positions:
                offset = self.position - other_position
                other_distance = offset.length()
                if 1e-6 < other_distance < BOAT_AVOIDANCE_RADIUS:
                    strength = (BOAT_AVOIDANCE_RADIUS - other_distance) / BOAT_AVOIDANCE_RADIUS
                    avoidance += offset.normalize() * (strength * strength)
            if avoidance.length_squared() > 1e-6:
                steering_direction += avoidance.normalize() * BOAT_AVOIDANCE_RADIUS * 2.0

        target_angle = math.atan2(steering_direction.y, steering_direction.x)
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
        base_speed = max_speed if max_speed is not None else self.speed
        steering_speed = min(base_speed * self.oil_speed_multiplier, distance * self.turn_speed * 0.5)
        if distance < 60.0:
            alignment = max(0.25, math.cos(angle_diff))
            steering_speed *= alignment

        forward = pygame.Vector2(math.cos(self.heading), math.sin(self.heading))
        self.velocity = forward * steering_speed
        self.position += self.velocity * delta_time

        # Respect ocean boundaries
        if self.state not in (BoatState.DUMPING, BoatState.RETURNING):
            self.position = world_coordinator.bounds.clamp(self.position, use_margin=True)

    # ----------------- Sensor Perception -----------------

    def detect_schools(self, schools: list[FishSchool]) -> list[FishSchool]:
        """
        Detects available, unassigned fish schools within detection_radius
        whose color matches this boat's target_color.
        If the boat has no active target color, returns empty list.
        """
        if self.target_color is None:
            return []

        detected: list[FishSchool] = []
        for school in schools:
            if (not self.is_cargo_full and school.is_available()
                    and getattr(school, "color", None) == self.target_color):
                dist = self.position.distance_to(school.position)
                if dist <= self.detection_radius:
                    detected.append(school)
        return detected

    # ----------------- Simulation Update Loop -----------------

    def update(self, delta_time: float, world_coordinator):
        """
        Updates boat state and motion according to its active state.
        """
        if self.state == BoatState.WHIRLPOOL:
            return

        if self.oil_slow_remaining > 0.0:
            self.oil_slow_remaining = max(0.0, self.oil_slow_remaining - delta_time)
            if self.oil_slow_remaining == 0.0:
                self.oil_speed_multiplier = 1.0

        if self.needs_rescue:
            self.velocity.update(0, 0)
            return

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
            target = self.target_position or (self.claimed_rescue.position if self.claimed_rescue is not None else None)
            if self.boat_type == BoatType.TOWING and target is not None:
                self.steer_towards(target, delta_time, world_coordinator)
            else:
                self.velocity = pygame.Vector2(0, 0)

        elif self.state == BoatState.FISHING:
            self._update_fishing(delta_time, world_coordinator)

        elif self.state == BoatState.DUMPING:
            self._update_dumping(delta_time, world_coordinator)

        elif self.state == BoatState.RETURNING:
            self._update_returning(delta_time, world_coordinator)

        elif self.state in (BoatState.RESERVED, BoatState.BROKEN, BoatState.MOVING_TO_SPILL,
                            BoatState.CLEANING, BoatState.TOWING):
            self.velocity = pygame.Vector2(0, 0)

    @property
    def remaining_fish_capacity(self) -> float:
        return max(0.0, self.fish_capacity - self.fish_catch)

    @property
    def is_cargo_full(self) -> bool:
        """Returns True when the boat's fish inventory has reached its max capacity."""
        return self.fish_capacity > 0.0 and self.fish_catch >= self.fish_capacity

    def record_harvest(self, amount: float) -> float:
        if self.is_cargo_full or self.boat_type == BoatType.SONAR:
            return 0.0
        mission_capacity = (self.mission.amount - self.fish_catch
                            if self.mission is not None else self.remaining_fish_capacity)
        stored = min(max(0.0, amount), self.remaining_fish_capacity, max(0.0, mission_capacity))
        self.fish_catch += stored
        return stored

    def unload_cargo(self) -> float:
        """Empties the boat's fish cargo and returns the amount unloaded."""
        unloaded = self.fish_catch
        self.fish_catch = 0.0
        return unloaded

    def apply_oil_slow(self, duration: float, speed_multiplier: float):
        self.oil_slow_remaining = max(self.oil_slow_remaining, duration)
        self.oil_speed_multiplier = min(self.oil_speed_multiplier, speed_multiplier)

    def _update_exploring(self, delta_time: float, world_coordinator):
        """Manages local 3x3 grid exploration and waypoint progression."""
        # Prioritize claimed rescue target if a TowingBoat has one assigned
        if self.boat_type == BoatType.TOWING and self.claimed_rescue is not None:
            if self.transition_to(BoatState.MOVING_TO_TOW):
                world_coordinator.release_exploration_target(self.boat_id)
                self.target_position = pygame.Vector2(self.claimed_rescue.position)
                self.current_grid = None
                self.current_cell_index = None
                return

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

    def begin_dumping(self, world_coordinator, target_position=None):
        """Release navigation assignments and head for the pier."""
        self.state = BoatState.DUMPING
        self.current_operation_id = None
        self.assigned_school_id = None
        self.assigned_school_pos = None
        self.target_position = (pygame.Vector2(target_position) if target_position is not None
                                else self._nearest_edge_point(world_coordinator))

    def _nearest_edge_point(self, world_coordinator):
        x, y = self.position
        width = world_coordinator.bounds.width
        height = world_coordinator.bounds.height
        distances = (x, width - x, y, height - y)
        edge = distances.index(min(distances))
        if edge == 0:
            return pygame.Vector2(-BOAT_LENGTH, y)
        if edge == 1:
            return pygame.Vector2(width + BOAT_LENGTH, y)
        if edge == 2:
            return pygame.Vector2(x, -BOAT_LENGTH)
        return pygame.Vector2(x, height + BOAT_LENGTH)

    def _update_dumping(self, delta_time, world_coordinator):
        if self.target_position is None:
            self.target_position = self._nearest_edge_point(world_coordinator)
        if self.position.distance_to(self.target_position) <= 15.0:
            self.velocity = pygame.Vector2(0, 0)
            return
        self.steer_towards(self.target_position, delta_time, world_coordinator)

    def _update_returning(self, delta_time, world_coordinator):
        bounds = world_coordinator.bounds
        self.target_position = bounds.clamp(self.position, use_margin=True)
        self.steer_towards(self.target_position, delta_time, world_coordinator)
        if bounds.is_inside(self.position, use_margin=True):
            self.state = BoatState.EXPLORING
            self.current_grid = None
            self.target_position = None

    # ----------------- Rendering -----------------

    def draw(
        self,
        surface: pygame.Surface,
        font: Optional[pygame.font.Font] = None,
        show_debug: bool = False,
        minimal: bool = False,
        show_label: bool = True,
        animation_time: float = 0.0,
    ):
        """Draw a heading-aware hull and role-specific deck equipment."""
        animation_phase = animation_time * 2.6 + self.boat_id * 0.83
        bob = 0.0 if self.needs_rescue else math.sin(animation_phase) * 1.6
        render_position = self.position + pygame.Vector2(0, bob)
        pos = (round(render_position.x), round(render_position.y))
        render_heading = (self.heading if self.needs_rescue else
                          self.heading + math.sin(animation_phase * .55) * .018)
        # Homogenous & Industrial utilitarian fleet aesthetics:
        # Tighter, cohesive palette of muted slate greys, dark navy, rusted iron, and safety orange accents.
        role_styles = {
            BoatType.SONAR: {
                "length": BOAT_LENGTH * 1.25, "width": BOAT_WIDTH * 1.10,
                "hull": (32, 42, 52),       # Dark slate navy
                "deck": (68, 76, 84),       # Weathered steel deck
                "accent": (225, 95, 32),    # Safety orange housing / antenna
                "trim": (145, 82, 50),      # Rusted iron plate
            },
            BoatType.TOWING: {
                "length": BOAT_LENGTH * 1.35, "width": BOAT_WIDTH * 1.25,
                "hull": (24, 34, 46),       # Heavy dark navy steel
                "deck": (62, 70, 78),       # Industrial non-slip slate
                "accent": (230, 92, 30),    # Safety orange gantry
                "trim": (160, 75, 42),      # Heavy rusted steel trim
            },
            BoatType.CLEANING: {
                "length": BOAT_LENGTH * 1.05, "width": BOAT_WIDTH * 0.94,
                "hull": (48, 42, 40),       # Rusted iron & dark charcoal
                "deck": (70, 74, 80),       # Slate steel
                "accent": (220, 90, 30),    # Safety orange recovery boom
                "trim": (150, 85, 52),      # Rusted iron fittings
            },
            BoatType.REGULAR: {
                "length": BOAT_LENGTH * 1.10, "width": BOAT_WIDTH * 1.02,
                "hull": (38, 46, 54),       # Muted slate grey
                "deck": (66, 74, 82),       # Weathered steel deck
                "accent": (225, 95, 32),    # Safety orange winch & equipment
                "trim": (145, 80, 48),      # Rusted iron plate
            },
        }
        style = dict(role_styles[self.boat_type])  # shallow copy so we can mutate
        model_scale = 0.9
        style["length"] *= model_scale
        style["width"] *= model_scale


        # Desaturate hull/deck/accent when at full cargo capacity
        if self.is_cargo_full and not minimal:
            def _desaturate(color):
                grey = int(0.30 * color[0] + 0.59 * color[1] + 0.11 * color[2])
                # Blend 70 % toward grey for a clearly washed-out look
                return tuple(int(c * 0.3 + grey * 0.7) for c in color)
            for key in ("hull", "deck"):
                style[key] = _desaturate(style[key])
        if self.oil_slow_remaining > 0.0:
            style.update({
                "hull": (75, 35, 112),
                "deck": (125, 62, 177),
                "accent": (193, 128, 239),
                "trim": (220, 176, 251),
            })
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
        forward = pygame.Vector2(math.cos(render_heading), math.sin(render_heading))
        across = pygame.Vector2(-forward.y, forward.x)

        def world(longitudinal, lateral):
            return render_position + forward * longitudinal + across * lateral

        def polygon(local_points, color, outline=None, line_width=1):
            points = [world(x * length, y * width) for x, y in local_points]
            points = [(round(point.x), round(point.y)) for point in points]
            pygame.draw.polygon(surface, color, points)
            if outline is not None:
                pygame.draw.polygon(surface, outline, points, line_width)

        boat_speed = self.velocity.length()
        if boat_speed > 8.0:
            wave_phase = (animation_time * 1.15 + self.boat_id * .29) % 1.0
            stern = -.47 * length
            for crest in range(2):
                phase = (wave_phase + crest * .5) % 1.0
                radius = 2.5 + phase * 7.5
                points = [
                    world(stern - radius * math.cos(angle),
                          radius * 1.3 * math.sin(angle))
                    for angle in (math.pi * step / 16 - math.pi / 2
                                  for step in range(17))
                ]
                pygame.draw.aalines(surface, (48, 112, 130), False, points)

            # Small bow ripples part around the moving hull and spread outward.
            bow_phase = (animation_time * 1.05 + self.boat_id * .41) % 1.0
            for crest in range(2):
                phase = (bow_phase + crest * .5) % 1.0
                radius = 1.5 + phase * 4.0
                points = [
                    world(.53 * length + radius * math.cos(angle),
                          radius * 1.25 * math.sin(angle))
                    for angle in (math.pi * step / 16 - math.pi / 2
                                  for step in range(17))
                ]
                pygame.draw.aalines(surface, (68, 132, 148), False, points)

        if self.boat_type == BoatType.TOWING:
            hull_shape = [(-.5, -.3), (-.42, -.46), (.18, -.45), (.4, -.29),
                          (.56, 0), (.4, .29), (.18, .45), (-.42, .46), (-.5, .3)]
            polygon(hull_shape, style["hull"], (153, 164, 154), 1)
            polygon([(-.33, -.33), (.25, -.34), (.39, -.2), (.42, 0),
                     (.39, .2), (.25, .34), (-.33, .33)], style["deck"])
            polygon([(-.08, -.22), (.2, -.22), (.29, -.13), (.29, .13),
                     (.2, .22), (-.08, .22)], style["accent"], (39, 54, 59))
            pygame.draw.line(surface, (132, 157, 158), world(.02 * length, -.17 * width),
                             world(.02 * length, .17 * width), 2)
            # Reinforced bow bumper and industrial deck rails.
            pygame.draw.line(surface, style["trim"], world(.46 * length, -.32 * width),
                             world(.52 * length, 0), 4)
            pygame.draw.line(surface, style["trim"], world(.52 * length, 0),
                             world(.46 * length, .32 * width), 4)
            for side in (-1, 1):
                pygame.draw.line(surface, (157, 128, 78), world(-.32 * length, side * .4 * width),
                                 world(.2 * length, side * .4 * width), 1)
            # A-frame tow gantry and stern hook distinguish the tug silhouette.
            gantry_color = style["accent"]
            for side in (-1, 1):
                pygame.draw.line(surface, gantry_color,
                                 world(-.28 * length, side * .39 * width),
                                 world(-.43 * length, 0), 2)
            pygame.draw.line(surface, gantry_color,
                             world(-.28 * length, -.39 * width),
                             world(-.28 * length, .39 * width), 2)
            hook = world(-.48 * length, 0)
            pygame.draw.circle(surface, style["accent"],
                               (round(hook.x), round(hook.y)), 2)

        elif self.boat_type == BoatType.CLEANING:
            polygon([(-.5, -.3), (-.4, -.45), (.22, -.42), (.43, -.25),
                     (.56, 0), (.43, .25), (.22, .42), (-.4, .45), (-.5, .3)],
                    style["hull"], (177, 139, 85), 1)
            polygon([(-.28, -.27), (.22, -.27), (.37, 0), (.22, .27), (-.28, .27)], style["deck"])
            polygon([(-.2, -.19), (.02, -.19), (.1, -.1), (.1, .1),
                     (.02, .19), (-.2, .19)], style["accent"], (70, 73, 64))
            # Compact aft recovery tank and a short intake roller at the bow.
            polygon([(-.37, -.24), (-.20, -.24), (-.15, -.16),
                     (-.15, .16), (-.20, .24), (-.37, .24)],
                    (78, 83, 75), (174, 135, 73), 1)
            pygame.draw.line(surface, style["trim"], world(.34 * length, -.22 * width),
                             world(.34 * length, .22 * width), 3)

        elif self.boat_type == BoatType.SONAR:
            # Twin-hull survey craft with an enclosed wheelhouse and mast.
            for side in (-1, 1):
                center = side * .24
                polygon([(-.5, center - .13), (-.4, center - .17),
                         (.18, center - .17), (.46, center - .11),
                         (.58, center), (.46, center + .11),
                         (.18, center + .17), (-.4, center + .17),
                         (-.5, center + .13)],
                        style["hull"], (119, 143, 141), 1)
            polygon([(-.34, -.20), (.20, -.20), (.39, -.10), (.43, 0),
                     (.39, .10), (.20, .20), (-.34, .20)], style["deck"])
            polygon([(-.12, -.22), (.14, -.22), (.28, -.11), (.28, .11),
                     (.14, .22), (-.12, .22)], style["accent"], (50, 68, 69), 1)
            polygon([(-.35, -.17), (-.22, -.17), (-.17, -.09),
                     (-.17, .09), (-.22, .17), (-.35, .17)],
                    (49, 104, 112), style["trim"], 1)
            pygame.draw.line(surface, (85, 182, 184), world(-.29 * length, 0),
                             world(-.29 * length, -.3 * width), 2)
            pygame.draw.line(surface, (85, 182, 184), world(-.29 * length, -.3 * width),
                             world(-.17 * length, -.3 * width), 2)

        else:
            polygon([(-.5, -.3), (-.4, -.46), (.2, -.43), (.42, -.25),
                     (.56, 0), (.42, .25), (.2, .43), (-.4, .46), (-.5, .3)],
                    style["hull"], (138, 155, 148), 1)
            polygon([(-.31, -.32), (.24, -.32), (.41, -.17), (.43, 0),
                     (.41, .17), (.24, .32), (-.31, .32)], style["deck"])
            polygon([(-.08, -.23), (.19, -.23), (.28, -.14), (.28, .14),
                     (.19, .23), (-.08, .23)], style["accent"], (45, 71, 80))
            pygame.draw.line(surface, (132, 157, 158), world(.03 * length, -.18 * width),
                             world(.03 * length, .18 * width), 2)
            # Aft trawl frame, net lines and paired buoys.
            pygame.draw.line(surface, style["trim"], world(-.35 * length, -.46 * width),
                             world(-.35 * length, .46 * width), 2)
            pygame.draw.line(surface, (151, 137, 98), world(-.35 * length, -.4 * width),
                             world(-.48 * length, -.5 * width), 1)
            pygame.draw.line(surface, (151, 137, 98), world(-.35 * length, .4 * width),
                             world(-.48 * length, .5 * width), 1)
            for side in (-1, 1):
                buoy = world(-.35 * length, side * .46 * width)
                pygame.draw.circle(surface, (165, 129, 70), (round(buoy.x), round(buoy.y)), 2)

        # Muted cabin glazing keeps the hull silhouettes legible at small scale.
        window_color = (175, 222, 218)
        pygame.draw.line(surface, window_color,
                         world(.17 * length, -.12 * width),
                         world(.17 * length, .12 * width), max(1, round(width * .12)))
        for side in (-1, 1):
            side_window_start = world(-.07 * length, side * .20 * width)
            side_window_end = world(.08 * length, side * .20 * width)
            pygame.draw.line(surface, window_color, side_window_start, side_window_end,
                             max(1, round(width * .09)))

        if self.state == BoatState.FISHING:
            school_delta = (self.assigned_school_pos - self.position
                            if self.assigned_school_pos is not None else across)
            cast_direction = (school_delta.normalize() if school_delta.length_squared() > 1e-6
                              else across)
            cast_cycle = (animation_time * .48 + self.boat_id * .23) % 1.0
            cast_lift = math.sin(cast_cycle * math.pi)
            rod_base = world(-.12 * length, .27 * width)
            rod_mid = rod_base + cast_direction * (10 + 3 * cast_lift) + across * 4
            rod_tip = rod_base + cast_direction * (20 + 5 * cast_lift) + across * 7
            splash_distance = min(31.0, max(19.0, school_delta.length() * .58))
            splash = render_position + cast_direction * splash_distance
            rod_brown = (126, 77, 42)
            cast_yellow = (255, 225, 52)
            pygame.draw.lines(surface, rod_brown, False,
                              [rod_base, rod_mid, rod_tip], 3)
            cast_arc = []
            for step in range(9):
                t = step / 8
                point = rod_tip.lerp(splash, t)
                point.y -= math.sin(t * math.pi) * (8 + 5 * cast_lift)
                cast_arc.append((round(point.x), round(point.y)))
            pygame.draw.lines(surface, cast_yellow, False, cast_arc, 2)

            if cast_cycle < .24:
                splash_progress = cast_cycle / .24
                splash_radius = 2 + round(splash_progress * 6)
                splash_center = (round(splash.x), round(splash.y))
                splash_rect = pygame.Rect(
                    splash_center[0] - splash_radius * 2,
                    splash_center[1] - splash_radius,
                    splash_radius * 4,
                    splash_radius * 2,
                )
                pygame.draw.ellipse(surface, (104, 193, 207), splash_rect, 1)
                pygame.draw.ellipse(surface, (76, 151, 169), splash_rect.inflate(-4, -2), 1)
                droplet_height = round(math.sin(splash_progress * math.pi) * 4)
                for droplet_offset in (-3, 0, 3):
                    droplet = (splash_center[0] + droplet_offset,
                               splash_center[1] - droplet_height - abs(droplet_offset))
                    pygame.draw.circle(surface, (147, 218, 224), droplet, 1)

        if self.state == BoatState.BROKEN:
            pygame.draw.circle(surface, (255, 50, 50), pos, 14, 2)
            pygame.draw.line(surface, (255, 50, 50), (pos[0] - 8, pos[1] - 8), (pos[0] + 8, pos[1] + 8), 2)
            pygame.draw.line(surface, (255, 50, 50), (pos[0] - 8, pos[1] + 8), (pos[0] + 8, pos[1] - 8), 2)

        # Full-cargo visual marker
        if not minimal and self.is_cargo_full and self.state != BoatState.BROKEN:
            pygame.draw.circle(surface, (160, 160, 160), pos, 11, 2)

        if not minimal and self.deposit_glow_remaining > 0.0:
            pulse = 1.0 - self.deposit_glow_remaining / 3.0
            glow_radius = 15 + round(5 * abs(math.sin(pulse * math.pi * 4)))
            glow = pygame.Surface((glow_radius * 2 + 4, glow_radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 235, 120, 75), (glow_radius + 2, glow_radius + 2), glow_radius)
            surface.blit(glow, (pos[0] - glow_radius - 2, pos[1] - glow_radius - 2))
            pygame.draw.circle(surface, (255, 235, 120), pos, glow_radius, 2)

        if show_debug:
            if self.state == BoatState.EXPLORING:
                pygame.draw.circle(surface, (*debug_color, 40), pos, int(self.detection_radius), 1)
            if self.target_position is not None and self.state in (
                BoatState.EXPLORING, BoatState.MOVING_TO_SPILL, BoatState.MOVING_TO_TOW
            ):
                tgt = (int(self.target_position.x), int(self.target_position.y))
                pygame.draw.line(surface, debug_color, pos, tgt, 1)
                pygame.draw.circle(surface, debug_color, tgt, 3)

        if not minimal and self.target_color is not None and self.state != BoatState.BROKEN:
            swatch_center = (pos[0], pos[1] - 12)
            pygame.draw.circle(surface, self.target_color, swatch_center, 3)
            pygame.draw.circle(surface, (20, 20, 20), swatch_center, 3, 1)

        if not minimal and self.mission is not None and font is not None:
            mission_text = f"{self.mission.amount:.0f} {self.mission.size.lower()}"
            mission_surf = font.render(mission_text, True, self.mission.color)
            mission_rect = mission_surf.get_rect(center=(pos[0], pos[1] + 22))
            surface.blit(mission_surf, mission_rect)

        if font is not None and not minimal and show_label:
            lbl = f"B{self.boat_id} [{self.boat_type.value[:3]}:{self.state.value[:4]}]"
            if self.is_cargo_full:
                lbl += " FULL"
            surf = font.render(lbl, True, COLOR_TEXT)
            rect = surf.get_rect(center=(pos[0], pos[1] - 20))
            surface.blit(surf, rect)
            if self.target_color is not None:
                swatch_center = (rect.right + 6, rect.centery)
                pygame.draw.circle(surface, self.target_color, swatch_center, 4)
                pygame.draw.circle(surface, (20, 20, 20), swatch_center, 4, 1)


class RegularBoat(BoatAgent):
    def __init__(self, position, target_color=None, **kwargs):
        kwargs.setdefault("boat_type", BoatType.REGULAR)
        super().__init__(position, target_color=target_color, **kwargs)


class TowingBoat(BoatAgent):
    def __init__(self, position, target_color=None, **kwargs):
        kwargs.setdefault("speed", TOWING_BOAT_SPEED)
        kwargs.setdefault("boat_type", BoatType.TOWING)
        kwargs.setdefault("fish_capacity", TOWING_BOAT_FISH_CAPACITY)
        super().__init__(position, target_color=target_color, **kwargs)

    def assign_rescue(self, wreck: BoatAgent):
        """Claims a rescue target, sets target position, and transitions to MOVING_TO_TOW."""
        self.claimed_rescue = wreck
        self.target_position = pygame.Vector2(wreck.position)
        self.transition_to(BoatState.MOVING_TO_TOW)


class CleaningBoat(BoatAgent):
    def __init__(self, position, target_color=None, **kwargs):
        kwargs.setdefault("speed", CLEANING_BOAT_SPEED)
        kwargs.setdefault("boat_type", BoatType.CLEANING)
        kwargs.setdefault("fish_capacity", CLEANING_BOAT_FISH_CAPACITY)
        super().__init__(position, target_color=target_color, **kwargs)


class SonarBoat(BoatAgent):
    """Non-fishing survey boat that relays nearby schools to matching boats."""

    def __init__(self, position, **kwargs):
        kwargs.setdefault("boat_type", BoatType.SONAR)
        kwargs.setdefault("speed", SONAR_BOAT_SPEED)
        kwargs.setdefault("fish_capacity", 0.0)
        super().__init__(position, **kwargs)
        self.detection_radius = SONAR_DETECTION_RADIUS
        self.pulse_timer = 0.0
        self.active_pulses = []

    def avoid_discovery_zones(self, other_sonars, world_coordinator):
        """Move the patrol waypoint outside other sonar boats' discovery ranges."""
        other_sonars = tuple(other_sonars)
        if self.target_position is None or self.state not in (BoatState.IDLE, BoatState.EXPLORING):
            return

        target = pygame.Vector2(self.target_position)
        clearance = self.detection_radius + 1.0
        for _ in range(max(1, len(other_sonars))):
            for other in other_sonars:
                offset = target - other.position
                distance = offset.length()
                if distance < clearance:
                    if distance < 1e-6:
                        # Give coincident boats a consistent direction to separate.
                        offset = pygame.Vector2(1.0 if self.boat_id < other.boat_id else -1.0, 0.0)
                    else:
                        offset /= distance
                    target = other.position + offset * clearance
                    target = world_coordinator.bounds.clamp(target, use_margin=True)

        if target.distance_to(self.target_position) > 1e-3:
            self.target_position = target
            world_coordinator.release_exploration_target(self.boat_id)
            world_coordinator.reserve_exploration_target(self.boat_id, target)

    def detect_schools(self, schools):
        """Sonar vessels discover for broadcasting but never join fishing operations."""
        return []

    def draw(self, surface, font=None, show_debug=False, minimal=False, show_label=True,
             animation_time=0.0):
        if not minimal:
            ring = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            for position, color, age in self.active_pulses:
                progress = age / SONAR_PULSE_DURATION
                radius = max(1, round(SONAR_PULSE_RADIUS * progress))
                alpha = round(180 * (1.0 - progress))
                fill_alpha = round(36 * (1.0 - progress))
                pygame.draw.circle(ring, (*color, fill_alpha),
                                   (round(position.x), round(position.y)), radius)
                pygame.draw.circle(ring, (*color, alpha),
                                   (round(position.x), round(position.y)), radius, 3)
            surface.blit(ring, (0, 0))
        super().draw(surface, font, show_debug, minimal, show_label, animation_time)

    def advance_pulse(self, delta_time):
        self.pulse_timer += delta_time
        self.active_pulses = [pulse for pulse in self.active_pulses
                              if pulse[2] + delta_time < SONAR_PULSE_DURATION]
        self.active_pulses = [(position, color, age + delta_time)
                              for position, color, age in self.active_pulses]
        if self.pulse_timer >= SONAR_PULSE_INTERVAL:
            self.pulse_timer %= SONAR_PULSE_INTERVAL
            return True
        return False

    def emit_pulse(self, school):
        self.active_pulses.append((self.position.copy(), school.color, 0.0))
