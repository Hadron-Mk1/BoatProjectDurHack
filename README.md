# FishSwarm – An Autonomous Multi-Agent Fishing Simulation

FishSwarm is a 2D multi-agent autonomous fishing simulation built in Python with Pygame. Autonomous fishing boats independently explore an ocean using randomised grid patterns, discover different coloured schools of fish, cooperatively signal the nearest available boats, harvest the fish, completing different fish quotas.

---

## Features

- **Autonomous 3×3 Grid Exploration:** 
Boats independently explore local 3×3 grids around their search positions, covering cells whilst keeping within the ocean boundary.
- **Shared Target Coordination:** 
Sonar ships detect fishing areas and transmit signals that allow for some boats to locate their target fishing pool.
- **Proximity-Based Signalling:** 
When fish are discovered, the closest boats within range will be recruited and drawn to the area if it fulfills their own tasks.
- **Simultaneous Discovery Arbitration and Cooperative Harvesting:** 
Deterministic request handling prevents race conditions and eliminates double-booking. Every boat that fishes within an area updates a combined harvest rate, with depletion resulting in a strict zero.
- **Telemetry HUD & Visual Debugger:** 
Real-time metrics display (fleet catch, active schools, boat state distributions) and optional toggle display of hitboxes and signal interactions.
- **Specialized Fleet:** 
Default fleet includes Towing, Cleaning, and Regular boats. All boats fish when available; the towing specialist handles wreck recovery and cleaning boats handle oil spills.
- **Oil Spill Response:** 
Moving boats have a chance to leave a silent spill in open water. The next boat to contact it is slowed and broadcasts the purple hazard alert; available Cleaning Boats are dispatched while the fleet avoids the reported area. Cleaners hold position as they clean, then resume waypoint search.
- **Role-Limited Rescue:** 
Only Towing Boats can fill either of the two rescue slots. A wreck waits for two free Towing Boats; both of which use the normal waypoint steering toward the wreck.
- **Fish Capacity & Recovery:** 
Boat classes have different fish capacities, with depleted fish schools respawning after a certain duration.

---

## Quick Start

### Installation
Ensure Python is installed. Install dependencies:
```bash
pip install -r requirements.txt
```

### Run Automated Tests
All unit and integration tests run entirely within the command line:
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
| **S** | Cycle through simulation speeds (1x → 2x → 4x) |
| **D** | Toggle debug overlays (detection radii, exploration waypoints, cooperation rays) |
| **R** | Reset simulation to the beginning |
| **F11** | Toggle fullscreen / maximized window |
| **M** | Minimize the window |
| **ESC** | Exit simulation |

The window can also be resized or minimized with the operating system's window controls. The simulation keeps its fixed 1200 × 800 world and scales the rendered view to fill the window, so there are no unused bars or gaps. Simulation positions and movement stay unchanged; the view may stretch slightly when the window aspect ratio differs from 3:2.

---

