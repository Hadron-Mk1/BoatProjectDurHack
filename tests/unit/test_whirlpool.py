"""
Unit tests for FishSwarm Whirlpool Event Mechanic.
Verifies:
1. Whirlpool Spawning & Lifecycle (exact 15s duration, 120s strict minimum cooldown + randomized delay, random spin).
2. Boat Behaviour & State Management (excluding broken boats, task suspension & seamless resumption,
   dual-radius distribution, uniform circumferential spacing, counter-orbit opposite spin direction).
3. UI Status Bar (visible and updating 0-100% during active event, hidden when inactive).
"""
import math
import pytest
import pygame

from src.config import (
    OCEAN_WIDTH,
    OCEAN_HEIGHT,
    WHIRLPOOL_DURATION,
    WHIRLPOOL_MIN_COOLDOWN,
    WHIRLPOOL_INNER_RADIUS,
    WHIRLPOOL_OUTER_RADIUS,
    WHIRLPOOL_RANDOM_DELAY_MIN,
    WHIRLPOOL_RANDOM_DELAY_MAX,
    COLOR_FISH_RED,
    COLOR_FISH_BLUE,
    COLOR_FISH_YELLOW,
)
from src.core.simulation import FishSwarmSimulation
from src.core.whirlpool_manager import WhirlpoolManager
from src.entities.boat_agent import BoatAgent, BoatState, BoatType, RegularBoat, TowingBoat, CleaningBoat, SonarBoat
from src.entities.fish_school import FishSchool


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


def test_whirlpool_initial_randomized_trigger_window():
    """Verify the first whirlpool is scheduled randomly within 120 sim seconds."""
    wm = WhirlpoolManager()
    assert wm.is_active is False
    assert wm.duration == 15.0
    assert wm.min_cooldown == 120.0
    assert wm.cooldown_remaining == 0.0
    assert WHIRLPOOL_RANDOM_DELAY_MIN <= wm.random_delay_remaining <= WHIRLPOOL_RANDOM_DELAY_MAX
    assert wm.progress == 0.0
    assert wm.time_remaining == 0.0

    wm.random_delay_remaining = 120.0
    sim = FishSwarmSimulation()
    wm.update(119.0, sim)
    assert wm.is_active is False
    wm.update(1.0, sim)
    assert wm.is_active is True


def test_whirlpool_duration_is_exactly_15_seconds():
    """Verify whirlpool active phase lasts exactly 15 seconds and then despawns."""
    sim = FishSwarmSimulation()
    boat = RegularBoat(position=(600 + WHIRLPOOL_INNER_RADIUS, 400))
    sim.add_boat(boat)

    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400), spin_direction=1)

    assert wm.is_active is True
    assert wm.duration == 15.0
    assert wm.time_remaining == 15.0
    assert wm.progress == 0.0

    # Advance 5 seconds
    wm.update(5.0, sim)
    assert wm.is_active is True
    assert pytest.approx(wm.time_remaining, rel=1e-3) == 10.0
    assert pytest.approx(wm.progress, rel=1e-3) == 5.0 / 15.0

    # Advance another 9.9 seconds (total 14.9s)
    wm.update(9.9, sim)
    assert wm.is_active is True
    assert pytest.approx(wm.time_remaining, rel=1e-3) == 0.1

    # Advance final 0.1s to reach exactly 15.0s
    wm.update(0.1, sim)
    assert wm.is_active is False
    assert wm.time_remaining == 0.0
    assert wm.progress == 0.0


def test_whirlpool_timers_follow_simulation_time():
    """Whirlpool countdown advances only when simulation time advances."""
    sim = FishSwarmSimulation()
    boat = RegularBoat(position=(600 + WHIRLPOOL_INNER_RADIUS, 400))
    sim.add_boat(boat)
    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))
    assert wm.phase == "countering"

    sim.update(5.0)
    assert sim.sim_time == 5.0
    assert wm.time_remaining == pytest.approx(10.0)

    # A paused app does not call simulation.update(), so whirlpool time freezes.
    frozen_remaining = wm.time_remaining
    frozen_sim_time = sim.sim_time
    assert wm.time_remaining == frozen_remaining
    assert sim.sim_time == frozen_sim_time

    # Simulation speed is represented by the larger delta passed to update.
    sim.update(10.0)
    assert sim.sim_time == 15.0
    assert wm.is_active is False

def test_strict_two_minute_cooldown_and_randomized_trigger_window_after_despawn():
    """
    Enforce a strict 2-minute minimum cooldown after despawn, followed by a
    randomized trigger time within the next 2-minute window.
    """
    sim = FishSwarmSimulation()
    boat = RegularBoat(position=(600 + WHIRLPOOL_INNER_RADIUS, 400))
    sim.add_boat(boat)

    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))
    assert wm.is_active is True

    # Complete the 15s duration to trigger despawn
    wm.update(15.0, sim)
    assert wm.is_active is False

    # Check strict 120s minimum cooldown and randomized window were set.
    assert wm.cooldown_remaining == 120.0
    assert WHIRLPOOL_RANDOM_DELAY_MIN <= wm.random_delay_remaining <= WHIRLPOOL_RANDOM_DELAY_MAX
    wm.random_delay_remaining = 60.0

    # Step 119 seconds: still in cooldown, must NOT spawn
    wm.update(119.0, sim)
    assert wm.is_active is False
    assert pytest.approx(wm.cooldown_remaining, abs=1e-3) == 1.0

    # Step 1 second: exactly 120s has elapsed; random window starts.
    wm.update(1.0, sim)
    assert wm.is_active is False
    assert wm.cooldown_remaining == 0.0
    assert wm.random_delay_remaining == 60.0

    # It remains inactive until the randomized trigger time arrives.
    wm.update(58.99, sim)
    assert wm.is_active is False

    wm.update(1.02, sim)
    assert wm.is_active is True


def test_spin_direction_and_counter_orbit():
    """
    Spin direction must be assigned to clockwise (+1) or anticlockwise (-1).
    Affected boats must orbit in the OPPOSITE direction of whirlpool spin.
    """
    sim = FishSwarmSimulation()
    b1 = RegularBoat(position=(600, 300))
    sim.add_boat(b1)

    wm = sim.whirlpool_manager

    # Test clockwise whirlpool (+1) -> counter-orbit must be anticlockwise (-1)
    wm.trigger_spawn(sim, center=(600, 400), spin_direction=1)
    assert wm.spin_direction == 1
    assert wm.orbit_direction == -1
    wm.despawn(sim)

    # Test anticlockwise whirlpool (-1) -> counter-orbit must be clockwise (+1)
    wm.trigger_spawn(sim, center=(600, 400), spin_direction=-1)
    assert wm.spin_direction == -1
    assert wm.orbit_direction == 1
    wm.despawn(sim)


def test_broken_boats_strictly_excluded():
    """
    Verify behaviour applies to all active boats, EXPLICITLY excluding broken boats,
    which must remain completely unaffected in their current state and position.
    """
    sim = FishSwarmSimulation()
    active_boat1 = RegularBoat(position=(500, 350))
    active_boat2 = TowingBoat(position=(700, 450))
    broken_boat = RegularBoat(position=(300, 200))
    broken_boat.transition_to(BoatState.BROKEN)
    broken_boat_initial_pos = broken_boat.position.copy()
    broken_boat_initial_heading = broken_boat.heading

    sim.add_boat(active_boat1)
    sim.add_boat(active_boat2)
    sim.add_boat(broken_boat)

    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))

    # Active boats must be captured into whirlpool
    assert active_boat1.state == BoatState.WHIRLPOOL
    assert active_boat2.state == BoatState.WHIRLPOOL
    assert active_boat1 in wm.affected_boats
    assert active_boat2 in wm.affected_boats

    # Broken boat must be strictly EXCLUDED
    assert broken_boat not in wm.affected_boats
    assert broken_boat.state == BoatState.BROKEN
    assert broken_boat.needs_rescue is True
    assert broken_boat.position == broken_boat_initial_pos
    assert broken_boat.heading == broken_boat_initial_heading

    for _ in range(30):
        sim.update(0.1)
    assert broken_boat.state == BoatState.BROKEN
    assert broken_boat.position == broken_boat_initial_pos
    assert broken_boat.heading == broken_boat_initial_heading


def test_broken_boat_does_not_block_arrival_or_move_during_whirlpool():
    sim = FishSwarmSimulation()
    broken = RegularBoat(position=(500, 400))
    broken.transition_to(BoatState.BROKEN)
    active = RegularBoat(position=(600 + WHIRLPOOL_INNER_RADIUS, 400))
    sim.add_boat(broken)
    sim.add_boat(active)
    broken_position = broken.position.copy()

    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))
    assert broken not in wm.affected_boats
    assert wm.phase == "countering"

    # An active boat at the wreck's position is not pushed, and the wreck is fixed.
    active.position = broken.position.copy()
    sim.rescue_manager._resolve_collisions(sim, {})
    assert broken.position == broken_position
    assert active.position == broken_position

    # The broken boat is absent from active boats' soft-avoidance points.
    sim.update(0.1)
    assert not any(p.distance_to(broken_position) < 1.0 for p in active.avoidance_positions)

    wm.despawn(sim)
    active.position = broken.position.copy()
    sim.rescue_manager._resolve_collisions(sim, {})
    assert broken.position == broken_position
    assert active.position.distance_to(broken_position) >= 32.0


def test_boat_breaking_during_approach_is_removed_from_readiness_and_not_resumed():
    sim = FishSwarmSimulation()
    broken_mid_event = RegularBoat(position=(300, 300))
    survivor = RegularBoat(position=(850, 650))
    sim.add_boat(broken_mid_event)
    sim.add_boat(survivor)
    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))
    assert wm.phase == "approach"

    broken_mid_event.transition_to(BoatState.BROKEN)
    fixed_position = broken_mid_event.position.copy()
    for _ in range(1000):
        wm.update(0.1, sim)
        if wm.phase == "countering":
            break
    assert wm.phase == "countering"
    assert broken_mid_event not in wm.affected_boats
    assert broken_mid_event.position == fixed_position

    wm.despawn(sim)
    assert broken_mid_event.state == BoatState.BROKEN
    assert broken_mid_event.suspended_task is None
    assert survivor.state == BoatState.EXPLORING


def test_specialized_boats_suspend_and_resume_their_exact_tasks():
    sim = FishSwarmSimulation()
    wreck = RegularBoat(position=(100, 100))
    cleaner = CleaningBoat(position=(300, 300))
    sonar = SonarBoat(position=(700, 600))
    tow = TowingBoat(position=(900, 200))
    tow.claimed_rescue = wreck
    tow.target_position = pygame.Vector2(wreck.position)
    tow.state = BoatState.MOVING_TO_TOW
    cleaner.target_spill = object()
    cleaner.target_position = pygame.Vector2(320, 320)
    cleaner.state = BoatState.MOVING_TO_SPILL
    for boat in (wreck, cleaner, sonar, tow):
        sim.add_boat(boat)

    original = {
        boat.boat_id: (boat.state, boat.target_position.copy() if boat.target_position else None,
                       boat.target_spill, boat.claimed_rescue)
        for boat in (cleaner, sonar, tow)
    }
    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))
    assert all(b.state == BoatState.WHIRLPOOL for b in (cleaner, sonar, tow))
    assert len(wm.affected_boats) == 4
    wm.despawn(sim)

    for boat in (cleaner, sonar, tow):
        state, target, spill, claimed = original[boat.boat_id]
        assert boat.state == state
        assert boat.target_position == target
        assert boat.target_spill is spill
        assert boat.claimed_rescue is claimed

def test_task_suspension_and_seamless_resumption():
    """
    When whirlpool spawns, save/pause each active boat's current task state.
    Immediately after 15s duration ends, restore suspended tasks seamlessly.
    """
    sim = FishSwarmSimulation()
    school = FishSchool(position=(650, 450), population=100.0, color=COLOR_FISH_RED)
    sim.add_school(school)

    boat = RegularBoat(position=(620, 430), target_color=COLOR_FISH_RED)
    sim.add_boat(boat)

    # Transition boat to a specific task state (FISHING) with an assigned operation
    boat.transition_to(
        BoatState.FISHING,
        operation_id="op_alpha_99",
        school_id=school.school_id,
        school_pos=school.position,
    )
    saved_target_pos = pygame.Vector2(650, 450)
    boat.target_position = saved_target_pos.copy()

    assert boat.state == BoatState.FISHING
    assert boat.current_operation_id == "op_alpha_99"

    # Spawn whirlpool
    sim.whirlpool_manager.trigger_spawn(sim, center=(500, 400))

    # Boat task must be paused and transitioned to WHIRLPOOL
    assert boat.state == BoatState.WHIRLPOOL
    assert boat.suspended_task is not None
    assert boat.suspended_task["state"] == BoatState.FISHING
    assert boat.suspended_task["current_operation_id"] == "op_alpha_99"
    assert boat.suspended_task["assigned_school_id"] == school.school_id
    assert boat.suspended_task["target_position"] == saved_target_pos

    # Countering is gated on reaching the slot; approach time is not part of
    # the 15-second fighting duration.
    for _ in range(1000):
        if sim.whirlpool_manager.phase == "countering":
            break
        sim.whirlpool_manager.update(0.1, sim)
    assert sim.whirlpool_manager.phase == "countering"

    # Advance 15 seconds so whirlpool concludes
    sim.whirlpool_manager.update(15.0, sim)

    # Boat must seamlessly resume its exact suspended task
    assert boat.state == BoatState.FISHING
    assert boat.current_operation_id == "op_alpha_99"
    assert boat.assigned_school_id == school.school_id
    assert boat.assigned_school_pos == school.position
    assert boat.target_position == saved_target_pos
    assert boat.suspended_task is None


def test_dual_radius_distribution_and_uniform_spacing():
    """
    Divide orbiting boats evenly across two distinct orbital radii (inner & outer)
    and space them out uniformly along the circumference of each ring to prevent overlapping.
    """
    sim = FishSwarmSimulation()
    # Add 10 boats around the map
    fleet = [
        RegularBoat(position=(200 + i * 80, 200 + (i % 3) * 100))
        for i in range(10)
    ]
    for b in fleet:
        sim.add_boat(b)

    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400), spin_direction=1)

    # Total 10 active boats divided evenly: 5 on inner ring, 5 on outer ring
    assert len(wm.affected_boats) == 10
    assert len(wm.inner_ring_boats) == 5
    assert len(wm.outer_ring_boats) == 5

    # Check inner ring radii and angular offsets
    for boat in wm.inner_ring_boats:
        slot = wm.boat_orbital_slots[boat.boat_id]
        assert slot["ring"] == "inner"
        assert slot["radius"] == WHIRLPOOL_INNER_RADIUS

    # Check outer ring radii and angular offsets
    for boat in wm.outer_ring_boats:
        slot = wm.boat_orbital_slots[boat.boat_id]
        assert slot["ring"] == "outer"
        assert slot["radius"] == WHIRLPOOL_OUTER_RADIUS

    # Check uniform circumferential spacing on inner ring:
    # Consecutive boats must have angular difference of 2*pi / 5
    inner_offsets = sorted(
        wm.boat_orbital_slots[b.boat_id]["base_offset"] for b in wm.inner_ring_boats
    )
    expected_spacing_inner = 2.0 * math.pi / 5.0
    for i in range(len(inner_offsets) - 1):
        diff = inner_offsets[i + 1] - inner_offsets[i]
        assert pytest.approx(diff, rel=1e-3) == expected_spacing_inner

    # Check uniform circumferential spacing on outer ring:
    outer_offsets = sorted(
        wm.boat_orbital_slots[b.boat_id]["base_offset"] for b in wm.outer_ring_boats
    )
    expected_spacing_outer = 2.0 * math.pi / 5.0
    for i in range(len(outer_offsets) - 1):
        diff = outer_offsets[i + 1] - outer_offsets[i]
        assert pytest.approx(diff, rel=1e-3) == expected_spacing_outer

    # Advance simulation and verify boats remain spaced and don't overlap
    for _ in range(50):
        wm.update(0.1, sim)

    # Check that any two boats on the same ring maintain a safe distance
    for ring_boats in (wm.inner_ring_boats, wm.outer_ring_boats):
        for i in range(len(ring_boats)):
            for j in range(i + 1, len(ring_boats)):
                dist = ring_boats[i].position.distance_to(ring_boats[j].position)
                # No overlapping (boat length is 32, gap should be >= 40)
                assert dist > 40.0


def test_top_screen_ui_status_bar():
    """
    Verify progress bar anchored to the top of screen whenever a whirlpool is active,
    tracking completion from 0% to 100%, and hiding once event concludes.
    """
    sim = FishSwarmSimulation()
    boat = RegularBoat(position=(600 + WHIRLPOOL_INNER_RADIUS, 400))
    sim.add_boat(boat)

    surface = pygame.Surface((OCEAN_WIDTH, OCEAN_HEIGHT))
    wm = sim.whirlpool_manager

    # When inactive, draw_ui does nothing (hidden)
    assert wm.is_active is False
    wm.draw_ui(surface)  # Should not raise and should not draw active bar

    # Trigger whirlpool spawn
    wm.trigger_spawn(sim, center=(600, 400))
    assert wm.is_active is True
    assert wm.progress == 0.0

    # Draw at 0%
    wm.draw_ui(surface)

    # Update halfway through (7.5s elapsed)
    wm.update(7.5, sim)
    assert pytest.approx(wm.progress, abs=1e-2) == 0.50
    wm.draw_ui(surface)

    # Update to 15.0s (100% complete)
    wm.update(7.5, sim)
    assert wm.is_active is False
    assert wm.progress == 0.0
    # Once concluded, UI is hidden
    wm.draw_ui(surface)


def test_odd_boat_count_distribution():
    """Verify dual-ring distribution works cleanly for odd and small boat counts."""
    sim = FishSwarmSimulation()
    # 7 boats -> 4 inner, 3 outer
    for i in range(7):
        sim.add_boat(RegularBoat(position=(300 + i * 50, 400)))

    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))
    assert len(wm.affected_boats) == 7
    assert len(wm.inner_ring_boats) == 4
    assert len(wm.outer_ring_boats) == 3
    wm.despawn(sim)

    # 1 boat -> 1 inner, 0 outer
    sim1 = FishSwarmSimulation()
    sim1.add_boat(RegularBoat(position=(500, 400)))
    wm1 = sim1.whirlpool_manager
    wm1.trigger_spawn(sim1, center=(600, 400))
    assert len(wm1.affected_boats) == 1
    assert len(wm1.inner_ring_boats) == 1
    assert len(wm1.outer_ring_boats) == 0
    wm1.despawn(sim1)

    # 0 boats -> 0 inner, 0 outer
    sim0 = FishSwarmSimulation()
    wm0 = sim0.whirlpool_manager
    wm0.trigger_spawn(sim0, center=(600, 400))
    assert len(wm0.affected_boats) == 0
    assert len(wm0.inner_ring_boats) == 0
    assert len(wm0.outer_ring_boats) == 0
    wm0.despawn(sim0)


def test_counter_orbit_angular_motion():
    """Verify boats rotate around the whirlpool center in the counter-orbit direction."""
    sim = FishSwarmSimulation()
    boat = RegularBoat(position=(600 + WHIRLPOOL_INNER_RADIUS, 400))
    sim.add_boat(boat)

    center = pygame.Vector2(600, 400)
    wm = sim.whirlpool_manager
    # Whirlpool spin = clockwise (+1) -> counter-orbit = anticlockwise (-1)
    wm.trigger_spawn(sim, center=center, spin_direction=1)
    assert wm.orbit_direction == -1

    # In polar coordinates: boat at (600 + R, 400) starts near angle 0.
    # An anticlockwise orbit decreases angle in standard screen coords (y-down) or increases CCW.
    # After a small delta_time, the angle advances by orbit_direction * orbit_speed * dt.
    initial_angle = math.atan2(boat.position.y - center.y, boat.position.x - center.x)
    wm.update(1.0, sim)
    new_angle = math.atan2(boat.position.y - center.y, boat.position.x - center.x)

    angle_diff = (new_angle - initial_angle + math.pi) % (2 * math.pi) - math.pi
    # Direction of angle change matches orbit_direction
    assert (angle_diff < 0) == (wm.orbit_direction < 0)


def test_full_scenario_simulation_with_whirlpool():
    """Verify full FishSwarm simulation loop runs without error through an entire whirlpool lifecycle."""
    from run_simulation import create_default_scenario
    sim = create_default_scenario()

    # Step normal simulation for 2 seconds
    for _ in range(20):
        sim.update(0.1)
    # Trigger whirlpool event
    sim.whirlpool_manager.trigger_spawn(sim)
    assert sim.whirlpool_manager.is_active is True

    # Approach does not consume the 15-second fighting duration.
    for _ in range(3000):
        if sim.whirlpool_manager.phase == "countering":
            break
        sim.update(0.1)
    assert sim.whirlpool_manager.phase == "countering"
    for _ in range(int(15.0 / 0.1)):
        sim.update(0.1)

    # Whirlpool must have despawned cleanly
    assert sim.whirlpool_manager.is_active is False
    assert sim.whirlpool_manager.cooldown_remaining == WHIRLPOOL_MIN_COOLDOWN

    # Run another 20 steps post-despawn
    for _ in range(20):
        sim.update(0.1)

\n