"""Shared dispatch simulation primitives.

Common, policy-agnostic helpers used by the baseline (T4) and, later, the
optimized (T5) dispatch policies: travel-time lookup, vehicle/task
compatibility, a mutable per-vehicle simulation state, and a simple
deterministic energy / CO2e proxy model.

All quantities are synthetic prototype proxies, not real measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ecoturn.schemas import GeneratedScenario, Task, Vehicle

# --- Synthetic energy / emissions model constants --------------------------
# These are deliberately simple, deterministic proxies (not physical models).
BATTERY_CAPACITY_KWH: float = 50.0
# Minutes to charge an empty battery to full (linear proxy).
FULL_CHARGE_MINUTES: float = 45.0
# Grid CO2e attributed per unit of EV energy proxy (kept well below the
# diesel emission rate so electrification clearly reduces the CO2e proxy).
EV_GRID_CO2_FACTOR: float = 0.1

EV_POWERTRAINS: frozenset[str] = frozenset({"ev", "autonomous_ev"})


def travel_time(scenario: GeneratedScenario, origin: str, destination: str) -> float:
    """Look up synthetic travel time (minutes) between two zones."""

    if origin == destination:
        return 0.0
    return scenario.travel_times[origin][destination]


def is_compatible(vehicle: Vehicle, task: Task) -> bool:
    """Whether ``vehicle`` may serve ``task``.

    Compatible if the task type is listed in the vehicle's ``compatible_tasks``
    or the vehicle type is listed in the task's ``compatible_vehicle_types``.
    """

    return (
        task.task_type in vehicle.compatible_tasks
        or vehicle.vehicle_type in task.compatible_vehicle_types
    )


def operating_minutes(travel_to: float, travel_origin_dest: float, duration: float) -> float:
    """Total minutes a vehicle is actively engaged for a task."""

    return travel_to + travel_origin_dest + duration


@dataclass
class VehicleState:
    """Mutable simulation state for a single vehicle.

    Tracks when the vehicle next becomes available, where it is, and (for
    electric powertrains) its state of charge. ``soc`` is ``None`` for
    diesel vehicles.
    """

    vehicle: Vehicle
    available_time: float = 0.0
    current_zone: str = ""
    soc: float | None = None

    def __post_init__(self) -> None:
        if not self.current_zone:
            self.current_zone = self.vehicle.current_zone
        self.soc = self.vehicle.soc

    @property
    def is_electric(self) -> bool:
        return self.vehicle.powertrain in EV_POWERTRAINS


def init_vehicle_states(scenario: GeneratedScenario) -> list[VehicleState]:
    """Build initial per-vehicle states from a scenario's fleet."""

    return [VehicleState(vehicle=v) for v in scenario.vehicles]
