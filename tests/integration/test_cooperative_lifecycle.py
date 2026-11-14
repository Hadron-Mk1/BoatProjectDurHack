"""
Integration tests for the complete cooperative fishing lifecycle.
Verifies end-to-end flow:
Explore -> Discover -> Recruit 2 -> Travel -> Fish -> Deplete -> Recover to Explore.
Also verifies pre-arrival depletion recovery and multiple concurrent operations.
"""
import pytest
import pygame
from src.core.simulation import FishSwarmSimulation
from src.entities.boat_agent import BoatAgent, BoatState
from src.entities.fish_school import FishSchool
from src.core.operation_coordinator import OperationCoordinator
from src.config import FISH_RESPAWN_DELAY

@pytest.fixture(autouse=True)
def reset_all_counters():
    """Ensure determinism across integration tests."""
    BoatAgent.reset_id_counter(1)
    FishSchool.reset_id_counter(1)
    OperationCoordinator.reset_id_counter(1)

def test_full_cooperative_cycle_end_to_end():
    """
    Complete lifecycle integration test:
    3 boats start EXPLORING.
    Boat 1 discovers a school and recruits Boats 2 & 3.
    Boats travel to school, engage in cooperative fishing, deplete it,
    and all 3 return to independent EXPLORING.
    """
    sim = FishSwarmSimulation(width=1000, height=800, margin=50)
    
    # Place lead right next to school, assistants slightly farther
    lead = BoatAgent(position=(200, 200), speed=200.0)
    assistant_1 = BoatAgent(position=(260, 200), speed=200.0)
    assistant_2 = BoatAgent(position=(200, 260), speed=200.0)
    
    # Moderate population so harvest takes a few frames
    school = FishSchool(position=(220, 220), population=30.0)
    
    sim.add_boat(lead)
    sim.add_boat(assistant_1)
    sim.add_boat(assistant_2)
    sim.add_school(school)
    
    # Step 1: Initial state
    assert all(b.state == BoatState.EXPLORING for b in sim.boats)
    assert school.is_available() is True
    
    # Step 2: Run simulation step to trigger discovery
    dt = 0.1
    sim.update(dt)
    
    # Verification: Operation should be created, assistants recruited
    assert len(sim.operation_coordinator.operations) == 1
    op = list(sim.operation_coordinator.operations.values())[0]
    assert op.lead_boat_id == lead.boat_id
    assert assistant_1.boat_id in op.confirmed_assistant_ids
    assert assistant_2.boat_id in op.confirmed_assistant_ids
    
    # Step 3: Run simulation steps until assistants arrive and school is harvested
    max_steps = 200
    for _ in range(max_steps):
        sim.update(dt)
        if school.is_depleted:
            break
            
    # Verification: School must be fully depleted
    assert school.is_depleted is True
    assert school.population == 0.0
    assert sim.total_fish_harvested == pytest.approx(30.0)
    
    # Verification: Operation must be completed and removed
    assert len(sim.operation_coordinator.operations) == 0
    assert sim.total_operations_completed == 1
    
    # Verification: All 3 participating boats must have returned to EXPLORING
    for b in sim.boats:
        assert b.state == BoatState.EXPLORING, f"Boat {b.boat_id} should be EXPLORING, got {b.state}"
        assert b.current_operation_id is None

def test_depletion_recovery_while_assistant_in_transit():
    """
    If a school with very low population is depleted by the Lead boat
    while an assistant is still TRAVELING, the assistant must cleanly
    recover to EXPLORING without getting stuck.
    """
    sim = FishSwarmSimulation(width=1000, height=800, margin=50)
    
    # Lead is already at school, assistant is far away (requires several seconds to travel)
    lead = BoatAgent(position=(200, 200), speed=100.0)
    far_assistant = BoatAgent(position=(700, 700), speed=100.0)
    
    # Very small population (depleted in 1-2 frames by lead alone)
    school = FishSchool(position=(210, 210), population=5.0)
    
    sim.add_boat(lead)
    sim.add_boat(far_assistant)
    sim.add_school(school)
    
    dt = 0.1
    # Frame 1: Discovery and recruitment
    sim.update(dt)
    assert far_assistant.state == BoatState.TRAVELING
    
    # Run a few frames: lead harvests the 5 units immediately
    for _ in range(20):
        sim.update(dt)
        if school.is_depleted:
            break
            
    assert school.is_depleted is True
    # Assistant never reached the school, yet must recover cleanly to EXPLORING
    assert far_assistant.state == BoatState.EXPLORING
    assert far_assistant.current_operation_id is None
    assert lead.state == BoatState.EXPLORING

def test_multiple_concurrent_fishing_operations():
    """
    Verify multiple independent fishing operations running simultaneously
    at different fish schools with disjoint teams.
    """
    sim = FishSwarmSimulation(width=1400, height=1000, margin=50)
    
    # Team Alpha (near School Alpha at 200, 200)
    lead_a = BoatAgent((190, 190), speed=150.0)
    asst_a1 = BoatAgent((230, 200), speed=150.0)
    asst_a2 = BoatAgent((200, 230), speed=150.0)
    school_a = FishSchool((200, 200), population=25.0)
    
    # Team Beta (near School Beta at 900, 700)
    lead_b = BoatAgent((890, 690), speed=150.0)
    asst_b1 = BoatAgent((930, 700), speed=150.0)
    asst_b2 = BoatAgent((900, 730), speed=150.0)
    school_b = FishSchool((900, 700), population=25.0)
    
    for b in [lead_a, asst_a1, asst_a2, lead_b, asst_b1, asst_b2]:
        sim.add_boat(b)
    sim.add_school(school_a)
    sim.add_school(school_b)
    
    dt = 0.1
    # Frame 1: Both leads discover their respective schools
    sim.update(dt)
    assert len(sim.operation_coordinator.operations) == 2
    
    # Run until both schools deplete
    for _ in range(150):
        sim.update(dt)
        if school_a.is_depleted and school_b.is_depleted:
            break
            
    assert school_a.is_depleted is True
    assert school_b.is_depleted is True
    assert sim.total_operations_completed == 2
    assert sim.total_fish_harvested == pytest.approx(50.0)
    
    # All 6 boats must be back in EXPLORING
    assert all(b.state == BoatState.EXPLORING for b in sim.boats)


def test_depleted_school_respawns_after_configured_delay():
    sim = FishSwarmSimulation(width=500, height=400, margin=20)
    school = FishSchool((250, 200), population=10.0)
    school.claim("test_op")
    school.apply_harvest("test_op", active_boat_count=1, delta_time=1.0)
    sim.add_school(school)

    sim.update(0.1)  # Registers the respawn timer.
    for _ in range(int(FISH_RESPAWN_DELAY) - 1):
        sim.update(1.0)
    assert school.is_depleted

    sim.update(1.0)
    assert school.is_depleted is False
    assert school.population == pytest.approx(school.initial_population)
    assert school.is_available()
