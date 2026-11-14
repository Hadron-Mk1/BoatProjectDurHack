"""
Unit tests for FishSchool and OceanBounds.
Verifies unique identity, single-operation locking, combined cooperative harvesting,
population non-negativity, depletion state transitions, and boundary clamping.
"""
import pytest
import pygame
from src.entities.fish_school import FishSchool
from src.core.world import OceanBounds
from src.config import BASE_HARVEST_RATE

@pytest.fixture(autouse=True)
def reset_school_ids():
    """Ensure ID determinism across tests."""
    FishSchool.reset_id_counter(start_id=1)

# ----------------- FishSchool Identity & State Tests -----------------

def test_fish_school_unique_ids():
    """Verify unique auto-incrementing school IDs."""
    school1 = FishSchool((100, 100), population=50)
    school2 = FishSchool((200, 200), population=50)
    school3 = FishSchool((300, 300), population=50)
    
    assert school1.school_id == 1
    assert school2.school_id == 2
    assert school3.school_id == 3
    assert school1.school_id != school2.school_id != school3.school_id

def test_fish_school_explicit_id():
    """Verify explicit school ID assignment and subsequent counter bump."""
    school = FishSchool((100, 100), population=50, school_id=42)
    assert school.school_id == 42
    next_school = FishSchool((200, 200), population=50)
    assert next_school.school_id == 43

def test_fish_school_initial_availability():
    """Verify a newly created school is available and not depleted."""
    school = FishSchool((100, 100), population=100.0)
    assert school.is_available() is True
    assert school.is_depleted is False
    assert school.assigned_operation_id is None
    assert school.population == 100.0

# ----------------- Operation Claim & Locking Tests -----------------

def test_fish_school_single_operation_claim_lock():
    """A fish school can have at most one active fishing operation."""
    school = FishSchool((200, 200), population=100.0)
    
    # Operation A claims school
    assert school.claim("op_alpha") is True
    assert school.assigned_operation_id == "op_alpha"
    assert school.is_available() is False
    
    # Same operation re-claiming succeeds idempotently
    assert school.claim("op_alpha") is True
    
    # Conflicting Operation B attempts to claim the same school -> must fail
    assert school.claim("op_beta") is False
    assert school.assigned_operation_id == "op_alpha"

def test_fish_school_release_by_owner():
    """Releasing by the claiming operation frees the school; strangers cannot release."""
    school = FishSchool((200, 200), population=100.0)
    school.claim("op_alpha")
    
    # Unauthorized release attempt
    assert school.release("op_impostor") is False
    assert school.assigned_operation_id == "op_alpha"
    
    # Authorized release
    assert school.release("op_alpha") is True
    assert school.assigned_operation_id is None
    assert school.is_available() is True

def test_fish_school_depleted_cannot_be_claimed():
    """A depleted school cannot be claimed by any operation."""
    school = FishSchool((100, 100), population=0.0)
    assert school.is_depleted is True
    assert school.claim("op_gamma") is False
    assert school.assigned_operation_id is None

# ----------------- Cooperative Harvesting & Depletion Tests -----------------

def test_single_boat_harvest():
    """Test harvest calculation with one active boat."""
    school = FishSchool((100, 100), population=100.0)
    school.claim("op_1")
    
    # 1 boat for 1.0 second
    harvested = school.apply_harvest(operation_id="op_1", active_boat_count=1, delta_time=1.0)
    expected = BASE_HARVEST_RATE * 1.0 * 1.0
    assert harvested == pytest.approx(expected)
    assert school.population == pytest.approx(100.0 - expected)
    assert school.is_depleted is False

def test_multi_boat_combined_harvest():
    """
    Test cooperative harvesting: combined harvest applied once per update.
    Formula: total_harvest = base_harvest_rate * active_boats * delta_time
    """
    school = FishSchool((100, 100), population=100.0)
    school.claim("op_1")
    
    # 3 boats (1 lead + 2 assistants) for 0.5s
    active_boats = 3
    dt = 0.5
    harvested = school.apply_harvest(operation_id="op_1", active_boat_count=active_boats, delta_time=dt)
    
    expected = BASE_HARVEST_RATE * active_boats * dt
    assert harvested == pytest.approx(expected)
    assert school.population == pytest.approx(100.0 - expected)

def test_unauthorized_operation_cannot_harvest():
    """A school must reject harvesting from an unrelated or expired operation."""
    school = FishSchool((100, 100), population=100.0)
    school.claim("op_legit")
    
    # Malicious or expired operation tries to harvest
    harvested = school.apply_harvest(operation_id="op_intruder", active_boat_count=2, delta_time=1.0)
    assert harvested == 0.0
    assert school.population == 100.0

def test_harvest_population_never_negative_and_marks_depleted():
    """Population must never fall below zero; school marks depleted at zero."""
    school = FishSchool((100, 100), population=10.0)
    school.claim("op_1")
    
    # Request harvest exceeding remaining population (e.g., 3 boats * 15 rate * 1s = 45 units)
    harvested = school.apply_harvest(operation_id="op_1", active_boat_count=3, delta_time=1.0)
    
    assert harvested == pytest.approx(10.0), "Harvest must be capped at remaining population"
    assert school.population == 0.0
    assert school.is_depleted is True
    
    # Subsequent harvest calls return 0
    subsequent = school.apply_harvest(operation_id="op_1", active_boat_count=3, delta_time=1.0)
    assert subsequent == 0.0


def test_respawn_restores_initial_population_and_availability():
    school = FishSchool((100, 100), population=12.0)
    school.claim("op_1")
    school.apply_harvest("op_1", active_boat_count=1, delta_time=1.0)

    assert school.is_depleted
    assert school.respawn() is True
    assert school.population == pytest.approx(12.0)
    assert school.is_available()
    assert school.radius == pytest.approx(30.0)

# ----------------- OceanBounds Environment Tests -----------------

def test_ocean_bounds_containment_and_clamping():
    """Verify ocean boundary detection and coordinate clamping."""
    bounds = OceanBounds(width=1000, height=800, margin=50)
    
    # Inside point
    assert bounds.is_inside((500, 400)) is True
    
    # Boundary edge points
    assert bounds.is_inside((50, 50)) is True
    assert bounds.is_inside((950, 750)) is True
    
    # Outside points (in margin or negative)
    assert bounds.is_inside((20, 400)) is False
    assert bounds.is_inside((980, 400)) is False
    assert bounds.is_inside((500, -10)) is False
    assert bounds.is_inside((500, 810)) is False
    
    # Clamping out-of-bounds coordinate into valid margins
    clamped = bounds.clamp((-20, 900))
    assert clamped.x == 50.0
    assert clamped.y == 750.0
