import pygame

from src.core.oil_spill_manager import OilSpillManager
from src.entities.boat_agent import CleaningBoat, RegularBoat, TowingBoat
from src.entities.fish_school import FishSchool
from src.entities.oil_spill import OilSpill
from src.ui.ocean_renderer import OceanRenderer


def pixels(surface):
    return pygame.image.tobytes(surface, "RGB")


def test_boat_classes_render_distinct_role_silhouettes(init_headless_pygame):
    renders = []
    for boat_type in (TowingBoat, CleaningBoat, RegularBoat):
        surface = pygame.Surface((120, 100))
        surface.fill((3, 7, 11))
        boat_type((60, 50)).draw(surface)
        renders.append(pixels(surface))

    assert len(set(renders)) == 3


def test_fish_school_cluster_moves_between_frames(init_headless_pygame):
    school = FishSchool((100, 100), population=100)
    first = pygame.Surface((200, 200))
    second = pygame.Surface((200, 200))
    school.draw(first, sim_time=0.0)
    school.draw(second, sim_time=1.0)

    assert pixels(first) != pixels(second)


def test_slick_is_organic_and_alert_changes_its_render(init_headless_pygame):
    spill = OilSpill(1, pygame.Vector2(100, 100), 15.0)
    manager = OilSpillManager()
    manager.spills.append(spill)
    silent = pygame.Surface((220, 220))
    alerted = pygame.Surface((220, 220))
    silent.fill((12, 35, 50))
    alerted.fill((12, 35, 50))
    manager.draw(silent, 0.0)
    spill.reported = True
    manager.draw(alerted, 0.0)

    assert pixels(silent) != pixels(alerted)
    assert pixels(silent) != pixels(pygame.Surface((220, 220)))


def test_ocean_has_layered_color_and_animated_ripples(init_headless_pygame):
    ocean = OceanRenderer(240, 160)
    first = pygame.Surface((240, 160))
    second = pygame.Surface((240, 160))
    ocean.draw(first, 0.0)
    ocean.draw(second, 1.0)

    assert first.get_at((120, 5)) != first.get_at((120, 155))
    assert pixels(first) != pixels(second)
