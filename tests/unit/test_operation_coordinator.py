"""
Unit tests for OperationCoordinator.
Verifies unique operation IDs, atomic recruitment (0, 1, 2, and >2 available boats),
closest-boat proximity selection, simultaneous discovery arbitration,
and safe reservation release upon cancellation or completion.
"""
import pytest
import pygame
from src.core.operation_coordinator import OperationCoordinator
from src.core.comms_hub import CommsHub
from src.entities.boat_agent import BoatAgent, BoatState
from src.entities.fish_school import FishSchool

@pytest.fixture(autouse=True)
def reset_counters():
    """Ensure ID determinism across tests."""
    BoatAgent.reset_id_counter(1)
    FishSchool.reset_id_counter(1)
    OperationCoordinator.reset_id_counter(1)

@pytest.fixture
def comms():
    return CommsHub()

@pytest.fixture
def op_coord(comms):
    return OperationCoordinator(comms_hub=comms)

# ----------------- Recruitment Scalability Tests -----------------

def test_recruitment_with_zero_available_assistants(op_coord):
    """When zero other boats are available, lead boat operates solo."""
    lead = BoatAgent((100, 100))
    school = FishSchool((150, 150), population=50)
    
    all_boats = [lead]
    op = op_coord.create_operation(lead, school, all_boats)
    
    assert op is not None
    assert op.lead_boat_id == lead.boat_id
    assert len(op.confirmed_assistant_ids) == 0
    assert op.total_active_boats == 1
    assert lead.state in (BoatState.TRAVELING, BoatState.FISHING)

def test_recruitment_with_one_available_assistant(op_coord):
    """When only 1 assistant is available, exactly 1 is recruited."""
    lead = BoatAgent((100, 100))
    assistant = BoatAgent((200, 100))
    busy_boat = BoatAgent((300, 100))
    busy_boat.state = BoatState.FISHING  # Not available
    
    school = FishSchool((120, 100), population=50)
    all_boats = [lead, assistant, busy_boat]
    
    op = op_coord.create_operation(lead, school, all_boats)
    assert op is not None
    assert len(op.confirmed_assistant_ids) == 1
    assert assistant.boat_id in op.confirmed_assistant_ids
    assert assistant.state == BoatState.TRAVELING
    assert op.total_active_boats == 2

def test_recruitment_with_two_available_assistants(op_coord):
    """When exactly 2 assistants are available, both are recruited."""
    lead = BoatAgent((100, 100))
    a1 = BoatAgent((200, 100))
    a2 = BoatAgent((100, 200))
    
    school = FishSchool((120, 120), population=50)
    all_boats = [lead, a1, a2]
    
    op = op_coord.create_operation(lead, school, all_boats)
    assert op is not None
    assert len(op.confirmed_assistant_ids) == 2
    assert a1.state == BoatState.TRAVELING
    assert a2.state == BoatState.TRAVELING
    assert op.total_active_boats == 3

def test_recruitment_selects_closest_two_available_assistants(op_coord):
    """
    When >2 assistants are available, the two closest by Euclidean distance
    to the school must be selected.
    """
    lead = BoatAgent((100, 100))
    school = FishSchool((200, 200), population=50)
    
    # Assistants at varying distances from (200, 200):
    a_close1 = BoatAgent((200, 210))  # dist = 10
    a_close2 = BoatAgent((200, 180))  # dist = 20
    a_far1 = BoatAgent((200, 300))    # dist = 100
    a_far2 = BoatAgent((600, 200))    # dist = 400
    
    all_boats = [lead, a_far1, a_close1, a_far2, a_close2]
    
    op = op_coord.create_operation(lead, school, all_boats)
    assert op is not None
    assert len(op.confirmed_assistant_ids) == 2
    assert a_close1.boat_id in op.confirmed_assistant_ids
    assert a_close2.boat_id in op.confirmed_assistant_ids
    
    # Far boats should remain unaffected in EXPLORING
    assert a_far1.state == BoatState.EXPLORING
    assert a_far2.state == BoatState.EXPLORING

# ----------------- Simultaneous Discovery & Race Conditions -----------------

def test_simultaneous_discoveries_prevent_double_booking(op_coord):
    """
    Two boats discover two different schools simultaneously.
    Boats recruited by Op 1 must not be recruited by Op 2.
    """
    lead_a = BoatAgent((100, 100))
    lead_b = BoatAgent((800, 800))
    
    # Assistant situated near School A
    assistant_near_a = BoatAgent((120, 120))
    # Assistant situated between both schools
    assistant_mid = BoatAgent((450, 450))
    # Assistant situated near School B
    assistant_near_b = BoatAgent((780, 780))
    
    school_a = FishSchool((110, 110), population=50)
    school_b = FishSchool((790, 790), population=50)
    
    all_boats = [lead_a, lead_b, assistant_near_a, assistant_mid, assistant_near_b]
    
    # Operation A initiated: recruits the 2 closest (assistant_near_a and assistant_mid)
    op_a = op_coord.create_operation(lead_a, school_a, all_boats)
    assert op_a is not None
    assert assistant_near_a.boat_id in op_a.confirmed_assistant_ids
    assert assistant_mid.boat_id in op_a.confirmed_assistant_ids
    
    # Operation B initiated immediately on the same frame
    op_b = op_coord.create_operation(lead_b, school_b, all_boats)
    assert op_b is not None
    
    # assistant_mid and assistant_near_a are already booked, so Op B recruits only remaining assistant_near_b
    assert assistant_near_a.boat_id not in op_b.confirmed_assistant_ids
    assert assistant_mid.boat_id not in op_b.confirmed_assistant_ids
    assert assistant_near_b.boat_id in op_b.confirmed_assistant_ids
    
    # Verify mutual exclusivity of assignments
    assert op_coord.boat_to_operation[assistant_near_a.boat_id] == op_a.operation_id
    assert op_coord.boat_to_operation[assistant_mid.boat_id] == op_a.operation_id
    assert op_coord.boat_to_operation[assistant_near_b.boat_id] == op_b.operation_id

def test_duplicate_discovery_of_same_school_rejected(op_coord):
    """If two boats discover the same school, only the first operation succeeds."""
    lead_1 = BoatAgent((100, 100))
    lead_2 = BoatAgent((900, 900))  # Far away so not recruited as assistant
    school = FishSchool((110, 100), population=50)
    
    a1 = BoatAgent((120, 100))
    a2 = BoatAgent((130, 100))
    all_boats = [lead_1, lead_2, a1, a2]
    
    op1 = op_coord.create_operation(lead_1, school, all_boats)
    assert op1 is not None
    assert a1.boat_id in op1.confirmed_assistant_ids
    assert a2.boat_id in op1.confirmed_assistant_ids
    assert lead_2.state == BoatState.EXPLORING
    
    # Lead 2 attempts to claim the same school -> rejected
    op2 = op_coord.create_operation(lead_2, school, all_boats)
    assert op2 is None, "Duplicate operation on same school must be rejected"
    assert lead_2.state == BoatState.EXPLORING

# ----------------- Cancellation & Completion Safety -----------------

def test_operation_cancellation_releases_all_boats(op_coord):
    """Cancelling an operation resets all participants back to EXPLORING."""
    lead = BoatAgent((100, 100))
    a1 = BoatAgent((150, 150))
    a2 = BoatAgent((160, 160))
    school = FishSchool((120, 120), population=50)
    all_boats = [lead, a1, a2]
    
    op = op_coord.create_operation(lead, school, all_boats)
    op_id = op.operation_id
    
    op_coord.cancel_operation(op_id, all_boats, school)
    
    assert lead.state == BoatState.EXPLORING
    assert a1.state == BoatState.EXPLORING
    assert a2.state == BoatState.EXPLORING
    assert school.assigned_operation_id is None
    assert op_id not in op_coord.operations
    assert len(op_coord.boat_to_operation) == 0

def test_operation_completion_releases_all_boats(op_coord):
    """Completing an operation on school depletion frees all participating boats."""
    lead = BoatAgent((100, 100))
    a1 = BoatAgent((150, 150))
    school = FishSchool((120, 120), population=50.0)
    all_boats = [lead, a1]
    
    op = op_coord.create_operation(lead, school, all_boats)
    assert op is not None
    
    # Deplete school and complete operation
    school.apply_harvest(op.operation_id, active_boat_count=2, delta_time=10.0)
    assert school.is_depleted is True
    
    op_coord.complete_operation(op.operation_id, all_boats, school)
    
    assert lead.state == BoatState.EXPLORING
    assert a1.state == BoatState.EXPLORING
    assert len(op_coord.operations) == 0
