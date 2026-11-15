"""Collision detection and towing recovery for the simulation kernel."""
import math
import random

import pygame

from src.config import (
    BOAT_BREAK_CHANCE, BOAT_COLLISION_DIST, BOAT_SEPARATION_GAP,
    PIER_COLLISION_SAFE_DISTANCE, RESCUE_TOW_SPEED, RESCUE_PICKUP_RADIUS,
    WAYPOINT_REACH_RADIUS,
)
from src.core.comms_hub import Message
from src.entities.boat_agent import BoatState, BoatType


class RescueManager:
    """Resolves boat contacts and coordinates towing boats recovering broken boats."""

    def __init__(self, rng=None, required_rescuers: int = 2):
        self.rng = rng or random
        self.required_rescuers = required_rescuers
        self._incidents = []

    def poll(self, simulation):
        """Claim idle towing boats and register any broken boats before the normal boat AI update runs."""
        registered_wreck_ids = {incident["wreck"].boat_id for incident in self._incidents}
        for boat in simulation.boats:
            if (boat.state == BoatState.BROKEN or getattr(boat, "needs_rescue", False)) and boat.boat_id not in registered_wreck_ids:
                self.register_broken_boat(simulation, boat)

        self._dispatch_waiting_calls(simulation)

    def register_broken_boat(self, simulation, boat, colliders=None, contact_position=None):
        """Registers a broken boat as needing rescue and prepares an incident."""
        for incident in self._incidents:
            if incident["wreck"].boat_id == boat.boat_id:
                return

        boat.needs_rescue = True
        boat.velocity.update(0, 0)
        boat.target_position = None
        if contact_position is not None:
            boat.position = simulation.world_coordinator.bounds.clamp(contact_position, use_margin=True)

        if boat.state != BoatState.BROKEN:
            boat.transition_to(BoatState.BROKEN)

        wreck_operation = simulation.operation_coordinator.get_boat_operation(boat.boat_id)
        if wreck_operation is not None:
            school = simulation.get_school(wreck_operation.school_id)
            simulation.operation_coordinator.cancel_operation(
                wreck_operation.operation_id, simulation.boats, school,
                simulation.world_coordinator,
            )

        simulation.world_coordinator.release_exploration_target(boat.boat_id)

        destination = simulation.pier_manager.repair_position()

        self._incidents.append({
            "wreck": boat,
            "colliders": set(colliders or [boat.boat_id]),
            "rescuers": [],
            "waiting_rescuer_ids": set(),
            "destination": destination,
            "phase": "waiting",
        })

        if simulation.comms_hub is not None:
            simulation.comms_hub.broadcast(Message(
                msg_type=Message.RESCUE_REQUEST,
                sender_id=boat.boat_id,
                target_id=None,
                payload={"wreck_id": boat.boat_id, "position": (boat.position.x, boat.position.y)},
            ))

        self._dispatch_waiting_calls(simulation)

    def update(self, simulation, delta_time, previous_positions=None):
        self.poll(simulation)
        self._update_tows(simulation, delta_time)
        previous_positions = previous_positions or {}
        self._resolve_collisions(simulation, previous_positions)
        self._break_moving_boats(simulation, previous_positions)

    def finish_movement_update(self, simulation, previous_positions):
        """Enforce hull clearance after any later movement systems have run."""
        previous_positions = previous_positions or {}
        self._resolve_collisions(simulation, previous_positions)

    def _resolve_collisions(self, simulation, previous_positions):
        boats = simulation.boats
        clearance = BOAT_COLLISION_DIST + BOAT_SEPARATION_GAP
        tow_groups = self._active_tow_groups()
        tow_group_by_id = {
            boat_id: group
            for group in tow_groups
            for boat_id in group
        }
        boats_by_id = {boat.boat_id: boat for boat in boats}
        waiting_tow_ids = set().union(*(
            incident.get("waiting_rescuer_ids", set())
            for incident in self._incidents
            if incident["phase"] == "approach"
        ))
        fixed_states = (BoatState.BROKEN, BoatState.RESERVED, BoatState.DUMPING,
                        BoatState.CLEANING, BoatState.TOWING)
        for separation_pass in range(3):
            for index, first in enumerate(boats):
                for second in boats[index + 1:]:
                    first_group = tow_group_by_id.get(first.boat_id)
                    second_group = tow_group_by_id.get(second.boat_id)
                    if first_group is not None and first_group is second_group:
                        continue
                    whirlpool_active = simulation.whirlpool_manager.is_active
                    if whirlpool_active and (
                        first.needs_rescue or first.state == BoatState.BROKEN
                        or second.needs_rescue or second.state == BoatState.BROKEN
                    ):
                        continue
                    if first_group is not None or second_group is not None:
                        continue
                    if first.state == BoatState.WHIRLPOOL or second.state == BoatState.WHIRLPOOL:
                        continue
                    if (first.state == BoatState.DUMPING
                            and second.state == BoatState.DUMPING
                            and first.boat_id in simulation.pier_manager.dock_slots
                            and second.boat_id in simulation.pier_manager.dock_slots):
                        continue
                    final_delta = second.position - first.position
                    final_distance = final_delta.length()
                    if final_distance >= clearance:
                        continue

                    direction = (final_delta.normalize() if final_distance > 1e-6
                                 else pygame.Vector2(1, 0))
                    midpoint = (first.position + second.position) / 2
                    first_fixed = (first.needs_rescue or first.state in fixed_states
                                   or first.boat_id in waiting_tow_ids)
                    second_fixed = (second.needs_rescue or second.state in fixed_states
                                    or second.boat_id in waiting_tow_ids)
                    if first_fixed and second_fixed:
                        continue
                    first_tow = getattr(first, "boat_type", None) == BoatType.TOWING
                    second_tow = getattr(second, "boat_type", None) == BoatType.TOWING

                    # Tow boat push priority: Tow boats have higher mass/priority and actively push smaller boats clear
                    if first_tow and not second_tow and not second_fixed:
                        direction = self._move_clear_of_anchor(
                            second, first.position, direction, clearance,
                            simulation.world_coordinator.bounds,
                        )
                    elif second_tow and not first_tow and not first_fixed:
                        direction = -self._move_clear_of_anchor(
                            first, second.position, -direction, clearance,
                            simulation.world_coordinator.bounds,
                        )
                    elif first_fixed:
                        direction = self._move_clear_of_anchor(
                            second, first.position, direction, clearance,
                            simulation.world_coordinator.bounds,
                        )

                    elif second_fixed:
                        direction = -self._move_clear_of_anchor(
                            first, second.position, -direction, clearance,
                            simulation.world_coordinator.bounds,
                        )
                    else:
                        direction = self._separate_pair(
                            first, second, midpoint, direction, clearance,
                            simulation.world_coordinator.bounds,
                        )
            self._resolve_tow_group_collisions(
                tow_groups, boats, boats_by_id, clearance,
                simulation.world_coordinator.bounds,
            )

    @staticmethod
    def _shift_tow_group(group, offset, bounds, boats_by_id):
        members = [boats_by_id[boat_id] for boat_id in group if boat_id in boats_by_id]
        if not members:
            return
        center = sum((boat.position for boat in members), pygame.Vector2()) / len(members)
        shift = bounds.clamp(center + offset, use_margin=True) - center
        for boat in members:
            boat.position += shift

    def _resolve_tow_group_collisions(self, groups, boats, boats_by_id, clearance, bounds):
        for group in groups:
            members = [boats_by_id[boat_id] for boat_id in group if boat_id in boats_by_id]
            if not members:
                continue
            for boat in boats:
                if boat.boat_id in group or boat.needs_rescue or boat.state == BoatState.BROKEN:
                    continue
                center = sum((member.position for member in members), pygame.Vector2()) / len(members)
                radius = max(center.distance_to(member.position) for member in members)
                offset = boat.position - center
                distance = offset.length()
                minimum_distance = radius + clearance
                if distance >= minimum_distance:
                    continue
                direction = offset.normalize() if distance > 1e-6 else pygame.Vector2(1, 0)
                self._shift_tow_group(
                    group, -direction * (minimum_distance - distance), bounds, boats_by_id
                )

        for first_index, first_group in enumerate(groups):
            first_members = [boats_by_id[boat_id] for boat_id in first_group
                             if boat_id in boats_by_id]
            if not first_members:
                continue
            first_center = sum((boat.position for boat in first_members), pygame.Vector2()) / len(first_members)
            first_radius = max(first_center.distance_to(boat.position) for boat in first_members)
            for second_group in groups[first_index + 1:]:
                second_members = [boats_by_id[boat_id] for boat_id in second_group
                                  if boat_id in boats_by_id]
                if not second_members:
                    continue
                second_center = sum((boat.position for boat in second_members), pygame.Vector2()) / len(second_members)
                second_radius = max(second_center.distance_to(boat.position) for boat in second_members)
                offset = second_center - first_center
                distance = offset.length()
                minimum_distance = first_radius + second_radius + clearance
                if distance >= minimum_distance:
                    continue
                direction = offset.normalize() if distance > 1e-6 else pygame.Vector2(1, 0)
                overlap = minimum_distance - distance
                self._shift_tow_group(first_group, -direction * (overlap / 2), bounds, boats_by_id)
                self._shift_tow_group(second_group, direction * (overlap / 2), bounds, boats_by_id)

    @staticmethod
    def _candidate_directions(direction):
        if direction.length_squared() <= 1e-6:
            direction = pygame.Vector2(1, 0)
        else:
            direction = direction.normalize()
        return (direction, direction.rotate(90), direction.rotate(-90), -direction,
                pygame.Vector2(1, 0), pygame.Vector2(-1, 0),
                pygame.Vector2(0, 1), pygame.Vector2(0, -1))

    @classmethod
    def _move_clear_of_anchor(cls, moving_boat, anchor, direction, clearance, bounds):
        candidates = []
        for candidate_direction in cls._candidate_directions(direction):
            position = bounds.clamp(
                anchor + candidate_direction * clearance, use_margin=True
            )
            distance = position.distance_to(anchor)
            if distance >= clearance - 1e-4:
                candidates.append((position.distance_squared_to(moving_boat.position),
                                   position, candidate_direction))
        if candidates:
            _, moving_boat.position, chosen_direction = min(candidates, key=lambda item: item[0])
            return chosen_direction
        moving_boat.position = bounds.clamp(
            anchor + cls._candidate_directions(direction)[0] * clearance,
            use_margin=True,
        )
        return cls._candidate_directions(direction)[0]

    @classmethod
    def _separate_pair(cls, first, second, midpoint, direction, clearance, bounds):
        candidates = []
        for candidate_direction in cls._candidate_directions(direction):
            first_position = bounds.clamp(
                midpoint - candidate_direction * (clearance / 2), use_margin=True
            )
            second_position = bounds.clamp(
                midpoint + candidate_direction * (clearance / 2), use_margin=True
            )
            if first_position.distance_to(second_position) >= clearance - 1e-4:
                move_cost = (first_position.distance_squared_to(first.position)
                             + second_position.distance_squared_to(second.position))
                candidates.append((move_cost, first_position, second_position,
                                   candidate_direction))

        if not candidates:
            for candidate_direction in cls._candidate_directions(direction):
                second_position = bounds.clamp(
                    first.position + candidate_direction * clearance, use_margin=True
                )
                if second_position.distance_to(first.position) >= clearance - 1e-4:
                    candidates.append((second_position.distance_squared_to(second.position),
                                       first.position.copy(), second_position,
                                       candidate_direction))
                first_position = bounds.clamp(
                    second.position - candidate_direction * clearance, use_margin=True
                )
                if first_position.distance_to(second.position) >= clearance - 1e-4:
                    candidates.append((first_position.distance_squared_to(first.position),
                                       first_position, second.position.copy(),
                                       candidate_direction))

        if candidates:
            _, first.position, second.position, chosen_direction = min(
                candidates, key=lambda item: item[0]
            )
            return (second.position - first.position).normalize()

        first.position = bounds.clamp(first.position, use_margin=True)
        second.position = bounds.clamp(second.position, use_margin=True)
        return direction

    def _break_moving_boats(self, simulation, previous_positions):
        """Apply the break roll once to each eligible boat that moved this update."""
        eligible_states = (BoatState.EXPLORING, BoatState.TRAVELING, BoatState.FISHING)
        towing_ids = set().union(*self._active_tow_groups())
        for boat in simulation.boats:
            if (boat.state not in eligible_states or boat.needs_rescue
                    or boat.boat_id in towing_ids):
                continue
            previous = previous_positions.get(boat.boat_id, boat.position)
            if boat.position.distance_squared_to(previous) <= 1e-6:
                continue
            if self._near_a_pier(simulation, boat.position):
                continue
            if self.rng.random() < BOAT_BREAK_CHANCE:
                self._start_tow(simulation, boat, boat.position)

    def _active_tow_groups(self):
        """Return the wreck and assigned rescuers in each active tow convoy."""
        groups = []
        for incident in self._incidents:
            if incident["phase"] != "tow":
                continue
            group = {incident["wreck"].boat_id}
            group.update(rescuer.boat_id for rescuer in incident["rescuers"])
            groups.append(group)
        return groups

    @staticmethod
    def _near_a_pier(simulation, position):
        """Keep random break events disabled around the mission and repair docks."""
        for dock in (simulation.pier_manager.dock_rect(),
                     simulation.pier_manager.repair_dock_rect()):
            protected_area = dock.inflate(
                round(PIER_COLLISION_SAFE_DISTANCE * 2),
                round(PIER_COLLISION_SAFE_DISTANCE * 2),
            )
            if protected_area.collidepoint(round(position.x), round(position.y)):
                return True
        return False

    def _start_tow(self, simulation, boat, contact_position):
        active_towing_boats = sum(
            candidate.boat_type == BoatType.TOWING
            and candidate.state != BoatState.BROKEN
            and not getattr(candidate, "needs_rescue", False)
            for candidate in simulation.boats
        )
        if active_towing_boats < 3 and boat.boat_type == BoatType.TOWING:
            return
        self.register_broken_boat(simulation, boat, contact_position=contact_position)

    def _dispatch_waiting_calls(self, simulation):
        """Pair waiting rescue incidents with available towing boats."""
        for incident in self._incidents:
            if (incident["phase"] not in ("waiting", "approach")
                    or len(incident["rescuers"]) >= self.required_rescuers):
                continue
            wreck = incident["wreck"]
            needed = self.required_rescuers - len(incident["rescuers"])
            active_states = (BoatState.EXPLORING, BoatState.RESERVED,
                             BoatState.TRAVELING, BoatState.FISHING, BoatState.DUMPING)
            rescuers = [boat for boat in simulation.boats
                        if boat.boat_type == BoatType.TOWING
                        and boat.boat_id != wreck.boat_id
                        and not getattr(boat, "needs_rescue", False)
                        and boat.state in active_states
                        and getattr(boat, "claimed_rescue", None) is None]
            if not rescuers:
                continue

            rescuers.sort(key=lambda b: b.position.distance_to(wreck.position))
            chosen_rescuers = rescuers[:needed]

            # Cancel any fishing operations the chosen rescuers were participating in
            operations = {}
            for rescuer in chosen_rescuers:
                operation = simulation.operation_coordinator.get_boat_operation(rescuer.boat_id)
                if operation is not None:
                    operations[operation.operation_id] = operation
            for operation in operations.values():
                school = simulation.get_school(operation.school_id)
                simulation.operation_coordinator.cancel_operation(
                    operation.operation_id, simulation.boats, school,
                    simulation.world_coordinator,
                )

            # Assign and route rescuers to the wreck's coordinates
            for rescuer in chosen_rescuers:
                simulation.world_coordinator.release_exploration_target(rescuer.boat_id)
                rescuer.current_grid = None
                rescuer.current_cell_index = None
                rescuer.claimed_rescue = wreck
                if rescuer.transition_to(BoatState.MOVING_TO_TOW):
                    rescuer.target_position = pygame.Vector2(wreck.position)

            incident["rescuers"].extend(chosen_rescuers)
            incident["phase"] = "approach"

            if simulation.comms_hub is not None:
                for rescuer in chosen_rescuers:
                    simulation.comms_hub.broadcast(Message(
                        msg_type=Message.RESCUE_DISPATCH,
                        sender_id=rescuer.boat_id,
                        target_id=wreck.boat_id,
                        payload={"rescuer_id": rescuer.boat_id, "wreck_id": wreck.boat_id},
                    ))

    def _update_tows(self, simulation, delta_time):
        self._dispatch_waiting_calls(simulation)

        for incident in self._incidents[:]:
            wreck = incident["wreck"]
            destination = incident["destination"]
            if simulation.whirlpool_manager.is_active and (
                wreck.state == BoatState.BROKEN
                or any(rescuer.state == BoatState.WHIRLPOOL
                       for rescuer in incident["rescuers"])
            ):
                continue

            if incident["phase"] == "approach":
                wreck.velocity.update(0, 0)
                all_arrived = True
                waiting_rescuer_ids = incident.setdefault("waiting_rescuer_ids", set())
                for rescuer in incident["rescuers"]:
                    dist = rescuer.position.distance_to(wreck.position)
                    if rescuer.target_position is not None:
                        dist = min(dist, rescuer.position.distance_to(rescuer.target_position))
                    if dist > RESCUE_PICKUP_RADIUS:
                        waiting_rescuer_ids.discard(rescuer.boat_id)
                        all_arrived = False
                    else:
                        waiting_rescuer_ids.add(rescuer.boat_id)
                        rescuer.velocity = pygame.Vector2(0, 0)
                        rescuer.target_position = rescuer.position.copy()

                if (all_arrived
                        and len(incident["rescuers"]) >= self.required_rescuers):
                    incident["phase"] = "tow"
                    for rescuer in incident["rescuers"]:
                        rescuer.target_position = pygame.Vector2(destination)
                        rescuer.transition_to(BoatState.TOWING)
                    if simulation.comms_hub is not None and incident["rescuers"]:
                        simulation.comms_hub.broadcast(Message(
                            msg_type=Message.RESCUE_ATTACHED,
                            sender_id=incident["rescuers"][0].boat_id,
                            target_id=wreck.boat_id,
                            payload={"wreck_id": wreck.boat_id},
                        ))
                continue

            if incident["phase"] == "tow":
                offset = destination - wreck.position
                distance = offset.length()

                if distance <= RESCUE_TOW_SPEED * delta_time or distance <= 1e-6:
                    # Drop-off destination reached: repair wreck and restore operational status
                    wreck.position = simulation.world_coordinator.bounds.clamp(destination, use_margin=True)
                    wreck.velocity.update(0, 0)
                    wreck.needs_rescue = False
                    has_usable_mission = (
                        wreck.mission is not None
                        and wreck.fish_catch < wreck.mission.amount
                    )
                    wreck.reset_to_exploring(simulation.world_coordinator)
                    if not has_usable_mission:
                        simulation.pier_manager.request_support_return(wreck, simulation)

                    exits_top_or_bottom = (
                        abs(destination.y - simulation.world_coordinator.bounds.min_y) <= 1e-6
                        or abs(destination.y - simulation.world_coordinator.bounds.max_y) <= 1e-6
                    )
                    separation_axis = (pygame.Vector2(1, 0) if exits_top_or_bottom
                                       else pygame.Vector2(0, 1))
                    for rescuer, side in zip(incident["rescuers"], (-1, 1)):
                        rescuer.claimed_rescue = None
                        rescuer.target_position = None
                        rescuer.reset_to_exploring(simulation.world_coordinator)
                        rescuer.position = simulation.world_coordinator.bounds.clamp(
                            destination + separation_axis * side * BOAT_COLLISION_DIST * 2,
                            use_margin=True,
                        )
                        simulation.pier_manager.request_support_return(rescuer, simulation)
                    self._incidents.remove(incident)
                    if simulation.comms_hub is not None and incident["rescuers"]:
                        simulation.comms_hub.broadcast(Message(
                            msg_type=Message.RESCUE_COMPLETED,
                            sender_id=incident["rescuers"][0].boat_id,
                            target_id=wreck.boat_id,
                            payload={"wreck_id": wreck.boat_id},
                        ))
                    continue

                tow_dir = offset.normalize() if distance > 1e-6 else pygame.Vector2(1, 0)
                movement = min(RESCUE_TOW_SPEED * delta_time, distance)
                tow_heading = math.atan2(tow_dir.y, tow_dir.x)

                wreck.position += tow_dir * movement
                wreck.heading = tow_heading
                wreck.velocity = tow_dir * RESCUE_TOW_SPEED

                if len(incident["rescuers"]) == 1:
                    rescuer = incident["rescuers"][0]
                    rescuer.position = simulation.world_coordinator.bounds.clamp(
                        wreck.position + tow_dir * 28.0, use_margin=True
                    )
                    rescuer.heading = tow_heading
                    rescuer.velocity = tow_dir * RESCUE_TOW_SPEED
                else:
                    lateral = pygame.Vector2(-tow_dir.y, tow_dir.x)
                    for rescuer, side in zip(incident["rescuers"], (-1, 1)):
                        rescuer.position = simulation.world_coordinator.bounds.clamp(
                            wreck.position + lateral * (side * 24.0), use_margin=True
                        )
                        rescuer.heading = tow_heading
                        rescuer.velocity = tow_dir * RESCUE_TOW_SPEED

    def draw(self, surface, font=None, minimal=False):
        """Render active tow lines and rescue status clearly."""
        if not self._incidents:
            return

        if font is None and pygame.font.get_init():
            font = pygame.font.SysFont("Arial", 13, bold=True)

        for incident in self._incidents:
            wreck = incident["wreck"]
            wreck_pos = (round(wreck.position.x), round(wreck.position.y))
            phase = incident.get("phase", "waiting")

            if phase == "waiting":
                # Draw SOS pulse beacon indicator around broken boat
                pygame.draw.circle(surface, (255, 60, 60), wreck_pos, 22, 2)
                pygame.draw.circle(surface, (255, 120, 120), wreck_pos, 14, 1)
                if font is not None and not minimal:
                    badge = font.render("SOS: AWAITING RESCUE", True, (255, 90, 90))
                    badge_rect = badge.get_rect(center=(wreck_pos[0], wreck_pos[1] - 28))
                    bg_rect = badge_rect.inflate(6, 4)
                    pygame.draw.rect(surface, (30, 20, 25), bg_rect)
                    pygame.draw.rect(surface, (255, 60, 60), bg_rect, 1)
                    surface.blit(badge, badge_rect)

            elif phase == "approach":
                # Rescuers en route: draw approach tracking lines to wreck
                if not minimal:
                    for rescuer in incident["rescuers"]:
                        resc_pos = (round(rescuer.position.x), round(rescuer.position.y))
                        pygame.draw.line(surface, (95, 165, 235), resc_pos, wreck_pos, 1)
                        pygame.draw.circle(surface, (95, 165, 235), resc_pos, 4, 1)

                waiting_ids = incident.get("waiting_rescuer_ids", set())
                for rescuer in incident["rescuers"]:
                    if rescuer.boat_id in waiting_ids:
                        self._draw_waiting_cogwheel(
                            surface, rescuer.position, minimal=minimal
                        )

                if font is not None and not minimal:
                    badge = font.render("RESCUE INCOMING", True, (95, 195, 255))
                    badge_rect = badge.get_rect(center=(wreck_pos[0], wreck_pos[1] - 28))
                    bg_rect = badge_rect.inflate(6, 4)
                    pygame.draw.rect(surface, (20, 30, 45), bg_rect)
                    pygame.draw.rect(surface, (95, 195, 255), bg_rect, 1)
                    surface.blit(badge, badge_rect)

            elif phase == "tow":
                # Active tow lines
                for rescuer in incident["rescuers"]:
                    resc_pos = (round(rescuer.position.x), round(rescuer.position.y))
                    # Sturdy tow cable
                    pygame.draw.line(surface, (245, 180, 80), resc_pos, wreck_pos, 3)
                    pygame.draw.line(surface, (255, 230, 160), resc_pos, wreck_pos, 1)
                    # Cable hitches
                    pygame.draw.circle(surface, (255, 210, 100), resc_pos, 4)
                    pygame.draw.circle(surface, (255, 210, 100), wreck_pos, 4)

                if font is not None:
                    badge = font.render("TOWING TO REPAIR", True, (255, 200, 60))
                    badge_rect = badge.get_rect(center=(wreck_pos[0], wreck_pos[1] - 28))
                    bg_rect = badge_rect.inflate(6, 4)
                    pygame.draw.rect(surface, (40, 30, 15), bg_rect)
                    pygame.draw.rect(surface, (245, 180, 80), bg_rect, 1)
                    surface.blit(badge, badge_rect)

    @staticmethod
    def _draw_waiting_cogwheel(surface, position, minimal=False):
        center_x = round(position.x) + 22
        center_y = round(position.y) - 8
        yellow = (255, 235, 35)
        points = []
        teeth = 8
        for tooth in range(teeth):
            base_angle = tooth * math.tau / teeth - math.pi / 2
            tooth_profile = ((-math.pi / 8, 5.8),
                             (-math.pi / 14, 5.8),
                             (-math.pi / 14, 8.0),
                             (math.pi / 14, 8.0),
                             (math.pi / 14, 5.8),
                             (math.pi / 8, 5.8))
            for angle_offset, radius in tooth_profile:
                angle = base_angle + angle_offset
                points.append((round(center_x + math.cos(angle) * radius),
                               round(center_y + math.sin(angle) * radius)))
        pygame.draw.polygon(surface, yellow, points)
        pygame.draw.circle(surface, (18, 29, 38), (center_x, center_y), 3)
