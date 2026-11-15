"""
FishSwarm - Main Application Runner.
Launches the fishing simulation with Pygame.
"""
import sys
import pygame
from pygame._sdl2 import Window as PygameWindow

from src.config import (
    OCEAN_WIDTH,
    OCEAN_HEIGHT,
    COLOR_OCEAN_BORDER,
    COLOR_FISH_RED,
    COLOR_FISH_BLUE,
    COLOR_FISH_YELLOW,
    COLOR_FISH_GREEN,
    COLOR_FISH_PURPLE,
    COLOR_FISH_ORANGE,
    COLOR_FISH_CYAN,
)
from src.core.simulation import BoatSwarmSimulation
from src.entities.boat_agent import CleaningBoat, RegularBoat, SonarBoat, TowingBoat
from src.entities.fish_school import FishSchool
from src.ui.hud import SimulationHUD
from src.ui.debug_overlay import DebugOverlay
from src.ui.ocean_renderer import OceanRenderer

def create_default_scenario() -> BoatSwarmSimulation:
    #Creates a balanced simulation scenario with boats and schools.
    sim = BoatSwarmSimulation(width=OCEAN_WIDTH, height=OCEAN_HEIGHT, margin=40)

    # Spawn fleet of autonomous boats
    fleet = [
        (TowingBoat, (150, 150), None),
        (CleaningBoat, (350, 600), None),
        (TowingBoat, (400, 350), None),
        (RegularBoat, (600, 300), COLOR_FISH_RED),
        (RegularBoat, (850, 150), COLOR_FISH_BLUE),
        (TowingBoat, (1050, 650), None),
        (CleaningBoat, (550, 700), None),
        (CleaningBoat, (1000, 300), None),
        (RegularBoat, (200, 420), COLOR_FISH_YELLOW),
        (RegularBoat, (1000, 420), COLOR_FISH_GREEN),
        (RegularBoat, (720, 700), COLOR_FISH_PURPLE),
        (RegularBoat, (900, 650), COLOR_FISH_ORANGE),
        (RegularBoat, (750, 100), COLOR_FISH_CYAN),
        (RegularBoat, (400, 700), COLOR_FISH_PURPLE),
        (SonarBoat, (600, 650), None),
        (SonarBoat, (600, 100), None),
        (SonarBoat, (300, 100), None),
        (TowingBoat, (350, 140), None),
        (TowingBoat, (500, 450), None),
        (CleaningBoat, (150, 700), None),
        (CleaningBoat, (450, 250), None),
        (RegularBoat, (300, 180), COLOR_FISH_RED),
        (RegularBoat, (560, 520), COLOR_FISH_BLUE),
    ]
    for boat_class, pos, target_color in fleet:
        sim.add_boat(boat_class(position=pos, target_color=target_color))

    # Spawn stationary fish schools with varied populations
    school_configs = [
        ((250, 300), 80.0, COLOR_FISH_RED),
        ((500, 180), 120.0, COLOR_FISH_BLUE),
        ((750, 500), 100.0, COLOR_FISH_YELLOW),
        ((1020, 650), 90.0, COLOR_FISH_GREEN),
        ((350, 650), 60.0, COLOR_FISH_PURPLE),
        ((850, 250), 90.0, COLOR_FISH_ORANGE),
        ((650, 320), 110.0, COLOR_FISH_CYAN),
    ]
    for pos, pop, color in school_configs:
        sim.add_school(FishSchool(position=pos, population=pop, color=color))

    return sim


def fit_surface_rect(window_size: tuple[int, int]) -> pygame.Rect:
    """Return the full window area, avoiding unused bars around the scene."""
    return pygame.Rect(0, 0, max(1, window_size[0]), max(1, window_size[1]))


def main():
    pygame.init()
    pygame.display.set_caption("FishSwarm - Autonomous Multi-Agent Fishing Simulation")
    pygame.display.set_mode((OCEAN_WIDTH, OCEAN_HEIGHT), pygame.RESIZABLE)
    # Keep a standard decorated window so the OS provides minimize,
    # maximize/restore, and close buttons in its title bar.
    app_window = PygameWindow.from_display_module()
    app_window.resizable = True
    app_window.maximize()
    # Keep the simulation's coordinate system fixed; only scale the final frame.
    screen = pygame.Surface((OCEAN_WIDTH, OCEAN_HEIGHT))
    is_fullscreen = False
    clock = pygame.time.Clock()
    ocean = OceanRenderer(OCEAN_WIDTH, OCEAN_HEIGHT)

    hud = SimulationHUD()
    sim = create_default_scenario()

    is_paused = False
    show_info_ui = True
    show_sim_options = False
    speed_multiplier = 1.0
    display_modes = ("debug", "minimal", "normal")
    display_mode = "debug"

    running = True
    while running:
        dt = clock.tick(60) / 1000.0  # Real-world delta time in seconds
        dt = min(dt, 0.1) 
        """ Caps dt by choosing 0.1 if the delta time is too large from
        window being dragged around, resized, etc """

        # Event Handling / Controls
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11:
                    if is_fullscreen:
                        app_window.set_windowed()
                        app_window.maximize()
                    else:
                        app_window.set_fullscreen(desktop=True)
                    is_fullscreen = not is_fullscreen
                elif event.key == pygame.K_m:
                    app_window.minimize()
                elif event.key == pygame.K_SPACE:
                    is_paused = not is_paused
                elif event.key == pygame.K_s:
                    # Cycle speed: 1.0x -> 2.0x -> 4.0x -> 1.0x
                    speeds = [1.0, 2.0, 4.0]
                    next_idx = (speeds.index(speed_multiplier) + 1) % len(speeds)
                    speed_multiplier = speeds[next_idx]
                elif event.key == pygame.K_d:
                    display_mode = display_modes[(display_modes.index(display_mode) + 1)
                                                 % len(display_modes)]
                elif event.key == pygame.K_i:
                    show_info_ui = not show_info_ui
                elif event.key == pygame.K_TAB:
                    show_sim_options = not show_sim_options
                elif event.key == pygame.K_r:
                    sim = create_default_scenario()
                elif event.key == pygame.K_w:
                    sim.whirlpool_manager.trigger_spawn(sim)


            elif event.type == pygame.MOUSEBUTTONDOWN:
                window = pygame.display.get_surface()
                display_rect = fit_surface_rect(window.get_size())
                logical_pos = (
                    round(event.pos[0] * OCEAN_WIDTH / display_rect.width),
                    round(event.pos[1] * OCEAN_HEIGHT / display_rect.height),
                )
                logical_event = pygame.event.Event(
                    event.type, {**event.dict, "pos": logical_pos}
                )
                sim.pier_manager.handle_event(logical_event, screen, simulation=sim)

        # Makes sure speed multiplier runs correctly
        if not is_paused:
            effective_dt = dt * speed_multiplier
            sim.update(effective_dt)

        # Rendering
        minimal_mode = display_mode == "minimal"
        show_debug = display_mode == "debug"
        ocean.draw(screen, sim.sim_time)
        sim.whirlpool_manager.draw_visuals(screen, sim.sim_time)


        # Ocean border
        b = sim.world_coordinator.bounds
        border_rect = pygame.Rect(
            int(b.min_x),
            int(b.min_y),
            int(b.max_x - b.min_x),
            int(b.max_y - b.min_y),
        )
        if show_debug:
            pygame.draw.rect(screen, COLOR_OCEAN_BORDER, border_rect, 2)

        # Render fish schools
        for school in sim.schools:
            school.draw(
                screen,
                None if minimal_mode else hud.font,
                show_debug=show_debug,
                sim_time=sim.sim_time,
                minimal=minimal_mode,
            )

        # Render debug connection lines and exploration waypoints
        if show_debug:
            DebugOverlay.draw(screen, sim)

        sim.oil_spill_manager.draw(screen, sim.sim_time)

        # Render boats
        for boat in sim.boats:
            boat.draw(
                screen,
                None if minimal_mode else hud.font,
                show_debug=show_debug,
                minimal=minimal_mode,
                show_label=display_mode == "debug",
                animation_time=sim.sim_time,
            )

        sim.rescue_manager.draw(screen, minimal=minimal_mode)

        # Render HUD
        if not minimal_mode and show_info_ui:
            hud.draw(
                screen,
                sim,
                is_paused=is_paused,
                speed_multiplier=speed_multiplier,
                show_debug=show_debug,
                display_mode=display_mode,
                expanded_options=show_sim_options,
            )
        elif not minimal_mode:
            hud.draw_controls(screen, speed_multiplier, display_mode, show_sim_options)
        sim.pier_manager.draw(screen, hud.font, show_ui=True, sim_time=sim.sim_time,
                              simulation=sim)
        sim.whirlpool_manager.draw_ui(screen, hud.font)


        window = pygame.display.get_surface()
        display_rect = fit_surface_rect(window.get_size())
        window.blit(pygame.transform.smoothscale(screen, display_rect.size),
                    display_rect.topleft)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)

if __name__ == "__main__":
    main()
