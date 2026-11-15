import pytest

from src.core.simulation import FishSwarmSimulation
from src.core.pier_manager import FishingMission
from src.entities.boat_agent import BoatState, CleaningBoat, RegularBoat, TowingBoat


@pytest.mark.parametrize(
    ("boat_class", "expected_amount"),
    [
        (CleaningBoat, 25.0),
        (RegularBoat, 60.0),
        (TowingBoat, 95.0),
    ],
)
def test_docked_boat_gets_largest_mission_within_its_capacity(boat_class, expected_amount):
    sim = FishSwarmSimulation()
    boat = boat_class((100, 100))
    sim.add_boat(boat)
    boat.mission = None
    boat.state = BoatState.DUMPING

    pier = sim.pier_manager
    pier.dock_slots[boat.boat_id] = 0
    boat.position = pier.approach_position_for(boat.boat_id)
    pier.missions = [
        FishingMission((235, 65, 65), 25.0, "SMALL"),
        FishingMission((65, 145, 255), 60.0, "MEDIUM"),
        FishingMission((255, 215, 50), 95.0, "LARGE"),
    ]
    pier.mission_cooldowns = [0.0, 0.0, 0.0]

    pier.process_arrivals(sim)

    assert boat.mission is not None
    assert boat.mission.amount == expected_amount
    assert boat.mission.amount <= boat.fish_capacity


def test_docked_boat_chooses_best_ready_mission_under_capacity():
    sim = FishSwarmSimulation()
    boat = RegularBoat((100, 100))
    sim.add_boat(boat)
    boat.mission = None
    boat.state = BoatState.DUMPING

    pier = sim.pier_manager
    pier.dock_slots[boat.boat_id] = 0
    boat.position = pier.approach_position_for(boat.boat_id)
    pier.missions = [
        FishingMission((235, 65, 65), 25.0, "SMALL"),
        FishingMission((65, 145, 255), 60.0, "MEDIUM"),
        FishingMission((255, 215, 50), 95.0, "LARGE"),
    ]
    pier.mission_cooldowns = [0.0, 10.0, 0.0]

    pier.process_arrivals(sim)

    assert boat.mission is not None
    assert boat.mission.amount == 25.0
