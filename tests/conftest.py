"""
Pytest configuration and shared fixtures for FishSwarm testing.
Ensures all tests run cleanly in headless mode.
"""
import os
import sys

# Ensure headless execution before pygame is loaded
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

# Add repository root and src directory to sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(repo_root, "src")
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pytest
import pygame

@pytest.fixture(scope="session", autouse=True)
def init_headless_pygame():
    """Initializes Pygame in headless mode once for the test session."""
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    yield screen
    pygame.quit()
