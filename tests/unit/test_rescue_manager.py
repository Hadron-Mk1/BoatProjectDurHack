import pygame

from src.config import BOAT_BREAK_CHANCE
from src.core.simulation import FishSwarmSimulation
from src.entities.boat_agent import BoatAgent, BoatState, BoatType


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
