"""Layered ocean colors and lightweight animated surface ripples."""
import math
import random

import pygame


class OceanRenderer:
    """Caches the water gradient and animates layered, gently traveling waves."""

    def __init__(self, width: int, height: int):
        self.width = int(width)
        self.height = int(height)
        self.base = pygame.Surface((self.width, self.height))
        deep = (8, 31, 51)
        shallow = (24, 91, 111)
        for y in range(self.height):
            blend = y / max(1, self.height - 1)
            blend = blend * blend * (3.0 - 2.0 * blend)
            color = tuple(round(a + (b - a) * blend) for a, b in zip(deep, shallow))
            pygame.draw.line(self.base, color, (0, y), (self.width, y))

        # A broad, translucent shoal of shallow light adds depth without a map-like gradient.
        shoal = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.ellipse(shoal, (85, 151, 151, 8),
                            (int(self.width * .48), int(self.height * .38),
                             int(self.width * .55), int(self.height * .72)))
        pygame.draw.ellipse(shoal, (5, 18, 39, 9),
                            (-int(self.width * .27), -int(self.height * .18),
                             int(self.width * .8), int(self.height * .86)))
        self.base.blit(shoal, (0, 0))

        rng = random.Random(4731)
        self.wave_bands = []
        for index in range(24):
            self.wave_bands.append({
                "x": rng.randrange(-self.width, self.width),
                "y": round((index + .5) * self.height / 24
                           + rng.uniform(-self.height / 36, self.height / 36)),
                "length": rng.randrange(170, 380),
                "amplitude": rng.uniform(1.0, 2.6),
                "phase": rng.uniform(0, math.tau),
                "speed": rng.uniform(.35, .72),
                "drift": rng.uniform(10.0, 24.0),
                "frequency": rng.uniform(.009, .022),
                "width": rng.choice((1, 1, 2)),
                "color": rng.choice(((103, 174, 191, 24), (83, 148, 170, 22),
                                      (153, 195, 187, 23))),
            })
        self.ripple_layer = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

    def draw(self, surface: pygame.Surface, sim_time: float):
        surface.blit(self.base, (0, 0))
        self.ripple_layer.fill((0, 0, 0, 0))
        for wave in self.wave_bands:
            points = []
            x_origin = ((wave["x"] + sim_time * wave["drift"])
                        % (self.width + wave["length"]) - wave["length"])
            for step in range(33):
                x = x_origin + wave["length"] * step / 32
                phase = x * wave["frequency"] - sim_time * wave["speed"] + wave["phase"]
                y = (wave["y"] + math.sin(phase) * wave["amplitude"]
                     + math.sin(phase * .53 + sim_time * .17)
                     * wave["amplitude"] * .32)
                points.append((round(x), round(y)))
            pygame.draw.aalines(self.ripple_layer, wave["color"], False, points)
            if wave["width"] == 2:
                offset_points = [(x, y + 1) for x, y in points]
                pygame.draw.aalines(self.ripple_layer, wave["color"], False, offset_points)
        surface.blit(self.ripple_layer, (0, 0))
