import pygame

from src.config import OIL_SPILL_CHANCE
from src.core.comms_hub import Message
from src.core.simulation import BoatSwarmSimulation
from src.entities.boat_agent import BoatAgent, BoatState, BoatType, CleaningBoat, RegularBoat, TowingBoat
from src.entities.fish_school import FishSchool
from src.entities.oil_spill import OilSpill


class AlwaysSpawnRng:
    @staticmethod
    def random():
        return 0.0


class NeverSpawnRng:
    @staticmethod
    def random():
        return 1.0


def test_boat_classes_have_distinct_speeds_and_fish_capacities():
    towing = TowingBoat((100, 100))
    cleaning = CleaningBoat((200, 100))
    regular = RegularBoat((300, 100))

    assert towing.speed < regular.speed < cleaning.speed
    assert towing.fish_capacity > regular.fish_capacity > cleaning.fish_capacity
    assert towing.boat_type == BoatType.TOWING
    assert cleaning.boat_type == BoatType.CLEANING
    assert regular.boat_type == BoatType.REGULAR


def test_fishing_harvest_respects_each_boats_remaining_capacity():
    boat = RegularBoat((100, 100), fish_capacity=10.0)
    school = FishSchool((100, 100), population=100.0)
    school.claim("op_capacity")

    harvested = school.apply_harvest(
        "op_capacity", active_boat_count=1, delta_time=1.0,
        harvest_limit=boat.remaining_fish_capacity,
    )
    boat.record_harvest(harvested)

    assert boat.fish_catch == 10.0
    assert boat.remaining_fish_capacity == 0.0
    assert school.population == 90.0


def test_moving_boat_can_spawn_alerted_spill_in_open_water():
    assert 0.0 < OIL_SPILL_CHANCE <= 1.0
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    boat = RegularBoat((210, 200))
    sim.add_boat(boat)
    sim.oil_spill_manager.rng = AlwaysSpawnRng()
    previous = {boat.boat_id: pygame.Vector2(200, 200)}

    sim.oil_spill_manager.update(sim, 0.1, previous)

    assert len(sim.oil_spill_manager.spills) == 1
    spill = sim.oil_spill_manager.spills[0]
    sim.oil_spill_manager.spills.remove(spill)
    assert sim.oil_spill_manager.is_open_water(sim, spill.position, spill.radius)
    sim.oil_spill_manager.spills.append(spill)
    assert spill.reported is False
    assert not any(m.msg_type == Message.OIL_SPILL_ALERT
                   for m in sim.comms_hub.get_message_log())
    sim.oil_spill_manager.update(sim, 0.1, {boat.boat_id: boat.position.copy()})
    assert spill.reported is False


def test_next_boat_contact_reports_slowdowns_and_dispatches_cleaner():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    creator = RegularBoat((100, 100))
    discoverer = TowingBoat((200, 200))
    cleaner = CleaningBoat((250, 200))
    for boat in (creator, discoverer, cleaner):
        sim.add_boat(boat)
    spill = OilSpill(1, pygame.Vector2(200, 200), 15.0, created_by=creator.boat_id)
    sim.oil_spill_manager.spills.append(spill)

    sim.oil_spill_manager.update(sim, 0.1, {b.boat_id: b.position.copy() for b in sim.boats})

    assert spill.reported
    assert discoverer.oil_slow_remaining == 10.0
    assert cleaner.state == BoatState.MOVING_TO_SPILL
    assert discoverer.position.distance_to(spill.position) >= spill.radius + 12.0
    assert any(m.msg_type == Message.OIL_SPILL_ALERT
               for m in sim.comms_hub.get_message_log())


def test_spill_spawn_rejects_dock_or_obstacle_clearance():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    boat = RegularBoat((210, 200))
    sim.add_boat(boat)
    sim.obstacles.append(pygame.Rect(120, 160, 60, 80))
    sim.oil_spill_manager.rng = AlwaysSpawnRng()

    sim.oil_spill_manager.update(sim, 0.1, {boat.boat_id: pygame.Vector2(200, 200)})

    assert sim.oil_spill_manager.spills == []


def test_oil_collision_slows_boat_and_dispatches_nearest_cleaner():
    sim = BoatSwarmSimulation(width=600, height=500, margin=20)
    boat = RegularBoat((190, 200))
    nearest_cleaner = CleaningBoat((244, 200))
    farther_cleaner = CleaningBoat((200, 350))
    for member in (boat, nearest_cleaner, farther_cleaner):
        sim.add_boat(member)
    spill = OilSpill(1, pygame.Vector2(200, 200), 34.0)
    spill.distress_sent = True
    spill.distressed_by = boat.boat_id
    sim.oil_spill_manager.spills.append(spill)

    sim.oil_spill_manager.update(sim, 0.1, {b.boat_id: b.position.copy() for b in sim.boats})

    assert boat.oil_speed_multiplier < 1.0
    assert boat.oil_slow_remaining > 0.0
    assert boat.position.distance_to(spill.position) >= spill.radius + 12.0
    assert nearest_cleaner.state == BoatState.MOVING_TO_SPILL
    assert farther_cleaner.state == BoatState.EXPLORING
    distress = [m for m in sim.comms_hub.get_message_log()
                if m.msg_type == Message.OIL_SPILL_DISTRESS]
    assert any(m.target_id == nearest_cleaner.boat_id for m in distress)


def test_priority_states_do_not_run_exploration_or_fishing_movement():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    for boat, state in (
        (CleaningBoat((100, 100)), BoatState.MOVING_TO_SPILL),
        (TowingBoat((200, 100)), BoatState.MOVING_TO_TOW),
        (TowingBoat((300, 100)), BoatState.TOWING),
        (CleaningBoat((400, 100)), BoatState.CLEANING),
    ):
        boat.state = state
        original_position = boat.position.copy()
        boat.update(0.5, sim.world_coordinator)
        assert boat.position == original_position
        assert boat.state == state


def test_non_towing_classes_cannot_enter_tow_states():
    for boat in (RegularBoat((100, 100)), CleaningBoat((200, 100))):
        assert not boat.transition_to(BoatState.MOVING_TO_TOW)
        boat.state = BoatState.MOVING_TO_TOW
        assert not boat.transition_to(BoatState.TOWING)


def test_invalid_raw_tow_state_is_rejected_by_regular_boat_update():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    regular = RegularBoat((250, 200))
    regular.state = BoatState.TOWING

    regular.update(0.1, sim.world_coordinator)

    assert regular.state == BoatState.EXPLORING


def test_cleaning_boat_holds_position_then_clears_spill():
    sim = BoatSwarmSimulation(width=600, height=500, margin=20)
    cleaner = CleaningBoat((200, 200))
    sim.add_boat(cleaner)
    spill = OilSpill(1, pygame.Vector2(200, 200), 34.0)
    sim.oil_spill_manager.spills.append(spill)

    sim.oil_spill_manager.update(sim, 0.1, {cleaner.boat_id: cleaner.position.copy()})
    assert cleaner.state == BoatState.CLEANING
    assert cleaner.position == spill.position
    assert cleaner.target_spill is spill

    for _ in range(39):
        sim.oil_spill_manager.update(sim, 0.1, {cleaner.boat_id: cleaner.position.copy()})
    assert sim.oil_spill_manager.spills
    assert cleaner.state == BoatState.CLEANING
    sim.oil_spill_manager.update(sim, 0.1, {cleaner.boat_id: cleaner.position.copy()})

    assert sim.oil_spill_manager.spills == []
    assert cleaner.state == BoatState.EXPLORING
    assert cleaner.target_spill is None
    assert cleaner.target_position is not None
    assert any(m.msg_type == Message.OIL_SPILL_CLEARED
               for m in sim.comms_hub.get_message_log())


def test_cleaning_boat_does_not_claim_silent_spill_before_discovery():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    cleaner = CleaningBoat((300, 200))
    sim.add_boat(cleaner)
    spill = OilSpill(1, pygame.Vector2(200, 200), 34.0)
    sim.oil_spill_manager.spills.append(spill)

    sim.oil_spill_manager.update(sim, 0.1, {cleaner.boat_id: cleaner.position.copy()})

    assert spill.reported is False
    assert cleaner.state == BoatState.EXPLORING
    assert cleaner.target_spill is None


def test_cleaning_boat_polls_and_claims_reported_spill():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    cleaner = CleaningBoat((300, 200))
    sim.add_boat(cleaner)
    spill = OilSpill(1, pygame.Vector2(200, 200), 34.0, reported=True)
    sim.oil_spill_manager.spills.append(spill)

    sim.oil_spill_manager.poll(sim)

    assert cleaner.state == BoatState.MOVING_TO_SPILL
    assert cleaner.target_spill is spill


def test_only_cleaning_class_can_be_assigned_to_spill_cleanup():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    regular = BoatAgent((100, 100))
    sim.add_boat(regular)
    spill = OilSpill(1, pygame.Vector2(200, 200), 34.0)
    spill.distress_sent = True
    spill.distressed_by = regular.boat_id
    sim.oil_spill_manager.spills.append(spill)

    sim.oil_spill_manager.update(sim, 0.1, {regular.boat_id: regular.position.copy()})

    assert regular.state == BoatState.EXPLORING
    assert sim.oil_spill_manager._cleanups == {}


def test_oil_speed_debuff_expires_after_ten_seconds():
    boat = RegularBoat((100, 100))
    boat.state = BoatState.FISHING
    boat.apply_oil_slow(10.0, 0.55)

    boat.update(9.9, BoatSwarmSimulation(width=500, height=400).world_coordinator)
    assert boat.oil_speed_multiplier == 0.55
    assert boat.oil_slow_remaining > 0.0

    boat.update(0.1, BoatSwarmSimulation(width=500, height=400).world_coordinator)
    assert boat.oil_speed_multiplier == 1.0
    assert boat.oil_slow_remaining == 0.0


def test_movement_tick_spill_roll_can_fail():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    boat = RegularBoat((210, 200))
    sim.add_boat(boat)
    sim.oil_spill_manager.rng = NeverSpawnRng()

    sim.oil_spill_manager.update(sim, 0.1, {boat.boat_id: pygame.Vector2(200, 200)})

    assert sim.oil_spill_manager.spills == []


def test_cargo_capacities_match_spec():
    towing = TowingBoat((100, 100))
    regular = RegularBoat((200, 100))
    cleaning = CleaningBoat((300, 100))

    assert towing.fish_capacity == 100.0
    assert regular.fish_capacity == 70.0
    assert cleaning.fish_capacity == 40.0


def test_is_cargo_full_property():
    boat = RegularBoat((100, 100))
    assert not boat.is_cargo_full
    assert boat.remaining_fish_capacity == 70.0

    boat.fish_catch = 69.0
    assert not boat.is_cargo_full

    boat.fish_catch = 70.0
    assert boat.is_cargo_full
    assert boat.remaining_fish_capacity == 0.0


def test_record_harvest_stops_at_capacity():
    boat = RegularBoat((100, 100), fish_capacity=10.0)
    stored = boat.record_harvest(7.0)
    assert stored == 7.0
    assert boat.fish_catch == 7.0
    assert not boat.is_cargo_full

    stored = boat.record_harvest(5.0)
    assert stored == 3.0
    assert boat.fish_catch == 10.0
    assert boat.is_cargo_full

    # Once full, further harvest returns 0
    stored = boat.record_harvest(10.0)
    assert stored == 0.0
    assert boat.fish_catch == 10.0


def test_unload_cargo_empties_and_restores_capacity():
    boat = TowingBoat((100, 100))
    boat.record_harvest(100.0)
    assert boat.is_cargo_full

    unloaded = boat.unload_cargo()
    assert unloaded == 100.0
    assert boat.fish_catch == 0.0
    assert not boat.is_cargo_full
    assert boat.remaining_fish_capacity == 100.0


def test_full_capacity_boat_excluded_from_fishing_participants():
    sim = BoatSwarmSimulation(width=500, height=400, margin=20)
    boat = RegularBoat((100, 100), fish_capacity=5.0)
    boat.fish_catch = 5.0
    sim.add_boat(boat)

    assert boat.is_cargo_full
    assert boat.remaining_fish_capacity == 0.0


def test_full_cargo_renders_desaturated_hull():
    def render_boat(boat_class, fill_cargo):
        surface = pygame.Surface((120, 100))
        surface.fill((3, 7, 11))
        boat = boat_class((60, 50))
        if fill_cargo:
            boat.fish_catch = boat.fish_capacity
        boat.draw(surface)
        return pygame.image.tobytes(surface, "RGB")

    for boat_class in (TowingBoat, CleaningBoat, RegularBoat):
        normal = render_boat(boat_class, False)
        full = render_boat(boat_class, True)
        assert normal != full, f"{boat_class.__name__} must look different when cargo is full"


def test_unloaded_boat_restores_normal_render():
    surface_a = pygame.Surface((120, 100))
    surface_b = pygame.Surface((120, 100))
    surface_a.fill((3, 7, 11))
    surface_b.fill((3, 7, 11))

    boat_a = RegularBoat((60, 50))
    boat_b = RegularBoat((60, 50))
    boat_b.fish_catch = boat_b.fish_capacity
    boat_b.unload_cargo()

    boat_a.draw(surface_a)
    boat_b.draw(surface_b)

    assert pygame.image.tobytes(surface_a, "RGB") == pygame.image.tobytes(surface_b, "RGB")
