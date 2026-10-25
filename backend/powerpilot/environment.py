"""Shared exogenous world: load-shedding, demand, weather, faults and theft.

Both network twins read from the same stream so that any difference in
outcomes comes from operating policy alone.
"""

import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .config import SIM_START_HOUR, STEP_HOURS, STEPS_PER_DAY, STEPS_PER_HOUR
from .sites import Site

ZONE_BLOCK_STARTS = {"A": (4, 16), "B": (6, 18), "C": (8, 20), "D": (10, 22)}

_HOURLY_DEMAND = (
    0.15, 0.10, 0.08, 0.08, 0.10, 0.20, 0.40, 0.60, 0.75, 0.75, 0.70, 0.70,
    0.72, 0.70, 0.68, 0.68, 0.72, 0.82, 0.92, 0.95, 0.90, 0.75, 0.50, 0.30,
)
_AREA_DEMAND = {"urban": 1.0, "peri": 0.85, "rural": 0.7}

THEFT_STEPS = 8
FUEL_SIPHON_L_PER_STEP = 30.0
BATTERY_REMOVAL_SHARE_PER_STEP = 0.125


def hour_of_day(step: int) -> float:
    return (SIM_START_HOUR + step * STEP_HOURS) % 24


def demand_profile(area: str, hour: float) -> float:
    lower = int(hour) % 24
    upper = (lower + 1) % 24
    frac = hour - int(hour)
    value = _HOURLY_DEMAND[lower] * (1 - frac) + _HOURLY_DEMAND[upper] * frac
    return value * _AREA_DEMAND[area]


def solar_factor(hour: float) -> float:
    if hour <= 6 or hour >= 18:
        return 0.0
    return math.sin(math.pi * (hour - 6) / 12)


@lru_cache(maxsize=64)
def zone_schedule(zone: str, stage: int) -> tuple[bool, ...]:
    length = stage * 2
    day = []
    for slot in range(STEPS_PER_DAY):
        hour = hour_of_day(slot)
        off = stage > 0 and any((hour - start) % 24 < length for start in ZONE_BLOCK_STARTS[zone])
        day.append(not off)
    return tuple(day)


def grid_scheduled_on(zone: str, step: int, stage: int) -> bool:
    return zone_schedule(zone, stage)[step % STEPS_PER_DAY]


def steps_until_scheduled_on(zone: str, step: int, stage: int, limit: int = STEPS_PER_DAY) -> int | None:
    for ahead in range(limit + 1):
        if grid_scheduled_on(zone, step + ahead, stage):
            return ahead
    return None


def scheduled_off_hours_per_day(stage: int) -> float:
    return min(24.0, stage * 4.0)


@dataclass(frozen=True)
class Theft:
    id: str
    site_index: int
    kind: str
    start: int

    def active(self, step: int) -> bool:
        return self.start <= step < self.start + THEFT_STEPS


@dataclass(frozen=True)
class Outage:
    id: str
    site_index: int
    kind: str
    start: int
    end: int | None


@dataclass
class DayBlock:
    traffic_noise: np.ndarray
    cloud: np.ndarray
    grid_faults: list[Outage] = field(default_factory=list)
    link_faults: list[Outage] = field(default_factory=list)
    thefts: list[Theft] = field(default_factory=list)
    false_alarms: set[tuple[int, int]] = field(default_factory=set)


class World:
    def __init__(self, sites: tuple[Site, ...], seed: int, stage: int):
        self.sites = sites
        self.seed = seed
        self.stage = stage
        self._days: dict[int, DayBlock] = {}
        self._injected_thefts: list[Theft] = []
        self._injected_links: list[Outage] = []
        self._injected_grid: list[Outage] = []
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:04d}"

    def _day(self, day: int) -> DayBlock:
        if day not in self._days:
            self._days[day] = self._generate_day(day)
        return self._days[day]

    def _generate_day(self, day: int) -> DayBlock:
        rng = np.random.default_rng([self.seed, day])
        n = len(self.sites)
        weather = rng.uniform(0.55, 1.0, size=(n, 1))
        block = DayBlock(
            traffic_noise=rng.normal(0.0, 0.05, size=(n, STEPS_PER_DAY)),
            cloud=np.clip(weather + rng.normal(0, 0.08, size=(n, STEPS_PER_DAY)), 0.2, 1.0),
        )
        base = day * STEPS_PER_DAY
        for i, site in enumerate(self.sites):
            rural = site.area == "rural"
            if site.has_grid and rng.random() < (0.08 if rural else 0.03):
                start = base + int(rng.integers(0, STEPS_PER_DAY))
                length = int(rng.integers(1 * STEPS_PER_HOUR, 6 * STEPS_PER_HOUR))
                block.grid_faults.append(Outage(f"GF-{day}-{i}", i, "grid_fault", start, start + length))
            if rng.random() < 0.01:
                start = base + int(rng.integers(0, STEPS_PER_DAY))
                block.link_faults.append(Outage(f"LF-{day}-{i}", i, "link_fault", start, None))
            theft_rate = 0.008 if site.area == "urban" else (0.015 if site.guarded else 0.05)
            if rng.random() < theft_rate:
                night_hour = float(rng.uniform(22, 28)) % 24
                offset = int(((night_hour - SIM_START_HOUR) % 24) * STEPS_PER_HOUR)
                kind = "fuel" if site.has_generator and rng.random() < 0.4 else "battery"
                block.thefts.append(Theft(f"TH-{day}-{i}", i, kind, base + offset))
            if rng.random() < 0.15:
                block.false_alarms.add((i, base + int(rng.integers(0, STEPS_PER_DAY))))
        return block

    def ensure(self, step: int) -> None:
        self._day(step // STEPS_PER_DAY)
        self._day(step // STEPS_PER_DAY + 1)

    def traffic(self, index: int, step: int) -> float:
        block = self._day(step // STEPS_PER_DAY)
        noise = block.traffic_noise[index, step % STEPS_PER_DAY]
        value = demand_profile(self.sites[index].area, hour_of_day(step)) + noise
        return float(min(1.0, max(0.02, value)))

    def solar_kw(self, index: int, step: int) -> float:
        block = self._day(step // STEPS_PER_DAY)
        cloud = block.cloud[index, step % STEPS_PER_DAY]
        return self.sites[index].solar_kw * solar_factor(hour_of_day(step)) * float(cloud)

    def _all(self, attr: str, step: int) -> list:
        day = step // STEPS_PER_DAY
        items = []
        for d in (day - 1, day):
            if d >= 0:
                items.extend(getattr(self._day(d), attr))
        return items

    def grid_fault_active(self, index: int, step: int) -> bool:
        faults = self._all("grid_faults", step) + self._injected_grid
        return any(f.site_index == index and f.start <= step < (f.end or step + 1) for f in faults)

    def scheduled_on(self, index: int, step: int) -> bool:
        return grid_scheduled_on(self.sites[index].zone, step, self.stage)

    def grid_on(self, index: int, step: int) -> bool:
        site = self.sites[index]
        if not site.has_grid:
            return False
        return self.scheduled_on(index, step) and not self.grid_fault_active(index, step)

    def link_faults_started(self, step: int) -> list[Outage]:
        faults = self._all("link_faults", step) + self._injected_links
        return [f for f in faults if f.start == step]

    def thefts_at(self, step: int) -> list[Theft]:
        thefts = self._all("thefts", step) + self._injected_thefts
        return [t for t in thefts if t.active(step)]

    def false_alarm(self, index: int, step: int) -> bool:
        return (index, step) in self._day(step // STEPS_PER_DAY).false_alarms

    def inject_theft(self, index: int, kind: str, step: int) -> Theft:
        theft = Theft(self._next_id("TH-X"), index, kind, step)
        self._injected_thefts.append(theft)
        return theft

    def inject_link_fault(self, index: int, step: int) -> Outage:
        fault = Outage(self._next_id("LF-X"), index, "link_fault", step, None)
        self._injected_links.append(fault)
        return fault

    def inject_grid_fault(self, index: int, step: int, hours: float) -> Outage:
        fault = Outage(self._next_id("GF-X"), index, "grid_fault", step, step + int(hours * STEPS_PER_HOUR))
        self._injected_grid.append(fault)
        return fault
