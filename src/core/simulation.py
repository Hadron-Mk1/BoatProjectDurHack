"""
SimulationManager for FishSwarm.
Orchestrates world state, boat fleets, fish schools, discovery scans,
cooperative harvesting loops, depletion handling, and recovery back to exploration.
"""
from typing import Optional
import pygame

from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, OCEAN_MARGIN, FISH_RESPAWN_DELAY
from src.core.world_coordinator import WorldCoordinator
from src.core.operation_coordinator import OperationCoordinator
from src.core.comms_hub import CommsHub
from src.core.rescue_manager import RescueManager
from src.core.oil_spill_manager import OilSpillManager
from src.entities.boat_agent import BoatAgent, BoatState
from src.entities.fish_school import FishSchool

class FishSwarmSimulation:
    """
    Master simulation kernel coordinating all entities and subsystems.
    """
    
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
        self.boats.append(boat)
        self.comms_hub.register_agent(
            boat.boat_id,
            lambda msg: None,  # Hook for agent internal message handling
        )

    def add_school(self, school: FishSchool):
        """Adds a fish school to the simulation."""
        self.schools.append(school)

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

        # 1. Discovery scan: exploring boats query available schools
        for boat in self.boats:
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
        for boat in self.boats:
            boat.update(delta_time, self.world_coordinator)

        # Resolve contacts after normal movement so collision recovery cannot
        # replace or bypass exploration and operation navigation.
        self.rescue_manager.update(self, delta_time, previous_positions)
        self.oil_spill_manager.update(self, delta_time, previous_positions)

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
                             and b.state == BoatState.FISHING
                             and b.remaining_fish_capacity > 0.0]
            active_fishing_count = len(fishing_boats)

            # Apply combined harvest once per update
            if active_fishing_count > 0:
                harvested = school.apply_harvest(
                    operation_id=op.operation_id,
                    active_boat_count=active_fishing_count,
                    delta_time=delta_time,
                    harvest_limit=sum(b.remaining_fish_capacity for b in fishing_boats),
                )
                self.total_fish_harvested += harvested
                unassigned_harvest = harvested
                for boat in fishing_boats:
                    unassigned_harvest -= boat.record_harvest(unassigned_harvest)
                    if unassigned_harvest <= 0.0:
                        break

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
