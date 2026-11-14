"""
Baseline test suite for FishSwarm project setup.
Verifies the test environment, headless Pygame display, and font subsystem.
"""
import os
import pygame

def test_headless_pygame_initialized(init_headless_pygame):
    """Verify that Pygame display is initialized in headless mode."""
    assert pygame.display.get_init(), "Pygame display should be initialized"
    surface = pygame.display.get_surface()
    assert surface is not None, "A valid display surface must exist"
    assert surface.get_size() == (800, 600)

def test_headless_surface_creation():
    """Verify arbitrary surface creation and pixel fill operations."""
    test_surface = pygame.Surface((200, 200))
    test_surface.fill((20, 50, 85))
    assert test_surface.get_size() == (200, 200)

def test_font_subsystem():
    """Verify Pygame font subsystem initializes and renders text."""
    pygame.font.init()
    assert pygame.font.get_init(), "Font subsystem must be initialized"
    font = pygame.font.Font(None, 24)
    rendered = font.render("FishSwarm Test", True, (255, 255, 255))
    assert rendered.get_width() > 0
    assert rendered.get_height() > 0
