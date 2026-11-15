"""Pier, fish missions, and cargo drop-off coordination."""
from dataclasses import dataclass
import math
import random

import pygame

from src.config import BOAT_LENGTH, FISH_COLORS, FISH_COLOR_MAP, COLOR_TEXT
from src.entities.boat_agent import BoatState, BoatType


@dataclass(frozen=True)
class FishingMission:
    color: tuple[int, int, int]
    amount: float
    size: str


class PierManager:
    """Manages fish missions, pier missions, and boats arriving to the pier."""

    MISSION_RANGES = {
        "SMALL": (10, 40),
        "MEDIUM": (41, 70),
        "LARGE": (71, 100),
    }
    ARRIVAL_RADIUS = 22.0
    DOCKING_DWELL = 1.0
    MAX_DOCKED_BOATS = 3
    PIER_LENGTH_SCALE = 0.68
    REPAIR_DOCK_LENGTH_SCALE = 0.68
    BOAT_COLLISION_RADIUS = BOAT_LENGTH / 2 + 2
    MISSION_RESET_COOLDOWN = 1.0
    FISH_CLEARANCE = 55.0
    MISSION_PANEL_WIDTH = 236
    MISSION_PANEL_HEIGHT = 194
    MISSION_BUTTON_SIZE = 36
    FLEET_PANEL_WIDTH = 248
    FLEET_PANEL_HEIGHT = 230
    FLEET_ROW_HEIGHT = 43
    FLEET_BOAT_TYPES = (
        (BoatType.REGULAR, "Regular"),
        (BoatType.TOWING, "Towing"),
        (BoatType.CLEANING, "Cleaning"),
        (BoatType.SONAR, "Sonar"),
    )

    def __init__(self, width: float, height: float, margin: float, rng=None):
        self.width = float(width)
        self.height = float(height)
        self.position = pygame.Vector2(width - margin - 75, height / 2)
        dock_left = self.dock_rect().left
        self.approach_position = pygame.Vector2(
            dock_left - self.BOAT_COLLISION_RADIUS - 2,
            self.position.y,
        )
        self.rng = rng or random
        self.missions = [self._new_mission(size) for size in self.MISSION_RANGES]
        self.mission_cooldowns = [0.0 for _ in self.missions]
        self.menu_open = False
        self.fleet_menu_open = False
        self.dock_slots = {}
        self.docked_until = {}
        self.waiting_for_dock = set()
        self.force_mission_refresh = set()

    def _new_mission(self, size: str, previous=None) -> FishingMission:
        low, high = self.MISSION_RANGES[size]
        colors = [color for color in FISH_COLORS if previous is None or color != previous.color]
        amounts = [amount for amount in range(low, high + 1) if previous is None or amount != round(previous.amount)]
        return FishingMission(
            color=self.rng.choice(colors),
            amount=float(self.rng.choice(amounts)),
            size=size,
        )

    def new_starting_mission(self) -> FishingMission:
        """Create an independent small mission for a newly added fishing boat."""
        return self._new_mission("SMALL")

    def prepare(self, simulation, delta_time: float):
        """Route boats needing service and keep the dock within its capacity."""
        self.mission_cooldowns = [max(0.0, remaining - delta_time)
                                  for remaining in self.mission_cooldowns]
        for boat in simulation.boats:
            if boat.state == BoatState.WHIRLPOOL:
                if boat.boat_id in self.docked_until:
                    self.docked_until[boat.boat_id] += delta_time
                continue
            boat.deposit_glow_remaining = max(0.0, boat.deposit_glow_remaining - delta_time)
            if boat.boat_type == BoatType.SONAR or boat.state in (
                BoatState.BROKEN, BoatState.MOVING_TO_TOW, BoatState.TOWING,
                BoatState.MOVING_TO_SPILL, BoatState.CLEANING,
            ):
                continue
            needs_dock = (
                boat.boat_id in self.force_mission_refresh
                or boat.mission is None
                or (boat.mission is not None and boat.fish_catch >= boat.mission.amount)
            )
            if needs_dock:
                if boat.mission is not None and boat.fish_catch >= boat.mission.amount:
                    self._cancel_boat_operation(simulation, boat)
                self.request_dock(boat, simulation)

    def request_support_return(self, boat, simulation):
        """Send a boat back to the pier after completing towing or cleanup work."""
        if boat.boat_type == BoatType.SONAR:
            return False
        self.force_mission_refresh.add(boat.boat_id)
        self.request_dock(boat, simulation)

    def request_dock(self, boat, simulation):
        """Reserve a mission or let the boat roam until a space becomes free."""
        if boat.boat_type == BoatType.SONAR:
            return False
        boat_id = boat.boat_id
        if boat_id in self.dock_slots:
            if boat.state != BoatState.DUMPING:
                boat.begin_dumping(
                    simulation.world_coordinator,
                    self.approach_position_for(boat_id),
                )
            return True

        occupied = set(self.dock_slots.values())
        slot = next((index for index in range(self.MAX_DOCKED_BOATS)
                     if index not in occupied), None)
        if slot is None:
            self.waiting_for_dock.add(boat_id)
            if boat.state != BoatState.EXPLORING:
                boat.reset_to_exploring(simulation.world_coordinator)
                boat.current_grid = None
            return False

        self.dock_slots[boat_id] = slot
        self.waiting_for_dock.discard(boat_id)
        simulation.world_coordinator.release_exploration_target(boat_id)
        if boat.state != BoatState.DUMPING:
            boat.begin_dumping(
                simulation.world_coordinator,
                self.approach_position_for(boat_id),
            )
        return True

    def approach_position_for(self, boat_id):
        """Return the approach waypoint for a boat's assigned berth."""
        slot = self.dock_slots.get(boat_id, 1)
        y_offset = (slot - 1) * 34
        return pygame.Vector2(self.approach_position.x,
                              self.approach_position.y + y_offset)

    def release_dock(self, boat_id):
        self.dock_slots.pop(boat_id, None)
        self.docked_until.pop(boat_id, None)
        self.waiting_for_dock.discard(boat_id)

    def process_arrivals(self, simulation):
        """Deposit completed loads and assign the next compatible mission at the pier."""
        for boat in simulation.boats:
            if (boat.boat_type == BoatType.SONAR or boat.state != BoatState.DUMPING
                    or boat.boat_id not in self.dock_slots
                    or boat.position.distance_to(self.approach_position_for(boat.boat_id)) > self.ARRIVAL_RADIUS):
                continue

            docked_until = self.docked_until.get(boat.boat_id)
            if docked_until is not None:
                boat.velocity.update(0, 0)
                if simulation.sim_time < docked_until or boat.mission is None:
                    continue
                boat.reset_to_exploring(simulation.world_coordinator)
                boat.current_grid = None
                boat.position.x = (self.dock_rect().left
                                   - self.BOAT_COLLISION_RADIUS - 4)
                self.release_dock(boat.boat_id)
                continue

            boat.position = self.approach_position_for(boat.boat_id)
            boat.target_position = boat.position.copy()
            boat.velocity.update(0, 0)

            if boat.fish_catch > 0.0:
                boat.unload_cargo()
                boat.mission = None
                boat.deposit_glow_remaining = 3.0
            if boat.boat_id in self.force_mission_refresh:
                boat.mission = None

            if boat.mission is None:
                compatible_slots = [
                    index for index, mission in enumerate(self.missions)
                    if mission.amount <= boat.fish_capacity
                    and self.mission_cooldowns[index] <= 0.0
                ]
                slot = max(
                    compatible_slots,
                    key=lambda index: self.missions[index].amount,
                    default=None,
                )
                if slot is not None:
                    mission = self.missions[slot]
                    self.missions[slot] = self._new_mission(mission.size, previous=mission)
                    self.mission_cooldowns[slot] = self.MISSION_RESET_COOLDOWN
                    boat.mission = mission
                    boat.target_color = mission.color
                    self.force_mission_refresh.discard(boat.boat_id)

            if boat.mission is not None:
                self.docked_until[boat.boat_id] = simulation.sim_time + self.DOCKING_DWELL

    def _cancel_boat_operation(self, simulation, boat):
        operation = simulation.operation_coordinator.get_boat_operation(boat.boat_id)
        if operation is None:
            return
        school = simulation.get_school(operation.school_id)
        simulation.operation_coordinator.cancel_operation(
            operation.operation_id, simulation.boats, school,
            simulation.world_coordinator,
        )

    def _menu_header_rect(self, surface):
        dock = self.dock_rect()
        size = self.MISSION_BUTTON_SIZE
        return pygame.Rect(dock.right - size, dock.top - size, size, size)

    def _menu_panel_rect(self, surface):
        header = self._menu_header_rect(surface)
        x = max(8, min(header.right - self.MISSION_PANEL_WIDTH,
                       surface.get_width() - self.MISSION_PANEL_WIDTH - 8))
        y = header.bottom + 5
        if y + self.MISSION_PANEL_HEIGHT > surface.get_height() - 8:
            y = header.y - self.MISSION_PANEL_HEIGHT - 5
        return pygame.Rect(x, max(8, y), self.MISSION_PANEL_WIDTH, self.MISSION_PANEL_HEIGHT)

    def _fleet_header_rect(self, surface):
        size = self.MISSION_BUTTON_SIZE
        repair_dock = self.repair_dock_rect()
        return pygame.Rect(repair_dock.left, repair_dock.top - size, size, size)

    def _fleet_panel_rect(self, surface):
        header = self._fleet_header_rect(surface)
        x = max(8, min(header.right + 4,
                       surface.get_width() - self.FLEET_PANEL_WIDTH - 8))
        y = header.bottom + 5
        if y + self.FLEET_PANEL_HEIGHT > surface.get_height() - 8:
            y = header.y - self.FLEET_PANEL_HEIGHT - 5
        return pygame.Rect(x, max(8, y), self.FLEET_PANEL_WIDTH, self.FLEET_PANEL_HEIGHT)

    def _fleet_row_rect(self, panel, index):
        return pygame.Rect(panel.x + 7, panel.y + 31 + index * self.FLEET_ROW_HEIGHT,
                           panel.width - 14, 39)

    def _fleet_adjust_button_rects(self, row):
        plus = pygame.Rect(row.right - 31, row.centery - 12, 24, 24)
        minus = pygame.Rect(plus.x - 28, plus.y, 24, 24)
        return minus, plus

    def dock_rect(self):
        """Solid rectangular footprint of the pier, extending down the east edge."""
        x, y = round(self.position.x), round(self.position.y)
        original_left = x - 105
        original_length = max(0, round(self.width) - original_left)
        dock_length = min(round(original_length * self.PIER_LENGTH_SCALE), round(self.height))
        return pygame.Rect(round(self.width) - 39, round(y - dock_length / 2), 39, dock_length)

    def repair_dock_rect(self):
        """Solid repair-station footprint on the west edge of the arena."""
        y = round(self.position.y)
        original_left = round(self.position.x) - 105
        original_length = max(0, round(self.width) - original_left)
        dock_length = min(round(original_length * self.REPAIR_DOCK_LENGTH_SCALE),
                          round(self.height))
        return pygame.Rect(0, round(y - dock_length / 2), 39, dock_length)

    @staticmethod
    def _chamfered_points(rect, bevel=None):
        bevel = (min(BOAT_LENGTH / 2, rect.width / 3, rect.height / 3)
                 if bevel is None else min(bevel, rect.width / 3, rect.height / 3))
        return [
            pygame.Vector2(rect.left + bevel, rect.top),
            pygame.Vector2(rect.right - bevel, rect.top),
            pygame.Vector2(rect.right, rect.top + bevel),
            pygame.Vector2(rect.right, rect.bottom - bevel),
            pygame.Vector2(rect.right - bevel, rect.bottom),
            pygame.Vector2(rect.left + bevel, rect.bottom),
            pygame.Vector2(rect.left, rect.bottom - bevel),
            pygame.Vector2(rect.left, rect.top + bevel),
        ]

    @staticmethod
    def _point_in_polygon(point, polygon):
        inside = False
        previous = polygon[-1]
        for current in polygon:
            if ((current.y > point.y) != (previous.y > point.y)
                    and point.x < (previous.x - current.x)
                    * (point.y - current.y) / (previous.y - current.y)
                    + current.x):
                inside = not inside
            previous = current
        return inside

    @staticmethod
    def _segments_intersect(a, b, c, d):
        def orientation(p, q, r):
            return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)

        def on_segment(p, q, r):
            return (min(p.x, r.x) - 1e-6 <= q.x <= max(p.x, r.x) + 1e-6
                    and min(p.y, r.y) - 1e-6 <= q.y <= max(p.y, r.y) + 1e-6)

        first = orientation(a, b, c)
        second = orientation(a, b, d)
        third = orientation(c, d, a)
        fourth = orientation(c, d, b)
        if first * second < 0 and third * fourth < 0:
            return True
        return ((abs(first) <= 1e-6 and on_segment(a, c, b))
                or (abs(second) <= 1e-6 and on_segment(a, d, b))
                or (abs(third) <= 1e-6 and on_segment(c, a, d))
                or (abs(fourth) <= 1e-6 and on_segment(c, b, d)))

    @classmethod
    def _segment_hits_polygon(cls, start, end, polygon):
        if cls._point_in_polygon(start, polygon) or cls._point_in_polygon(end, polygon):
            return True
        previous = polygon[-1]
        for current in polygon:
            if cls._segments_intersect(start, end, previous, current):
                return True
            previous = current
        return False

    @staticmethod
    def _nearest_polygon_edge(point, polygon):
        nearest = None
        outward = None
        best_distance = float("inf")
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            edge = end - start
            length_squared = edge.length_squared()
            ratio = (0.0 if length_squared <= 1e-9 else
                     max(0.0, min(1.0, (point - start).dot(edge) / length_squared)))
            candidate = start + edge * ratio
            distance = point.distance_squared_to(candidate)
            if distance < best_distance:
                best_distance = distance
                nearest = candidate
                outward = pygame.Vector2(edge.y, -edge.x).normalize()
        return nearest, outward

    def repair_position(self):
        """Return the safe drop-off point just east of the repair dock."""
        dock = self.repair_dock_rect()
        return pygame.Vector2(dock.right + self.BOAT_COLLISION_RADIUS + 2,
                              dock.centery)

    def is_clear_of_dock(self, position, clearance=0.0):
        """Return whether a point has the requested clearance from the pier."""
        rect = self.dock_rect()
        rect.inflate_ip(round(clearance * 2), round(clearance * 2))
        return not rect.collidepoint(round(position[0]), round(position[1]))

    def keep_boat_out(self, boat, previous_position, bounds, simulation_time=0.0,
                      delta_time=1 / 60):
        """Deflect boats from beveled pier edges without trapping them on corners."""
        if boat.needs_rescue or boat.state == BoatState.BROKEN:
            return
        current = boat.position.copy()
        previous = pygame.Vector2(previous_position)
        for dock in (self.dock_rect(), self.repair_dock_rect()):
            collision_area = dock.inflate(round(self.BOAT_COLLISION_RADIUS * 2),
                                          round(self.BOAT_COLLISION_RADIUS * 2))
            polygon = self._chamfered_points(collision_area)
            current_inside = self._point_in_polygon(current, polygon)
            previous_inside = self._point_in_polygon(previous, polygon)
            crossed = current_inside or self._segment_hits_polygon(previous, current, polygon)
            if not crossed:
                continue

            # Docked boats occupy the safe approach point beside the mission pier.
            if boat.state == BoatState.DUMPING and boat.boat_id in self.dock_slots:
                return

            response_point = current if current_inside else previous
            edge_point, outward = self._nearest_polygon_edge(response_point, polygon)
            safe_position = bounds.clamp(edge_point + outward * 2.0, use_margin=True)
            target = boat.target_position
            if (target is not None
                    and boat.state in (BoatState.IDLE, BoatState.EXPLORING,
                                       BoatState.MOVING_TO_SPILL)
                    and self._point_in_polygon(target, polygon)):
                boat.target_position = safe_position.copy()

            if current_inside:
                boat.position = safe_position
            else:
                boat.position = bounds.clamp(previous + outward * 2.0, use_margin=True)
            velocity = pygame.Vector2(boat.velocity)
            if velocity.dot(outward) < 0.0:
                boat.velocity = velocity - 2 * velocity.dot(outward) * outward
            if boat.velocity.length_squared() > 1e-6:
                boat.heading = math.atan2(boat.velocity.y, boat.velocity.x)
            return

    def handle_event(self, event, surface, simulation=None):
        """Handle mission and live fleet controls on the pier."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        mission_header = self._menu_header_rect(surface)
        fleet_header = self._fleet_header_rect(surface)
        mission_panel = self._menu_panel_rect(surface)
        fleet_panel = self._fleet_panel_rect(surface)
        if mission_header.collidepoint(event.pos):
            self.menu_open = not self.menu_open
            self.fleet_menu_open = False
        elif fleet_header.collidepoint(event.pos):
            self.fleet_menu_open = not self.fleet_menu_open
            self.menu_open = False
        elif self.fleet_menu_open and fleet_panel.collidepoint(event.pos):
            if simulation is not None:
                for index, (boat_type, _) in enumerate(self.FLEET_BOAT_TYPES):
                    row = self._fleet_row_rect(fleet_panel, index)
                    minus, plus = self._fleet_adjust_button_rects(row)
                    if minus.collidepoint(event.pos):
                        simulation.adjust_boat_count(boat_type, -1)
                        return
                    if plus.collidepoint(event.pos):
                        simulation.adjust_boat_count(boat_type, 1)
                        return
        elif self.menu_open and not mission_panel.collidepoint(event.pos):
            self.menu_open = False
        elif self.fleet_menu_open and not fleet_panel.collidepoint(event.pos):
            self.fleet_menu_open = False

    def _draw_ambient_people(self, surface: pygame.Surface, sim_time: float = 0.0):
        """
        Renders miniature decorative people standing along the pier deck.
        Each person is rendered using simple geometric shapes (circle for head, triangle for body)
        with continuous, subtle up-and-down bobbing motion with staggered sine-wave offsets.
        Zero collision or gameplay impact.
        """
        dock = self.dock_rect()
        deck = dock.inflate(-7, -6)
        repair_dock = self.repair_dock_rect()
        repair_deck = repair_dock.inflate(-7, -6)

        # Ambient people configurations on main pier: (x_rel, y_rel, phase, bob_speed, shirt_color)
        main_pier_people = [
            (0.35, 0.18, 0.0, 3.1, (245, 195, 40)),   # Yellow slicker
            (0.65, 0.38, 1.4, 2.8, (45, 95, 175)),   # Navy jacket
            (0.38, 0.62, 2.7, 3.3, (215, 60, 50)),   # Red jacket
            (0.62, 0.82, 4.2, 2.9, (45, 165, 115)),  # Seafoam sweater
        ]

        # Ambient people on repair dock
        repair_people = [
            (0.50, 0.32, 0.9, 3.0, (235, 135, 35)),   # Orange workwear
            (0.52, 0.68, 3.4, 2.7, (90, 115, 135)),   # Mechanic blue-grey
        ]

        for deck_rect, people_list in ((deck, main_pier_people), (repair_deck, repair_people)):
            if deck_rect.width <= 0 or deck_rect.height <= 0:
                continue
            for x_rel, y_rel, phase, speed, shirt_color in people_list:
                bx = deck_rect.left + deck_rect.width * x_rel
                by = deck_rect.top + deck_rect.height * y_rel
                # Continuous staggered sine-wave vertical bobbing
                bob = math.sin(sim_time * speed + phase) * 1.4
                cy = by + bob

                # Miniature ground contact shadow
                shadow_surf = pygame.Surface((10, 4), pygame.SRCALPHA)
                pygame.draw.ellipse(shadow_surf, (20, 20, 20, 75), (0, 0, 10, 4))
                surface.blit(shadow_surf, (round(bx - 5), round(by + 6)))

                # Body: simple geometric triangle pointing upward
                body_top = (bx, cy - 2)
                body_left = (bx - 3.5, cy + 6)
                body_right = (bx + 3.5, cy + 6)
                pygame.draw.polygon(surface, shirt_color, [body_top, body_left, body_right])
                pygame.draw.polygon(surface, (25, 30, 40), [body_top, body_left, body_right], 1)

                # Head: simple geometric circle
                head_center = (round(bx), round(cy - 5))
                head_radius = 2.5
                pygame.draw.circle(surface, (245, 208, 175), head_center, head_radius)
                # Subtle dark hair / sailor cap
                pygame.draw.circle(surface, (35, 45, 60), (head_center[0], head_center[1] - 1), 2)

    def draw(self, surface, font=None, show_ui=True, sim_time: float = 0.0,
             simulation=None):
        """Draw a slim right-edge jetty and a polished, collapsible mission list."""
        dock = self.dock_rect()
        pygame.draw.polygon(surface, (73, 57, 43), [
            (round(point.x), round(point.y))
            for point in self._chamfered_points(dock, 7)
        ])
        deck = dock.inflate(-7, -6)
        pygame.draw.polygon(surface, (183, 151, 105), [
            (round(point.x), round(point.y))
            for point in self._chamfered_points(deck, 6)
        ])
        pygame.draw.line(surface, (224, 194, 145), (deck.left + 4, deck.top + 5),
                         (deck.left + 4, deck.bottom - 5), 2)
        for plank_y in range(deck.top + 16, deck.bottom - 5, 22):
            pygame.draw.line(surface, (145, 113, 78), (deck.left + 2, plank_y),
                             (deck.right - 2, plank_y), 1)
        for post_y in (dock.top + 10, dock.top + 70, dock.top + 130,
                       dock.bottom - 10):
            if dock.top <= post_y <= dock.bottom:
                pygame.draw.circle(surface, (91, 72, 55), (dock.left + 2, post_y), 4)
                pygame.draw.circle(surface, (91, 72, 55), (dock.right - 2, post_y), 4)

        repair_dock = self.repair_dock_rect()
        pygame.draw.polygon(surface, (48, 63, 75), [
            (round(point.x), round(point.y))
            for point in self._chamfered_points(repair_dock, 7)
        ])
        repair_deck = repair_dock.inflate(-7, -6)
        pygame.draw.polygon(surface, (112, 135, 145), [
            (round(point.x), round(point.y))
            for point in self._chamfered_points(repair_deck, 6)
        ])
        for plank_y in range(repair_deck.top + 16, repair_deck.bottom - 5, 22):
            pygame.draw.line(surface, (77, 100, 111),
                             (repair_deck.left + 2, plank_y),
                             (repair_deck.right - 2, plank_y), 1)
        for post_y in (repair_dock.top + 10, repair_dock.top + 70,
                       repair_dock.top + 130, repair_dock.bottom - 10):
            if repair_dock.top <= post_y <= repair_dock.bottom:
                pygame.draw.circle(surface, (48, 63, 75),
                                   (repair_dock.left + 2, post_y), 4)
                pygame.draw.circle(surface, (48, 63, 75),
                                   (repair_dock.right - 2, post_y), 4)
        wrench_color = (230, 205, 125)
        pygame.draw.line(surface, wrench_color,
                         (repair_dock.centerx - 5, repair_dock.centery + 5),
                         (repair_dock.centerx + 2, repair_dock.centery - 2), 3)
        pygame.draw.circle(surface, wrench_color,
                           (repair_dock.centerx + 3, repair_dock.centery - 3), 4, 2)
        pygame.draw.line(surface, (112, 135, 145),
                         (repair_dock.centerx + 3, repair_dock.centery - 7),
                         (repair_dock.centerx + 7, repair_dock.centery - 3), 3)

        # Render ambient miniature decorative people standing on the pier deck
        self._draw_ambient_people(surface, sim_time)


        if not show_ui:
            return

        if font is None and pygame.font.get_init():
            font = pygame.font.SysFont("Arial", 13, bold=True)
        if font is None or not pygame.font.get_init():
            return

        header = self._menu_header_rect(surface)
        is_full = len(self.dock_slots) >= self.MAX_DOCKED_BOATS
        header_fill = (49, 32, 30) if is_full else (11, 27, 41)
        header_border = (218, 112, 78) if is_full else (93, 158, 183)
        pygame.draw.rect(surface, header_fill, header, border_radius=8)
        pygame.draw.rect(surface, header_border, header, 1, border_radius=8)
        arrow_surf = font.render("<", True, (193, 218, 226))
        surface.blit(arrow_surf, arrow_surf.get_rect(center=header.center))

        fleet_header = self._fleet_header_rect(surface)
        pygame.draw.rect(surface, (11, 27, 41), fleet_header, border_radius=8)
        pygame.draw.rect(surface, (93, 158, 183), fleet_header, 1, border_radius=8)
        fleet_icon = font.render(">", True, (193, 218, 226))
        surface.blit(fleet_icon, fleet_icon.get_rect(center=fleet_header.center))

        if not self.menu_open and not self.fleet_menu_open:
            return

        heading_font = pygame.font.SysFont("Arial", 13, bold=True)
        small_font = pygame.font.SysFont("Arial", 10, bold=True)
        if self.menu_open:
            panel = self._menu_panel_rect(surface)
            panel_fill = pygame.Surface(panel.size, pygame.SRCALPHA)
            pygame.draw.rect(panel_fill, (10, 24, 37, 150), panel_fill.get_rect(), border_radius=9)
            surface.blit(panel_fill, panel)
            pygame.draw.rect(surface, (47, 78, 94), panel, 1, border_radius=9)
            heading = heading_font.render("Missions", True, (229, 240, 245))
            surface.blit(heading, heading.get_rect(center=(panel.centerx, panel.y + 17)))
            amount_font = pygame.font.SysFont("Arial", 16, bold=True)
            color_names = {value: name.upper() for name, value in FISH_COLOR_MAP.items()}
            for index, mission in enumerate(self.missions):
                row = pygame.Rect(panel.x + 7, panel.y + 31 + index * 49,
                                  panel.width - 14, 45)
                row_fill = pygame.Surface(row.size, pygame.SRCALPHA)
                pygame.draw.rect(row_fill, (20, 41, 56, 135), row_fill.get_rect(), border_radius=6)
                surface.blit(row_fill, row)
                pygame.draw.rect(surface, (51, 76, 88), row, 1, border_radius=6)
                pygame.draw.rect(surface, mission.color, (row.x + 1, row.y + 5, 3, row.height - 10),
                                 border_radius=2)
                pygame.draw.circle(surface, mission.color, (row.x + 19, row.centery), 6)
                remaining = self.mission_cooldowns[index]
                if remaining > 0.0:
                    resetting = small_font.render(f"RESETTING  {remaining:.1f}s", True,
                                                   (245, 190, 105))
                    surface.blit(resetting, (row.x + 32, row.centery - 5))
                    continue
                size_label = small_font.render(mission.size, True, (152, 183, 196))
                amount_label = amount_font.render(f"{mission.amount:.0f}", True, (242, 246, 239))
                fish_label = small_font.render(color_names.get(mission.color, "FISH"), True,
                                               (166, 193, 201))
                surface.blit(size_label, (row.x + 32, row.y + 5))
                surface.blit(amount_label, (row.x + 32, row.y + 18))
                surface.blit(fish_label, (row.right - fish_label.get_width() - 8, row.centery - 5))

        if self.fleet_menu_open:
            panel = self._fleet_panel_rect(surface)
            panel_fill = pygame.Surface(panel.size, pygame.SRCALPHA)
            pygame.draw.rect(panel_fill, (10, 24, 37, 205), panel_fill.get_rect(), border_radius=9)
            surface.blit(panel_fill, panel)
            pygame.draw.rect(surface, (47, 78, 94), panel, 1, border_radius=9)
            heading = heading_font.render("Fleet", True, (229, 240, 245))
            surface.blit(heading, heading.get_rect(center=(panel.centerx, panel.y + 17)))
            count_font = pygame.font.SysFont("Arial", 14, bold=True)
            for index, (boat_type, label) in enumerate(self.FLEET_BOAT_TYPES):
                row = self._fleet_row_rect(panel, index)
                row_fill = pygame.Surface(row.size, pygame.SRCALPHA)
                pygame.draw.rect(row_fill, (20, 41, 56, 190), row_fill.get_rect(), border_radius=6)
                surface.blit(row_fill, row)
                pygame.draw.rect(surface, (51, 76, 88), row, 1, border_radius=6)
                label_surf = small_font.render(label, True, (202, 220, 226))
                surface.blit(label_surf, (row.x + 10, row.centery - label_surf.get_height() // 2))
                count = simulation.boat_count(boat_type) if simulation is not None else 0
                count_surf = count_font.render(str(count), True, (242, 246, 239))
                minus, plus = self._fleet_adjust_button_rects(row)
                surface.blit(count_surf, count_surf.get_rect(center=(minus.left - 15, row.centery)))
                self._draw_fleet_adjust_button(surface, minus, "−", enabled=count > 0)
                self._draw_fleet_adjust_button(surface, plus, "+", enabled=True)

    @staticmethod
    def _draw_fleet_adjust_button(surface, rect, label, enabled=True):
        fill = (24, 58, 73) if enabled else (31, 39, 46)
        border = (85, 166, 184) if enabled else (64, 76, 82)
        pygame.draw.rect(surface, fill, rect, border_radius=5)
        pygame.draw.rect(surface, border, rect, 1, border_radius=5)
        font = pygame.font.SysFont("Arial", 16, bold=True)
        glyph = font.render(label, True, (219, 237, 240) if enabled else (116, 128, 132))
        surface.blit(glyph, glyph.get_rect(center=rect.center))
