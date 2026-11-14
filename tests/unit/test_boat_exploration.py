"""
Unit tests for BoatAgent and 3x3 Exploration subsystem.
Verifies 9-cell local grid generation, boundary clamping, shared cell reservations,
state machine transitions, kinematic steering, and sensor detection.
"""
import math
import pytest
import pygame
from src.entities.boat_agent import BoatAgent, BoatState
from src.entities.exploration import LocalGrid
from src.core.world_coordinator import WorldCoordinator
from src.entities.fish_school import FishSchool
from src.config import BOAT_CRUISE_SPEED, DETECTION_RADIUS, FISHING_RADIUS

@pytest.fixture(autouse=True)
def reset_counters():
    """Ensure ID determinism across tests."""
    BoatAgent.reset_id_counter(1)
    FishSchool.reset_id_counter(1)

@pytest.fixture
def coordinator():
    """Provides a fresh WorldCoordinator for tests."""
    return WorldCoordinator(width=1000, height=800, margin=50)

# ----------------- 3x3 Local Grid Tests -----------------

def test_local_grid_contains_exactly_nine_cells(coordinator):
    """A local grid must contain exactly nine cells around its center."""
    grid = LocalGrid(center=(500, 400), bounds=coordinator.bounds, cell_size=100)
    assert grid.total_cells == 9
    assert len(grid.cells) == 9
    assert grid.is_complete() is False
    assert len(grid.get_unvisited_indices()) == 9

def test_local_grid_cells_respect_ocean_boundaries(coordinator):
    """Grid generation near the ocean edge must clamp cells within ocean boundaries."""
    # Place center near corner: margin is 50, center is (60, 60)
    grid = LocalGrid(center=(60, 60), bounds=coordinator.bounds, cell_size=100)
    for cell in grid.cells:
        assert coordinator.bounds.is_inside(cell, use_margin=True)
        assert cell.x >= 50
        assert cell.y >= 50

def test_local_grid_visited_progression(coordinator):
    """Marking cells as visited reduces unvisited count until all 9 are complete."""
    grid = LocalGrid(center=(500, 400), bounds=coordinator.bounds, cell_size=100)
    
    for i in range(8):
        grid.mark_visited(i)
        assert grid.is_complete() is False
        assert len(grid.get_unvisited_indices()) == (9 - (i + 1))
        
    grid.mark_visited(8)
    assert grid.is_complete() is True
    assert len(grid.get_unvisited_indices()) == 0

# ----------------- Shared Exploration Reservation Tests -----------------

def test_shared_exploration_reservation_prevents_overlap(coordinator):
    """Boats must not reserve overlapping exploration cells."""
    target_pos = pygame.Vector2(300, 300)
    
    # Boat 1 reserves target_pos
    assert coordinator.reserve_exploration_target(boat_id=1, target_pos=target_pos) is True
    assert coordinator.get_reserved_target(boat_id=1) == target_pos
    
    # Boat 2 attempts to reserve same target -> must be rejected
    assert coordinator.reserve_exploration_target(boat_id=2, target_pos=target_pos) is False
    
    # Boat 2 attempts to reserve a target very close (within min_separation) -> rejected
    close_pos = pygame.Vector2(320, 310)
    assert coordinator.reserve_exploration_target(boat_id=2, target_pos=close_pos) is False
    
    # Boat 2 reserves a distant target -> succeeds
    far_pos = pygame.Vector2(600, 600)
    assert coordinator.reserve_exploration_target(boat_id=2, target_pos=far_pos) is True
    
    # Once Boat 1 releases its target, another boat can claim it
    coordinator.release_exploration_target(boat_id=1)
    assert coordinator.reserve_exploration_target(boat_id=3, target_pos=target_pos) is True

# ----------------- Boat State Machine Tests -----------------

def test_boat_state_normal_lifecycle():
    """Verify normal lifecycle: EXPLORING -> RESERVED -> TRAVELING -> FISHING -> EXPLORING."""
    boat = BoatAgent((100, 100))
    assert boat.state == BoatState.EXPLORING
    
    # 1. Recruited as assistant
    assert boat.transition_to(BoatState.RESERVED, operation_id="op_1", school_id=1) is True
    assert boat.state == BoatState.RESERVED
    assert boat.current_operation_id == "op_1"
    
    # 2. Assignment confirmed -> TRAVELING
    assert boat.transition_to(BoatState.TRAVELING, school_pos=(200, 200)) is True
    assert boat.state == BoatState.TRAVELING
    
    # 3. Arrives at school -> FISHING
    assert boat.transition_to(BoatState.FISHING) is True
    assert boat.state == BoatState.FISHING
    
    # 4. School depleted -> returns to EXPLORING
    assert boat.transition_to(BoatState.EXPLORING) is True
    assert boat.state == BoatState.EXPLORING
    assert boat.current_operation_id is None

def test_boat_discovering_lead_direct_transition():
    """Discovering boat transitions directly into TRAVELING or FISHING without reserving itself."""
    lead = BoatAgent((100, 100))
    assert lead.transition_to(BoatState.TRAVELING, operation_id="op_lead", school_id=10, school_pos=(150, 150)) is True
    assert lead.state == BoatState.TRAVELING

def test_boat_recovery_transitions(coordinator):
    """Verify recovery from cancelled operations, failed recruitment, and pre-arrival depletion."""
    # Recovery from RESERVED
    boat1 = BoatAgent((100, 100))
    boat1.transition_to(BoatState.RESERVED, operation_id="op_cancelled")
    boat1.reset_to_exploring(coordinator)
    assert boat1.state == BoatState.EXPLORING
    assert boat1.current_operation_id is None
    
    # Recovery from TRAVELING (e.g. school depleted while in transit)
    boat2 = BoatAgent((100, 100))
    boat2.transition_to(BoatState.RESERVED, operation_id="op_depleted")
    boat2.transition_to(BoatState.TRAVELING, school_pos=(400, 400))
    assert boat2.transition_to(BoatState.EXPLORING) is True
    assert boat2.state == BoatState.EXPLORING
    
    # Recovery from FISHING
    boat3 = BoatAgent((100, 100))
    boat3.transition_to(BoatState.TRAVELING, operation_id="op_done")
    boat3.transition_to(BoatState.FISHING)
    assert boat3.transition_to(BoatState.EXPLORING) is True
    assert boat3.state == BoatState.EXPLORING

def test_boat_invalid_transitions_rejected():
    """Invalid transitions must be rejected by the state machine."""
    boat = BoatAgent((100, 100))
    
    # Cannot jump from FISHING to RESERVED
    boat.transition_to(BoatState.TRAVELING, operation_id="op_test")
    boat.transition_to(BoatState.FISHING)
    assert boat.transition_to(BoatState.RESERVED) is False
    assert boat.state == BoatState.FISHING

# ----------------- Kinematics & Boundary Steering Tests -----------------

def test_boat_kinematic_movement_and_boundary_clamping(coordinator):
    """Boat moves toward waypoint and respects ocean boundaries."""
    boat = BoatAgent(position=(100, 100), speed=100.0, heading=0.0)
    target = pygame.Vector2(200, 100)
    
    # Move for 0.5 seconds
    boat.steer_towards(target, delta_time=0.5, world_coordinator=coordinator)
    assert boat.position.x > 100.0, "Boat should advance toward target"
    assert coordinator.bounds.is_inside(boat.position, use_margin=True)
    
    # Steer aggressively towards outside ocean border -> position must be clamped
    out_target = pygame.Vector2(-500, -500)
    for _ in range(20):
        boat.steer_towards(out_target, delta_time=0.5, world_coordinator=coordinator)
    assert coordinator.bounds.is_inside(boat.position, use_margin=True)


def test_boat_slows_near_waypoint_instead_of_orbiting_it(coordinator):
    """A turn-limited boat should converge on a close target instead of circling."""
    boat = BoatAgent(position=(400, 400), speed=120.0, heading=math.pi / 2)
    target = pygame.Vector2(500, 400)

    for _ in range(300):
        boat.steer_towards(target, delta_time=0.1, world_coordinator=coordinator)

    assert boat.position.distance_to(target) <= 15.0

# ----------------- Sensor Perception Tests -----------------

def test_boat_sensor_detection():
    """Boat detects available fish schools within detection_radius."""
    boat = BoatAgent((200, 200))
    
    # School within range (distance 50 < DETECTION_RADIUS 140)
    near_school = FishSchool((250, 200), population=50)
    # School out of range (distance 300 > DETECTION_RADIUS 140)
    far_school = FishSchool((500, 200), population=50)
    # School in range but already claimed
    claimed_school = FishSchool((210, 210), population=50)
    claimed_school.claim("op_other")
    # School in range but depleted
    depleted_school = FishSchool((220, 220), population=0)
    
    detected = boat.detect_schools([near_school, far_school, claimed_school, depleted_school])
    assert len(detected) == 1
    assert detected[0].school_id == near_school.school_id
