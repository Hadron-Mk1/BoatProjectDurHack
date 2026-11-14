"""
FishSwarm - Main Application Runner.
Launches the autonomous multi-agent fishing simulation with Pygame.
"""
import sys
import pygame

from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, COLOR_OCEAN, COLOR_OCEAN_BORDER
from src.core.simulation import FishSwarmSimulation
from src.entities.boat_agent import BoatAgent
from src.entities.fish_school import FishSchool
from src.ui.hud import SimulationHUD
from src.ui.debug_overlay import DebugOverlay

def create_default_scenario() -> FishSwarmSimulation:
    """Creates a balanced simulation scenario with boats and schools."""
    sim = FishSwarmSimulation(width=OCEAN_WIDTH, height=OCEAN_HEIGHT, margin=40)

    # 1. Spawn fleet of autonomous boats
    boat_starts = [
        (150, 150),
        (350, 600),
        (600, 300),
        (850, 150),
        (1050, 650),
        (550, 700),
    ]
    for pos in boat_starts:
        sim.add_boat(BoatAgent(position=pos))

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
        screen.fill(COLOR_OCEAN)

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
            school.draw(screen, hud.font, show_debug=show_debug)

        # Render debug connection lines and exploration waypoints
        if show_debug:
            DebugOverlay.draw(screen, sim)

        # Render boats
        for boat in sim.boats:
            boat.draw(screen, hud.font, show_debug=show_debug)

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
