"""
Unit tests for HUD and default scenario configuration.
"""
import pytest
import pygame
from src.ui.hud import SimulationHUD
from run_simulation import create_default_scenario
from src.entities.boat_agent import BoatType

def test_default_scenario_setup():
    """Verify default scenario spawns boats in the requested 1:1:2 ratio."""
    sim = create_default_scenario()
    assert len(sim.boats) == 8
    assert sum(b.boat_type == BoatType.TOWING for b in sim.boats) == 2
    assert sum(b.boat_type == BoatType.CLEANING for b in sim.boats) == 2
    assert sum(b.boat_type == BoatType.REGULAR for b in sim.boats) == 4
    assert len(sim.schools) == 5
    assert all(b.state.value == "EXPLORING" for b in sim.boats)
    assert all(not s.is_depleted for s in sim.schools)

def test_hud_rendering(init_headless_pygame):
    """Verify HUD draws cleanly on Pygame surface without errors."""
    surface = pygame.display.get_surface()
    sim = create_default_scenario()
    hud = SimulationHUD()
    
    # Render with paused=False and paused=True
    hud.draw(surface, sim, is_paused=False, speed_multiplier=1.0)
    hud.draw(surface, sim, is_paused=True, speed_multiplier=2.0)
