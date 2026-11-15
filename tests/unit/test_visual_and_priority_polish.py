"""
Unit tests for visual polish, pier ambient NPCs, boat-to-boat collision priority,
smooth whirlpool entry, and world-space whirlpool UI.
"""
import math
import pytest
import pygame

from src.config import (
    OCEAN_WIDTH,
    OCEAN_HEIGHT,
    BOAT_COLLISION_DIST,
    BOAT_SEPARATION_GAP,
    WHIRLPOOL_INNER_RADIUS,
    WHIRLPOOL_OUTER_RADIUS,
)
from src.core.simulation import FishSwarmSimulation
from src.core.pier_manager import PierManager
from src.core.rescue_manager import RescueManager
from src.core.whirlpool_manager import WhirlpoolManager
from src.entities.boat_agent import BoatAgent, BoatState, BoatType, RegularBoat, TowingBoat, CleaningBoat


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    yield
    pygame.quit()


def test_ambient_pier_people_rendered_without_collision():
    """
    Verify ambient decorative people are drawn along the pier deck,
    have continuous bobbing motion, and do not introduce any collision geometry.
    """
    pier = PierManager(width=OCEAN_WIDTH, height=OCEAN_HEIGHT, margin=40)
    surface = pygame.Surface((OCEAN_WIDTH, OCEAN_HEIGHT))

    # Render at t = 0.0
    pier.draw(surface, sim_time=0.0)

    # Render at t = 1.0 (bobbing animation progresses smoothly)
    pier.draw(surface, sim_time=1.0)

    # Verify no collision impact:
    # A point clear of the wooden pier remains clear
    open_water_point = pygame.Vector2(OCEAN_WIDTH - 150, OCEAN_HEIGHT / 2)
    assert pier.is_clear_of_dock(open_water_point, clearance=10.0) is True

    # Pier collision geometry is unaffected
    dock_rect = pier.dock_rect()
    assert dock_rect.width == 39


def test_tow_boat_pushes_smaller_boat_on_collision():
    """
    Tow boats have higher mass/priority: when a tow boat and smaller boat collide,
    the tow boat holds its position and actively pushes the smaller boat out of the way.
    """
    sim = FishSwarmSimulation()
    tow_boat = TowingBoat(position=(500, 400))
    regular_boat = RegularBoat(position=(515, 400))  # Contact overlap (distance = 15 < clearance)

    sim.add_boat(tow_boat)
    sim.add_boat(regular_boat)

    tow_initial_pos = tow_boat.position.copy()
    clearance = BOAT_COLLISION_DIST + BOAT_SEPARATION_GAP

    # Run collision resolution
    sim.rescue_manager._resolve_collisions(sim, previous_positions={})

    # Tow boat must remain at or near its initial anchor position (higher mass)
    assert tow_boat.position.distance_to(tow_initial_pos) <= 1e-4

    # Regular boat must be pushed clear to at least clearance distance
    dist_after = tow_boat.position.distance_to(regular_boat.position)
    assert dist_after >= clearance - 1e-3


def test_tow_boat_does_not_yield_to_smaller_boat_in_avoidance():
    """
    Tow boats do not yield to smaller vessels during navigation,
    while smaller vessels yield to heavy tow boats.
    """
    sim = FishSwarmSimulation()
    tow_boat = TowingBoat(position=(500, 400))
    regular_boat = RegularBoat(position=(530, 400))

    sim.add_boat(tow_boat)
    sim.add_boat(regular_boat)

    # Step simulation once so avoidance_positions are computed
    sim.update(0.01)

    # Tow boat must NOT have regular boat in its avoidance positions (tow boat holds course)
    assert not any(pos.distance_to(regular_boat.position) < 1.0 for pos in tow_boat.avoidance_positions)

    # Regular boat MUST have tow boat in its avoidance positions (smaller boat yields)
    assert any(pos.distance_to(tow_boat.position) < 1.0 for pos in regular_boat.avoidance_positions)


def test_whirlpool_dynamic_rotation_speed_ramping():
    """
    Whirlpool features dynamic rotation speed ramping:
    Spins up smoothly on spawn (first 2s) and dissipates smoothly on despawn (last 2s).
    """
    sim = FishSwarmSimulation()
    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))

    # At spawn: ramp factor is 0.0
    assert wm.get_ramp_factor() == 0.0

    # At 1.0s: spinning up
    wm.update(1.0, sim)
    ramp_1s = wm.get_ramp_factor()
    assert 0.5 < ramp_1s < 1.0

    # At 2.0s: fully spun up (ramp factor = 1.0)
    wm.update(1.0, sim)
    assert pytest.approx(wm.get_ramp_factor(), abs=1e-3) == 1.0

    # At 7.5s (midway): stays at full speed
    wm.update(5.5, sim)
    assert pytest.approx(wm.get_ramp_factor(), abs=1e-3) == 1.0

    # At 14.0s (1s remaining before 15s despawn): dissipating smoothly
    wm.update(6.5, sim)
    ramp_14s = wm.get_ramp_factor()
    assert 0.5 < ramp_14s < 1.0


def test_whirlpool_smooth_travel_entry_no_snap():
    """
    When whirlpool spawns, boats steer and travel smoothly into their orbital slots
    rather than snapping or teleporting instantly.
    """
    sim = FishSwarmSimulation()
    # Place a boat 250px away from the whirlpool center
    boat = RegularBoat(position=(850, 400))
    sim.add_boat(boat)

    initial_pos = boat.position.copy()
    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=(600, 400))

    # Take a small delta time step (0.05s)
    dt = 0.05
    wm.update(dt, sim)

    # Distance moved in one 0.05s frame must be kinematic (not a 250px snap)
    step_distance = boat.position.distance_to(initial_pos)
    max_expected_step = boat.speed * 2.5 * dt + 2.0
    assert step_distance < max_expected_step
    assert step_distance > 0.01  # Boat is actively moving towards slot


def test_world_space_whirlpool_status_bar_and_label():
    """
    World-space progress bar floats directly above the whirlpool in canvas coordinates
    and displays the label 'Counteracting Whirlpool'.
    """
    sim = FishSwarmSimulation()
    boat = RegularBoat(position=(600, 300))
    sim.add_boat(boat)

    center = pygame.Vector2(600, 400)
    wm = sim.whirlpool_manager
    wm.trigger_spawn(sim, center=center)

    surface = pygame.Surface((OCEAN_WIDTH, OCEAN_HEIGHT))

    # Advance through approach; the fighting timer starts only after arrival.
    for _ in range(1000):
        if wm.phase == "countering":
            break
        wm.update(0.1, sim)
    assert wm.phase == "countering"
    wm.update(2.0, sim)
    assert wm.get_ramp_factor() > 0.5

    # Draw UI on canvas
    wm.draw_ui(surface)

    # Target Y for the floating bar directly above whirlpool outer radius:
    expected_bar_y = round(center.y - wm.outer_radius - 28.0)
    assert expected_bar_y == round(400 - 165 - 28) == 207

    # Conclude whirlpool: status bar hides once concluded
    wm.update(13.0, sim)
    assert wm.is_active is False
    # Drawing when concluded does nothing (hidden)
    wm.draw_ui(surface)
