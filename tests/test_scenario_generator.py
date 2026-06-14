"""T3 — scenario generator tests.

Verify deterministic synthetic scenario generation: reproducibility,
schema validity of generated objects, zone/charger referential integrity,
the travel-time matrix, EV SOC ranges, and default-scenario content.
"""

from __future__ import annotations

from ecoturn.scenario_generator import (
    CARGO_ZONES,
    CHARGING_HUB_ZONES,
    DEFAULT_ZONES,
    RESTRICTED_ZONE,
    default_scenario_spec,
    generate_scenario,
)
from ecoturn.schemas import Charger, ScenarioSpec, Task, Vehicle

REQUIRED_ATL_ZONES = [
    "domestic_terminal_north",
    "domestic_terminal_south",
    "concourse_T",
    "concourse_A",
    "concourse_B",
    "concourse_C",
    "concourse_D",
    "concourse_E",
    "concourse_F",
    "international_terminal",
    "cargo_north",
    "cargo_midfield",
    "cargo_south",
    "catering_facility",
    "maintenance_base",
    "charging_hub_west",
    "charging_hub_midfield",
    "charging_hub_east",
    "restricted_runway_crossing",
    "future_autonomy_corridor",
]


def _default_scenario():
    return generate_scenario(default_scenario_spec(), seed=42)


def test_same_seed_identical_scenario() -> None:
    spec = default_scenario_spec()
    a = generate_scenario(spec, seed=42)
    b = generate_scenario(spec, seed=42)
    assert a.model_dump() == b.model_dump()


def test_different_seed_changes_some_data() -> None:
    spec = default_scenario_spec()
    a = generate_scenario(spec, seed=42)
    b = generate_scenario(spec, seed=7)
    assert a.model_dump() != b.model_dump()


def test_generated_vehicles_validate_against_schema() -> None:
    scenario = _default_scenario()
    assert scenario.vehicles
    for vehicle in scenario.vehicles:
        assert isinstance(vehicle, Vehicle)
        Vehicle.model_validate(vehicle.model_dump())


def test_generated_tasks_validate_against_schema() -> None:
    scenario = _default_scenario()
    assert scenario.tasks
    for task in scenario.tasks:
        assert isinstance(task, Task)
        Task.model_validate(task.model_dump())


def test_generated_chargers_validate_against_schema() -> None:
    scenario = _default_scenario()
    assert scenario.chargers
    for charger in scenario.chargers:
        assert isinstance(charger, Charger)
        Charger.model_validate(charger.model_dump())


def test_task_zones_exist() -> None:
    scenario = _default_scenario()
    zones = set(scenario.zones)
    for task in scenario.tasks:
        assert task.origin_zone in zones
        assert task.destination_zone in zones


def test_charger_zones_exist() -> None:
    scenario = _default_scenario()
    zones = set(scenario.zones)
    for charger in scenario.chargers:
        assert charger.zone in zones


def test_travel_time_matrix_covers_every_pair() -> None:
    scenario = _default_scenario()
    zones = scenario.zones
    for a in zones:
        assert a in scenario.travel_times
        for b in zones:
            assert b in scenario.travel_times[a]
            if a == b:
                assert scenario.travel_times[a][b] == 0.0
            else:
                assert scenario.travel_times[a][b] > 0.0


def test_travel_times_symmetric() -> None:
    scenario = _default_scenario()
    zones = scenario.zones
    for a in zones:
        for b in zones:
            assert scenario.travel_times[a][b] == scenario.travel_times[b][a]


def test_ev_soc_within_range() -> None:
    scenario = _default_scenario()
    for vehicle in scenario.vehicles:
        if vehicle.powertrain in ("ev", "autonomous_ev"):
            assert vehicle.soc is not None
            assert 0.0 <= vehicle.soc <= 1.0
        elif vehicle.powertrain == "diesel":
            assert vehicle.soc is None


def test_vehicle_compatible_tasks_match_generated_task_types() -> None:
    scenario = _default_scenario()
    generated_task_types = {task.task_type for task in scenario.tasks}
    for vehicle in scenario.vehicles:
        assert vehicle.compatible_tasks
        assert generated_task_types.intersection(vehicle.compatible_tasks)


def test_autonomous_vehicles_exclude_restricted_runway_crossing_by_default() -> None:
    scenario = _default_scenario()
    autos = [v for v in scenario.vehicles if v.powertrain == "autonomous_ev"]
    assert autos
    for vehicle in autos:
        assert RESTRICTED_ZONE not in vehicle.allowed_zones
        assert vehicle.current_zone != RESTRICTED_ZONE


def test_autonomous_may_include_future_autonomy_corridor() -> None:
    scenario = _default_scenario()
    autos = [v for v in scenario.vehicles if v.powertrain == "autonomous_ev"]
    assert autos
    assert all("future_autonomy_corridor" in v.allowed_zones for v in autos)


def test_autonomous_allowed_when_explicitly_permitted() -> None:
    spec = ScenarioSpec(scenario_name="airside_pilot")
    spec.fleet.autonomous_ev_count = 2
    spec.safety_policy.autonomous_allowed_zones = [RESTRICTED_ZONE]
    scenario = generate_scenario(spec, seed=42)
    autos = [v for v in scenario.vehicles if v.powertrain == "autonomous_ev"]
    assert autos
    assert any(RESTRICTED_ZONE in v.allowed_zones for v in autos)


def test_default_scenario_has_catering_task() -> None:
    scenario = _default_scenario()
    perishable = [
        t
        for t in scenario.tasks
        if t.task_type == "catering" or t.freshness_decay_rate > 0.0
    ]
    assert perishable


def test_default_scenario_has_ev_vehicle() -> None:
    scenario = _default_scenario()
    assert any(v.powertrain == "ev" for v in scenario.vehicles)


def test_wireless_future_only_for_future_scenarios() -> None:
    default_scenario = _default_scenario()
    assert all(
        c.charger_type != "wireless_future" for c in default_scenario.chargers
    )

    future = generate_scenario(
        ScenarioSpec(scenario_name="future_fleet_2040"), seed=42
    )
    assert any(c.charger_type == "wireless_future" for c in future.chargers)


def test_zone_set_matches_default() -> None:
    scenario = _default_scenario()
    assert scenario.zones == DEFAULT_ZONES


def test_default_scenario_includes_all_atl_sandbox_zones() -> None:
    scenario = _default_scenario()
    zones = set(scenario.zones)
    missing = [z for z in REQUIRED_ATL_ZONES if z not in zones]
    assert not missing, f"missing ATL-sandbox zones: {missing}"


def test_catering_tasks_originate_from_catering_facility() -> None:
    scenario = _default_scenario()
    catering = [t for t in scenario.tasks if t.task_type == "catering"]
    assert catering
    for task in catering:
        assert task.origin_zone == "catering_facility"


def test_cargo_tasks_involve_a_cargo_zone() -> None:
    scenario = _default_scenario()
    cargo = [t for t in scenario.tasks if t.task_type == "cargo"]
    assert cargo
    cargo_zone_set = set(CARGO_ZONES)
    for task in cargo:
        assert cargo_zone_set.intersection({task.origin_zone, task.destination_zone})


def test_maintenance_tasks_involve_maintenance_base() -> None:
    scenario = _default_scenario()
    maintenance = [t for t in scenario.tasks if t.task_type == "maintenance"]
    assert maintenance
    for task in maintenance:
        assert "maintenance_base" in {task.origin_zone, task.destination_zone}


def test_charger_zones_are_charging_hubs() -> None:
    scenario = _default_scenario()
    hub_zones = set(CHARGING_HUB_ZONES)
    for charger in scenario.chargers:
        assert charger.zone in hub_zones


def test_travel_time_matrix_covers_every_atl_zone_pair() -> None:
    scenario = _default_scenario()
    for a in REQUIRED_ATL_ZONES:
        assert a in scenario.travel_times
        for b in REQUIRED_ATL_ZONES:
            assert b in scenario.travel_times[a]
            if a == b:
                assert scenario.travel_times[a][b] == 0.0
            else:
                assert scenario.travel_times[a][b] > 0.0
