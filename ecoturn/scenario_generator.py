"""Synthetic data generation only.

Generates a deterministic synthetic airport ground-operations scenario from
a :class:`~ecoturn.schemas.ScenarioSpec`. Given the same spec and seed the
output is identical.

The default graph is an **ATL-sandbox**: an ATL-inspired synthetic airport
layout (domestic/international terminals, concourses T/A/B/C/D/E/F, cargo
areas, catering, maintenance, and charging hubs) used purely for
storytelling and demo relevance. It is NOT real ATL operational data, real
Delta fleet counts, real flight schedules, real GSE locations, or real
charging infrastructure. All output is synthetic.
"""

from __future__ import annotations

import math
import random

from ecoturn.schemas import (
    Charger,
    GeneratedScenario,
    ScenarioSpec,
    Task,
    Vehicle,
)

# ATL-sandbox zones, ordered roughly west-to-east along the concourse line:
# domestic terminals / T / A / B / C / D / E / F / international terminal,
# followed by cargo, support, charging, restricted, and future zones.
DEFAULT_ZONES: list[str] = [
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

# Approximate 2D layout coordinates (synthetic). The concourse line runs
# west (x=0) to east (x=9.5) so travel times roughly increase with distance
# along the terminal/concourse chain.
ZONE_COORDS: dict[str, tuple[float, float]] = {
    "domestic_terminal_north": (0.0, 0.6),
    "domestic_terminal_south": (0.0, -0.6),
    "concourse_T": (2.0, 0.0),
    "concourse_A": (3.0, 0.0),
    "concourse_B": (4.0, 0.0),
    "concourse_C": (5.0, 0.0),
    "concourse_D": (6.0, 0.0),
    "concourse_E": (7.0, 0.0),
    "concourse_F": (8.0, 0.0),
    "international_terminal": (9.5, 0.0),
    "cargo_north": (4.0, 3.0),
    "cargo_midfield": (5.0, 2.5),
    "cargo_south": (6.0, 3.0),
    "catering_facility": (3.0, -3.0),
    "maintenance_base": (1.0, -3.0),
    "charging_hub_west": (1.5, 1.5),
    "charging_hub_midfield": (5.0, 1.5),
    "charging_hub_east": (8.0, 1.5),
    "restricted_runway_crossing": (5.0, -2.0),
    "future_autonomy_corridor": (10.0, 2.0),
}

CONCOURSE_ZONES: list[str] = [
    "concourse_T",
    "concourse_A",
    "concourse_B",
    "concourse_C",
    "concourse_D",
    "concourse_E",
    "concourse_F",
]
TERMINAL_ZONES: list[str] = [
    "domestic_terminal_north",
    "domestic_terminal_south",
    "international_terminal",
]
CARGO_ZONES: list[str] = ["cargo_north", "cargo_midfield", "cargo_south"]
CHARGING_HUB_ZONES: list[str] = [
    "charging_hub_west",
    "charging_hub_midfield",
    "charging_hub_east",
]
CATERING_ZONE = "catering_facility"
MAINTENANCE_ZONE = "maintenance_base"
RESTRICTED_ZONE = "restricted_runway_crossing"
FUTURE_CORRIDOR_ZONE = "future_autonomy_corridor"

# Passenger-facing zones used by general (baggage/belt/tow) tasks.
PASSENGER_ZONES: list[str] = TERMINAL_ZONES + CONCOURSE_ZONES

VEHICLE_TYPES: list[str] = [
    "baggage_tractor",
    "belt_loader",
    "tow_tractor",
    "catering_truck",
    "cargo_tug",
    "service_van",
]

TASK_TYPES: list[str] = [
    "baggage",
    "belt_load",
    "tow",
    "catering",
    "cargo",
    "maintenance",
]

# Which task types a vehicle type can serve.
VEHICLE_TASK_COMPAT: dict[str, list[str]] = {
    "baggage_tractor": ["baggage"],
    "belt_loader": ["belt_load"],
    "tow_tractor": ["tow"],
    "catering_truck": ["catering"],
    "cargo_tug": ["cargo"],
    "service_van": ["maintenance"],
}

# Inverse mapping: which vehicle types can serve a task type.
TASK_VEHICLE_COMPAT: dict[str, list[str]] = {
    "baggage": ["baggage_tractor"],
    "belt_load": ["belt_loader"],
    "tow": ["tow_tractor"],
    "catering": ["catering_truck"],
    "cargo": ["cargo_tug"],
    "maintenance": ["service_van"],
}

# Default mixed fleet when the spec does not request any vehicles.
DEFAULT_DIESEL_COUNT = 4
DEFAULT_EV_COUNT = 4
DEFAULT_AUTONOMOUS_EV_COUNT = 2

# Travel-time model parameters (synthetic minutes).
_TRAVEL_BASE_MIN = 1.5
_TRAVEL_DISTANCE_SCALE = 1.2


def _is_future_scenario(spec: ScenarioSpec) -> bool:
    """Future-fleet scenarios unlock wireless charging pads."""

    return "future" in spec.scenario_name.lower()


def _build_travel_times(
    zones: list[str], rng: random.Random
) -> dict[str, dict[str, float]]:
    """Symmetric travel-time matrix: 0 on the diagonal, positive elsewhere.

    Off-diagonal times derive from the synthetic 2D layout (so the
    west-to-east concourse ordering is reflected) plus a small seed-driven
    jitter, keeping same-seed determinism and different-seed variation.
    """

    matrix: dict[str, dict[str, float]] = {a: {} for a in zones}
    for i, a in enumerate(zones):
        for b in zones[i:]:
            if a == b:
                matrix[a][b] = 0.0
                continue
            if a in ZONE_COORDS and b in ZONE_COORDS:
                ax, ay = ZONE_COORDS[a]
                bx, by = ZONE_COORDS[b]
                distance = math.hypot(ax - bx, ay - by)
                jitter = rng.uniform(0.0, 1.0)
                minutes = round(
                    _TRAVEL_BASE_MIN
                    + _TRAVEL_DISTANCE_SCALE * distance
                    + jitter,
                    1,
                )
            else:
                minutes = round(rng.uniform(2.0, 15.0), 1)
            matrix[a][b] = minutes
            matrix[b][a] = minutes
    return matrix


def _autonomous_allowed_zones(spec: ScenarioSpec, zones: list[str]) -> list[str]:
    """Allowed zones for autonomous EVs.

    Excludes ``restricted_runway_crossing`` (and any spec-declared restricted
    zones) unless the scenario explicitly lists them as allowed corridors.
    ``future_autonomy_corridor`` is not restricted, so autonomous EVs may use
    it.
    """

    restricted = {RESTRICTED_ZONE} | set(spec.safety_policy.restricted_zones)
    explicitly_allowed = set(spec.safety_policy.autonomous_allowed_zones)
    return [z for z in zones if z not in restricted or z in explicitly_allowed]


def _build_vehicles(
    spec: ScenarioSpec, zones: list[str], rng: random.Random
) -> list[Vehicle]:
    diesel = spec.fleet.diesel_count
    ev = spec.fleet.ev_count
    autonomous = spec.fleet.autonomous_ev_count
    if diesel + ev + autonomous == 0:
        diesel, ev, autonomous = (
            DEFAULT_DIESEL_COUNT,
            DEFAULT_EV_COUNT,
            DEFAULT_AUTONOMOUS_EV_COUNT,
        )

    powertrains = (["diesel"] * diesel) + (["ev"] * ev) + (["autonomous_ev"] * autonomous)
    auto_zones = _autonomous_allowed_zones(spec, zones)
    non_restricted = [z for z in zones if z != RESTRICTED_ZONE]

    vehicles: list[Vehicle] = []
    for idx, powertrain in enumerate(powertrains):
        vehicle_type = VEHICLE_TYPES[idx % len(VEHICLE_TYPES)]
        compatible_tasks = list(VEHICLE_TASK_COMPAT[vehicle_type])

        if powertrain == "diesel":
            soc: float | None = None
            allowed_zones = list(zones)
            current_zone = rng.choice(non_restricted)
            emission_rate = round(rng.uniform(2.0, 3.2), 3)
            energy_rate = 0.0
        elif powertrain == "ev":
            soc = round(rng.uniform(0.35, 1.0), 3)
            allowed_zones = list(zones)
            current_zone = rng.choice(non_restricted)
            emission_rate = 0.0
            energy_rate = round(rng.uniform(0.8, 1.5), 3)
        else:  # autonomous_ev
            soc = round(rng.uniform(0.35, 1.0), 3)
            allowed_zones = list(auto_zones)
            current_zone = rng.choice(auto_zones)
            emission_rate = 0.0
            energy_rate = round(rng.uniform(0.8, 1.5), 3)

        vehicles.append(
            Vehicle(
                vehicle_id=f"V{idx + 1:02d}",
                vehicle_type=vehicle_type,
                powertrain=powertrain,
                soc=soc,
                current_zone=current_zone,
                compatible_tasks=compatible_tasks,
                allowed_zones=allowed_zones,
                speed_mph=round(rng.uniform(10.0, 18.0), 1),
                emission_rate=emission_rate,
                energy_rate=energy_rate,
            )
        )
    return vehicles


def _pick_task_zones(task_type: str, rng: random.Random) -> tuple[str, str]:
    """Choose ATL-sandbox origin/destination zones for a task type."""

    if task_type == "catering":
        origin = CATERING_ZONE
        destination = rng.choice(CONCOURSE_ZONES)
    elif task_type == "cargo":
        origin = rng.choice(CARGO_ZONES)
        destination = rng.choice(PASSENGER_ZONES)
    elif task_type == "maintenance":
        origin = MAINTENANCE_ZONE
        destination = rng.choice(PASSENGER_ZONES)
    else:  # baggage, belt_load, tow
        origin = rng.choice(PASSENGER_ZONES)
        destination = rng.choice([z for z in PASSENGER_ZONES if z != origin])
    return origin, destination


def _build_tasks(
    spec: ScenarioSpec, rng: random.Random, n_tasks: int
) -> list[Task]:
    horizon = spec.planning_horizon_min
    tasks: list[Task] = []
    for idx in range(n_tasks):
        task_type = TASK_TYPES[idx % len(TASK_TYPES)]
        origin_zone, destination_zone = _pick_task_zones(task_type, rng)
        freshness_decay_rate = (
            round(rng.uniform(0.02, 0.10), 3) if task_type == "catering" else 0.0
        )

        release_time_min = round(rng.uniform(0.0, max(1.0, horizon * 0.6)), 1)
        duration_min = round(rng.uniform(5.0, 20.0), 1)
        slack = round(rng.uniform(10.0, 40.0), 1)
        deadline_min = round(release_time_min + duration_min + slack, 1)

        is_critical = task_type in {"tow", "catering"} and rng.random() < 0.5

        tasks.append(
            Task(
                task_id=f"T{idx + 1:02d}",
                task_type=task_type,
                release_time_min=release_time_min,
                deadline_min=deadline_min,
                duration_min=duration_min,
                origin_zone=origin_zone,
                destination_zone=destination_zone,
                compatible_vehicle_types=list(TASK_VEHICLE_COMPAT[task_type]),
                priority=rng.choice([1, 2, 3]),
                freshness_decay_rate=freshness_decay_rate,
                is_critical=is_critical,
            )
        )
    return tasks


def _build_chargers(spec: ScenarioSpec, rng: random.Random) -> list[Charger]:
    # Chargers are distributed across the three ATL-sandbox charging hubs.
    chargers: list[Charger] = [
        Charger(
            charger_id="CH_DC_MID",
            charger_type="dc_fast",
            zone="charging_hub_midfield",
            power_kw=150.0,
            capacity=2,
        ),
        Charger(
            charger_id="CH_AC_WEST",
            charger_type="ac",
            zone="charging_hub_west",
            power_kw=22.0,
            capacity=4,
        ),
        Charger(
            charger_id="CH_OPP_EAST",
            charger_type="opportunity",
            zone="charging_hub_east",
            power_kw=50.0,
            capacity=1,
        ),
        Charger(
            charger_id="CH_OPP_MID",
            charger_type="opportunity",
            zone="charging_hub_midfield",
            power_kw=50.0,
            capacity=1,
        ),
    ]
    if _is_future_scenario(spec):
        chargers.append(
            Charger(
                charger_id="CH_WL_CORRIDOR",
                charger_type="wireless_future",
                zone=FUTURE_CORRIDOR_ZONE,
                power_kw=round(rng.uniform(60.0, 120.0), 1),
                capacity=1,
            )
        )
    return chargers


def generate_scenario(spec: ScenarioSpec, seed: int = 42) -> GeneratedScenario:
    """Generate a deterministic synthetic ATL-sandbox scenario from ``spec``.

    The same ``spec`` and ``seed`` always produce identical output. All
    returned data is synthetic sandbox data.
    """

    rng = random.Random(seed)
    zones = list(DEFAULT_ZONES)

    travel_times = _build_travel_times(zones, rng)
    vehicles = _build_vehicles(spec, zones, rng)

    n_tasks = max(len(TASK_TYPES) * 2, int(spec.planning_horizon_min // 10))
    tasks = _build_tasks(spec, rng, n_tasks)
    chargers = _build_chargers(spec, rng)

    return GeneratedScenario(
        spec=spec,
        zones=zones,
        travel_times=travel_times,
        vehicles=vehicles,
        tasks=tasks,
        chargers=chargers,
        synthetic=True,
    )


def default_scenario_spec(
    scenario_name: str = "atl_sandbox_default",
) -> ScenarioSpec:
    """Convenience synthetic spec for demos and tests."""

    return ScenarioSpec(scenario_name=scenario_name)
