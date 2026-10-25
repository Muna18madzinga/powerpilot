"""A running copy of the Midlands network under one operating policy."""

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .config import STEP_HOURS, STEPS_PER_HOUR, Settings
from .environment import (
    BATTERY_REMOVAL_SHARE_PER_STEP,
    FUEL_SIPHON_L_PER_STEP,
    World,
    steps_until_scheduled_on,
)
from .power import PowerInput, site_load_kw, step_power
from .sites import DEPOTS, Depot, Site, nearest_depot

HISTORY_STEPS = 48 * STEPS_PER_HOUR

SOC_SENSOR_SD = 0.05
FUEL_SENSOR_SD_L = 1.5
BATTERY_SENSOR_SD_KWH = 0.08

JOB_DONE_LABELS = {
    "refuel": "Generator refuelled",
    "replace_battery": "Battery bank replaced",
    "repair_link": "Transmission link restored",
    "security": "Security on site",
    "mobile_genset": "Mobile generator connected",
}

BASELINE = "baseline"
POWERPILOT = "powerpilot"


@dataclass
class SiteState:
    soc: float
    fuel_l: float
    battery_kwh: float
    gen_kva: float
    tank_l: float
    status: str = "up"
    gen_on: bool = False
    sleeping: bool = False
    sleep_enabled: bool = False
    smart_genset: bool = False
    grid_on: bool = True
    traffic: float = 0.0
    load_kw: float = 0.0
    solar_kw: float = 0.0
    door_alarm: bool = False
    fuel_drop_l: float = 0.0
    battery_drop_kwh: float = 0.0
    fuel_burned_last_l: float = 0.0
    link_fault_id: str | None = None
    down_since: int | None = None
    mobile_gen_until: int | None = None
    health: float = 1.0
    soc_reading: float = 0.0
    fuel_reading: float = 0.0
    battery_reading: float = 0.0
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY_STEPS))

    @property
    def is_down(self) -> bool:
        return self.status != "up"


@dataclass
class Metrics:
    diesel_burned_l: float = 0.0
    diesel_stolen_l: float = 0.0
    battery_stolen_kwh: float = 0.0
    outage_site_hours: float = 0.0
    subscriber_hours_lost: float = 0.0
    revenue_lost_usd: float = 0.0
    generator_hours: float = 0.0
    grid_kwh: float = 0.0
    sleep_kwh_saved: float = 0.0
    trips: int = 0
    trip_km: float = 0.0
    batteries_replaced_kwh: float = 0.0


@dataclass(frozen=True)
class DispatchPlan:
    depot: Depot
    road_km: float
    crew: int | None
    depart: int
    arrive: int
    done: int
    responder: str


@dataclass
class Job:
    id: str
    site_index: int
    kind: str
    depot_id: str
    created: int
    depart: int
    arrive: int
    done: int
    km: float
    reason: str
    ref: str | None = None
    completed: bool = False


class Network:
    def __init__(self, name: str, policy: str, sites: tuple[Site, ...], world: World, settings: Settings):
        self.name = name
        self.policy = policy
        self.sites = sites
        self.world = world
        self.settings = settings
        self.metrics = Metrics()
        self.jobs: list[Job] = []
        self.stopped_thefts: set[str] = set()
        self.crew_free_at = {d.id: [0] * d.crews for d in DEPOTS}
        self.events: list[dict] = []
        self._job_counter = 0
        self._sensor_rng = np.random.default_rng([world.seed, 17])
        health = np.random.default_rng([world.seed, 23]).uniform(0.6, 1.0, size=len(sites))
        self.states = [
            SiteState(
                soc=0.85,
                fuel_l=s.tank_l * 0.6,
                battery_kwh=s.battery_kwh,
                gen_kva=s.gen_kva,
                tank_l=s.tank_l,
                sleep_enabled=policy == POWERPILOT,
                smart_genset=policy == POWERPILOT,
                health=float(h),
            )
            for s, h in zip(sites, health, strict=False)
        ]

    def open_jobs(self, site_index: int, kind: str | None = None) -> list[Job]:
        return [j for j in self.jobs if not j.completed and j.site_index == site_index and (kind is None or j.kind == kind)]

    def plan_dispatch(self, site_index: int, kind: str, step: int,
                      delay_hours: float = 0.0, extra_work_hours: float = 0.0) -> DispatchPlan:
        site = self.sites[site_index]
        ops = self.settings.field_ops
        depot, km = nearest_depot(site)
        road_km = km * ops.road_factor
        start = step + math.ceil(delay_hours * STEPS_PER_HOUR)

        if kind == "security":
            hours = ops.guard_response_hours if site.guarded else road_km / ops.security_speed_kmh
            arrive = start + max(1, math.ceil(hours * STEPS_PER_HOUR))
            responder = "on-site guard" if site.guarded else "security patrol"
            return DispatchPlan(depot, road_km, None, start, arrive, arrive, responder)

        travel = max(1, math.ceil(road_km / ops.crew_speed_kmh * STEPS_PER_HOUR))
        work = math.ceil((ops.work_hours.get(kind, 1.0) + extra_work_hours) * STEPS_PER_HOUR)
        crews = self.crew_free_at[depot.id]
        crew = min(range(len(crews)), key=lambda c: crews[c])
        depart = max(start, crews[crew])
        arrive = depart + travel
        busy = sum(1 for free_at in crews if free_at > step)
        crew_note = f"{len(crews) - busy} of {len(crews)} crews free" if busy < len(crews) else "all crews busy, it queues"
        return DispatchPlan(depot, road_km, crew, depart, arrive, arrive + work, crew_note)

    def dispatch(self, site_index: int, kind: str, step: int, reason: str,
                 ref: str | None = None, delay_hours: float = 0.0, extra_work_hours: float = 0.0) -> Job:
        plan = self.plan_dispatch(site_index, kind, step, delay_hours, extra_work_hours)
        self._job_counter += 1
        job_id = f"{self.name[:2].upper()}-J{self._job_counter:04d}"
        km = 0.0
        if plan.crew is not None:
            travel = plan.arrive - plan.depart
            self.crew_free_at[plan.depot.id][plan.crew] = plan.done + travel
            km = plan.road_km * 2
            self.metrics.trips += 1
            self.metrics.trip_km += km
        job = Job(job_id, site_index, kind, plan.depot.id, step, plan.depart, plan.arrive, plan.done, km, reason, ref)
        self.jobs.append(job)
        return job

    def _complete_jobs(self, step: int) -> None:
        for job in self.jobs:
            if job.completed or job.done > step:
                continue
            state = self.states[job.site_index]
            site = self.sites[job.site_index]
            if job.kind == "refuel":
                state.fuel_l = state.tank_l
            elif job.kind == "replace_battery":
                self.metrics.batteries_replaced_kwh += site.battery_kwh - state.battery_kwh
                state.battery_kwh = site.battery_kwh
                state.health = 1.0
                state.soc = max(state.soc, 0.5)
            elif job.kind == "repair_link":
                state.link_fault_id = None
            elif job.kind == "security":
                self.stopped_thefts.update(
                    t.id for t in self.world.thefts_at(step) if t.site_index == job.site_index
                )
                if job.ref:
                    self.stopped_thefts.add(job.ref)
            elif job.kind == "mobile_genset":
                state.gen_kva = max(state.gen_kva, 8.0)
                state.tank_l = max(state.tank_l, 120.0)
                state.fuel_l = max(state.fuel_l, 120.0)
                state.mobile_gen_until = step + 24 * STEPS_PER_HOUR
            job.completed = True
            self._emit(step, "job_done", job.site_index, f"{JOB_DONE_LABELS[job.kind]} at {site.name}", job=job.id)

    def _emit(self, step: int, kind: str, site_index: int, message: str, **extra) -> None:
        self.events.append({"step": step, "kind": kind, "site_id": self.sites[site_index].id, "message": message, **extra})

    def _apply_thefts(self, step: int) -> None:
        for theft in self.world.thefts_at(step):
            if theft.id in self.stopped_thefts:
                continue
            state = self.states[theft.site_index]
            site = self.sites[theft.site_index]
            state.door_alarm = True
            if theft.kind == "fuel":
                taken = min(state.fuel_l, FUEL_SIPHON_L_PER_STEP)
                state.fuel_l -= taken
                state.fuel_drop_l += taken
                self.metrics.diesel_stolen_l += taken
            elif step > theft.start:
                taken = min(state.battery_kwh, site.battery_kwh * BATTERY_REMOVAL_SHARE_PER_STEP)
                state.battery_kwh -= taken
                state.battery_drop_kwh += taken
                self.metrics.battery_stolen_kwh += taken

    def step(self, step: int) -> None:
        self.events = []
        world = self.world
        rules = self.settings.power
        sleep_rules = self.settings.sleep
        for state in self.states:
            state.door_alarm = False
            state.fuel_drop_l = 0.0
            state.battery_drop_kwh = 0.0

        self._complete_jobs(step)
        self._apply_thefts(step)
        for fault in world.link_faults_started(step):
            state = self.states[fault.site_index]
            if state.link_fault_id is None:
                state.link_fault_id = fault.id

        for i, (site, state) in enumerate(zip(self.sites, self.states, strict=False)):
            if world.false_alarm(i, step):
                state.door_alarm = True
            if state.mobile_gen_until is not None and step >= state.mobile_gen_until:
                state.gen_kva, state.tank_l, state.mobile_gen_until = site.gen_kva, site.tank_l, None
                state.fuel_l = min(state.fuel_l, state.tank_l)

            traffic = world.traffic(i, step)
            if state.sleep_enabled and len(site.layers) > 1:
                if state.sleeping and traffic > sleep_rules.wake_above_traffic:
                    state.sleeping = False
                elif not state.sleeping and traffic < sleep_rules.sleep_below_traffic:
                    state.sleeping = True
            elif state.sleeping:
                state.sleeping = False

            grid_on = world.grid_on(i, step)
            hours_to_grid = None
            if site.has_grid:
                ahead = steps_to_grid(world, i, step)
                hours_to_grid = None if ahead is None else ahead * STEP_HOURS

            state.traffic = traffic
            state.grid_on = grid_on
            state.solar_kw = world.solar_kw(i, step)
            state.load_kw = site_load_kw(site.idle_kw, site.traffic_kw, site.sleepable_kw, traffic, state.sleeping, sleep_rules)
            was_power_dark = state.status == "dark"
            result = step_power(
                PowerInput(
                    battery_kwh=state.battery_kwh * state.health,
                    soc=state.soc,
                    fuel_l=state.fuel_l,
                    gen_kva=state.gen_kva,
                    gen_on=state.gen_on,
                    smart=state.smart_genset,
                    grid_on=grid_on,
                    solar_kw=state.solar_kw,
                    load_kw=state.load_kw,
                    hours_to_grid=hours_to_grid,
                    dark=was_power_dark,
                ),
                rules,
                STEP_HOURS,
            )
            state.soc = result.soc
            state.gen_on = result.gen_on
            state.fuel_l = max(0.0, state.fuel_l - result.fuel_burned_l)
            state.fuel_burned_last_l = result.fuel_burned_l
            self.metrics.diesel_burned_l += result.fuel_burned_l
            self.metrics.grid_kwh += result.grid_kwh
            if result.gen_on:
                self.metrics.generator_hours += STEP_HOURS
            if state.sleeping and result.powered:
                self.metrics.sleep_kwh_saved += site.sleepable_kw * (1 - sleep_rules.residual_share) * STEP_HOURS

            previous = state.status
            if not result.powered:
                state.status = "dark"
            elif state.link_fault_id:
                state.status = "link_down"
            else:
                state.status = "up"

            if state.status != "up":
                if state.down_since is None:
                    state.down_since = step
                self.metrics.outage_site_hours += STEP_HOURS
                self.metrics.subscriber_hours_lost += site.subscribers * STEP_HOURS
                revenue_rate = self.settings.economics.revenue_per_subscriber_hour
                self.metrics.revenue_lost_usd += site.subscribers * revenue_rate * STEP_HOURS
            else:
                state.down_since = None

            if previous != state.status:
                if state.status == "up":
                    self._emit(step, "restored", i, f"{site.name} back on air")
                elif state.status == "dark":
                    self._emit(step, "down", i, f"{site.name} went dark: no power left")
                else:
                    self._emit(step, "down", i, f"{site.name} lost its transmission link")

            noise = self._sensor_rng.normal(0.0, 1.0, size=3)
            state.soc_reading = min(1.0, max(0.0, state.soc + noise[0] * SOC_SENSOR_SD))
            state.fuel_reading = max(0.0, state.fuel_l + noise[1] * FUEL_SENSOR_SD_L) if state.tank_l else 0.0
            state.battery_reading = max(0.0, state.battery_kwh + noise[2] * BATTERY_SENSOR_SD_KWH)
            state.history.append({
                "step": step,
                "soc": round(state.soc_reading, 3),
                "fuel": round(state.fuel_reading, 1),
                "traffic": round(traffic, 3),
                "grid": grid_on,
                "gen": result.gen_on,
                "sleep": state.sleeping,
                "status": state.status,
                "load": round(state.load_kw, 2),
                "battery": round(state.battery_reading, 2),
            })

        if self.policy == BASELINE:
            self._scheduled_refuels(step)
        self._reactive_dispatch(step)

    def _scheduled_refuels(self, step: int) -> None:
        interval = int(self.settings.field_ops.baseline_refuel_interval_hours * STEPS_PER_HOUR)
        for i, (site, _state) in enumerate(zip(self.sites, self.states, strict=False)):
            if site.has_generator and (step + i * 7) % interval == 0 and not self.open_jobs(i, "refuel"):
                self.dispatch(i, "refuel", step, "scheduled refuel round")

    def _reactive_dispatch(self, step: int) -> None:
        """What the NOC does today once a site has been reported down."""
        ops = self.settings.field_ops
        detection = int(ops.baseline_detection_hours * STEPS_PER_HOUR)
        diagnosis = ops.baseline_onsite_diagnosis_hours
        for i, (site, state) in enumerate(zip(self.sites, self.states, strict=False)):
            if state.down_since is None or step - state.down_since < detection or self.open_jobs(i):
                continue
            if state.status == "link_down":
                self.dispatch(i, "repair_link", step, "site reported down", extra_work_hours=diagnosis)
            elif state.battery_kwh < site.battery_kwh * 0.6:
                self.dispatch(i, "replace_battery", step, "site reported down",
                              delay_hours=ops.battery_release_hours_baseline, extra_work_hours=diagnosis)
            elif state.tank_l > 0 and state.fuel_l <= self.settings.power.gen_min_fuel_l:
                self.dispatch(i, "refuel", step, "site reported down", extra_work_hours=diagnosis)


def steps_to_grid(world: World, index: int, step: int, limit: int = 24 * STEPS_PER_HOUR) -> int | None:
    return steps_until_scheduled_on(world.sites[index].zone, step, world.stage, limit)
