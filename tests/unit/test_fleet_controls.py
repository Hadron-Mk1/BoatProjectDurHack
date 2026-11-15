import pygame

from src.core.simulation import BoatSwarmSimulation
from src.entities.boat_agent import BoatState, BoatType, RegularBoat


def click(point):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": point})


def test_fleet_panel_adds_and_removes_boats_of_each_type_dynamically():
    sim = BoatSwarmSimulation()
    pier = sim.pier_manager
    surface = pygame.Surface((1200, 800))
    assert not pier.fleet_menu_open
    header = pier._fleet_header_rect(surface)
    repair_dock = pier.repair_dock_rect()
    assert header.left == repair_dock.left
    assert header.bottom == repair_dock.top
    pier.handle_event(click(header.center), surface,
                      simulation=sim)
    assert pier.fleet_menu_open
    panel = pier._fleet_panel_rect(surface)
    assert panel.left >= header.right
    assert panel.top > header.bottom
    pier.draw(surface, show_ui=True, simulation=sim)

    for index, boat_type in enumerate(type for type, _ in pier.FLEET_BOAT_TYPES):
        panel = pier._fleet_panel_rect(surface)
        row = pier._fleet_row_rect(panel, index)
        _, plus = pier._fleet_adjust_button_rects(row)
        pier.handle_event(click(plus.center), surface, simulation=sim)
        assert sim.boat_count(boat_type) == 1
        boat = next(member for member in sim.boats if member.boat_type == boat_type)
        assert sim.comms_hub.is_registered(boat.boat_id)

        minus, _ = pier._fleet_adjust_button_rects(row)
        pier.handle_event(click(minus.center), surface, simulation=sim)
        assert sim.boat_count(boat_type) == 0
        assert not sim.comms_hub.is_registered(boat.boat_id)


def test_boat_added_during_whirlpool_joins_the_active_event():
    sim = BoatSwarmSimulation()
    lead = RegularBoat((685, 400))
    sim.add_boat(lead)
    sim.whirlpool_manager.trigger_spawn(sim, center=(600, 400))

    assert sim.adjust_boat_count(BoatType.SONAR, 1)
    added = next(boat for boat in sim.boats if boat.boat_type == BoatType.SONAR)
    assert added.state == BoatState.WHIRLPOOL
    assert added in sim.whirlpool_manager.affected_boats
    assert added.boat_id in sim.whirlpool_manager.boat_orbital_slots


def test_removing_a_boat_during_whirlpool_detaches_its_slot():
    sim = BoatSwarmSimulation()
    boat = RegularBoat((685, 400))
    sim.add_boat(boat)
    sim.whirlpool_manager.trigger_spawn(sim, center=(600, 400))

    assert sim.adjust_boat_count(BoatType.REGULAR, -1)
    assert boat not in sim.boats
    assert boat not in sim.whirlpool_manager.affected_boats
    assert boat.boat_id not in sim.whirlpool_manager.boat_orbital_slots
