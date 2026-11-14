"""
SimulationManager for FishSwarm.
Orchestrates world state, boat fleets, fish schools, discovery scans,
cooperative harvesting loops, depletion handling, and recovery back to exploration.
"""
from typing import Optional
import pygame

from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, OCEAN_MARGIN
from src.core.world_coordinator import WorldCoordinator
from src.core.operation_coordinator import OperationCoordinator
from src.core.comms_hub import CommsHub
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

        self.boats: list[BoatAgent] = []
        self.schools: list[FishSchool] = []

        self.sim_time: float = 0.0
        self.total_fish_harvested: float = 0.0
        self.total_operations_completed: int = 0

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

        # 1. Discovery scan: exploring boats query available schools
        for boat in self.boats:
            if boat.state == BoatState.EXPLORING:
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
        for boat in self.boats:
            boat.update(delta_time, self.world_coordinator)

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
            active_fishing_count = sum(
                1 for b in self.boats
                if b.current_operation_id == op.operation_id and b.state == BoatState.FISHING
            )

            # Apply combined harvest once per update
            if active_fishing_count > 0:
                harvested = school.apply_harvest(
                    operation_id=op.operation_id,
                    active_boat_count=active_fishing_count,
                    delta_time=delta_time,
                )
                self.total_fish_harvested += harvested

            # Check if harvest step caused depletion
            if school.is_depleted:
                self.operation_coordinator.complete_operation(
                    op.operation_id, self.boats, school, self.world_coordinator
                )
                self.total_operations_completed += 1
