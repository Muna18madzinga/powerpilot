"""Predictive models: demand forecast, outage risk, theft detection and
forward simulation of each site."""

import math
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from .config import STEP_HOURS, STEPS_PER_DAY, STEPS_PER_HOUR, Settings
from .environment import World, hour_of_day, solar_factor
from .network import BASELINE, Network, SiteState, steps_to_grid
from .power import PowerInput, battery_runway_hours, generator_lph, site_load_kw, step_power
from .sites import Site

RISK_HORIZON_STEPS = 6 * STEPS_PER_HOUR
FORECAST_STEPS = 24 * STEPS_PER_HOUR
AREA_CODE = {"urban": 0, "peri": 1, "rural": 2}

POWER_FEATURES = (
    "soc", "battery_health", "fuel_share", "has_generator", "grid_on", "hours_to_grid",
    "offgrid_share_12h", "net_kw", "battery_runway_h", "fuel_runway_h", "hour_sin",
    "hour_cos", "area", "generator_on",
)
THEFT_FEATURES = ("fuel_drop_l", "battery_drop_kwh", "door_alarm", "night", "guarded", "rural")


class DemandForecaster:
    def __init__(self, n_sites: int, alpha: float = 0.05):
        self.profile = np.full((n_sites, STEPS_PER_DAY), 0.5)
        self.alpha = alpha

    def slot(self, step: int) -> int:
        return int(hour_of_day(step) * STEPS_PER_HOUR) % STEPS_PER_DAY

    def update(self, index: int, step: int, traffic: float) -> None:
        slot = self.slot(step)
        self.profile[index, slot] += self.alpha * (traffic - self.profile[index, slot])

    def predict(self, index: int, step: int) -> float:
        return float(self.profile[index, self.slot(step)])

    def fit(self, rows: list[tuple[int, int, float]]) -> None:
        sums = np.zeros_like(self.profile)
        counts = np.zeros_like(self.profile)
        for index, step, traffic in rows:
            sums[index, self.slot(step)] += traffic
            counts[index, self.slot(step)] += 1
        mask = counts > 0
        self.profile[mask] = sums[mask] / counts[mask]


@dataclass(frozen=True)
class Projection:
    dark_in_hours: float | None
    min_soc: float
    fuel_used_l: float
    generator_hours: float


def project_site(site: Site, state: SiteState, world: World, index: int, step: int,
                 forecaster: DemandForecaster, settings: Settings,
                 horizon: int = FORECAST_STEPS, smart: bool | None = None,
                 sleep_enabled: bool | None = None, trace: list[float] | None = None,
                 fuel_l: float | None = None) -> Projection:
    rules = settings.power
    sleep_rules = settings.sleep
    smart = state.smart_genset if smart is None else smart
    sleep_enabled = state.sleep_enabled if sleep_enabled is None else sleep_enabled
    soc, gen_on, sleeping = state.soc_reading, state.gen_on, state.sleeping
    fuel = state.fuel_reading if fuel_l is None else fuel_l
    dark = state.status == "dark"
    min_soc, fuel_used, gen_hours = soc, 0.0, 0.0
    first_dark: float | None = None
    off_steps = expected_offgrid(world, index, step, horizon + STEPS_PER_DAY)
    next_on = _steps_to_next_on(off_steps)

    for ahead in range(1, horizon + 1):
        future = step + ahead
        traffic = forecaster.predict(index, future)
        if sleep_enabled and len(site.layers) > 1:
            if sleeping and traffic > sleep_rules.wake_above_traffic:
                sleeping = False
            elif not sleeping and traffic < sleep_rules.sleep_below_traffic:
                sleeping = True
        grid_on = not off_steps[ahead - 1]
        hours_to_grid = None
        if site.has_grid and next_on[ahead - 1] is not None:
            hours_to_grid = next_on[ahead - 1] * STEP_HOURS
        result = step_power(
            PowerInput(
                battery_kwh=state.battery_kwh, soc=soc, fuel_l=fuel, gen_kva=state.gen_kva,
                gen_on=gen_on, smart=smart, grid_on=grid_on,
                solar_kw=site.solar_kw * solar_factor(hour_of_day(future)) * 0.8,
                load_kw=site_load_kw(site.idle_kw, site.traffic_kw, site.sleepable_kw, traffic, sleeping, sleep_rules),
                hours_to_grid=hours_to_grid, dark=dark,
            ),
            rules,
            STEP_HOURS,
        )
        soc, gen_on = result.soc, result.gen_on
        fuel = max(0.0, fuel - result.fuel_burned_l)
        fuel_used += result.fuel_burned_l
        gen_hours += STEP_HOURS if gen_on else 0.0
        min_soc = min(min_soc, soc)
        dark = not result.powered
        if trace is not None:
            trace.append(0.0 if dark else round(soc, 3))
        if dark and first_dark is None and state.status != "dark":
            first_dark = ahead * STEP_HOURS
            if trace is None:
                break
    if first_dark is None and dark:
        first_dark = 0.0
    return Projection(first_dark, min_soc, fuel_used, gen_hours)


FAULT_PERSISTENCE_STEPS = 3 * STEPS_PER_HOUR


def _steps_to_next_on(off_steps: list[bool]) -> list[int | None]:
    result: list[int | None] = [None] * len(off_steps)
    distance = None
    for k in range(len(off_steps) - 1, -1, -1):
        distance = 0 if not off_steps[k] else (None if distance is None else distance + 1)
        result[k] = distance
    return result


def expected_offgrid(world: World, index: int, step: int, count: int) -> list[bool]:
    """Grid availability the operator can know at `step`: the published
    load-shedding schedule plus any fault already in progress."""
    if not world.sites[index].has_grid:
        return [True] * count
    faulted = world.grid_fault_active(index, step)
    return [
        not world.scheduled_on(index, step + k) or (faulted and k <= FAULT_PERSISTENCE_STEPS)
        for k in range(1, count + 1)
    ]


def power_features(site: Site, state: SiteState, world: World, index: int, step: int, settings: Settings) -> list[float]:
    rules = settings.power
    net = state.load_kw - state.solar_kw
    if site.has_grid:
        ahead = steps_to_grid(world, index, step)
        hours_to_grid = 24.0 if ahead is None else ahead * STEP_HOURS
        offgrid = sum(not world.scheduled_on(index, s) for s in range(step + 1, step + 1 + 12 * STEPS_PER_HOUR))
    else:
        hours_to_grid, offgrid = 24.0, 12 * STEPS_PER_HOUR
    fuel_runway = 0.0
    if state.gen_kva > 0:
        fuel_runway = min(72.0, state.fuel_reading / generator_lph(state.gen_kva, max(net, 0.5), rules))
    hour = hour_of_day(step)
    return [
        state.soc_reading,
        state.battery_reading / site.battery_kwh,
        state.fuel_reading / state.tank_l if state.tank_l else 0.0,
        float(state.gen_kva > 0),
        float(state.grid_on),
        0.0 if state.grid_on else min(hours_to_grid, 24.0),
        offgrid / (12 * STEPS_PER_HOUR),
        net,
        min(24.0, battery_runway_hours(state.battery_reading, state.soc_reading, net, rules)),
        fuel_runway,
        math.sin(2 * math.pi * hour / 24),
        math.cos(2 * math.pi * hour / 24),
        float(AREA_CODE[site.area]),
        float(state.gen_on),
    ]


def theft_features(site: Site, state: SiteState, step: int, settings: Settings) -> list[float]:
    history = state.history
    fuel_drop = battery_drop = 0.0
    if len(history) >= 2:
        prev, curr = history[-2], history[-1]
        expected_burn = state.fuel_burned_last_l
        fuel_drop = max(0.0, prev["fuel"] - curr["fuel"] - expected_burn)
        battery_drop = max(0.0, prev["battery"] - curr["battery"])
    hour = hour_of_day(step)
    return [
        fuel_drop,
        battery_drop,
        float(state.door_alarm),
        float(hour >= 20 or hour < 5),
        float(site.guarded),
        float(site.area == "rural"),
    ]


@dataclass
class ModelCard:
    name: str
    algorithm: str
    trained_on: str
    metrics: dict

    def as_dict(self) -> dict:
        return {"name": self.name, "algorithm": self.algorithm, "trained_on": self.trained_on, "metrics": self.metrics}


class OutageRiskModel:
    def __init__(self):
        self.model = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.07, max_leaf_nodes=24, random_state=7)
        self.card: ModelCard | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, day: np.ndarray, trained_on: str) -> None:
        holdout = day >= day.max() - 1
        probe = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.07, max_leaf_nodes=24, random_state=7)
        probe.fit(X[~holdout], y[~holdout])
        scores = probe.predict_proba(X[holdout])[:, 1]
        self.model.fit(X, y)
        self.card = ModelCard(
            name="Outage risk (next 6 h)",
            algorithm="Gradient-boosted trees",
            trained_on=trained_on,
            metrics={
                "roc_auc": round(float(roc_auc_score(y[holdout], scores)), 3),
                "average_precision": round(float(average_precision_score(y[holdout], scores)), 3),
                "positive_rate": round(float(y.mean()), 3),
                "rows": int(len(y)),
            },
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]


class TheftDetector:
    """Scores how far fuel and battery readings fall beyond normal sensor
    noise, weighted by context (door alarm, night, unguarded, rural)."""

    CONTEXT_WEIGHTS = np.array([1.5, 1.0, -0.5, 0.5])

    def __init__(self):
        self.fuel_noise_l = 1.0
        self.battery_noise_kwh = 0.05
        self.threshold = 0.0
        self.card: ModelCard | None = None

    def fit(self, X: np.ndarray, is_theft: np.ndarray, trained_on: str) -> None:
        normal = X[~is_theft]
        self.fuel_noise_l = max(float(np.std(normal[:, 0])), 0.5)
        self.battery_noise_kwh = max(float(np.std(normal[:, 1])), 0.02)
        self.threshold = float(np.quantile(self.scores(normal), 0.999))
        flagged = self.is_theft(X)
        observable = is_theft & ((X[:, 0] > 0) | (X[:, 1] > 0))
        self.card = ModelCard(
            name="Theft and tamper detection",
            algorithm="Residual anomaly scoring on fuel and battery telemetry",
            trained_on=trained_on,
            metrics={
                "recall_on_tamper_steps": round(float(flagged[observable].mean()) if observable.any() else 0.0, 3),
                "false_alarm_rate": round(float(flagged[~is_theft].mean()), 4),
                "rows": int(len(X)),
            },
        )

    def scores(self, X: np.ndarray) -> np.ndarray:
        residual = np.maximum(X[:, 0] / self.fuel_noise_l, X[:, 1] / self.battery_noise_kwh)
        return residual + X[:, 2:6] @ self.CONTEXT_WEIGHTS

    def flag(self, X: np.ndarray, scores: np.ndarray) -> np.ndarray:
        material = (X[:, 0] > 8) | (X[:, 1] > 0.4)
        return (scores > self.threshold) & material

    def is_theft(self, X: np.ndarray) -> np.ndarray:
        return self.flag(X, self.scores(X))


@dataclass
class TrainedModels:
    forecaster: DemandForecaster
    risk: OutageRiskModel
    theft: TheftDetector


def train_models(sites: tuple[Site, ...], settings: Settings, days: int = 6) -> TrainedModels:
    world = World(sites, settings.seed + 101, settings.loadshedding_stage)
    network = Network("training", BASELINE, sites, world, settings)
    forecaster = DemandForecaster(len(sites))
    total = days * STEPS_PER_DAY

    power_rows, outage_flags, row_meta = [], [], []
    theft_rows, theft_flags, demand_rows = [], [], []
    status_by_step = np.zeros((total, len(sites)), dtype=bool)

    for step in range(total):
        world.ensure(step)
        network.step(step)
        active_thefts = {(t.site_index) for t in world.thefts_at(step)}
        for i, (site, state) in enumerate(zip(sites, network.states, strict=False)):
            status_by_step[step, i] = state.status == "dark"
            demand_rows.append((i, step, state.traffic))
            power_rows.append(power_features(site, state, world, i, step, settings))
            outage_flags.append(state.status == "up")
            row_meta.append((step, i))
            theft_rows.append(theft_features(site, state, step, settings))
            theft_flags.append(i in active_thefts)

    labels, keep, day = [], [], []
    for (step, i), was_up in zip(row_meta, outage_flags, strict=False):
        end = min(total, step + 1 + RISK_HORIZON_STEPS)
        if not was_up or end - step - 1 < RISK_HORIZON_STEPS:
            keep.append(False)
            labels.append(0)
            day.append(0)
            continue
        keep.append(True)
        labels.append(int(status_by_step[step + 1:end, i].any()))
        day.append(step // STEPS_PER_DAY)

    keep_mask = np.array(keep)
    X = np.array(power_rows)[keep_mask]
    y = np.array(labels)[keep_mask]
    d = np.array(day)[keep_mask]

    forecaster.fit(demand_rows)
    risk = OutageRiskModel()
    trained_on = f"{days} simulated days, {len(sites)} sites, Stage {settings.loadshedding_stage} load-shedding"
    risk.fit(X, y, d, trained_on)
    theft = TheftDetector()
    theft.fit(np.array(theft_rows), np.array(theft_flags), trained_on)
    return TrainedModels(forecaster, risk, theft)
