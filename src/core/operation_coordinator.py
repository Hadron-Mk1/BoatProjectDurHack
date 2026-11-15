"""
OperationCoordinator for FishSwarm.
Manages fishing operation lifecycles, atomic 2-boat recruitment,
reservation safety, simultaneous discovery arbitration, and cleanup.
"""
from dataclasses import dataclass, field
from typing import Optional
import pygame

from src.entities.boat_agent import BoatAgent, BoatState, BoatType
from src.entities.fish_school import FishSchool
from src.core.comms_hub import CommsHub, Message

@dataclass
class FishingOperation:
    """Represents an active fishing mission centered on a fish school."""
    operation_id: str
    school_id: int
    school_position: pygame.Vector2
    lead_boat_id: int
    reserved_assistant_ids: list[int] = field(default_factory=list)
    confirmed_assistant_ids: list[int] = field(default_factory=list)
    is_active: bool = True

    @property
    def all_participating_boat_ids(self) -> list[int]:
        """Returns all boats currently involved in the operation."""
        return [self.lead_boat_id] + list(self.confirmed_assistant_ids) + list(self.reserved_assistant_ids)

    @property
    def total_active_boats(self) -> int:
        """Count of boats in the operation (lead + confirmed assistants)."""
        return 1 + len(self.confirmed_assistant_ids)

class OperationCoordinator:
    """
    Coordinates multi-agent recruitment, assignment reservations,
    and operation lifecycle safety.
    """
    _next_op_id = 1

    def __init__(self, comms_hub: Optional[CommsHub] = None):
        self.comms_hub = comms_hub
        self.operations: dict[str, FishingOperation] = {}
        self.school_to_operation: dict[int, str] = {}
        self.boat_to_operation: dict[int, str] = {}

    @classmethod
    def reset_id_counter(cls, start_id: int = 1):
        """Resets operation counter for deterministic testing."""
        cls._next_op_id = start_id

    def get_boat_operation(self, boat_id: int) -> Optional[FishingOperation]:
        """Returns the active operation assigned to boat_id, if any."""
        op_id = self.boat_to_operation.get(int(boat_id))
        if op_id is not None:
            return self.operations.get(op_id)
        return None

    def get_school_operation(self, school_id: int) -> Optional[FishingOperation]:
        """Returns the active operation for school_id, if any."""
        op_id = self.school_to_operation.get(int(school_id))
        if op_id is not None:
            return self.operations.get(op_id)
        return None

    def create_operation(
        self,
        lead_boat: BoatAgent,
        school: FishSchool,
        all_boats: list[BoatAgent],
    ) -> Optional[FishingOperation]:
        """
        Initiates a new fishing operation:
        1. Validates school availability & lead boat eligibility.
        2. Claims school for new operation ID.
        3. Transitions lead boat directly into operation.
        4. Selects min(2, N_available) closest available boats.
        5. Atomically reserves candidates, then confirms assignments.
        6. Broadcasts discovery & assignment via CommsHub.
        """
        # Step 1: Pre-condition checks
        if not school.is_available() or school.school_id in self.school_to_operation:
            return None
            
        if (lead_boat.state not in (BoatState.EXPLORING, BoatState.FISHING)
                or lead_boat.current_operation_id is not None
                or lead_boat.boat_id in self.boat_to_operation
                or lead_boat.boat_type == BoatType.SONAR):
            return None

        # Check target color compatibility:
        # A boat with target_color only pursues schools matching its target_color
        if lead_boat.target_color is not None and lead_boat.target_color != school.color:
            return None

        # Step 2: Unique operation ID generation
        op_id = f"op_{OperationCoordinator._next_op_id}"
        OperationCoordinator._next_op_id += 1

        # Step 3: Claim school
        if not school.claim(op_id):
            return None

        # Step 4: Setup operation object
        operation = FishingOperation(
            operation_id=op_id,
            school_id=school.school_id,
            school_position=pygame.Vector2(school.position),
            lead_boat_id=lead_boat.boat_id,
        )

        # Transition lead boat directly into TRAVELING (or FISHING if already inside radius)
        lead_target_state = (
            BoatState.FISHING
            if lead_boat.position.distance_to(school.position) <= lead_boat.fishing_radius
            else BoatState.TRAVELING
        )
        lead_boat.transition_to(
            lead_target_state,
            operation_id=op_id,
            school_id=school.school_id,
            school_pos=school.position,
        )
        self.boat_to_operation[lead_boat.boat_id] = op_id
        self.school_to_operation[school.school_id] = op_id
        self.operations[op_id] = operation

        # Step 5: Find available candidate boats
        # Filter: exploring, not the lead, not already booked in an operation,
        # and matching target color (ignoring schools of different color,
        # and if lead targets a color, uncolored boats patrol/wait rather than join).
        available_candidates: list[BoatAgent] = []
        for b in all_boats:
            if b.boat_id != lead_boat.boat_id:
                if (b.state == BoatState.EXPLORING
                        and b.boat_type != BoatType.SONAR
                        and b.boat_id not in self.boat_to_operation
                        and not getattr(b, "needs_rescue", False)
                        and getattr(b, "claimed_rescue", None) is None):
                    if lead_boat.target_color is not None:
                        if b.target_color == school.color:
                            available_candidates.append(b)
                    else:
                        if b.target_color is None or b.target_color == school.color:
                            available_candidates.append(b)

        # Sort candidates by Euclidean distance to school (closest first)
        available_candidates.sort(key=lambda b: b.position.distance_to(school.position))

        # Select min(2, N_available)
        num_to_recruit = min(2, len(available_candidates))
        chosen_candidates = available_candidates[:num_to_recruit]

        # Step 6: Atomic Reservation & Confirmation Phase
        try:
            for candidate in chosen_candidates:
                # 6A. Reservation
                if not candidate.transition_to(BoatState.RESERVED, operation_id=op_id, school_id=school.school_id):
                    raise RuntimeError(f"Failed to reserve boat {candidate.boat_id}")
                operation.reserved_assistant_ids.append(candidate.boat_id)
                self.boat_to_operation[candidate.boat_id] = op_id

            # 6B. Confirmation -> TRAVELING
            for candidate in chosen_candidates:
                candidate.transition_to(BoatState.TRAVELING, school_pos=school.position)
                operation.reserved_assistant_ids.remove(candidate.boat_id)
                operation.confirmed_assistant_ids.append(candidate.boat_id)

        except Exception:
            # Rollback all reservations on error
            self.cancel_operation(op_id, all_boats, school)
            return None

        # Step 7: Broadcast via CommsHub if present
        if self.comms_hub is not None:
            self.comms_hub.send_broadcast(
                sender_id=lead_boat.boat_id,
                msg_type=Message.DISCOVERY,
                payload={
                    "operation_id": op_id,
                    "school_id": school.school_id,
                    "school_pos": (school.position.x, school.position.y),
                    "recruited_assistants": list(operation.confirmed_assistant_ids),
                },
            )

        return operation

    def cancel_operation(
        self,
        operation_id: str,
        all_boats: list[BoatAgent],
        school: Optional[FishSchool] = None,
        world_coordinator=None,
    ):
        """
        Safely cancels an operation and releases all participating boats back to EXPLORING.
        """
        op = self.operations.get(operation_id)
        if op is None:
            return

        op.is_active = False

        # Release all participating boats
        boat_lookup = {b.boat_id: b for b in all_boats}
        for b_id in op.all_participating_boat_ids:
            boat = boat_lookup.get(b_id)
            if boat is not None:
                boat.reset_to_exploring(world_coordinator)
            self.boat_to_operation.pop(b_id, None)

        # Release school
        if school is not None:
            school.release(operation_id)
        self.school_to_operation.pop(op.school_id, None)
        self.operations.pop(operation_id, None)

        if self.comms_hub is not None:
            self.comms_hub.send_broadcast(
                sender_id=op.lead_boat_id,
                msg_type=Message.OPERATION_CANCELLED,
                payload={"operation_id": operation_id},
            )

    def complete_operation(
        self,
        operation_id: str,
        all_boats: list[BoatAgent],
        school: Optional[FishSchool] = None,
        world_coordinator=None,
    ):
        """
        Concludes an operation upon fish school depletion.
        Releases all participating boats back to independent exploration.
        """
        op = self.operations.get(operation_id)
        if op is None:
            return

        op.is_active = False

        boat_lookup = {b.boat_id: b for b in all_boats}
        for b_id in op.all_participating_boat_ids:
            boat = boat_lookup.get(b_id)
            if boat is not None:
                boat.reset_to_exploring(world_coordinator)
            self.boat_to_operation.pop(b_id, None)

        if school is not None:
            school.release(operation_id)
        self.school_to_operation.pop(op.school_id, None)
        self.operations.pop(operation_id, None)

        if self.comms_hub is not None:
            self.comms_hub.send_broadcast(
                sender_id=op.lead_boat_id,
                msg_type=Message.SCHOOL_DEPLETED,
                payload={"operation_id": operation_id, "school_id": op.school_id},
            )
