"""Oil slick hazard placed in open water."""
from dataclasses import dataclass, field

import pygame


@dataclass
class OilSpill:
    spill_id: int
    position: pygame.Vector2
    radius: float
    affected_boat_ids: set[int] = field(default_factory=set)
    reported: bool = False
    created_by: int = 0
    distressed_by: int = 0

    @property
    def distress_sent(self):
        """Compatibility name for the spill's reported/alerted status."""
        return self.reported

    @distress_sent.setter
    def distress_sent(self, value):
        self.reported = bool(value)
