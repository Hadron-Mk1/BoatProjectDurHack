"""
FishSwarm - Main Application Runner.
Launches the autonomous multi-agent fishing simulation with Pygame.
"""
import sys
import pygame

from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, COLOR_OCEAN_BORDER
from src.core.simulation import FishSwarmSimulation
from src.entities.boat_agent import CleaningBoat, RegularBoat, TowingBoat
from src.entities.fish_school import FishSchool
from src.ui.hud import SimulationHUD
from src.ui.debug_overlay import DebugOverlay
from src.ui.ocean_renderer import OceanRenderer

def create_default_scenario() -> FishSwarmSimulation:
    """Creates a balanced simulation scenario with boats and schools."""
    sim = FishSwarmSimulation(width=OCEAN_WIDTH, height=OCEAN_HEIGHT, margin=40)

    # 1. Spawn fleet of autonomous boats
    fleet = [
        (TowingBoat, (150, 150)),
        (CleaningBoat, (350, 600)),
        (RegularBoat, (600, 300)),
        (RegularBoat, (850, 150)),
        (TowingBoat, (1050, 650)),
        (CleaningBoat, (550, 700)),
        (RegularBoat, (200, 420)),
        (RegularBoat, (1000, 420)),
    ]
    for boat_class, pos in fleet:
        sim.add_boat(boat_class(position=pos))

    # 2. Spawn stationary fish schools with varied populations
    school_configs = [
        ((250, 300), 80.0),
        ((500, 180), 120.0),
        ((750, 500), 100.0),
        ((950, 350), 90.0),
        ((350, 650), 60.0),
    ]
    for pos, pop in school_configs:
        sim.add_school(FishSchool(position=pos, population=pop))

    return sim

def main():
    pygame.init()
    pygame.display.set_caption("FishSwarm - Autonomous Multi-Agent Fishing Simulation")
    screen = pygame.display.set_mode((OCEAN_WIDTH, OCEAN_HEIGHT))
    clock = pygame.time.Clock()
    ocean = OceanRenderer(OCEAN_WIDTH, OCEAN_HEIGHT)

    hud = SimulationHUD()
    sim = create_default_scenario()

    is_paused = False
    speed_multiplier = 1.0
    show_debug = True

    running = True
    while running:
        dt = clock.tick(60) / 1000.0  # Real-world delta time in seconds
        # Cap dt to prevent huge leaps if window moved
        dt = min(dt, 0.1)

        # 1. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    is_paused = not is_paused
                elif event.key == pygame.K_s:
                    # Cycle speed: 1.0x -> 2.0x -> 4.0x -> 1.0x
                    speeds = [1.0, 2.0, 4.0]
                    next_idx = (speeds.index(speed_multiplier) + 1) % len(speeds)
                    speed_multiplier = speeds[next_idx]
                elif event.key == pygame.K_d:
                    show_debug = not show_debug
                elif event.key == pygame.K_r:
                    sim = create_default_scenario()

        # 2. Simulation Step
        if not is_paused:
            effective_dt = dt * speed_multiplier
            sim.update(effective_dt)

        # 3. Rendering
        ocean.draw(screen, sim.sim_time)

        # Ocean boundary border
        b = sim.world_coordinator.bounds
        border_rect = pygame.Rect(
            int(b.min_x),
            int(b.min_y),
            int(b.max_x - b.min_x),
            int(b.max_y - b.min_y),
        )
        pygame.draw.rect(screen, COLOR_OCEAN_BORDER, border_rect, 2)

        # Render fish schools
        for school in sim.schools:
            school.draw(screen, hud.font, show_debug=show_debug, sim_time=sim.sim_time)

        # Render debug connection lines and exploration waypoints
        if show_debug:
            DebugOverlay.draw(screen, sim)

        sim.oil_spill_manager.draw(screen, sim.sim_time)

        # Render boats
        for boat in sim.boats:
            boat.draw(screen, hud.font, show_debug=show_debug)

        sim.rescue_manager.draw(screen)

        # Render HUD
        hud.draw(
            screen,
            sim,
            is_paused=is_paused,
            speed_multiplier=speed_multiplier,
            show_debug=show_debug,
        )

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
