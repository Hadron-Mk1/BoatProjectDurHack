import pygame

from src.config import BOAT_BREAK_CHANCE, RESCUE_PICKUP_RADIUS
from src.core.simulation import FishSwarmSimulation
from src.entities.boat_agent import BoatAgent, BoatState, BoatType, RegularBoat, TowingBoat
from src.entities.fish_school import FishSchool


class FixedRng:
    def __init__(self, roll, choice_index=0):
        self.roll = roll
        self.choice_index = choice_index

    def random(self):
        return self.roll

    def choice(self, values):
        return values[self.choice_index]


def make_simulation(positions):
    sim = FishSwarmSimulation(width=500, height=400, margin=20)
    boats = [BoatAgent(position=p) for p in positions]
    if len(boats) >= 4:
        boats[2].boat_type = BoatType.TOWING
        boats[3].boat_type = BoatType.TOWING
    for boat in boats:
        sim.add_boat(boat)
    return sim, boats


def test_collision_break_chance_is_ten_percent():
    assert BOAT_BREAK_CHANCE == 0.10


def test_collision_without_break_separates_boats_and_preserves_states():
    sim, boats = make_simulation([(200, 200), (210, 200), (300, 300), (350, 300)])
    sim.rescue_manager.rng = FixedRng(0.5)

    sim.rescue_manager.update(sim, 0.1)
    sim.rescue_manager.update(sim, 0.1)

    assert all(boat.state == BoatState.EXPLORING for boat in boats)
    assert boats[0].position.distance_to(boats[1].position) >= 24


def test_collision_assigns_two_other_boats_and_tows_wreck_to_boundary():
    sim, boats = make_simulation([
        (200, 200), (210, 200), (205, 225), (205, 175), (350, 300)
    ])
    sim.rescue_manager.rng = FixedRng(0.0)
    sim.rescue_manager.update(sim, 0.1)
    sim.rescue_manager.update(sim, 0.1)

    wrecks = [boat for boat in boats if boat.state == BoatState.BROKEN]
    rescuers = [boat for boat in boats if boat.state == BoatState.MOVING_TO_TOW]
    assert len(wrecks) == 1
    assert len(rescuers) == 2
    assert all(rescuer.boat_type == BoatType.TOWING for rescuer in rescuers)
    assert all(rescuer.target_position == wrecks[0].position for rescuer in rescuers)

    heading_before = rescuers[0].heading
    rescuers[0].update(0.1, sim.world_coordinator)
    assert rescuers[0].heading != heading_before

    saw_towing_state = False
    for _ in range(100):
        for boat in rescuers:
            if boat.state == BoatState.MOVING_TO_TOW:
                boat.update(0.1, sim.world_coordinator)
        sim.rescue_manager.update(sim, 0.1)
        saw_towing_state |= any(boat.state == BoatState.TOWING for boat in boats)
        if all(boat.state == BoatState.EXPLORING for boat in boats):
            break

    assert all(boat.state == BoatState.EXPLORING for boat in boats)
    assert saw_towing_state
    assert sim.world_coordinator.bounds.is_inside(wrecks[0].position, use_margin=True)


def test_wreck_waits_for_two_towing_boats_without_using_regular_boats():
    sim, boats = make_simulation([(200, 200), (210, 200), (300, 300)])
    towing = BoatAgent((305, 300), boat_type=BoatType.TOWING)
    sim.add_boat(towing)
    sim.rescue_manager.rng = FixedRng(0.0)

    sim.rescue_manager.update(sim, 0.1)
    wreck = next(boat for boat in boats if boat.state == BoatState.BROKEN)

    assert wreck.state == BoatState.BROKEN
    assert towing.state == BoatState.EXPLORING
    assert all(boat.state != BoatState.MOVING_TO_TOW for boat in boats)

    second_towing = BoatAgent((310, 310), boat_type=BoatType.TOWING)
    sim.add_boat(second_towing)
    sim.rescue_manager.update(sim, 0.1)
    assert towing.state == BoatState.MOVING_TO_TOW
    assert second_towing.state == BoatState.MOVING_TO_TOW


def test_swept_collision_detects_boats_that_cross_between_frames():
    sim, boats = make_simulation([(100, 200), (200, 200), (300, 300), (350, 300)])
    previous = {boat.boat_id: boat.position.copy() for boat in boats}
    boats[0].position.x = 200
    boats[1].position.x = 100
    sim.rescue_manager.rng = FixedRng(0.0)

    sim.rescue_manager.update(sim, 0.1, previous)
    sim.rescue_manager.update(sim, 0.1)

    assert sum(boat.state == BoatState.BROKEN for boat in boats) == 1
    assert sum(boat.state == BoatState.MOVING_TO_TOW for boat in boats) == 2


def test_simulation_update_routes_crossing_collisions_to_rescue_manager():
    sim, boats = make_simulation([(100, 200), (200, 200), (300, 300), (350, 300)])
    sim.rescue_manager.rng = FixedRng(0.0)
    boats[0].update = lambda _dt, _world: setattr(boats[0], "position", boats[1].position.copy())
    boats[1].update = lambda _dt, _world: setattr(boats[1], "position", pygame.Vector2(100, 200))

    sim.update(0.1)
    sim.rescue_manager.update(sim, 0.1)

    assert sum(boat.state == BoatState.BROKEN for boat in boats) == 1
    assert sum(boat.state == BoatState.MOVING_TO_TOW for boat in boats) == 2


def test_only_towing_boats_can_enter_tow_states():
    regular = BoatAgent((100, 100), boat_type=BoatType.REGULAR)
    cleaner = BoatAgent((200, 100), boat_type=BoatType.CLEANING)
    for boat in (regular, cleaner):
        assert not boat.transition_to(BoatState.MOVING_TO_TOW)
        boat.state = BoatState.MOVING_TO_TOW
        assert not boat.transition_to(BoatState.TOWING)


def test_broken_boat_flags_itself_and_registers_with_rescue_manager():
    sim = FishSwarmSimulation(width=600, height=500, margin=30)
    boat = RegularBoat((250, 250))
    sim.add_boat(boat)
    assert not boat.needs_rescue

    boat.transition_to(BoatState.BROKEN)
    assert boat.needs_rescue is True
    assert boat.state == BoatState.BROKEN

    # Simulation poll or rescue_manager poll registers the broken boat
    sim.rescue_manager.poll(sim)
    assert len(sim.rescue_manager._incidents) == 1
    incident = sim.rescue_manager._incidents[0]
    assert incident["wreck"].boat_id == boat.boat_id
    assert incident["phase"] == "waiting"
    assert incident["destination"] is not None


def test_idle_towing_boat_prioritizes_rescue_over_wandering_and_fishing():
    sim = FishSwarmSimulation(width=600, height=500, margin=30)
    wreck = RegularBoat((200, 200))
    wreck.transition_to(BoatState.BROKEN)
    towing_1 = TowingBoat((220, 220))
    towing_2 = TowingBoat((240, 220))
    # Place fish school right next to towing boats
    school = FishSchool((230, 230), population=50.0)

    sim.add_boat(wreck)
    sim.add_boat(towing_1)
    sim.add_boat(towing_2)
    sim.add_school(school)

    # One update step: poll claims towing boats for rescue before fishing discovery scan
    sim.update(0.1)

    assert towing_1.state == BoatState.MOVING_TO_TOW or towing_1.state == BoatState.TOWING
    assert towing_2.state == BoatState.MOVING_TO_TOW or towing_2.state == BoatState.TOWING
    assert towing_1.claimed_rescue == wreck
    assert towing_2.claimed_rescue == wreck
    # Did not get recruited into or start a fishing operation
    assert len(sim.operation_coordinator.operations) == 0


def test_towing_boat_navigation_and_attachment_within_pickup_radius():
    sim = FishSwarmSimulation(width=600, height=500, margin=30)
    wreck = RegularBoat((300, 300))
    wreck.transition_to(BoatState.BROKEN)
    # Start rescuers further away than pickup radius
    towing_1 = TowingBoat((300, 300 + RESCUE_PICKUP_RADIUS + 40))
    towing_2 = TowingBoat((300, 300 - RESCUE_PICKUP_RADIUS - 40))

    sim.add_boat(wreck)
    sim.add_boat(towing_1)
    sim.add_boat(towing_2)

    sim.rescue_manager.poll(sim)
    incident = sim.rescue_manager._incidents[0]
    assert incident["phase"] == "approach"
    assert towing_1.state == BoatState.MOVING_TO_TOW
    assert towing_2.state == BoatState.MOVING_TO_TOW

    # Advance until they enter pickup radius and trigger attachment
    attached = False
    for _ in range(50):
        for b in [towing_1, towing_2]:
            b.update(0.1, sim.world_coordinator)
        sim.rescue_manager.update(sim, 0.1)
        if incident["phase"] == "tow":
            attached = True
            break

    assert attached is True
    assert towing_1.state == BoatState.TOWING
    assert towing_2.state == BoatState.TOWING


def test_full_tow_lifecycle_repairs_wreck_and_releases_towing_boats():
    sim = FishSwarmSimulation(width=500, height=400, margin=20)
    wreck = RegularBoat((200, 200))
    wreck.transition_to(BoatState.BROKEN)
    towing_1 = TowingBoat((200, 215))
    towing_2 = TowingBoat((200, 185))

    sim.add_boat(wreck)
    sim.add_boat(towing_1)
    sim.add_boat(towing_2)

    # First update attaches
    sim.rescue_manager.update(sim, 0.1)
    incident = sim.rescue_manager._incidents[0]
    assert incident["phase"] == "tow"

    # Step simulation until convoy reaches destination and wreck is repaired
    destination = incident["destination"]
    for _ in range(150):
        sim.rescue_manager.update(sim, 0.1)
        if len(sim.rescue_manager._incidents) == 0:
            break

    assert len(sim.rescue_manager._incidents) == 0
    # Wreck restored to operational status
    assert wreck.state == BoatState.EXPLORING
    assert wreck.needs_rescue is False
    assert sim.world_coordinator.bounds.is_inside(wreck.position, use_margin=True)
    # Towing boats released back to default behavior
    assert towing_1.state == BoatState.EXPLORING
    assert towing_2.state == BoatState.EXPLORING
    assert towing_1.claimed_rescue is None
    assert towing_2.claimed_rescue is None


def test_single_towing_boat_lifecycle():
    sim = FishSwarmSimulation(width=500, height=400, margin=20)
    sim.rescue_manager.required_rescuers = 1
    wreck = RegularBoat((200, 200))
    wreck.transition_to(BoatState.BROKEN)
    towing = TowingBoat((200, 220))

    sim.add_boat(wreck)
    sim.add_boat(towing)

    sim.rescue_manager.poll(sim)
    incident = sim.rescue_manager._incidents[0]
    assert incident["phase"] == "approach"
    sim.rescue_manager.update(sim, 0.1)
    assert incident["phase"] == "tow"
    assert towing.state == BoatState.TOWING

    for _ in range(150):
        sim.rescue_manager.update(sim, 0.1)
        if len(sim.rescue_manager._incidents) == 0:
            break

    assert len(sim.rescue_manager._incidents) == 0
    assert wreck.state == BoatState.EXPLORING
    assert wreck.needs_rescue is False
    assert towing.state == BoatState.EXPLORING
    assert towing.claimed_rescue is None


def test_rescue_manager_draw_renders_active_tow_lines_and_status():
    sim = FishSwarmSimulation(width=500, height=400, margin=20)
    wreck = RegularBoat((200, 200))
    wreck.transition_to(BoatState.BROKEN)
    towing_1 = TowingBoat((210, 210))
    towing_2 = TowingBoat((190, 190))
    sim.add_boat(wreck)
    sim.add_boat(towing_1)
    sim.add_boat(towing_2)

    # 1. Waiting phase render
    sim.rescue_manager.register_broken_boat(sim, wreck)
    incident = sim.rescue_manager._incidents[0]
    incident["phase"] = "waiting"

    surface = pygame.Surface((500, 400))
    surface.fill((20, 50, 85))
    initial_pixels = pygame.image.tobytes(surface, "RGB")

    sim.rescue_manager.draw(surface)
    waiting_pixels = pygame.image.tobytes(surface, "RGB")
    assert waiting_pixels != initial_pixels, "Waiting status beacon and badge must be rendered"

    # 2. Approach phase render
    incident["phase"] = "approach"
    incident["rescuers"] = [towing_1, towing_2]
    surface.fill((20, 50, 85))
    sim.rescue_manager.draw(surface)
    approach_pixels = pygame.image.tobytes(surface, "RGB")
    assert approach_pixels != initial_pixels, "Approach lines and badge must be rendered"

    # 3. Tow phase render
    incident["phase"] = "tow"
    surface.fill((20, 50, 85))
    sim.rescue_manager.draw(surface)
    tow_pixels = pygame.image.tobytes(surface, "RGB")
    assert tow_pixels != initial_pixels, "Active tow cables and badge must be rendered"
    assert tow_pixels != approach_pixels, "Tow rendering must be visually distinct from approach"
