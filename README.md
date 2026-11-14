# FishSwarm – Autonomous Multi-Agent Fishing Simulation

FishSwarm is a 2D multi-agent autonomous fishing simulation built in Python with Pygame. Autonomous fishing boats independently explore an ocean using randomized 3×3 grid patterns, discover stationary fish schools, cooperatively recruit the nearest available boats, harvest the biomass, and return to independent exploration upon school depletion.

---

## Features

- **Autonomous 3×3 Grid Exploration:** Boats independently explore local 3×3 grids around their search positions, systematically covering cells while avoiding ocean boundaries.
- **Shared Target Coordination:** A global coordinator reserves exploration targets, preventing fleet members from unnecessarily overlapping paths.
- **Proximity-Based Recruitment:** When a boat discovers a school, it becomes the Operation Lead and atomically recruits up to two closest available boats ($\min(2, N_{\text{available}})$).
- **Simultaneous Discovery Arbitration:** Deterministic request handling prevents race conditions and eliminates double-booking.
- **Synchronized Cooperative Harvesting:** Combined harvest rate ($\text{base\_rate} \times N_{\text{active}} \times \Delta t$) is calculated once per update; biomass is strictly clamped at zero upon depletion.
- **Clean Lifecycle Recovery:** Participating and in-transit assisting boats smoothly transition back to `EXPLORING` when operations conclude.
- **Telemetry HUD & Visual Debugger:** Real-time metrics display (fleet catch, active schools, boat state distributions) and toggleable vector/range overlays.
- **Specialized Fleet:** Default fleet uses a 1:1:2 Towing, Cleaning, and Regular boat ratio. All boats fish when available; the towing specialist handles wreck recovery and Cleaning Boats handle oil spills.
- **Oil Spill Response:** Moving boats use the configured per-tick chance to leave a silent spill in valid open water. The next boat to contact it is slowed for 10 seconds and broadcasts the purple hazard alert; available Cleaning Boats are dispatched while the fleet avoids the reported area. Cleaners hold position for four seconds, then resume waypoint search immediately.
- **Role-Limited Rescue:** Only Towing Boats can fill either of the two rescue slots. A wreck waits for two free Towing Boats; their approaches use the normal turn-limited waypoint steering toward the wreck.
- **Fish Capacity & Recovery:** Boat classes have different catch capacities, and depleted fish schools respawn at their starting population after eight simulation seconds.

---

## Quick Start

### Installation
Ensure Python (>= 3.10) is installed. Install dependencies:
```bash
pip install -r requirements.txt
```

### Run Automated Tests
All unit and integration tests run headlessly in pure CLI mode:
```bash
python run_tests.py
```

### Launch Interactive Simulation
Launch the visual Pygame simulation:
```bash
python run_simulation.py
```

### Controls
| Key | Action |
| :--- | :--- |
| **SPACE** | Pause / Resume simulation |
| **S** | Cycle simulation speed (1x → 2x → 4x) |
| **D** | Toggle debug overlays (detection radii, exploration waypoints, cooperation rays) |
| **R** | Reset simulation to default scenario |
| **ESC** | Exit simulation |

---

## Project Structure

```
BoatProjectDurHack/
├── run_simulation.py                 # Interactive Pygame visual simulation runner
├── run_tests.py                      # Headless CLI test runner
├── requirements.txt                  # Python dependencies (pygame-ce, pytest)
├── README.md                         # Documentation & controls guide
├── src/
│   ├── config.py                     # Arena bounds, speeds, radii, harvest rates, colors
│   ├── core/
│   │   ├── world.py                  # OceanBounds with containment and margin clamping
│   │   ├── world_coordinator.py      # Shared exploration target reservations
│   │   ├── comms_hub.py              # Modular message broker (DISCOVERY, REQUEST, ACK)
│   │   ├── operation_coordinator.py  # Atomic recruitment (min 2, N_available), safe locking
│   │   └── simulation.py             # Master simulation kernel and synchronized updates
│   ├── entities/
│   │   ├── fish_school.py            # Stationary biomass, single-op claim lock, depletion
│   │   ├── exploration.py            # 3x3 local grid generator, visited-cell tracking
│   │   └── boat_agent.py             # Kinematics, sensors, and 4-state lifecycle machine
│   └── ui/
│       ├── hud.py                    # Real-time metrics dashboard and state counters
│       └── debug_overlay.py          # Detection circles, 3x3 grids, operation connection rays
└── tests/                            # 42 Automated unit and integration tests
    ├── conftest.py                   # Headless Pygame fixture configuration
    ├── unit/
    │   ├── test_baseline.py
    │   ├── test_fish_school.py
    │   ├── test_boat_exploration.py
    │   ├── test_comms_hub.py
    │   ├── test_operation_coordinator.py
    │   └── test_hud.py
    └── integration/
        └── test_cooperative_lifecycle.py
```
