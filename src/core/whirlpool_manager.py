"""
WhirlpoolManager for FishSwarm.
Coordinates periodic whirlpool lifecycle, two-phase activation (Approach Phase -> Countering Phase),
inner-first dual-ring distribution, active boat task suspension, smooth travel entry,
counter-orbit kinematics, seamless task resumption, enhanced visual whirlpool rendering,
and world-space floating UI status display.
"""
import math
import random
from typing import Optional
import pygame

from src.config import (
    WHIRLPOOL_DURATION,
    WHIRLPOOL_MIN_COOLDOWN,
    WHIRLPOOL_RANDOM_DELAY_MIN,
    WHIRLPOOL_RANDOM_DELAY_MAX,
    WHIRLPOOL_INNER_RADIUS,
    WHIRLPOOL_OUTER_RADIUS,
    WHIRLPOOL_ORBIT_SPEED,
    COLOR_WHIRLPOOL_CYAN,
    COLOR_WHIRLPOOL_DEEP,
    COLOR_TEXT,
)
from src.entities.boat_agent import BoatAgent, BoatState


class WhirlpoolManager:
    """
    Manages the periodic Whirlpool event:
    - One event at a randomized time after each strict 120s cooldown.
    - Two-Phase Whirlpool Activation:
        1. Approach Phase: Boats cruise and steer smoothly towards their assigned ring slots.
           Timer, progress bar fill, and counter-orbit rotation do NOT start yet.
        2. Countering Phase: Once every non-broken boat arrives at its target position,
           the 15-second "Counteracting Whirlpool"
           timer, progress bar fill, and active counter-orbit begin.
    - Inner-First Dual-Ring Distribution:
        Divide active boats 50/50, filling the inner ring first up to half the count,
        then the outer ring with the remainder, uniformly spaced along the circumference (2*pi / count).
    - Captures active boats (strictly excluding broken boats).
    - Seamlessly restores suspended tasks upon despawn.
    - Renders sleek world-space progress bar floating directly above the whirlpool with
      label "Counteracting Whirlpool".
    """

    RAMP_DURATION = 2.0         # Seconds to spin up on spawn and dissipate on despawn
    ARRIVAL_THRESHOLD = 16.0     # Pixels distance considered arrived at assigned slot

    def __init__(
        self,
        duration: float = WHIRLPOOL_DURATION,
        min_cooldown: float = WHIRLPOOL_MIN_COOLDOWN,
        random_delay_range: tuple[float, float] = (
            WHIRLPOOL_RANDOM_DELAY_MIN,
            WHIRLPOOL_RANDOM_DELAY_MAX,
        ),
        inner_radius: float = WHIRLPOOL_INNER_RADIUS,
        outer_radius: float = WHIRLPOOL_OUTER_RADIUS,
        orbit_speed: float = WHIRLPOOL_ORBIT_SPEED,
        rng=None,
    ):
        self.duration = float(duration)
        self.min_cooldown = float(min_cooldown)
        self.random_delay_range = random_delay_range
        self.inner_radius = float(inner_radius)
        self.outer_radius = float(outer_radius)
        self.orbit_speed = float(orbit_speed)
        self.rng = rng or random

        # State flags, phases, and timers
        self.is_active: bool = False
        self.phase: str = "idle"  # "approach", "countering", or "idle"
        self.approach_time_elapsed: float = 0.0
        self.active_time_elapsed: float = 0.0
        self.active_time_remaining: float = 0.0

        # The first event is randomized within the opening 120-second window.
        # Later events use the full cooldown plus a fresh random delay.
        self.cooldown_remaining: float = 0.0
        self.random_delay_remaining: float = self.rng.uniform(
            self.random_delay_range[0], self.random_delay_range[1]
        )

        # Whirlpool spatial properties
        self.center: pygame.Vector2 = pygame.Vector2(600, 400)
        # Spin direction: +1 = clockwise, -1 = anticlockwise
        self.spin_direction: int = 1
        # Counter-orbit direction: strictly opposite to spin direction
        self.orbit_direction: int = -1
        self.current_orbit_angle: float = 0.0

        # Ring distributions
        self.affected_boats: list[BoatAgent] = []
        self.inner_ring_boats: list[BoatAgent] = []
        self.outer_ring_boats: list[BoatAgent] = []
        # Mapping: boat_id -> {"radius": float, "base_offset": float, "ring": str}
        self.boat_orbital_slots: dict[int, dict] = {}

    @property
    def progress(self) -> float:
        """Normalized completion progress of the active whirlpool event (0.0 to 1.0)."""
        if not self.is_active or self.phase != "countering" or self.duration <= 0.0:
            return 0.0
        return min(1.0, max(0.0, self.active_time_elapsed / self.duration))

    @property
    def time_remaining(self) -> float:
        """Seconds remaining in the active countering phase."""
        if self.phase == "approach":
            return self.duration
        return max(0.0, self.active_time_remaining)

    def get_ramp_factor(self) -> float:
        """
        Computes dynamic rotation speed ramping and visual intensity factor (0.0 to 1.0):
        Spins up smoothly on spawn and dissipates smoothly on despawn.
        """
        if not self.is_active or self.duration <= 0.0:
            return 0.0
        total_time = self.approach_time_elapsed + self.active_time_elapsed
        ramp_in = min(1.0, total_time / self.RAMP_DURATION)
        ramp_out = min(1.0, self.active_time_remaining / self.RAMP_DURATION)
        factor = min(ramp_in, ramp_out)
        return math.sin(factor * (math.pi / 2.0))

    def trigger_spawn(
        self,
        simulation,
        center: Optional[tuple[float, float] | pygame.Vector2] = None,
        spin_direction: Optional[int] = None,
    ) -> bool:
        """
        Manually triggers a whirlpool spawn event entering the Approach Phase.
        """
        if self.is_active:
            return False

        self.is_active = True
        self.phase = "approach"
        self.approach_time_elapsed = 0.0
        self.active_time_elapsed = 0.0
        self.active_time_remaining = self.duration
        self.current_orbit_angle = 0.0

        # Spin direction: randomly clockwise (+1) or anticlockwise (-1)
        if spin_direction is not None:
            self.spin_direction = 1 if spin_direction > 0 else -1
        else:
            self.spin_direction = self.rng.choice([1, -1])

        # Counter-orbit direction: strictly opposite to whirlpool spin
        self.orbit_direction = -self.spin_direction

        # Whirlpool center location
        if center is not None:
            self.center = pygame.Vector2(center[0], center[1])
        else:
            self.center = self._find_spawn_position(simulation)

        # Capture active boats, distribute inner-first, and suspend tasks
        simulation.rescue_manager.cancel_tows_for_whirlpool(simulation)
        self._capture_active_boats(simulation)

        self.phase = "approach"
        if self._all_participants_arrived():
            self._begin_countering()

        return True

    def despawn(self, simulation):
        """
        Concludes the whirlpool event:
        Releases all orbiting boats, seamlessly restores their suspended tasks,
        and starts the strict 120s cooldown timer + randomised delay.
        """
        if not self.is_active:
            return

        self.is_active = False
        self.phase = "idle"
        self.approach_time_elapsed = 0.0
        self.active_time_elapsed = 0.0
        self.active_time_remaining = 0.0

        # Restore suspended tasks for all captured boats
        for boat in self.affected_boats:
            if boat.state == BoatState.WHIRLPOOL and not boat.needs_rescue:
                boat.resume_task()

        self.affected_boats.clear()
        self.inner_ring_boats.clear()
        self.outer_ring_boats.clear()
        self.boat_orbital_slots.clear()

        # Strict 120s cooldown must elapse before randomised delay begins
        self.cooldown_remaining = self.min_cooldown
        self.random_delay_remaining = self.rng.uniform(
            self.random_delay_range[0], self.random_delay_range[1]
        )

    def update(self, delta_time: float, simulation):
        """
        Advances the two-phase whirlpool lifecycle:
        - When idle: decrements cooldown (120s minimum), then random delay, then spawns.
        - Approach Phase: Boats travel towards ring positions. Countering begins only
          after every remaining non-broken boat arrives.
        - Countering Phase: 15-second countdown timer runs, counter-orbit advances, progress bar fills.
        - Concludes and releases boats when 15 seconds expire.
        """
        if delta_time <= 0.0:
            return

        if not self.is_active:
            # Enforce strict 120s minimum cooldown first
            if self.cooldown_remaining > 0.0:
                overflow = delta_time - self.cooldown_remaining
                self.cooldown_remaining = max(0.0, self.cooldown_remaining - delta_time)
                if overflow > 0.0:
                    delta_time = overflow
                else:
                    return

            # Cooldown complete, select a random trigger time within the next 2 minutes.
            if self.random_delay_remaining > 0.0:
                self.random_delay_remaining = max(0.0, self.random_delay_remaining - delta_time)

            if self.random_delay_remaining <= 0.0:
                # Spawn next whirlpool
                self.trigger_spawn(simulation)
            return

        # ---------------- Phase 1: Approach Phase ----------------
        if self.phase == "approach":
            self._remove_broken_participants()
            time_in_approach = delta_time
            self.approach_time_elapsed += delta_time
            self.current_orbit_angle = 0.0
            all_arrived = self._update_approach_movement(time_in_approach)

            if not all_arrived:
                return
            self._begin_countering()
            return

        # ---------------- Phase 2: Countering Phase ----------------
        self._remove_broken_participants()
        self.active_time_elapsed += delta_time
        self.active_time_remaining = max(0.0, self.duration - self.active_time_elapsed)

        # Dynamic rotation speed ramping (spinning up on spawn and dissipating on despawn)
        ramp = self.get_ramp_factor()
        effective_orbit_speed = self.orbit_speed * max(0.20, ramp)

        # Advance orbital angle frame-rate independently
        self.current_orbit_angle += self.orbit_direction * effective_orbit_speed * delta_time
        self.current_orbit_angle = (self.current_orbit_angle + math.pi) % (2.0 * math.pi) - math.pi

        # Move affected boats in active counter-orbit
        self._update_countering_orbit(delta_time, effective_orbit_speed)

        # Conclude event when 15.0 seconds have elapsed (using epsilon for float precision)
        if self.active_time_remaining <= 1e-6:
            self.despawn(simulation)

    def _begin_countering(self):
        self.phase = "countering"
        self.active_time_elapsed = 0.0
        self.active_time_remaining = self.duration

    def _remove_broken_participants(self):
        """Remove participants that broke mid-event from slots and readiness."""
        broken_ids = {boat.boat_id for boat in self.affected_boats
                      if boat.state == BoatState.BROKEN or getattr(boat, "needs_rescue", False)}
        if not broken_ids:
            return
        self.affected_boats = [boat for boat in self.affected_boats if boat.boat_id not in broken_ids]
        self.inner_ring_boats = [boat for boat in self.inner_ring_boats if boat.boat_id not in broken_ids]
        self.outer_ring_boats = [boat for boat in self.outer_ring_boats if boat.boat_id not in broken_ids]
        for boat_id in broken_ids:
            self.boat_orbital_slots.pop(boat_id, None)

    def _all_participants_arrived(self):
        self._remove_broken_participants()
        for boat in self.affected_boats:
            slot_info = self._get_slot_target_pos(boat.boat_id, 0.0)
            if slot_info is None or (slot_info[0] - boat.position).length() > self.ARRIVAL_THRESHOLD:
                return False
        return True

    def _capture_active_boats(self, simulation):
        """
        Filters active boats, explicitly excluding broken boats.
        Applies Inner-First Dual-Ring Distribution:
        - Divides active boats evenly: 50% inner radius, 50% outer radius.
        - Fill order: Assigns slots to inner radius first up to half count, then remainder to outer.
        - Spaces boats uniformly along the circumference (2*pi / ringCount).
        """
        self.affected_boats.clear()
        self.inner_ring_boats.clear()
        self.outer_ring_boats.clear()
        self.boat_orbital_slots.clear()

        # Filter: active boats only, explicitly excluding broken boats
        eligible_boats = [
            boat for boat in simulation.boats
            if boat.state != BoatState.BROKEN and not getattr(boat, "needs_rescue", False)
        ]

        if not eligible_boats:
            return

        # Suspend tasks for all eligible boats
        for boat in eligible_boats:
            boat.suspend_task()
            self.affected_boats.append(boat)

        n_total = len(eligible_boats)
        # 50% inner radius, 50% outer radius (handling odd counts safely)
        n_inner = (n_total + 1) // 2
        n_outer = n_total // 2

        # Sort eligible boats by proximity to center so nearest boats fill inner ring first
        eligible_boats.sort(key=lambda b: b.position.distance_to(self.center))

        # Fill order: inner ring first up to half active boat count, then remainder to outer ring
        self.inner_ring_boats = eligible_boats[:n_inner]
        self.outer_ring_boats = eligible_boats[n_inner:]

        # Sort each ring by polar angle to assign clean sequential angular slots without crossing
        self.inner_ring_boats.sort(
            key=lambda b: math.atan2(b.position.y - self.center.y, b.position.x - self.center.x)
        )
        self.outer_ring_boats.sort(
            key=lambda b: math.atan2(b.position.y - self.center.y, b.position.x - self.center.x)
        )

        # Uniform angular distribution on inner ring: 2*pi / M
        m_inner = len(self.inner_ring_boats)
        for i, boat in enumerate(self.inner_ring_boats):
            base_offset = (2.0 * math.pi / m_inner) * i if m_inner > 0 else 0.0
            self.boat_orbital_slots[boat.boat_id] = {
                "radius": self.inner_radius,
                "base_offset": base_offset,
                "ring": "inner",
            }

        # Uniform angular distribution on outer ring: 2*pi / M with phase shift
        m_outer = len(self.outer_ring_boats)
        phase_shift = (math.pi / m_outer) if m_outer > 0 else 0.0
        for j, boat in enumerate(self.outer_ring_boats):
            base_offset = (2.0 * math.pi / m_outer) * j + phase_shift if m_outer > 0 else 0.0
            self.boat_orbital_slots[boat.boat_id] = {
                "radius": self.outer_radius,
                "base_offset": base_offset,
                "ring": "outer",
            }

    def _get_slot_target_pos(self, boat_id: int, current_angle: float) -> Optional[tuple[pygame.Vector2, float]]:
        """Computes target position and tangent heading for a given boat slot."""
        slot = self.boat_orbital_slots.get(boat_id)
        if not slot:
            return None
        radius = slot["radius"]
        base_offset = slot["base_offset"]
        slot_angle = current_angle + base_offset
        target_pos = self.center + pygame.Vector2(
            math.cos(slot_angle), math.sin(slot_angle)
        ) * radius
        if self.orbit_direction == 1:
            tangent_heading = slot_angle + math.pi / 2.0
        else:
            tangent_heading = slot_angle - math.pi / 2.0
        tangent_heading = (tangent_heading + math.pi) % (2.0 * math.pi) - math.pi
        return target_pos, tangent_heading

    def _update_approach_movement(self, delta_time: float) -> bool:
        """
        Moves boats smoothly towards their stationary assigned slots during the Approach Phase.
        Returns True if all participating boats are within ARRIVAL_THRESHOLD.
        """
        all_arrived = True
        for boat in self.affected_boats:
            slot_info = self._get_slot_target_pos(boat.boat_id, 0.0)
            if not slot_info:
                continue
            target_pos, tangent_heading = slot_info
            delta_vec = target_pos - boat.position
            dist = delta_vec.length()

            if dist <= self.ARRIVAL_THRESHOLD:
                boat.position = target_pos.copy()
                boat.heading = tangent_heading
                boat.velocity = pygame.Vector2(0, 0)
            else:
                desired_angle = math.atan2(delta_vec.y, delta_vec.x)
                angle_diff = (desired_angle - boat.heading + math.pi) % (2.0 * math.pi) - math.pi
                turn_rate = boat.turn_speed * 2.0 * delta_time
                if abs(angle_diff) <= turn_rate:
                    boat.heading = desired_angle
                else:
                    boat.heading += math.copysign(turn_rate, angle_diff)
                boat.heading = (boat.heading + math.pi) % (2.0 * math.pi) - math.pi

                if dist < 25.0:
                    blend = (25.0 - dist) / 25.0
                    tangent_diff = (tangent_heading - boat.heading + math.pi) % (2.0 * math.pi) - math.pi
                    boat.heading += tangent_diff * blend * min(1.0, delta_time * 6.0)
                    boat.heading = (boat.heading + math.pi) % (2.0 * math.pi) - math.pi

                travel_speed = min(boat.speed * 1.35, max(boat.speed * 0.25, dist * 1.5))
                step = min(dist, travel_speed * delta_time)
                forward = pygame.Vector2(math.cos(boat.heading), math.sin(boat.heading))
                boat.position += forward * step
                boat.velocity = forward * (step / delta_time)

            final_dist = (target_pos - boat.position).length()
            if final_dist > self.ARRIVAL_THRESHOLD:
                all_arrived = False

        return all_arrived


    def _update_countering_orbit(self, delta_time: float, effective_orbit_speed: float):
        """
        Moves boats in active counter-orbit around the whirlpool during the Countering Phase.
        """
        self._remove_broken_participants()
        for boat in self.affected_boats:
            slot_info = self._get_slot_target_pos(boat.boat_id, self.current_orbit_angle)
            if not slot_info:
                continue
            target_pos, tangent_heading = slot_info
            radius = self.boat_orbital_slots[boat.boat_id]["radius"]

            delta_vec = target_pos - boat.position
            dist = delta_vec.length()

            if dist <= 3.0:
                boat.position = target_pos.copy()
                boat.heading = tangent_heading
                tangent_vec = pygame.Vector2(math.cos(tangent_heading), math.sin(tangent_heading))
                boat.velocity = tangent_vec * (effective_orbit_speed * radius)
            else:
                desired_angle = math.atan2(delta_vec.y, delta_vec.x)
                angle_diff = (desired_angle - boat.heading + math.pi) % (2.0 * math.pi) - math.pi
                turn_rate = boat.turn_speed * 2.2 * delta_time
                if abs(angle_diff) <= turn_rate:
                    boat.heading = desired_angle
                else:
                    boat.heading += math.copysign(turn_rate, angle_diff)
                boat.heading = (boat.heading + math.pi) % (2.0 * math.pi) - math.pi

                travel_speed = max(boat.speed * 1.3, min(boat.speed * 2.5, dist * 3.5))
                step = min(dist, travel_speed * delta_time)
                forward = pygame.Vector2(math.cos(boat.heading), math.sin(boat.heading))
                boat.position += forward * step
                boat.velocity = forward * (step / delta_time)

    def _find_spawn_position(self, simulation) -> pygame.Vector2:
        """
        Finds a spawn point in open water clear of docks and margins.
        """
        bounds = simulation.world_coordinator.bounds
        safe_margin = self.outer_radius + 50.0
        min_x = bounds.min_x + safe_margin
        max_x = bounds.max_x - safe_margin
        min_y = bounds.min_y + safe_margin
        max_y = bounds.max_y - safe_margin

        for _ in range(64):
            candidate = pygame.Vector2(
                self.rng.uniform(min_x, max_x),
                self.rng.uniform(min_y, max_y),
            )
            if hasattr(simulation, "pier_manager") and not simulation.pier_manager.is_clear_of_dock(
                candidate, self.outer_radius + 30.0
            ):
                continue

            broken_clear = all(
                candidate.distance_to(b.position) > (self.outer_radius + 20.0)
                for b in simulation.boats
                if b.state == BoatState.BROKEN or getattr(b, "needs_rescue", False)
            )
            if broken_clear:
                return candidate

        return pygame.Vector2((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)

    def draw_visuals(self, surface: pygame.Surface, sim_time: float):
        """
        Renders enhanced visual whirlpool graphics on the ocean water surface:
        - Layered, multi-ring concentric swirl arms.
        - Smooth water-foam gradients and alpha blending.
        - Dynamic rotation speed ramping (spinning up on spawn, dissipating on despawn).
        """
        if not self.is_active:
            return

        ramp = self.get_ramp_factor()
        if ramp <= 0.01:
            return

        center_pt = (round(self.center.x), round(self.center.y))

        # Surface canvas with alpha
        dim = int((self.outer_radius + 50.0) * 2.0)
        aura_surf = pygame.Surface((dim, dim), pygame.SRCALPHA)
        aura_center = (dim // 2, dim // 2)

        # 1. Concentric deep water-depression gradient discs (suction pit)
        base_alpha = int(140 * ramp)
        steps = 5
        for s in range(steps, 0, -1):
            r = int(self.outer_radius * (s / float(steps)))
            alpha = int(base_alpha * (1.0 - (s / (steps + 1.5))))
            pygame.draw.circle(aura_surf, (10, 28, 52, alpha), aura_center, r)

        # 2. Glowing orbital ring foam tracks
        inner_r = int(self.inner_radius)
        outer_r = int(self.outer_radius)
        ring_alpha_outer = int(70 * ramp)
        ring_alpha_inner = int(95 * ramp)
        pygame.draw.circle(aura_surf, (35, 160, 225, ring_alpha_outer), aura_center, outer_r, 2)
        pygame.draw.circle(aura_surf, (50, 205, 245, ring_alpha_inner), aura_center, inner_r, 2)

        # 3. Layered multi-ring swirl arms rotating in spin direction
        spin_phase = sim_time * 3.6 * self.spin_direction * ramp
        num_arms = 6
        arm_alpha = int(120 * ramp)

        for arm in range(num_arms):
            arm_base_angle = spin_phase + arm * (2.0 * math.pi / num_arms)
            points = []
            foam_dots = []
            steps_arm = 22
            for s in range(steps_arm):
                t = s / float(steps_arm)
                r = 12.0 + t * (self.outer_radius + 18.0)
                spiral_angle = arm_base_angle + self.spin_direction * (t * 2.4)
                px = aura_center[0] + math.cos(spiral_angle) * r
                py = aura_center[1] + math.sin(spiral_angle) * r
                points.append((px, py))
                if s % 5 == 0 and s > 2:
                    foam_dots.append((px, py, max(1.5, 3.5 * (1.0 - t * 0.5))))

            if len(points) >= 2:
                pygame.draw.lines(
                    aura_surf,
                    (65, 215, 255, arm_alpha),
                    False,
                    points,
                    2,
                )
                for fx, fy, fr in foam_dots:
                    pygame.draw.circle(
                        aura_surf,
                        (230, 250, 255, int(150 * ramp)),
                        (round(fx), round(fy)),
                        round(fr),
                    )

        # 4. Central deep vortex sinkhole eye
        core_r = int(self.inner_radius * 0.45)
        pygame.draw.circle(
            aura_surf,
            (6, 18, 34, int(220 * ramp)),
            aura_center,
            core_r,
        )
        eye_spin = spin_phase * 1.5
        for i in range(8):
            fa = eye_spin + i * (math.pi / 4.0)
            fx = aura_center[0] + math.cos(fa) * (core_r - 1)
            fy = aura_center[1] + math.sin(fa) * (core_r - 1)
            pygame.draw.circle(aura_surf, (220, 245, 255, int(180 * ramp)), (round(fx), round(fy)), 2)

        # Blit aura surface centered at whirlpool position
        surface.blit(
            aura_surf,
            (
                center_pt[0] - aura_center[0],
                center_pt[1] - aura_center[1],
            ),
        )

    def draw_ui(self, surface: pygame.Surface, font: Optional[pygame.font.Font] = None):
        """
        Renders the sleek world-space whirlpool status bar floating directly above
        the whirlpool in canvas coordinates.
        Features rounded corners, subtle drop shadow, sleek gradient fill, and
        the label "Counteracting Whirlpool" during the countering phase.
        Hides automatically once the event concludes.
        """
        if not self.is_active:
            return

        ramp = self.get_ramp_factor()
        if ramp <= 0.01:
            return

        # Position bar directly above the whirlpool in world/canvas space
        bar_w = 188
        bar_h = 13
        center_x = round(self.center.x)
        target_y = round(self.center.y - self.outer_radius - 28.0)
        bar_y = max(16, target_y)
        bar_x = center_x - bar_w // 2

        alpha = int(245 * ramp)

        # 1. Subtle drop shadow
        shadow_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(
            shadow_surf,
            (4, 10, 18, int(130 * ramp)),
            shadow_surf.get_rect(),
            border_radius=6,
        )
        surface.blit(shadow_surf, (bar_x + 1, bar_y + 2))

        # 2. Sleek dark container background
        container_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(
            container_surf,
            (10, 24, 38, alpha),
            container_surf.get_rect(),
            border_radius=6,
        )

        # 3. Progress fill
        fill_ratio = self.progress
        inner_w = bar_w - 4
        fill_w = max(0, min(inner_w, round(inner_w * fill_ratio)))
        if fill_w > 0:
            fill_rect = pygame.Rect(2, 2, fill_w, bar_h - 4)
            pygame.draw.rect(container_surf, (45, 205, 245, alpha), fill_rect, border_radius=4)
            highlight_rect = pygame.Rect(2, 2, fill_w, max(1, (bar_h - 4) // 2))
            pygame.draw.rect(
                container_surf, (160, 235, 255, int(160 * ramp)), highlight_rect, border_radius=3
            )

        # 4. Polished border
        pygame.draw.rect(
            container_surf,
            (70, 210, 255, alpha),
            container_surf.get_rect(),
            width=1,
            border_radius=6,
        )
        surface.blit(container_surf, (bar_x, bar_y))

        # 5. Font and Labels
        if font is None:
            if not pygame.font.get_init():
                pygame.font.init()
            font = pygame.font.SysFont("Consolas", 12, bold=True)
            if font is None:
                font = pygame.font.Font(None, 14)

        # Label: "Counteracting Whirlpool" during countering phase, or "Approaching Whirlpool" during approach
        if self.phase == "countering":
            title_text = "Counteracting Whirlpool"
        else:
            title_text = "Approaching Whirlpool"

        title_shadow = font.render(title_text, True, (0, 0, 0))
        title_surf = font.render(title_text, True, (230, 245, 255))
        tx = center_x - title_surf.get_width() // 2
        ty = bar_y - title_surf.get_height() - 2

        surface.blit(title_shadow, (tx + 1, ty + 1))
        surface.blit(title_surf, (tx, ty))

        # Countdown / status text inside the bar
        if self.phase == "countering":
            percent = int(fill_ratio * 100)
            time_text = f"{self.active_time_remaining:.1f}s [{percent}%]"
        else:
            time_text = "POSITIONING"

        mini_font = pygame.font.SysFont("Consolas", 10, bold=True)
        if mini_font is None:
            mini_font = font
        time_shadow = mini_font.render(time_text, True, (0, 0, 0))
        time_surf = mini_font.render(time_text, True, (245, 252, 255))
        rx = center_x - time_surf.get_width() // 2
        ry = bar_y + (bar_h - time_surf.get_height()) // 2
        surface.blit(time_shadow, (rx + 1, ry + 1))
        surface.blit(time_surf, (rx, ry))
