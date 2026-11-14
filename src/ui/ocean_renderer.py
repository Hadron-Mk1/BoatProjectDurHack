"""Layered ocean colors and lightweight animated surface ripples."""
import math
import random

import pygame


class OceanRenderer:
    """Caches the water texture and animates a small set of current lines."""

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
        texture = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for _ in range(380):
            x = rng.randrange(self.width)
            y = rng.randrange(self.height)
            length = rng.randrange(2, 10)
            tint = (152, 204, 201, rng.randrange(5, 15))
            pygame.draw.line(texture, tint, (x, y), (x + length, y + rng.choice((-1, 0, 1))), 1)
        self.base.blit(texture, (0, 0))

        self.ripples = []
        for _ in range(34):
            self.ripples.append({
                "x": rng.randrange(-50, self.width + 50),
                "y": rng.randrange(0, self.height),
                "length": rng.randrange(28, 106),
                "amplitude": rng.uniform(1.2, 4.8),
                "phase": rng.uniform(0, math.tau),
                "speed": rng.uniform(.35, .8),
                "frequency": rng.uniform(.055, .12),
                "color": rng.choice(((143, 201, 206, 48), (96, 164, 179, 38),
                                      (183, 219, 207, 38))),
            })
        self.ripple_layer = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

    def draw(self, surface: pygame.Surface, sim_time: float):
        surface.blit(self.base, (0, 0))
        self.ripple_layer.fill((0, 0, 0, 0))
        for ripple in self.ripples:
            points = []
            for step in range(13):
                x = ripple["x"] + ripple["length"] * step / 12
                y = (ripple["y"]
                     + math.sin(step / 12 * math.tau + sim_time * ripple["speed"]
                                + ripple["phase"]) * ripple["amplitude"]
                     + math.sin(x * ripple["frequency"] + ripple["phase"]
                                - sim_time * .22) * ripple["amplitude"] * .42)
                points.append((round(x), round(y)))
            pygame.draw.lines(self.ripple_layer, ripple["color"], False, points, 1)
        surface.blit(self.ripple_layer, (0, 0))
