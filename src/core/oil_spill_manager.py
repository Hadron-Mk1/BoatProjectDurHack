"""Oil-spill generation, avoidance alerts, debuffs, and cleaning-boat AI."""
import math
import random

import pygame

from src.config import (
    OIL_SPILL_CHANCE,
    OIL_SPILL_CLEANUP_DURATION,
    OIL_SPILL_RADIUS,
    OIL_SPILL_SLOW_DURATION,
    OIL_SPILL_SPEED_MULTIPLIER,
    COLOR_OIL_SPILL,
)
from src.core.comms_hub import Message
from src.entities.boat_agent import BoatState, BoatType
from src.entities.oil_spill import OilSpill


class OilSpillManager:
    """Owns all active spills and assigns cleaning boats to distress calls."""

    def __init__(self, rng=None):
        self.rng = rng or random
        self.spills: list[OilSpill] = []
        self._next_spill_id = 1
        self._cleanups: dict[int, dict] = {}
        self._cleaner_to_spill: dict[int, int] = {}
        self.elapsed = 0.0

    def update(self, simulation, delta_time, previous_positions):
        self.elapsed += delta_time
        self._apply_spill_contacts(simulation, previous_positions)
        self._dispatch_waiting_calls(simulation)
        self._update_cleanups(simulation, delta_time)
        self._generate_from_movement(simulation, previous_positions)
        self._keep_boats_clear(simulation)

    def poll(self, simulation):
        """Claim any active spill before the normal boat AI update runs."""
        self._dispatch_waiting_calls(simulation)

    def _generate_from_movement(self, simulation, previous_positions):
        for boat in simulation.boats:
            previous = previous_positions.get(boat.boat_id, boat.position)
            movement = boat.position - previous
            if movement.length_squared() <= 1e-6 or self.rng.random() >= OIL_SPILL_CHANCE:
                continue
            direction = movement.normalize()
            wake_position = previous - direction * (OIL_SPILL_RADIUS * 1.45)
            if not self.is_open_water(simulation, wake_position, OIL_SPILL_RADIUS * 3.0):
                continue
            spill = OilSpill(
                self._next_spill_id, wake_position, OIL_SPILL_RADIUS,
                created_by=boat.boat_id,
            )
            self._next_spill_id += 1
            self.spills.append(spill)

    def is_open_water(self, simulation, position, clearance=0.0):
        """Reject positions outside the ocean or intersecting configured obstacles/spills."""
        bounds = simulation.world_coordinator.bounds
        if not (bounds.min_x + clearance <= position.x <= bounds.max_x - clearance
                and bounds.min_y + clearance <= position.y <= bounds.max_y - clearance):
            return False

        for obstacle in simulation.obstacles:
            if isinstance(obstacle, pygame.Rect):
                if obstacle.inflate(clearance * 2, clearance * 2).collidepoint(position.x, position.y):
                    return False
                continue
            obstacle_position = getattr(obstacle, "position", None)
            obstacle_radius = float(getattr(obstacle, "radius", 0.0))
            if obstacle_position is not None and position.distance_to(obstacle_position) <= clearance + obstacle_radius:
                return False

        return all(position.distance_to(spill.position) > clearance + spill.radius for spill in self.spills)

    @staticmethod
    def _spill_payload(spill):
        return {
            "spill_id": spill.spill_id,
            "position": (spill.position.x, spill.position.y),
            "radius": spill.radius,
        }

    @staticmethod
    def _segment_distance(point, start, end):
        segment = end - start
        length_squared = segment.length_squared()
        if length_squared <= 1e-9:
            return point.distance_to(start)
        t = max(0.0, min(1.0, (point - start).dot(segment) / length_squared))
        return point.distance_to(start + segment * t)

    def _apply_spill_contacts(self, simulation, previous_positions):
        for spill in self.spills:
            for boat in simulation.boats:
                # A spill's creator does not discover what happens.
                if boat.boat_id == spill.created_by:
                    continue
                if boat.boat_id in spill.affected_boat_ids:
                    continue
                previous = previous_positions.get(boat.boat_id, boat.position)
                contact_radius = spill.radius + 0.5 * 16.0
                if self._segment_distance(spill.position, previous, boat.position) > contact_radius:
                    continue
                spill.affected_boat_ids.add(boat.boat_id)
                boat.apply_oil_slow(OIL_SPILL_SLOW_DURATION, OIL_SPILL_SPEED_MULTIPLIER)
                if not spill.reported:
                    spill.reported = True
                    spill.distressed_by = boat.boat_id
                    simulation.comms_hub.send_broadcast(
                        sender_id=boat.boat_id,
                        msg_type=Message.OIL_SPILL_ALERT,
                        payload=self._spill_payload(spill),
                        timestamp=simulation.sim_time,
                    )

    def _dispatch_waiting_calls(self, simulation):
        for spill in self.spills:
            # Silent spills are not announced or assigned until another boat
            # discovers them by contact.
            if not spill.reported or spill.spill_id in self._cleanups:
                continue
            available = [b for b in simulation.boats
                         if b.boat_type == BoatType.CLEANING
                         and b.state not in (BoatState.BROKEN, BoatState.TOWING, BoatState.CLEANING)
                         and b.boat_id not in self._cleaner_to_spill]
            if not available:
                continue
            cleaner = min(available, key=lambda b: b.position.distance_to(spill.position))
            operation = simulation.operation_coordinator.get_boat_operation(cleaner.boat_id)
            if operation is not None:
                school = simulation.get_school(operation.school_id)
                simulation.operation_coordinator.cancel_operation(
                    operation.operation_id, simulation.boats, school, simulation.world_coordinator
                )
            simulation.world_coordinator.release_exploration_target(cleaner.boat_id)
            if not cleaner.transition_to(BoatState.MOVING_TO_SPILL):
                continue
            cleaner.target_position = pygame.Vector2(spill.position)
            cleaner.target_spill = spill
            self._cleanups[spill.spill_id] = {
                "cleaner": cleaner,
                "phase": "approach",
                "remaining": OIL_SPILL_CLEANUP_DURATION,
            }
            self._cleaner_to_spill[cleaner.boat_id] = spill.spill_id
            simulation.comms_hub.send_direct(
                sender_id=spill.distressed_by or cleaner.boat_id,
                target_id=cleaner.boat_id,
                msg_type=Message.OIL_SPILL_DISTRESS,
                payload=self._spill_payload(spill),
                timestamp=simulation.sim_time,
            )

    def _update_cleanups(self, simulation, delta_time):
        spills_by_id = {spill.spill_id: spill for spill in self.spills}
        for spill_id, cleanup in list(self._cleanups.items()):
            spill = spills_by_id.get(spill_id)
            cleaner = cleanup["cleaner"]
            if spill is None:
                cleaner.target_spill = None
                cleaner.reset_to_exploring(simulation.world_coordinator)
                cleaner._update_exploring(delta_time, simulation.world_coordinator)
                self._cleaner_to_spill.pop(cleaner.boat_id, None)
                del self._cleanups[spill_id]
                continue

            if cleanup["phase"] == "approach":
                cleaner.target_position = pygame.Vector2(spill.position)
                cleaner.steer_towards(spill.position, delta_time, simulation.world_coordinator)
                if cleaner.position.distance_to(spill.position) <= spill.radius:
                    cleaner.position = pygame.Vector2(spill.position)
                    cleaner.velocity = pygame.Vector2(0, 0)
                    cleaner.target_position = None
                    cleaner.transition_to(BoatState.CLEANING)
                    cleanup["phase"] = "cleaning"
                continue
            
            cleaner.velocity = pygame.Vector2(0, 0)
            cleanup["remaining"] -= delta_time

            if cleanup["remaining"] <= 0.0:
                self.spills.remove(spill)
                simulation.comms_hub.send_broadcast(
                    sender_id=cleaner.boat_id,
                    msg_type=Message.OIL_SPILL_CLEARED,
                    payload=self._spill_payload(spill),
                    timestamp=simulation.sim_time,
                )
                cleaner.target_spill = None
                cleaner.reset_to_exploring(simulation.world_coordinator)
                simulation.pier_manager.request_support_return(cleaner, simulation)
                self._cleaner_to_spill.pop(cleaner.boat_id, None)
                del self._cleanups[spill_id]

    def _keep_boats_clear(self, simulation):
        assigned_cleaner_ids = set(self._cleaner_to_spill)
        for spill in self.spills:
            if not spill.reported:
                continue
            for boat in simulation.boats:
                if boat.needs_rescue or boat.state == BoatState.BROKEN:
                    continue
                # The first-contact boat needs to travel through the slick to
                # experience its slowdown; only unaffected traffic avoids it.
                if (boat.boat_id in assigned_cleaner_ids
                        or boat.boat_id in spill.affected_boat_ids):
                    continue
                offset = boat.position - spill.position
                safe_distance = spill.radius + 12.0
                if offset.length() >= safe_distance:
                    continue
                direction = offset.normalize() if offset.length_squared() > 1e-9 else pygame.Vector2(1, 0)
                boat.position = simulation.world_coordinator.bounds.clamp(
                    spill.position + direction * safe_distance, use_margin=True
                )

    def draw(self, surface, sim_time):
        """Draw fluid, multi-lobed slicks and warning outlines after discovery."""
        for spill in self.spills:
            padding = int(spill.radius * 2.5 + 18)
            overlay = pygame.Surface((padding * 2, padding * 2), pygame.SRCALPHA)
            center = pygame.Vector2(padding, padding)
            pulse = 0.5 + 0.5 * math.sin(sim_time * 4.8 + spill.spill_id)

            def slick_points(scale=1.0, phase=0.0):
                points = []
                for index in range(48):
                    angle = math.tau * index / 48
                    wobble = (1.0 + 0.2 * math.sin(3 * angle + spill.spill_id * 0.8 + phase)
                              + 0.11 * math.sin(5 * angle - spill.spill_id * 0.45 - phase * 0.7)
                              + 0.055 * math.sin(8 * angle + phase * 1.3))
                    radius = spill.radius * scale * wobble
                    points.append((round(center.x + math.cos(angle) * radius),
                                   round(center.y + math.sin(angle) * radius * 0.72)))
                return points

            outer = slick_points(1.0, sim_time * 0.22)
            if spill.reported:
                fill = (17, 21, 42, 230)
                edge = (*COLOR_OIL_SPILL, 225)
                sheen_colors = ((96, 81, 179, 95), (40, 188, 183, 90), (225, 105, 188, 72))
            else:
                fill = (7, 34, 43, 225)
                edge = (48, 144, 145, 135)
                sheen_colors = ((33, 177, 160, 100), (128, 158, 83, 72), (126, 94, 170, 60))

            pygame.draw.polygon(overlay, fill, outer)
            pygame.draw.polygon(overlay, edge, outer, 2)

            # Overlapping translucent color films create an iridescent sheen.
            for index, color in enumerate(sheen_colors):
                sheen = slick_points(0.66 - index * 0.08,
                                     sim_time * (0.32 if index % 2 == 0 else -0.24) + index * 1.7)
                sheen = sheen[4 + index * 5:31 + index * 4]
                if len(sheen) >= 3:
                    pygame.draw.polygon(overlay, color, [center, *sheen])
            highlight = slick_points(0.82, -sim_time * 0.28 + 1.4)
            pygame.draw.lines(overlay, (179, 229, 205, 130), False, highlight[7:19], 1)

            if spill.reported:
                warning = slick_points(1.2 + pulse * 0.22, sim_time * 0.18)
                pygame.draw.lines(overlay, (*COLOR_OIL_SPILL, 210), True, warning, 2)
                outer_warning = slick_points(1.42 + pulse * 0.28, -sim_time * 0.12)
                pygame.draw.lines(overlay, (*COLOR_OIL_SPILL, 105), True, outer_warning, 1)

            surface.blit(overlay, (round(spill.position.x - padding),
                                   round(spill.position.y - padding)))
