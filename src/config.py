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
FISH_POPULATION_SCALE = 0.40  # Fish schools contain 60% less biomass than their configured amount.
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
TOWING_BOAT_FISH_CAPACITY = 100.0
CLEANING_BOAT_SPEED = 160.0
CLEANING_BOAT_FISH_CAPACITY = 40.0
REGULAR_BOAT_FISH_CAPACITY = 70.0

# Exploration 3x3 grid parameters
EXPLORATION_CELL_SIZE = 120.0  # Width and height of each 3x3 grid cell
WAYPOINT_REACH_RADIUS = 15.0   # Distance to consider a waypoint reached

# Collision & Rescue parameters
OIL_SPILL_CHANCE = 0.0005
BOAT_COLLISION_DIST = BOAT_LENGTH  # Contact threshold is about one large boat length
BOAT_BREAK_CHANCE = OIL_SPILL_CHANCE / 2  # Break roll per moving boat, matching oil-spill odds
BOAT_SEPARATION_GAP = 0.0      # Keep the enforced center spacing to about one boat length
BOAT_AVOIDANCE_RADIUS = 64.0   # Start steering around nearby vessels before contact
PIER_COLLISION_SAFE_DISTANCE = 90.0  # Docks are protected from collision breakage nearby
RESCUE_TOW_SPEED = 75.6        # 40% faster tow convoy speed
RESCUE_PICKUP_RADIUS = BOAT_COLLISION_DIST + BOAT_SEPARATION_GAP + 4.0

# Oil spill hazards
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

# Distinct fish color palette
COLOR_FISH_RED = (235, 65, 65)
COLOR_FISH_BLUE = (65, 145, 255)
COLOR_FISH_YELLOW = (255, 215, 50)
COLOR_FISH_GREEN = (60, 210, 110)
COLOR_FISH_ORANGE = (255, 140, 40)
COLOR_FISH_PURPLE = (175, 95, 230)
COLOR_FISH_CYAN = (50, 220, 220)
COLOR_CARGO_FULL = (145, 145, 145)

SONAR_PULSE_RADIUS = 400.0
SONAR_DETECTION_RADIUS = 225.0
SONAR_BOAT_SPEED = 150.0
SONAR_PULSE_INTERVAL = 1.5
SONAR_PULSE_DURATION = 0.8

FISH_COLORS: list[tuple[int, int, int]] = [
    COLOR_FISH_RED,
    COLOR_FISH_BLUE,
    COLOR_FISH_YELLOW,
    COLOR_FISH_GREEN,
    COLOR_FISH_ORANGE,
    COLOR_FISH_PURPLE,
    COLOR_FISH_CYAN,
]

FISH_COLOR_MAP: dict[str, tuple[int, int, int]] = {
    "red": COLOR_FISH_RED,
    "blue": COLOR_FISH_BLUE,
    "yellow": COLOR_FISH_YELLOW,
    "green": COLOR_FISH_GREEN,
    "orange": COLOR_FISH_ORANGE,
    "purple": COLOR_FISH_PURPLE,
    "cyan": COLOR_FISH_CYAN,
}


def normalize_fish_color(color):
    """Normalizes a fish color string or RGB tuple into a standard RGB 3-tuple."""
    if color is None:
        return None
    if isinstance(color, str):
        key = color.strip().lower()
        if key in FISH_COLOR_MAP:
            return FISH_COLOR_MAP[key]
        raise ValueError(f"Unknown fish color name: {color}. Expected one of {list(FISH_COLOR_MAP.keys())}")
    if isinstance(color, (tuple, list)):
        return (int(color[0]), int(color[1]), int(color[2]))
    return color


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
