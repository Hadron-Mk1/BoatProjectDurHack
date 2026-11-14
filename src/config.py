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
FISH_RESPAWN_DELAY = 8.0  # Seconds before a depleted school recovers its initial population
FISHING_RADIUS = 45.0      # Distance within which a boat can actively fish
DETECTION_RADIUS = 140.0   # Boat sensor detection range for fish schools

# Boat kinematics
BOAT_CRUISE_SPEED = 120.0  # Pixels per second
BOAT_TURN_SPEED = 3.5      # Radians per second
BOAT_LENGTH = 32.0
BOAT_WIDTH = 16.0
TOWING_BOAT_SPEED = 72.0
TOWING_BOAT_FISH_CAPACITY = 240.0
CLEANING_BOAT_SPEED = 160.0
CLEANING_BOAT_FISH_CAPACITY = 35.0
REGULAR_BOAT_FISH_CAPACITY = 100.0

# Exploration 3x3 grid parameters
EXPLORATION_CELL_SIZE = 120.0  # Width and height of each 3x3 grid cell
WAYPOINT_REACH_RADIUS = 15.0   # Distance to consider a waypoint reached

# Collision & Rescue parameters
BOAT_COLLISION_DIST = 22.0     # Contact threshold between boats
BOAT_BREAK_CHANCE = 0.10      # 10% chance a collision breaks one boat
BOAT_SEPARATION_GAP = 24.0     # Soft collision separation buffer
RESCUE_TOW_SPEED = 54.0        # Slow tow convoy speed, led by a Towing Boat

# Oil spill hazards
OIL_SPILL_CHANCE = 0.0005
OIL_SPILL_RADIUS = 15.0
OIL_SPILL_SLOW_DURATION = 10.0
OIL_SPILL_SPEED_MULTIPLIER = 0.55
OIL_SPILL_CLEANUP_DURATION = 4.0

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
COLOR_BROKEN = (235, 60, 60)
COLOR_TOWING = (245, 145, 35)
COLOR_TOWING_BOAT = (95, 165, 235)
COLOR_CLEANING_BOAT = (75, 220, 195)
COLOR_OIL_SPILL = (155, 70, 220)

COLOR_TEXT = (240, 245, 250)
COLOR_DEBUG_RAY = (255, 255, 120, 150)
