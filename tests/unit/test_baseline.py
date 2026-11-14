"""
Baseline test suite for FishSwarm project setup.
Verifies the test environment, headless Pygame display, and existing assets.
"""
import os
import pygame
from Terrain import Terrain

def test_headless_pygame_initialized(init_headless_pygame):
    """Verify that Pygame display is initialized in headless mode."""
    assert pygame.display.get_init(), "Pygame display should be initialized"
    surface = pygame.display.get_surface()
    assert surface is not None, "A valid display surface must exist"
    assert surface.get_size() == (800, 600)

def test_terrain_asset_loading():
    """Verify that existing Terrain loads all 6 animation frames correctly."""
    terrain = Terrain()
    assert len(terrain.terrain_animation_images) == 6, "Terrain must have 6 animation frames"
    assert terrain.image is not None, "Terrain active image must not be None"
    
    # Verify animation frame cycle
    initial_frame = terrain.frame_index
    for _ in range(12):
        terrain.animate()
    assert terrain.frame_index != initial_frame or terrain.frame_timer > 0, "Terrain should step frames"

def test_graphics_directory_integrity():
    """Verify required graphics assets exist."""
    required_graphics = [
        "graphics/terrain1.png",
        "graphics/terrain2.png",
        "graphics/terrain3.png",
        "graphics/terrain4.png",
        "graphics/terrain5.png",
        "graphics/terrain6.png",
        "graphics/speed_fast.png",
        "graphics/speed_slow.png",
        "graphics/paused.png",
        "graphics/unpaused.png",
    ]
    for rel_path in required_graphics:
        assert os.path.exists(rel_path), f"Required asset '{rel_path}' must exist"
