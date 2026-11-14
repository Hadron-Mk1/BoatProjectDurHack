"""
HUD (Heads-Up Display) for FishSwarm.
Renders real-time simulation metrics, fleet state distributions,
active operations, and playback controls.
"""
from typing import Optional
import pygame
from src.config import (
    COLOR_TEXT,
    COLOR_EXPLORING,
    COLOR_RESERVED,
    COLOR_TRAVELING,
    COLOR_FISHING,
)
from src.entities.boat_agent import BoatState

class SimulationHUD:
    """Renders simulation telemetry and interactive controls."""
    
    def __init__(self, font_size: int = 16, title_size: int = 20):
        pygame.font.init()
        self.font = pygame.font.SysFont("Consolas", font_size, bold=True)
        self.title_font = pygame.font.SysFont("Consolas", title_size, bold=True)
        if self.font is None or self.title_font is None:
            self.font = pygame.font.Font(None, font_size)
            self.title_font = pygame.font.Font(None, title_size)

    def draw(
        self,
        surface: pygame.Surface,
        sim,
        is_paused: bool = False,
        speed_multiplier: float = 1.0,
        show_debug: bool = True,
    ):
        """Draws telemetry overlay on top of the simulation surface."""
        # Semi-transparent background box for HUD in top-left
        hud_bg = pygame.Surface((340, 190), pygame.SRCALPHA)
        hud_bg.fill((15, 25, 45, 210))
        surface.blit(hud_bg, (15, 15))
        pygame.draw.rect(surface, (70, 120, 180), (15, 15, 340, 190), 2)

        # Title
        title_surf = self.title_font.render("FishSwarm Simulation", True, (255, 215, 0))
        surface.blit(title_surf, (25, 22))

        # Metrics
        y = 50
        time_text = f"Sim Time: {sim.sim_time:.1f}s | Speed: {speed_multiplier:.0f}x"
        if is_paused:
            time_text += " [PAUSED]"
        t_surf = self.font.render(time_text, True, COLOR_TEXT)
        surface.blit(t_surf, (25, y))
        y += 22

        harvest_text = f"Total Harvested: {sim.total_fish_harvested:.1f} fish"
        h_surf = self.font.render(harvest_text, True, (255, 200, 80))
        surface.blit(h_surf, (25, y))
        y += 22

        active_schools = sum(1 for s in sim.schools if not s.is_depleted)
        school_text = f"Active Schools: {active_schools} / {len(sim.schools)}"
        s_surf = self.font.render(school_text, True, COLOR_TEXT)
        surface.blit(s_surf, (25, y))
        y += 22

        ops_text = f"Active Operations: {len(sim.operation_coordinator.operations)}"
        o_surf = self.font.render(ops_text, True, COLOR_TEXT)
        surface.blit(o_surf, (25, y))
        y += 25

        # Boat state distribution bar
        counts = {
            BoatState.EXPLORING: sum(1 for b in sim.boats if b.state == BoatState.EXPLORING),
            BoatState.RESERVED: sum(1 for b in sim.boats if b.state == BoatState.RESERVED),
            BoatState.TRAVELING: sum(1 for b in sim.boats if b.state == BoatState.TRAVELING),
            BoatState.FISHING: sum(1 for b in sim.boats if b.state == BoatState.FISHING),
            BoatState.BROKEN: sum(1 for b in sim.boats if b.state == BoatState.BROKEN),
            BoatState.TOWING: sum(1 for b in sim.boats if b.state == BoatState.TOWING),
            BoatState.CLEANING: sum(1 for b in sim.boats if b.state == BoatState.CLEANING),
        }
        
        status_text = f"EXP:{counts[BoatState.EXPLORING]}  RES:{counts[BoatState.RESERVED]}  TRV:{counts[BoatState.TRAVELING]}  FSH:{counts[BoatState.FISHING]}"
        stat_surf = self.font.render(status_text, True, COLOR_TEXT)
        surface.blit(stat_surf, (25, y))
        y += 20

        rescue_text = (
            f"BRK:{counts[BoatState.BROKEN]}  TOW:{counts[BoatState.TOWING]}  "
            f"CLN:{counts[BoatState.CLEANING]}"
        )
        rescue_surf = self.font.render(rescue_text, True, (255, 150, 110))
        surface.blit(rescue_surf, (25, y))
        oil_text = f"Oil Spill Alerts: {len(sim.oil_spill_manager.spills)}"
        oil_surf = self.font.render(oil_text, True, (205, 145, 245))
        surface.blit(oil_surf, (25, y + 19))

        # Controls hint at bottom left
        hint_bg = pygame.Surface((440, 30), pygame.SRCALPHA)
        hint_bg.fill((15, 25, 45, 180))
        surface.blit(hint_bg, (15, surface.get_height() - 45))
        hint = "[SPACE] Pause/Play | [S] Speed (1x/2x/4x) | [D] Debug Overlay"
        hint_surf = self.font.render(hint, True, (190, 210, 230))
        surface.blit(hint_surf, (25, surface.get_height() - 38))
