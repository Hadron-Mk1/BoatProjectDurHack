"""
FishSwarm Configuration & Constants.
Centralizes world boundaries, rates, radii, and visual styles.
"""

# Ocean arena boundaries
OCEAN_WIDTH = 1200
OCEAN_HEIGHT = 800
OCEAN_MARGIN = 40.0

# Fish School parameters
DEFAULT_SCHOOL_POPULATION = 100.0
BASE_HARVEST_RATE = 15.0  # Population units depleted per active boat per second
FISHING_RADIUS = 45.0      # Distance within which a boat can actively fish
DETECTION_RADIUS = 140.0   # Boat sensor detection range for fish schools

# Boat kinematics
BOAT_CRUISE_SPEED = 120.0  # Pixels per second
BOAT_TURN_SPEED = 3.5      # Radians per second
BOAT_LENGTH = 32.0
BOAT_WIDTH = 16.0

# Exploration 3x3 grid parameters
EXPLORATION_CELL_SIZE = 120.0  # Width and height of each 3x3 grid cell
WAYPOINT_REACH_RADIUS = 15.0   # Distance to consider a waypoint reached

# Visual palette (Pygame RGB)
COLOR_OCEAN = (20, 50, 85)
COLOR_OCEAN_BORDER = (45, 95, 150)
COLOR_OCEAN_GRID = (30, 65, 105)
COLOR_FISH_SCHOOL = (255, 190, 50)
COLOR_FISH_DEPLETED = (90, 95, 105)

COLOR_EXPLORING = (80, 210, 110)
COLOR_RESERVED = (245, 195, 55)
COLOR_TRAVELING = (65, 165, 255)
COLOR_FISHING = (240, 80, 65)

COLOR_TEXT = (240, 245, 250)
COLOR_DEBUG_RAY = (255, 255, 120, 150)
