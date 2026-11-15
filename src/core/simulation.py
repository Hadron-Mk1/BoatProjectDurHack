"""
SimulationManager for FishSwarm.
Orchestrates world state, boat fleets, fish schools, discovery scans,
cooperative harvesting loops, depletion handling, and recovery back to exploration.
"""
import random
from typing import Optional
import pygame

from src.config import (
    OCEAN_WIDTH,
    OCEAN_HEIGHT,
    OCEAN_MARGIN,
    FISH_RESPAWN_DELAY,
    DEFAULT_SCHOOL_POPULATION,
    FISH_COLORS,
    SONAR_PULSE_RADIUS,
    normalize_fish_color,
)
from src.core.world_coordinator import WorldCoordinator
from src.core.operation_coordinator import OperationCoordinator
from src.core.comms_hub import CommsHub
from src.core.rescue_manager import RescueManager
from src.core.oil_spill_manager import OilSpillManager
from src.core.pier_manager import PierManager
from src.entities.boat_agent import BoatAgent, BoatState, BoatType, SonarBoat
from src.entities.fish_school import FishSchool

class FishSwarmSimulation:
    """
    Master simulation kernel coordinating all entities and subsystems.
    """

    MIN_SCHOOL_SPAWN_DISTANCE = 220.0
    SCHOOL_SPAWN_ATTEMPTS = 128
    
    def __init__(
        self,
        width: float = OCEAN_WIDTH,
        height: float = OCEAN_HEIGHT,
        margin: float = OCEAN_MARGIN,
    ):
        self.world_coordinator = WorldCoordinator(width, height, margin)
        self.comms_hub = CommsHub()
        self.operation_coordinator = OperationCoordinator(comms_hub=self.comms_hub)
        self.rescue_manager = RescueManager()
        self.oil_spill_manager = OilSpillManager()
        self.pier_manager = PierManager(width, height, margin)

        self.boats: list[BoatAgent] = []
        self.schools: list[FishSchool] = []
        # Optional land/dock/obstacle geometry. Items may be pygame.Rects or
        # objects exposing position and radius; the base scenario is open water.
        self.obstacles = []

        self.sim_time: float = 0.0
        self.total_fish_harvested: float = 0.0
        self.total_operations_completed: int = 0
        self._school_respawn_timers: dict[int, float] = {}

    def add_boat(self, boat: BoatAgent):
        """Adds a boat agent and registers it with CommsHub."""
        if boat.boat_type != BoatType.SONAR and boat.mission is None:
            boat.mission = self.pier_manager.new_starting_mission(boat.fish_capacity)
            if boat.mission is not None:
                boat.target_color = boat.mission.color
        self.boats.append(boat)
        self.comms_hub.register_agent(
            boat.boat_id,
            lambda msg: None,  # Hook for agent internal message handling
        )

    def add_school(self, school: FishSchool):
        """Adds a fish school to the simulation."""
        self.schools.append(school)

    def spawn_school(
        self,
        position: Optional[tuple[float, float] | pygame.Vector2] = None,
        population: float = DEFAULT_SCHOOL_POPULATION,
        color: Optional[tuple[int, int, int] | str] = None,
    ) -> FishSchool:
        """
        Dynamically spawns a fish school with a random palette color
        (or explicit color) within the ocean boundaries and adds it to the simulation.
        """
        if position is None:
            position = self._find_school_spawn_position()
        elif not self.pier_manager.is_clear_of_dock(
                position, self.pier_manager.FISH_CLEARANCE):
            position = self._find_school_spawn_position()
        if color is None:
            color = random.choice(FISH_COLORS)
        school = FishSchool(position=position, population=population, color=color)
        self.add_school(school)
        return school

    def _find_school_spawn_position(self):
        """Spread new schools across open water and keep them clear of the pier."""
        bounds = self.world_coordinator.bounds
        for _ in range(self.SCHOOL_SPAWN_ATTEMPTS):
            candidate = pygame.Vector2(
                random.uniform(bounds.min_x + 50.0, bounds.max_x - 50.0),
                random.uniform(bounds.min_y + 50.0, bounds.max_y - 50.0),
            )
            if not self.pier_manager.is_clear_of_dock(
                    candidate, self.pier_manager.FISH_CLEARANCE):
                continue
            if all(candidate.distance_to(school.position) >= self.MIN_SCHOOL_SPAWN_DISTANCE
                   for school in self.schools):
                return candidate

        # When the ocean is crowded, use a best available open-water point
        # instead of clustering schools or failing to spawn entirely.
        candidates = []
        for x in range(int(bounds.min_x + 50), int(bounds.max_x - 49), 40):
            for y in range(int(bounds.min_y + 50), int(bounds.max_y - 49), 40):
                point = pygame.Vector2(x, y)
                if self.pier_manager.is_clear_of_dock(
                        point, self.pier_manager.FISH_CLEARANCE):
                    spacing = min((point.distance_to(s.position) for s in self.schools),
                                  default=float("inf"))
                    candidates.append((spacing, point))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]

        return pygame.Vector2(bounds.min_x + 50.0, bounds.min_y + 50.0)

    def get_school(self, school_id: int) -> Optional[FishSchool]:
        """Look up school by ID."""
        for s in self.schools:
            if s.school_id == school_id:
                return s
        return None

    def update(self, delta_time: float):
        """
        Executes one complete simulation step:
        1. Discovery scan for exploring boats.
        2. Boat motion & state progression.
        3. Synchronized cooperative harvesting.
        4. Depletion detection & recovery release.
        """
        if delta_time <= 0.0:
            return

        self.sim_time += delta_time
        self._update_school_respawns(delta_time)
        self.oil_spill_manager.poll(self)
        self.rescue_manager.poll(self)
        self.pier_manager.prepare(self, delta_time)

        # 1. Discovery scan: exploring boats query available schools
        for boat in self.boats:
            if boat.boat_type == BoatType.SONAR:
                continue
            if boat.boat_id in self.pier_manager.waiting_for_dock:
                continue
            # Towing boats claimed for rescue or broken boats do not engage in fishing discovery
            if boat.boat_type == BoatType.TOWING and (getattr(boat, "claimed_rescue", None) is not None or boat.state in (BoatState.MOVING_TO_TOW, BoatState.TOWING)):
                continue
            if getattr(boat, "needs_rescue", False) or boat.state == BoatState.BROKEN:
                continue
            if boat.mission is None:
                continue
            # Boats with no active target color patrol/wait rather than fish randomly
            if getattr(boat, "target_color", None) is None:
                continue

            if boat.state in (BoatState.IDLE, BoatState.FISHING) and boat.current_operation_id is None:
                detected_schools = boat.detect_schools(self.schools)
                for candidate_school in detected_schools:
                    if candidate_school.is_available():
                        op = self.operation_coordinator.create_operation(
                            lead_boat=boat,
                            school=candidate_school,
                            all_boats=self.boats,
                        )
                        if op is not None:
                            # Successfully initiated operation, move to next boat
                            break

        # 2. Update boat motion, kinematics, and state progressions
        previous_positions = {boat.boat_id: boat.position.copy() for boat in self.boats}
        sonar_boats = [boat for boat in self.boats if isinstance(boat, SonarBoat)]
        for sonar in sonar_boats:
            sonar.avoid_discovery_zones(
                (other for other in sonar_boats if other is not sonar),
                self.world_coordinator,
            )
        for boat in self.boats:
            boat.avoidance_positions = [
                previous_positions[other.boat_id]
                for other in self.boats
                if other is not boat
                and other is not boat.claimed_rescue
                and not (boat.claimed_rescue is not None
                         and other.claimed_rescue is boat.claimed_rescue)
            ]
            if boat.state == BoatState.DUMPING:
                boat.avoidance_positions = []
            boat.update(delta_time, self.world_coordinator)
            if not boat.needs_rescue:
                self.pier_manager.keep_boat_out(
                    boat,
                    previous_positions[boat.boat_id],
                    self.world_coordinator.bounds,
                    self.sim_time,
                    delta_time,
                )
        self.pier_manager.process_arrivals(self)

        # Sonar boats patrol on the regular exploration loop and periodically
        # broadcast nearby schools to matching vessels within pulse range.
        for sonar in (b for b in self.boats if isinstance(b, SonarBoat)):
            if sonar.advance_pulse(delta_time):
                nearby = [school for school in self.schools
                          if sonar.position.distance_to(school.position) <= sonar.detection_radius
                          and not school.is_depleted]
                for school in nearby:
                    sonar.emit_pulse(school)
                    for boat in self.boats:
                        if (boat is sonar or boat.boat_type == BoatType.SONAR
                                or boat.is_cargo_full or boat.target_color != school.color
                                or boat.needs_rescue or boat.state != BoatState.EXPLORING
                                or boat.current_operation_id is not None
                                or boat.position.distance_to(sonar.position) > SONAR_PULSE_RADIUS):
                            continue
                        if school.is_available():
                            self.operation_coordinator.create_operation(boat, school, self.boats)

        # Resolve contacts after normal movement so collision recovery cannot
        # replace or bypass exploration and operation navigation.
        self.rescue_manager.update(self, delta_time, previous_positions)
        self.oil_spill_manager.update(self, delta_time, previous_positions)
        self.rescue_manager.finish_movement_update(self, previous_positions)

        # 3. Synchronized cooperative harvesting & depletion checks
        active_ops = list(self.operation_coordinator.operations.values())
        for op in active_ops:
            school = self.get_school(op.school_id)
            if school is None or school.is_depleted:
                self.operation_coordinator.complete_operation(
                    op.operation_id, self.boats, school, self.world_coordinator
                )
                self.total_operations_completed += 1
                continue

            # Count boats actively in FISHING state for this operation
            participants = [b for b in self.boats if b.boat_id in op.all_participating_boat_ids]
            fishing_boats = [b for b in participants
                             if b.current_operation_id == op.operation_id
                             and b.boat_type != BoatType.SONAR
                             and b.state == BoatState.FISHING
                             and b.remaining_fish_capacity > 0.0
                             and (b.target_color is None or b.target_color == school.color)]
            active_fishing_count = len(fishing_boats)

            # Apply combined harvest once per update
            if active_fishing_count > 0:
                harvested = school.apply_harvest(
                    operation_id=op.operation_id,
                    active_boat_count=active_fishing_count,
                    delta_time=delta_time,
                    harvest_limit=sum(
                        min(b.remaining_fish_capacity,
                            max(0.0, b.mission.amount - b.fish_catch)
                            if b.mission is not None else b.remaining_fish_capacity)
                        for b in fishing_boats
                    ),
                )
                self.total_fish_harvested += harvested
                unassigned_harvest = harvested
                for boat in fishing_boats:
                    unassigned_harvest -= boat.record_harvest(unassigned_harvest)
                    if unassigned_harvest <= 0.0:
                        break

                returning_boats = [
                    boat for boat in fishing_boats
                    if boat.is_cargo_full or (boat.mission is not None and boat.fish_catch >= boat.mission.amount)
                ]
                if returning_boats:
                    self.operation_coordinator.cancel_operation(
                        op.operation_id, self.boats, school, self.world_coordinator
                    )
                    for boat in returning_boats:
                        self.pier_manager.request_dock(boat, self)
                    continue

            # Check if harvest step caused depletion
            if school.is_depleted:
                self.operation_coordinator.complete_operation(
                    op.operation_id, self.boats, school, self.world_coordinator
                )
                self.total_operations_completed += 1
            elif participants and all(b.remaining_fish_capacity <= 0.0 for b in participants):
                self.operation_coordinator.complete_operation(
                    op.operation_id, self.boats, school, self.world_coordinator
                )
                self.total_operations_completed += 1

        self._schedule_depleted_school_respawns()

    def _update_school_respawns(self, delta_time: float):
        """Advance school recovery timers and revive schools whose delay elapsed."""
        for school in self.schools:
            remaining = self._school_respawn_timers.get(school.school_id)
            if remaining is None:
                continue
            remaining -= delta_time
            if remaining <= 0.0:
                school.respawn()
                self._school_respawn_timers.pop(school.school_id, None)
            else:
                self._school_respawn_timers[school.school_id] = remaining

    def _schedule_depleted_school_respawns(self):
        """Start one respawn timer for each depleted school with fish to recover."""
        for school in self.schools:
            if (school.is_depleted and school.initial_population > 0.0
                    and school.school_id not in self._school_respawn_timers):
                self._school_respawn_timers[school.school_id] = FISH_RESPAWN_DELAY
