"""
FishSwarm - Main Application Runner.
Launches the autonomous multi-agent fishing simulation with Pygame.
"""
import sys
import math
import random
import pygame

from src.config import OCEAN_WIDTH, OCEAN_HEIGHT, COLOR_OCEAN, COLOR_OCEAN_BORDER
from src.core.simulation import FishSwarmSimulation
from src.entities.boat_agent import BoatAgent
from src.entities.fish_school import FishSchool
from src.ui.hud import SimulationHUD
from src.ui.debug_overlay import DebugOverlay

SILVERS = [(205, 225, 240), (180, 205, 225), (225, 235, 245), (235, 200, 120)]

# --- Crash / rescue tuning ---
CRASH_DIST = 22
BREAK_CHANCE = 1 / 25      # rolled once per close encounter
GRID = 72
KEEP_OUT = GRID / 2 + 30
RESCUE_SPEED, TOW_SPEED = 150, 90
SLOT = 26
REENTRY_MARGIN = 60

# --- Traffic tuning ---
MIN_GAP = 40               # boats never closer than this (unless doomed to crash)
ENCOUNTER_DIST = 55        # first time two boats get this close, a crash roll happens
ENCOUNTER_RESET = 75       # pair must separate beyond this before it can roll again
CLOSE_SPEED = 60           # px/s a doomed pair closes on each other
MAX_PER_SPOT = 3           # UP TO this many boats per spot (a cap, not a requirement)
MIN_PREFERRED = 2          # initial targeting only: spots below this are filled first
SPOT_RING = 34             # fishing slots sit on a ring this far from the school center
SEEK_SPEED = 70            # px/s boats travel toward their assigned spot
CAPTURE = 3                # px from slot at which a boat commits to the spot

# --- Fish respawn tuning ---
DEPLETED_FRAC = 0.10
RESPAWN_DELAY = 8.0

# --- Debug cleanup ---
STRIP_BLUE_DOTS = True
BLUE_DOT = (60, 120, 255)
BLUE_TOLERANCE = (90, 90, 70)


class NullFont:
    """Swallows text so school.draw() skips its fish counter but keeps its other debug visuals."""
    def render(self, *a, **k):
        return pygame.Surface((1, 1), pygame.SRCALPHA)
    def size(self, t):
        return (0, 0)
    def get_height(self):
        return 0
    def get_linesize(self):
        return 0


NULL_FONT = NullFont()


def create_default_scenario() -> FishSwarmSimulation:
    sim = FishSwarmSimulation(width=OCEAN_WIDTH, height=OCEAN_HEIGHT, margin=40)
    for pos in [(150, 150), (350, 600), (600, 300), (850, 150), (1050, 650), (550, 700)]:
        sim.add_boat(BoatAgent(position=pos))
    for pos, pop in [((250, 300), 80.0), ((500, 180), 120.0), ((750, 500), 100.0),
                     ((950, 350), 90.0), ((350, 650), 60.0)]:
        sim.add_school(FishSchool(position=pos, population=pop))
    return sim


def make_fish(school, seed):
    rng = random.Random(seed)
    radius = 14 + math.sqrt(school.population) * 2.5
    fish = []
    for _ in range(int(school.population / 1.2)):
        r = radius * rng.random() ** 0.8 * 0.9
        a0 = rng.uniform(0, math.tau)
        w = 0.9 * (1.4 - r / radius) + rng.uniform(-0.1, 0.1)
        fish.append((r, a0, w, rng.uniform(0, math.tau),
                     rng.uniform(4.5, 6.5), rng.choice(SILVERS)))
    return fish


def build_clusters(sim):
    """Per school: [school, fish, start_pop, depleted_timer, (x, y)]."""
    return [[s, make_fish(s, i), max(s.population, 1.0), 0.0,
             (float(s.position[0]), float(s.position[1]))]
            for i, s in enumerate(sim.schools)]


def update_respawn(sim, clusters, dt):
    """Depleted school -> wait -> register a brand-new school through the simulation."""
    for i, c in enumerate(clusters):
        s, _, pop0, _, home = c
        gone = not any(x is s for x in sim.schools)
        if gone or s.population <= pop0 * DEPLETED_FRAC:
            c[3] += dt
            if c[3] >= RESPAWN_DELAY:
                if not gone:
                    remove = getattr(sim, "remove_school", None)
                    if remove:
                        remove(s)
                    else:
                        sim.schools[:] = [x for x in sim.schools if x is not s]
                new = FishSchool(position=home, population=pop0)
                sim.add_school(new)
                c[0], c[1], c[3] = new, make_fish(new, i + int(random.random() * 1e6)), 0.0
        else:
            c[3] = 0.0


def draw_clusters(screen, clusters, t):
    for s, fish, pop0, _, home in clusters:
        cx, cy = home
        visible = int(len(fish) * max(0.0, min(1.0, s.population / pop0)))
        for r, a0, w, ph, L, col in fish[:visible]:
            a = a0 + w * t
            rr = r + math.sin(t * 1.3 + ph) * 2.5
            x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
            hx, hy = -math.sin(a), math.cos(a)
            nx, ny = -hy, hx
            W = L * 0.28
            base = (x - hx * L * 0.55, y - hy * L * 0.55)
            tail_end = (base[0] - hx * L * 0.45, base[1] - hy * L * 0.45)
            pygame.draw.polygon(screen, tuple(int(c * 0.7) for c in col), [
                base,
                (tail_end[0] + nx * W * 1.1, tail_end[1] + ny * W * 1.1),
                (tail_end[0] - nx * W * 1.1, tail_end[1] - ny * W * 1.1)])
            pygame.draw.polygon(screen, col, [
                (x + hx * L * 0.5, y + hy * L * 0.5),
                (x + nx * W, y + ny * W), base,
                (x - nx * W, y - ny * W)])


def draw_debug_layer(screen, sim, layer):
    """School debug (no counter text) + DebugOverlay, with blue dots erased."""
    layer.fill((0, 0, 0, 0))
    for school in sim.schools:
        school.draw(layer, NULL_FONT, show_debug=True)
    DebugOverlay.draw(layer, sim)
    if STRIP_BLUE_DOTS:
        pygame.transform.threshold(layer, layer, BLUE_DOT, BLUE_TOLERANCE + (255,),
                                   (0, 0, 0, 0), 1, None, False)
    screen.blit(layer, (0, 0))


# ---------------------------------------------------------------- incidents
def pos(b):
    return pygame.Vector2(b.position[0], b.position[1])


def put(b, v):
    try:
        b.position[0], b.position[1] = v.x, v.y
    except TypeError:
        b.position = (v.x, v.y)


def step(cur, target, speed, dt):
    d = target - cur
    n = d.length()
    return target.copy() if n <= speed * dt else cur + d / n * speed * dt


class Hazards:
    """Traffic control (closest-spot targeting, up to 3 boats per spot, commit on arrival,
    no touching) -> rare doomed crash -> one breaks -> 2 OTHER boats place grid and tow it
    off screen -> replacement boat enters."""

    def __init__(self):
        self.incidents = []
        self.encounters = set()    # pairs in a close encounter (already rolled)
        self.doomed = {}           # pair key -> (a, b): allowed to close in and crash
        self.assign = {}           # id(boat) -> (boat, school, slot index)
        self.committed = set()     # ids of boats locked onto their slot
        self.saved = {}            # id(boat) -> position before sim.update
        self.initial_done = False  # True after the first targeting round
        self.dt = 0.0

    def freeze(self, sim):
        """Call right before sim.update(): remember where assigned boats are."""
        self.saved = {id(b): pos(b) for b, _, _ in self.assign.values()}

    @staticmethod
    def _stop(b):
        for attr in ("velocity", "vel"):
            v = getattr(b, attr, None)
            if v is not None:
                try:
                    v[0], v[1] = 0, 0
                except Exception:
                    pass

    def driven(self):
        ids = set()
        for i in self.incidents:
            ids |= {id(i["broken"])} | {id(r) for r in i["rescuers"]}
        return ids

    def break_boat(self, sim, broken, collider):
        """broken + collider caused the crash; two more boats are needed to recover it."""
        driven = self.driven()
        free = [b for b in sim.boats
                if b is not broken and b is not collider and id(b) not in driven]
        if id(broken) in driven or len(free) < 2:
            return
        bp = pos(broken)
        helpers = sorted(free, key=lambda b: pos(b).distance_to(bp))[:2]
        self.incidents.append(dict(
            broken=broken, rescuers=helpers, bp=bp,
            rps=[pos(h) for h in helpers], homes=[pos(h) for h in helpers],
            phase="approach", timer=1.5, grid=None, target=None))

    def force_break(self, sim):
        healthy = [b for b in sim.boats if id(b) not in self.driven()]
        if len(healthy) >= 4:
            a, b = random.sample(healthy, 2)
            self.doomed[frozenset((id(a), id(b)))] = (a, b)

    def _replace(self, sim, wreck, bp):
        """Remove the wreck and bring in a fresh boat at the edge where it left."""
        remove = getattr(sim, "remove_boat", None)
        if remove:
            remove(wreck)
        else:
            sim.boats[:] = [b for b in sim.boats if b is not wreck]
        x = min(max(bp.x, REENTRY_MARGIN), OCEAN_WIDTH - REENTRY_MARGIN)
        y = min(max(bp.y, REENTRY_MARGIN), OCEAN_HEIGHT - REENTRY_MARGIN)
        sim.add_boat(BoatAgent(position=(x, y)))

    # ---------------- spot assignment: closest spot with room, commit on arrival
    def _seek(self, sim, free, doomed_ids):
        live = [s for s in sim.schools if s.population > 0.01]
        live_ids = {id(s) for s in live}
        boat_ids = {id(b) for b in sim.boats}
        busy = self.driven() | doomed_ids

        for k, (b, s, slot) in list(self.assign.items()):
            if k not in boat_ids:
                del self.assign[k]
                self.committed.discard(k)
            elif id(s) not in live_ids:
                # School was respawned at the same spot? Keep the boat there.
                twin = next((n for n in live if pos(n).distance_to(pos(s)) < 1), None)
                if twin is not None:
                    self.assign[k] = (b, twin, slot)
                else:
                    del self.assign[k]
                    self.committed.discard(k)

        used = {id(s): set() for s in live}
        for b, s, slot in self.assign.values():
            used[id(s)].add(slot)

        # Assign idle boats (2-boat priority only in the very first round)
        unassigned = [b for b in free if id(b) not in busy and id(b) not in self.assign]
        while unassigned:
            best = None
            for b in unassigned:
                for s in live:
                    n = len(used[id(s)])
                    if n >= MAX_PER_SPOT:
                        continue
                    d = pos(b).distance_to(pos(s))
                    key = (n >= MIN_PREFERRED, d) if not self.initial_done else (0, d)
                    if best is None or key < best[0]:
                        best = (key, b, s)
            if best is None:
                break
            _, b, s = best
            slot = min(set(range(MAX_PER_SPOT)) - used[id(s)])
            used[id(s)].add(slot)
            self.assign[id(b)] = (b, s, slot)
            unassigned.remove(b)

        if free and live:
            self.initial_done = True

        for b, s, slot in self.assign.values():
            if id(b) in busy:
                continue                      # crash / rescue: keeps its spot, returns later
            ang = math.radians(90 + slot * 360 / MAX_PER_SPOT)
            target = pos(s) + pygame.Vector2(math.cos(ang), math.sin(ang)) * SPOT_RING

            if id(b) in self.committed:       # arrived: stay put, no matter what
                put(b, target)
                self._stop(b)
                continue

            if any(inc["grid"] and abs(target.x - inc["grid"].x) < KEEP_OUT
                   and abs(target.y - inc["grid"].y) < KEEP_OUT for inc in self.incidents):
                continue                      # slot inside a keep-out grid: wait outside it

            new = step(pos(b), target, SEEK_SPEED, self.dt)
            put(b, new)
            if new.distance_to(target) < CAPTURE:
                put(b, target)
                self.committed.add(id(b))
                self._stop(b)

    # ---------------- traffic
    def traffic(self, sim):
        driven = self.driven()
        free = [b for b in sim.boats if id(b) not in driven]

        # 1. Doomed pairs close in on each other and crash
        for k, (a, b) in list(self.doomed.items()):
            if id(a) in driven or id(b) in driven or a not in sim.boats or b not in sim.boats:
                del self.doomed[k]
                continue
            pa, pb = pos(a), pos(b)
            if pa.distance_to(pb) < CRASH_DIST:
                del self.doomed[k]
                self.break_boat(sim, *random.sample((a, b), 2))
            else:
                put(a, step(pa, pb, CLOSE_SPEED, self.dt))
                put(b, step(pb, pa, CLOSE_SPEED, self.dt))
        doomed_ids = {id(x) for pair in self.doomed.values() for x in pair}

        # 2. Close encounters: one crash roll per encounter (committed boats never roll)
        now = set()
        for i, a in enumerate(free):
            for b in free[i + 1:]:
                if id(a) in self.committed or id(b) in self.committed:
                    continue
                k = frozenset((id(a), id(b)))
                d = pos(a).distance_to(pos(b))
                if k in self.encounters and d < ENCOUNTER_RESET:
                    now.add(k)
                elif d < ENCOUNTER_DIST:
                    now.add(k)
                    if len(free) >= 4 and k not in self.doomed and random.random() < BREAK_CHANCE:
                        self.doomed[k] = (a, b)
        self.encounters = now

        # 3. No touching. Committed boats never get shoved; the other boat moves instead.
        for _ in range(2):
            for i, a in enumerate(sim.boats):
                for b in sim.boats[i + 1:]:
                    if frozenset((id(a), id(b))) in self.doomed:
                        continue
                    ad = id(a) in driven or id(a) in self.committed
                    bd = id(b) in driven or id(b) in self.committed
                    if ad and bd:
                        continue
                    pa, pb = pos(a), pos(b)
                    d = pa - pb
                    n = d.length()
                    if n >= MIN_GAP:
                        continue
                    u = d / n if n > 1e-3 else pygame.Vector2(1, 0)
                    push = MIN_GAP - n
                    if ad:
                        put(b, pb - u * push)
                    elif bd:
                        put(a, pa + u * push)
                    else:
                        put(a, pa + u * push / 2)
                        put(b, pb - u * push / 2)

        # 4. Targeting runs last so its position is the final word each frame
        self._seek(sim, free, doomed_ids)

    # ---------------- rescue state machine
    def update(self, sim, dt):
        self.dt = dt

        # Undo whatever the boat's own AI did this frame to assigned boats
        driven0 = self.driven()
        for b, _, _ in self.assign.values():
            p = self.saved.get(id(b))
            if p is not None and id(b) not in driven0:
                put(b, p)

        for inc in self.incidents[:]:
            ph, bp, rps = inc["phase"], inc["bp"], inc["rps"]
            slots = [bp + pygame.Vector2(-SLOT, 0), bp + pygame.Vector2(SLOT, 0)]

            if ph == "approach":
                for i in range(2):
                    rps[i] = step(rps[i], slots[i], RESCUE_SPEED, dt)
                if all(rps[i].distance_to(slots[i]) < 2 for i in range(2)):
                    inc["phase"], inc["grid"] = "place", bp.copy()

            elif ph == "place":
                inc["timer"] -= dt
                if inc["timer"] <= 0:
                    edges = [(bp.x, pygame.Vector2(-120, bp.y)),
                             (OCEAN_WIDTH - bp.x, pygame.Vector2(OCEAN_WIDTH + 120, bp.y)),
                             (bp.y, pygame.Vector2(bp.x, -120)),
                             (OCEAN_HEIGHT - bp.y, pygame.Vector2(bp.x, OCEAN_HEIGHT + 120))]
                    inc["target"] = min(edges, key=lambda e: e[0])[1]
                    inc["phase"] = "tow"

            elif ph == "tow":
                move = step(bp, inc["target"], TOW_SPEED, dt) - bp
                inc["bp"] = bp = bp + move
                for i in range(2):
                    rps[i] = rps[i] + move
                if inc["grid"] and bp.distance_to(inc["grid"]) > GRID:
                    inc["grid"] = None
                if not pygame.Rect(-40, -40, OCEAN_WIDTH + 80, OCEAN_HEIGHT + 80).collidepoint(bp):
                    self._replace(sim, inc["broken"], bp)
                    inc["phase"], inc["grid"] = "return", None

            elif ph == "return":
                for i in range(2):
                    rps[i] = step(rps[i], inc["homes"][i], RESCUE_SPEED, dt)
                if all(rps[i].distance_to(inc["homes"][i]) < 1 for i in range(2)):
                    for r, h in zip(inc["rescuers"], inc["homes"]):
                        put(r, h)
                    self.incidents.remove(inc)
                    continue

            if inc["phase"] != "return":
                put(inc["broken"], inc["bp"])
            for r, p in zip(inc["rescuers"], rps):
                put(r, p)

        # Keep non-involved boats out of any placed grid
        driven = self.driven()
        for inc in self.incidents:
            g = inc["grid"]
            if not g:
                continue
            for b in sim.boats:
                if id(b) in driven or id(b) in self.committed:
                    continue
                p = pos(b)
                d = p - g
                if abs(d.x) < KEEP_OUT and abs(d.y) < KEEP_OUT:
                    if KEEP_OUT - abs(d.x) < KEEP_OUT - abs(d.y):
                        p.x = g.x + math.copysign(KEEP_OUT, d.x or 1)
                    else:
                        p.y = g.y + math.copysign(KEEP_OUT, d.y or 1)
                    put(b, p)

        self.traffic(sim)

    def draw_under(self, screen):
        for inc in self.incidents:
            g = inc["grid"]
            if not g:
                continue
            surf = pygame.Surface((GRID, GRID), pygame.SRCALPHA)
            surf.fill((255, 200, 0, 50))
            for k in range(0, GRID * 2, 12):
                pygame.draw.line(surf, (255, 200, 0, 150), (k, 0), (0, k))
            pygame.draw.rect(surf, (255, 200, 0, 230), surf.get_rect(), 2)
            screen.blit(surf, (g.x - GRID / 2, g.y - GRID / 2))
            pygame.draw.rect(screen, (200, 160, 0),
                             pygame.Rect(g.x - KEEP_OUT, g.y - KEEP_OUT, KEEP_OUT * 2, KEEP_OUT * 2), 1)

    def draw_over(self, screen, font, t):
        for inc in self.incidents:
            if inc["phase"] == "tow":
                for rp in inc["rps"]:
                    pygame.draw.line(screen, (150, 110, 60), rp, inc["bp"], 2)
            if inc["phase"] != "return":
                x, y = inc["bp"]
                pygame.draw.circle(screen, (230, 60, 60), (int(x), int(y)), 16, 2)
                for k in range(3):
                    f = (t * 0.8 + k / 3) % 1.0
                    pygame.draw.circle(screen, (120, 120, 120),
                                       (int(x + math.sin(t * 2 + k) * 4), int(y - 8 - f * 22)),
                                       int(2 + f * 4), 1)
                lbl = font.render("BROKEN", True, (255, 110, 110))
                screen.blit(lbl, (x - lbl.get_width() // 2, y + 20))


def main():
    pygame.init()
    pygame.display.set_caption("FishSwarm - Autonomous Multi-Agent Fishing Simulation")
    screen = pygame.display.set_mode((OCEAN_WIDTH, OCEAN_HEIGHT))
    clock = pygame.time.Clock()
    debug_layer = pygame.Surface((OCEAN_WIDTH, OCEAN_HEIGHT), pygame.SRCALPHA)

    hud = SimulationHUD()
    sim = create_default_scenario()
    clusters = build_clusters(sim)
    hazards = Hazards()

    is_paused, speed_multiplier, show_debug, elapsed = False, 1.0, True, 0.0
    speeds = [1.0, 2.0, 4.0]

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.1)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    is_paused = not is_paused
                elif event.key == pygame.K_s:
                    speed_multiplier = speeds[(speeds.index(speed_multiplier) + 1) % len(speeds)]
                elif event.key == pygame.K_d:
                    show_debug = not show_debug
                elif event.key == pygame.K_c:
                    hazards.force_break(sim)      # test: two boats close in and crash
                elif event.key == pygame.K_r:
                    sim = create_default_scenario()
                    clusters = build_clusters(sim)
                    hazards = Hazards()

        if not is_paused:
            hazards.freeze(sim)                   # remember assigned boats' positions
            sim.update(dt * speed_multiplier)
            hazards.update(sim, dt * speed_multiplier)
            update_respawn(sim, clusters, dt * speed_multiplier)
            elapsed += dt * speed_multiplier

        screen.fill(COLOR_OCEAN)

        b = sim.world_coordinator.bounds
        pygame.draw.rect(screen, COLOR_OCEAN_BORDER,
                         pygame.Rect(int(b.min_x), int(b.min_y),
                                     int(b.max_x - b.min_x), int(b.max_y - b.min_y)), 2)

        draw_clusters(screen, clusters, elapsed)
        hazards.draw_under(screen)

        if show_debug:
            draw_debug_layer(screen, sim, debug_layer)

        for boat in sim.boats:
            boat.draw(screen, hud.font, show_debug=show_debug)
        hazards.draw_over(screen, hud.font, elapsed)

        hud.draw(screen, sim, is_paused=is_paused,
                 speed_multiplier=speed_multiplier, show_debug=show_debug)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()