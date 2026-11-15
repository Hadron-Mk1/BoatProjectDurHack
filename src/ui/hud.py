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
        display_mode: str = "debug",
        expanded_options: bool = False,
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

        self.draw_controls(surface, speed_multiplier, display_mode, expanded_options)

    def draw_controls(self, surface: pygame.Surface, speed_multiplier: float = 1.0,
                      display_mode: str = "debug", expanded: bool = False):
        """Keep the keyboard controls visible when the info panel is hidden."""
        if expanded:
            segments = [
                ("[Tab] Minimise | [SPACE] Pause/Play | [S] Speed ", "label"),
                ("1x", "speed_1"), (" / ", "separator"),
                ("2x", "speed_2"), (" / ", "separator"),
                ("4x", "speed_4"),
                (" | [D] Display ", "label"),
                ("Debug", "mode_debug"), (" / ", "separator"),
                ("Minimal", "mode_minimal"), (" / ", "separator"),
                ("Normal", "mode_normal"),
                (" | [I] Info HUD", "label"),
                (" | [Ctrl+F11] Fullscreen", "label"),
            ]
        else:
            segments = [("[Tab] Sim options", "label")]
        active_speed = f"speed_{speed_multiplier:g}"
        active_mode = f"mode_{display_mode.lower()}"
        inactive_color = (145, 165, 180)
        label_color = (190, 210, 230)
        active_color = (255, 255, 225)
        rendered = []
        total_width = 0
        for text, kind in segments:
            active = kind in (active_speed, active_mode)
            color = active_color if active else (
                inactive_color if kind.startswith("speed_") or kind.startswith("mode_")
                or kind == "separator" else label_color
            )
            text_surface = self.font.render(text, True, color)
            pad = 6 if active else 0
            rendered.append((text_surface, active, pad))
            total_width += text_surface.get_width() + pad * 2

        hint_bg = pygame.Surface((total_width + 20, 30), pygame.SRCALPHA)
        hint_bg.fill((15, 25, 45, 180))
        surface.blit(hint_bg, (15, surface.get_height() - 45))
        x = 25
        for text_surface, active, pad in rendered:
            if active:
                chip = pygame.Rect(x, surface.get_height() - 41,
                                   text_surface.get_width() + pad * 2, 22)
                pygame.draw.rect(surface, (38, 81, 98), chip, border_radius=4)
                pygame.draw.rect(surface, (102, 220, 222), chip, 1, border_radius=4)
                x += pad
            surface.blit(text_surface, (x, surface.get_height() - 38))
            x += text_surface.get_width() + (pad if active else 0)
