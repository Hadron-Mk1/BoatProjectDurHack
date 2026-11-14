"""Collision detection and two-boat recovery for the simulation kernel."""
import random

import pygame

from src.config import (
    BOAT_BREAK_CHANCE, BOAT_COLLISION_DIST, BOAT_SEPARATION_GAP,
    RESCUE_TOW_SPEED, WAYPOINT_REACH_RADIUS,
)
from src.entities.boat_agent import BoatState, BoatType


class RescueManager:
    """Resolves boat contacts and coordinates a pair of boats towing a wreck."""

    def __init__(self, rng=None):
        self.rng = rng or random
        self._encounters = set()
        self._incidents = []

    def update(self, simulation, delta_time, previous_positions=None):
        self._update_tows(simulation, delta_time)
        self._resolve_collisions(simulation, previous_positions or {})

    def _resolve_collisions(self, simulation, previous_positions):
        eligible_states = (BoatState.EXPLORING, BoatState.TRAVELING, BoatState.FISHING)
        boats = [b for b in simulation.boats if b.state in eligible_states]
        active_pairs = set()

        for index, first in enumerate(boats):
            for second in boats[index + 1:]:
                if first.state not in eligible_states or second.state not in eligible_states:
                    continue
                pair = frozenset((first.boat_id, second.boat_id))
                first_start = previous_positions.get(first.boat_id, first.position)
                second_start = previous_positions.get(second.boat_id, second.position)
                relative_start = second_start - first_start
                relative_motion = (second.position - second_start) - (first.position - first_start)
                motion_squared = relative_motion.length_squared()
                closest_t = 0.0
                if motion_squared > 1e-9:
                    closest_t = max(0.0, min(1.0, -relative_start.dot(relative_motion) / motion_squared))
                swept_distance = (relative_start + relative_motion * closest_t).length()
                final_delta = second.position - first.position
                final_distance = final_delta.length()

                if min(swept_distance, final_distance) >= BOAT_COLLISION_DIST + BOAT_SEPARATION_GAP:
                    continue

                active_pairs.add(pair)
                collided = swept_distance < BOAT_COLLISION_DIST
                if final_distance < BOAT_COLLISION_DIST:
                    direction = final_delta.normalize() if final_distance > 1e-6 else pygame.Vector2(1, 0)
                    separation = (BOAT_SEPARATION_GAP - final_distance) / 2
                    first.position -= direction * separation
                    second.position += direction * separation
                    first.position = simulation.world_coordinator.bounds.clamp(first.position, use_margin=True)
                    second.position = simulation.world_coordinator.bounds.clamp(second.position, use_margin=True)

                if collided and pair not in self._encounters:
                    self._encounters.add(pair)
                    if self.rng.random() < BOAT_BREAK_CHANCE:
                        first_contact = first_start + (first.position - first_start) * closest_t
                        second_contact = second_start + (second.position - second_start) * closest_t
                        self._start_tow(simulation, first, second, (first_contact + second_contact) / 2)

        # A new roll becomes possible only after boats separate beyond contact range.
        self._encounters.intersection_update(active_pairs)

    def _start_tow(self, simulation, first, second, contact_position):
        colliders = {first.boat_id, second.boat_id}
        wreck = self.rng.choice((first, second))
        wreck_operation = simulation.operation_coordinator.get_boat_operation(wreck.boat_id)
        if wreck_operation is not None:
            school = simulation.get_school(wreck_operation.school_id)
            simulation.operation_coordinator.cancel_operation(
                wreck_operation.operation_id, simulation.boats, school,
                simulation.world_coordinator,
            )
        wreck.position = simulation.world_coordinator.bounds.clamp(contact_position, use_margin=True)
        if not wreck.transition_to(BoatState.BROKEN):
            return

        simulation.world_coordinator.release_exploration_target(wreck.boat_id)

        bounds = simulation.world_coordinator.bounds
        exits = (pygame.Vector2(bounds.min_x, wreck.position.y),
                 pygame.Vector2(bounds.max_x, wreck.position.y),
                 pygame.Vector2(wreck.position.x, bounds.min_y),
                 pygame.Vector2(wreck.position.x, bounds.max_y))
        destination = min(exits, key=lambda p: p.distance_to(wreck.position))
        self._incidents.append({
            "wreck": wreck,
            "colliders": colliders,
            "rescuers": [],
            "destination": destination,
            "phase": "waiting",
        })

    def _update_tows(self, simulation, delta_time):
        for incident in self._incidents[:]:
            wreck = incident["wreck"]
            destination = incident["destination"]
            if incident["phase"] == "waiting":
                active_states = (BoatState.EXPLORING, BoatState.RESERVED,
                                 BoatState.TRAVELING, BoatState.FISHING)
                rescuers = [boat for boat in simulation.boats
                            if boat.boat_type == BoatType.TOWING
                            and boat.boat_id not in incident["colliders"]
                            and boat.state in active_states]
                if len(rescuers) < 2:
                    continue
                rescuers.sort(key=lambda boat: boat.position.distance_to(wreck.position))
                rescuers = rescuers[:2]

                operations = {}
                for rescuer in rescuers:
                    operation = simulation.operation_coordinator.get_boat_operation(rescuer.boat_id)
                    if operation is not None:
                        operations[operation.operation_id] = operation
                for operation in operations.values():
                    school = simulation.get_school(operation.school_id)
                    simulation.operation_coordinator.cancel_operation(
                        operation.operation_id, simulation.boats, school,
                        simulation.world_coordinator,
                    )

                for rescuer in rescuers:
                    simulation.world_coordinator.release_exploration_target(rescuer.boat_id)
                incident["rescuers"] = rescuers
                for rescuer in rescuers:
                    if rescuer.transition_to(BoatState.MOVING_TO_TOW):
                        # Navigate to the wreck's coordinates through the same
                        # turn-limited waypoint steering used by normal travel.
                        rescuer.target_position = pygame.Vector2(wreck.position)
                incident["phase"] = "approach"

            if incident["phase"] == "approach":
                all_arrived = True
                for rescuer in incident["rescuers"]:
                    target = rescuer.target_position
                    if target is None or rescuer.position.distance_to(target) > WAYPOINT_REACH_RADIUS:
                        all_arrived = False
                    else:
                        rescuer.velocity = pygame.Vector2(0, 0)
                if all_arrived:
                    incident["phase"] = "tow"
                    for rescuer in incident["rescuers"]:
                        rescuer.target_position = None
                        rescuer.transition_to(BoatState.TOWING)
                continue

            offset = destination - wreck.position
            distance = offset.length()
            previous_wreck_position = wreck.position.copy()
            if distance > 0:
                movement = min(RESCUE_TOW_SPEED * delta_time, distance)
                wreck.position += offset.normalize() * movement

            # Keep the two tow partners alongside the wreck as it moves.
            movement = wreck.position - previous_wreck_position
            for rescuer in incident["rescuers"]:
                rescuer.position = simulation.world_coordinator.bounds.clamp(
                    rescuer.position + movement, use_margin=True
                )
                rescuer.velocity = pygame.Vector2(0, 0)

            if distance <= RESCUE_TOW_SPEED * delta_time or distance <= 1e-6:
                wreck.position = destination
                wreck.reset_to_exploring(simulation.world_coordinator)
                exits_top_or_bottom = (
                    abs(destination.y - simulation.world_coordinator.bounds.min_y) <= 1e-6
                    or abs(destination.y - simulation.world_coordinator.bounds.max_y) <= 1e-6
                )
                separation_axis = (pygame.Vector2(1, 0) if exits_top_or_bottom
                                   else pygame.Vector2(0, 1))
                for rescuer, side in zip(incident["rescuers"], (-1, 1)):
                    rescuer.reset_to_exploring(simulation.world_coordinator)
                    rescuer.position = simulation.world_coordinator.bounds.clamp(
                        destination + separation_axis * side * BOAT_COLLISION_DIST * 2,
                        use_margin=True,
                    )
                self._incidents.remove(incident)

    def draw(self, surface):
        """Render tow lines so rescue activity is visible in the simulation."""
        for incident in self._incidents:
            if incident["phase"] != "tow":
                continue
            wreck_position = incident["wreck"].position
            for rescuer in incident["rescuers"]:
                pygame.draw.line(
                    surface,
                    (225, 190, 130),
                    (round(rescuer.position.x), round(rescuer.position.y)),
                    (round(wreck_position.x), round(wreck_position.y)),
                    2,
                )
