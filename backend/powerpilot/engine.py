"""Operations engine: runs both network twins, scores every site and turns
findings into recommendations an engineer can approve."""

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .config import SIM_START_ISO, STEP_HOURS, STEPS_PER_HOUR, Settings
from .environment import World, hour_of_day, scheduled_off_hours_per_day
from .goals import Goal, parse_goal
from .models import (
    TrainedModels,
    expected_offgrid,
    power_features,
    project_site,
    theft_features,
    train_models,
)
from .network import BASELINE, POWERPILOT, Network
from .sites import DEPOTS, build_sites

AUTONOMY_LEVELS = ("advise", "assist", "autopilot")
OPEN = ("pending", "approved", "auto")
URGENCY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FIELD_KINDS = {"refuel", "replace_battery", "repair_link", "security", "mobile_genset"}
REJECT_COOLDOWN_STEPS = 4 * STEPS_PER_HOUR


@dataclass
class Insight:
    risk: float
    dark_in_hours: float | None
    fuel_runway_hours: float | None
    diesel_24h_l: float
    theft_score: float
    theft_flag: bool
    battery_drop_kwh: float
    fuel_drop_l: float


@dataclass
class Recommendation:
    id: str
    site_index: int | None
    kind: str
    title: str
    urgency: str
    created_step: int
    trail: list[dict]
    benefit: str
    status: str = "pending"
    job_id: str | None = None
    eta_step: int | None = None
    ref: str | None = None
    goal_id: str | None = None
    resolved_step: int | None = None
    note: str | None = None


@dataclass
class GoalRecord:
    id: str
    goal: Goal
    created_step: int
    summary: str
    steps: list[str]
    recommendation_ids: list[str] = field(default_factory=list)


class Engine:
    def __init__(self, settings: Settings | None = None, autonomy: str = "assist", models: TrainedModels | None = None):
        self.settings = settings or Settings()
        self.sites = build_sites(self.settings.seed)
        self.models = models or train_models(self.sites, self.settings)
        self.autonomy = autonomy
        self.reset()

    def reset(self) -> None:
        self.world = World(self.sites, self.settings.seed, self.settings.loadshedding_stage)
        self.baseline = Network("baseline", BASELINE, self.sites, self.world, self.settings)
        self.pilot = Network("powerpilot", POWERPILOT, self.sites, self.world, self.settings)
        self.step = 0
        self.recommendations: dict[str, Recommendation] = {}
        self.goals: list[GoalRecord] = []
        self.log: deque = deque(maxlen=400)
        self.insights: list[Insight] = []
        self.baseline_soc: list[deque] = [deque(maxlen=48 * STEPS_PER_HOUR) for _ in self.sites]
        self._cooldown: dict[tuple[int | None, str], int] = {}
        self._counter = 0
        self.set_autonomy(self.autonomy)
        self.tick()

    @property
    def stage(self) -> int:
        return self.world.stage

    def time_at(self, step: int) -> datetime:
        return datetime.fromisoformat(SIM_START_ISO) + timedelta(hours=step * STEP_HOURS)

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:04d}"

    def _note(self, kind: str, message: str, site_index: int | None = None, **extra) -> None:
        self.log.appendleft({
            "step": self.step,
            "time": self.time_at(self.step).isoformat(),
            "kind": kind,
            "site_id": None if site_index is None else self.sites[site_index].id,
            "message": message,
            **extra,
        })

    def set_autonomy(self, level: str) -> None:
        if level not in AUTONOMY_LEVELS:
            raise ValueError(f"autonomy must be one of {AUTONOMY_LEVELS}")
        self.autonomy = level
        controls = level != "advise"
        for state in self.pilot.states:
            state.sleep_enabled = controls
            state.smart_genset = controls
        if level == "autopilot":
            for rec in self.open_recommendations():
                if rec.status == "pending":
                    self._approve(rec, auto=True)

    def set_stage(self, stage: int) -> None:
        stage = max(0, min(6, int(stage)))
        self.world.stage = stage
        hours = scheduled_off_hours_per_day(stage)
        self._note("schedule", f"Load-shedding moved to Stage {stage} ({hours:.0f} h off per day per zone)")

    def tick(self, count: int = 1) -> None:
        for _ in range(count):
            self._tick_once()

    def _tick_once(self) -> None:
        step = self.step
        self.world.ensure(step)
        self.baseline.step(step)
        self.pilot.step(step)
        for i, state in enumerate(self.baseline.states):
            self.baseline_soc[i].append(round(state.soc_reading, 3))
        for i, state in enumerate(self.pilot.states):
            self.models.forecaster.update(i, step, state.traffic)
        for event in self.pilot.events:
            index = next(k for k, s in enumerate(self.sites) if s.id == event["site_id"])
            self._note(event["kind"], event["message"], index)
        self.insights = self._assess(step)
        self._track_recommendations(step)
        self._plan(step)
        self.step += 1

    def _assess(self, step: int) -> list[Insight]:
        settings = self.settings
        power_rows = np.array([
            power_features(site, state, self.world, i, step, settings)
            for i, (site, state) in enumerate(zip(self.sites, self.pilot.states, strict=False))
        ])
        theft_rows = np.array([
            theft_features(site, state, step, settings) for site, state in zip(self.sites, self.pilot.states, strict=False)
        ])
        risk = self.models.risk.predict(power_rows)
        theft_scores = self.models.theft.scores(theft_rows)
        theft_flags = self.models.theft.flag(theft_rows, theft_scores)
        insights = []
        for i, (site, state) in enumerate(zip(self.sites, self.pilot.states, strict=False)):
            projection = project_site(site, state, self.world, i, step, self.models.forecaster, settings)
            runway = None
            if state.tank_l > 0:
                daily = max(projection.fuel_used_l, 1.0)
                runway = state.fuel_reading / daily * 24
            site_risk = float(risk[i])
            if state.status == "dark":
                site_risk = 1.0
            elif projection.dark_in_hours is not None and projection.dark_in_hours <= 6:
                site_risk = max(site_risk, 0.9 - projection.dark_in_hours * 0.05)
            insights.append(Insight(
                risk=round(site_risk, 3),
                dark_in_hours=projection.dark_in_hours,
                fuel_runway_hours=None if runway is None else round(runway, 1),
                diesel_24h_l=round(projection.fuel_used_l, 1),
                theft_score=round(float(theft_scores[i]), 3),
                theft_flag=bool(theft_flags[i]),
                battery_drop_kwh=float(theft_rows[i][1]),
                fuel_drop_l=float(theft_rows[i][0]),
            ))
            if state.door_alarm and not theft_flags[i] and (hour_of_day(step) >= 20 or hour_of_day(step) < 5):
                self._note("watch", f"Door alarm at {site.name} — no tamper pattern in telemetry, watching", i)
        return insights

    def open_recommendations(self) -> list[Recommendation]:
        return [r for r in self.recommendations.values() if r.status in OPEN]

    def _open(self, site_index: int | None, kind: str) -> Recommendation | None:
        return next((r for r in self.open_recommendations() if r.site_index == site_index and r.kind == kind), None)

    def _cooling(self, site_index: int | None, kind: str, step: int) -> bool:
        return self._cooldown.get((site_index, kind), -1) > step

    def _dispatch_line(self, site_index: int, kind: str, step: int, delay_hours: float = 0.0) -> str:
        plan = self.pilot.plan_dispatch(site_index, kind, step, delay_hours)
        eta = (plan.arrive - step) * STEP_HOURS
        if kind == "security":
            return f"{plan.responder.capitalize()} · ETA {_hours(eta)}"
        return f"{plan.depot.name} · {plan.road_km:.0f} km by road · {plan.responder} · on site in {_hours(eta)}"

    def _recommend(self, step: int, site_index: int | None, kind: str, title: str, urgency: str,
                   monitor: str, diagnose: str, plan: str, benefit: str,
                   ref: str | None = None, goal_id: str | None = None, delay_hours: float = 0.0) -> Recommendation | None:
        if self._open(site_index, kind) or self._cooling(site_index, kind, step):
            return None
        dispatch = "Applied to radio and power controllers — no site visit" if kind not in FIELD_KINDS else \
            self._dispatch_line(site_index, kind, step, delay_hours)
        rec = Recommendation(
            id=self._next_id("REC"),
            site_index=site_index,
            kind=kind,
            title=title,
            urgency=urgency,
            created_step=step,
            trail=[
                {"stage": "Monitor", "text": monitor},
                {"stage": "Diagnose", "text": diagnose},
                {"stage": "Plan", "text": plan},
                {"stage": "Dispatch", "text": dispatch},
            ],
            benefit=benefit,
            ref=ref,
            goal_id=goal_id,
        )
        self.recommendations[rec.id] = rec
        where = "" if site_index is None else f" for {self.sites[site_index].name}"
        self._note("recommendation", f"{title}{where}", site_index, recommendation=rec.id, urgency=urgency)
        if self.autonomy == "autopilot":
            self._approve(rec, auto=True)
        return rec

    def _plan(self, step: int) -> None:
        if self.autonomy == "advise" and not any(s.sleep_enabled for s in self.pilot.states):
            sites_on_backup = sum(1 for s in self.pilot.states if not s.grid_on)
            self._recommend(
                step, None, "enable_controls", "Switch on cell sleep and smart generator scheduling", "medium",
                f"{sites_on_backup} of {len(self.sites)} sites are on battery or generator right now.",
                "Capacity layers stay powered through low-traffic hours and generators follow load at poor efficiency.",
                "Sleep capacity layers when traffic is low. Cycle-charge generators only when the battery "
                "cannot reach the next grid window.",
                "Typically 10–20% less diesel and longer battery runway, with no site visits",
            )
        for i, (site, state, insight) in enumerate(zip(self.sites, self.pilot.states, self.insights, strict=False)):
            subs = f"{site.subscribers:,}"
            if insight.theft_flag:
                theft = next((t for t in self.world.thefts_at(step) if t.site_index == i), None)
                if insight.battery_drop_kwh > 0:
                    what = f"battery string lost {insight.battery_drop_kwh:.1f} kWh in 15 min"
                    diagnosis = "Battery modules are being removed. Theft in progress."
                else:
                    what = f"fuel level fell {insight.fuel_drop_l:.0f} L with the generator off"
                    diagnosis = "Diesel is being siphoned. Theft in progress."
                self._recommend(
                    step, i, "security", "Send security now", "critical",
                    f"Door alarm and {what}. Anomaly score {insight.theft_score:.1f} "
                    f"against an alert threshold of {self.models.theft.threshold:.1f}.",
                    diagnosis,
                    "Dispatch the nearest responder and alert the police post. Lock out the site until a technician checks it.",
                    f"Stops further loss at a site serving {subs} subscribers",
                    ref=theft.id if theft else None,
                )
            if state.battery_kwh < site.battery_kwh * 0.6:
                self._recommend(
                    step, i, "replace_battery", "Replace battery bank", "high",
                    f"Installed battery capacity is {state.battery_reading:.1f} kWh of {site.battery_kwh:.1f} kWh.",
                    "Capacity was lost suddenly, which matches removal rather than wear.",
                    "Release a replacement bank from stores and fit it on the next crew visit.",
                    f"Restores {site.battery_kwh * state.health:.0f} kWh of backup for {subs} subscribers",
                    delay_hours=self.settings.field_ops.battery_release_hours_powerpilot,
                )
            if state.status == "link_down":
                self._recommend(
                    step, i, "repair_link", "Send transmission technician", "critical",
                    "Site is off air while power is healthy "
                    f"({'grid' if state.grid_on else 'battery ' + format(state.soc_reading, '.0%')}).",
                    "Power is not the cause. The microwave or fibre link has failed.",
                    "Send a transmission technician with a spare ODU and route traffic to neighbouring cells meanwhile.",
                    f"Brings {subs} subscribers back on air",
                )
            if state.tank_l > 0 and site.has_generator and insight.fuel_runway_hours is not None:
                runway = insight.fuel_runway_hours
                threshold = self.settings.field_ops.predictive_refuel_runway_hours
                if runway < threshold or (state.status == "dark" and state.fuel_reading < 10):
                    urgency = "critical" if runway < 6 or state.status == "dark" else "high" if runway < 18 else "medium"
                    self._recommend(
                        step, i, "refuel", "Refuel generator", urgency,
                        f"Tank at {state.fuel_reading:.0f} L of {state.tank_l:.0f} L. "
                        f"Forecast burn {insight.diesel_24h_l:.0f} L over the next 24 h at Stage {self.stage}.",
                        f"Diesel runs out in about {_hours(runway)}, before the next routine refuel round.",
                        f"Top up to {state.tank_l:.0f} L now, while the crew can reach the site in daylight.",
                        f"Avoids an outage for {subs} subscribers",
                    )
            if (state.tank_l == 0 and site.has_grid and insight.dark_in_hours is not None
                    and insight.dark_in_hours <= 4 and state.status == "up"):
                offgrid = expected_offgrid(self.world, i, step, 12 * STEPS_PER_HOUR)
                dark_step = int(insight.dark_in_hours * STEPS_PER_HOUR)
                gap = sum(offgrid[dark_step:]) * STEP_HOURS if dark_step < len(offgrid) else 0
                if gap >= 2:
                    self._recommend(
                        step, i, "mobile_genset", "Deploy mobile generator", "high",
                        f"Battery-only site at {state.soc_reading:.0%}. Grid is scheduled off for most of the next 12 h.",
                        f"The site goes dark in about {_hours(insight.dark_in_hours)} and has no generator of its own.",
                        "Tow a mobile generator from the depot and leave it on site for 24 h.",
                        f"Keeps {subs} subscribers on air through about {gap:.0f} h of load-shedding",
                    )

    def _track_recommendations(self, step: int) -> None:
        for rec in self.open_recommendations():
            if rec.status in ("approved", "auto") and rec.job_id:
                job = next(j for j in self.pilot.jobs if j.id == rec.job_id)
                if job.completed:
                    rec.status, rec.resolved_step = "done", step
                continue
            if rec.status != "pending" or rec.site_index is None:
                continue
            state = self.pilot.states[rec.site_index]
            site = self.sites[rec.site_index]
            insight = self.insights[rec.site_index] if self.insights else None
            cleared = False
            if rec.kind == "refuel" and insight and insight.fuel_runway_hours:
                cleared = insight.fuel_runway_hours > self.settings.field_ops.predictive_refuel_runway_hours * 1.5
            elif rec.kind == "security":
                cleared = step - rec.created_step > 4 * STEPS_PER_HOUR
            elif rec.kind == "replace_battery":
                cleared = state.battery_kwh >= site.battery_kwh * 0.9
            elif rec.kind == "repair_link":
                cleared = state.link_fault_id is None
            elif rec.kind == "mobile_genset":
                cleared = state.grid_on and state.soc_reading > 0.5
            if cleared:
                rec.status, rec.resolved_step, rec.note = "expired", step, "Condition cleared before approval"

    def _approve(self, rec: Recommendation, auto: bool = False) -> None:
        step = self.step
        if rec.kind == "enable_controls":
            for state in self.pilot.states:
                state.sleep_enabled = True
                state.smart_genset = True
            rec.status, rec.resolved_step = "done", step
        elif rec.kind in FIELD_KINDS and rec.site_index is not None:
            delay = self.settings.field_ops.battery_release_hours_powerpilot if rec.kind == "replace_battery" else 0.0
            job = self.pilot.dispatch(rec.site_index, rec.kind, step, rec.title, ref=rec.ref, delay_hours=delay)
            rec.status = "auto" if auto else "approved"
            rec.job_id, rec.eta_step = job.id, job.arrive
        else:
            rec.status, rec.resolved_step = "done", step
        who = "Auto-approved" if auto else "Approved"
        target = "" if rec.site_index is None else f" at {self.sites[rec.site_index].name}"
        self._note("approved", f"{who}: {rec.title}{target}", rec.site_index, recommendation=rec.id)

    def approve(self, rec_id: str) -> Recommendation:
        rec = self.recommendations[rec_id]
        if rec.status != "pending":
            raise ValueError(f"{rec_id} is {rec.status}")
        self._approve(rec)
        return rec

    def reject(self, rec_id: str) -> Recommendation:
        rec = self.recommendations[rec_id]
        if rec.status != "pending":
            raise ValueError(f"{rec_id} is {rec.status}")
        rec.status, rec.resolved_step = "rejected", self.step
        self._cooldown[(rec.site_index, rec.kind)] = self.step + REJECT_COOLDOWN_STEPS
        target = "" if rec.site_index is None else f" at {self.sites[rec.site_index].name}"
        self._note("rejected", f"Rejected: {rec.title}{target}", rec.site_index, recommendation=rec.id)
        return rec

    def approve_all(self) -> int:
        pending = [r for r in self.open_recommendations() if r.status == "pending"]
        for rec in pending:
            self._approve(rec)
        return len(pending)

    def site_index(self, site_id: str) -> int:
        for i, site in enumerate(self.sites):
            if site.id == site_id:
                return i
        raise KeyError(site_id)

    def inject(self, kind: str, site_id: str | None = None, hours: float = 4.0, stage: int | None = None) -> str:
        step = self.step
        if kind == "stage":
            self.set_stage(stage if stage is not None else self.stage + 1)
            return f"Stage {self.stage}"
        index = self.site_index(site_id) if site_id else self._pick_target(kind)
        site = self.sites[index]
        if kind in ("battery_theft", "fuel_theft"):
            theft_kind = "battery" if kind == "battery_theft" else "fuel"
            if theft_kind == "fuel" and not site.has_generator:
                theft_kind = "battery"
            self.world.inject_theft(index, theft_kind, step)
            label = f"{theft_kind} theft begins at {site.name}"
        elif kind == "link_fault":
            self.world.inject_link_fault(index, step)
            label = f"transmission link fails at {site.name}"
        elif kind == "grid_fault":
            self.world.inject_grid_fault(index, step, hours)
            label = f"unplanned ZESA fault at {site.name} for {hours:.0f} h"
        else:
            raise ValueError(f"unknown scenario {kind}")
        self._note("scenario", f"Scenario: {label}", index)
        return label

    def _pick_target(self, kind: str) -> int:
        rng = np.random.default_rng([self.settings.seed, self.step, len(kind)])
        candidates = [i for i, s in enumerate(self.sites) if s.area != "urban" and (kind != "fuel_theft" or s.has_generator)]
        return int(rng.choice(candidates))

    def set_goal(self, text: str) -> GoalRecord:
        goal = parse_goal(text, self.sites, self.step)
        record = GoalRecord(self._next_id("GOAL"), goal, self.step, "", [])
        if goal.intent == "save_diesel":
            self._plan_savings(record)
        else:
            self._plan_uptime(record)
        self.goals.insert(0, record)
        self._note("goal", f"Goal set: “{goal.text}” — {record.summary}")
        return record

    def _window_projection(self, i: int, goal: Goal, **kwargs):
        start_offset = max(0, goal.start - self.step)
        horizon = start_offset + (goal.end - goal.start)
        return project_site(self.sites[i], self.pilot.states[i], self.world, i, self.step,
                            self.models.forecaster, self.settings, horizon=horizon, **kwargs)

    def _plan_uptime(self, record: GoalRecord) -> None:
        goal = record.goal
        at_risk = []
        for i in goal.site_indices:
            site, state = self.sites[i], self.pilot.states[i]
            projection = self._window_projection(i, goal)
            if projection.dark_in_hours is None and state.status == "up":
                continue
            at_risk.append(site.name)
            if state.status == "link_down":
                rec = self._recommend(self.step, i, "repair_link", "Send transmission technician", "critical",
                                      "Site is off air with healthy power.", "Transmission link failure.",
                                      "Repair before the goal window opens.", f"Required to keep {site.name} up",
                                      goal_id=record.id)
            elif state.tank_l > 0 and state.fuel_reading < max(projection.fuel_used_l * 1.3, state.tank_l * 0.4):
                rec = self._recommend(
                    self.step, i, "refuel", "Refuel generator before the window", "high",
                    f"Tank at {state.fuel_reading:.0f} L. The window needs about {projection.fuel_used_l:.0f} L.",
                    f"Without a top-up the site goes dark about {_hours(projection.dark_in_hours or 0)} from now.",
                    f"Top up to {state.tank_l:.0f} L ahead of {goal.window_label}.",
                    f"Keeps {site.name} on air for {goal.window_label}", goal_id=record.id)
            elif state.tank_l == 0:
                rec = self._recommend(
                    self.step, i, "mobile_genset", "Deploy mobile generator before the window", "high",
                    f"Battery-only site at {state.soc_reading:.0%}.",
                    f"The battery cannot bridge the load-shedding in {goal.window_label}.",
                    "Pre-position a mobile generator on site.",
                    f"Keeps {site.name} on air for {goal.window_label}", goal_id=record.id)
            elif state.battery_kwh < site.battery_kwh * 0.6:
                rec = self._recommend(
                    self.step, i, "replace_battery", "Replace battery bank before the window", "high",
                    "Battery capacity is depleted.", "Not enough storage to bridge the window.",
                    "Fit a replacement bank.", f"Keeps {site.name} on air for {goal.window_label}", goal_id=record.id)
            else:
                rec = None
            if rec:
                record.recommendation_ids.append(rec.id)
        for i in goal.site_indices:
            state = self.pilot.states[i]
            state.sleep_enabled = True
            state.smart_genset = True
        protected = len(goal.site_indices)
        record.steps = [
            f"Projected every target site through {goal.window_label} against the published Stage {self.stage} schedule.",
            f"Cell sleep and smart generator scheduling locked on for {protected} site{'s' if protected != 1 else ''}.",
            (f"{len(at_risk)} site{'s' if len(at_risk) != 1 else ''} would go dark: {', '.join(at_risk[:6])}"
             f"{'…' if len(at_risk) > 6 else ''}. Field actions queued for approval.") if at_risk else
            "No target site is projected to go dark. Nothing to dispatch.",
        ]
        record.summary = (f"{len(at_risk)} of {protected} sites need action" if at_risk
                          else f"all {protected} sites hold through {goal.window_label}")

    def _plan_savings(self, record: GoalRecord) -> None:
        goal = record.goal
        legacy = smart = 0.0
        for i in goal.site_indices:
            legacy += self._window_projection(i, goal, smart=False, sleep_enabled=False).fuel_used_l
            smart += self._window_projection(i, goal, smart=True, sleep_enabled=True).fuel_used_l
            self.pilot.states[i].sleep_enabled = True
            self.pilot.states[i].smart_genset = True
        saved = max(0.0, legacy - smart)
        price = self.settings.economics.diesel_usd_per_litre
        record.steps = [
            f"Compared legacy generator control with smart scheduling over {goal.window_label}.",
            f"Legacy control would burn about {legacy:.0f} L. Smart scheduling needs about {smart:.0f} L.",
            "Smart scheduling and cell sleep are now active on the target sites.",
        ]
        record.summary = f"about {saved:.0f} L (${saved * price:,.0f}) less diesel over {goal.window_label}"

    def kpis(self) -> dict:
        economics = self.settings.economics
        result = {}
        for key, network in (("baseline", self.baseline), ("powerpilot", self.pilot)):
            m = asdict(network.metrics)
            cost = (
                (m["diesel_burned_l"] + m["diesel_stolen_l"]) * economics.diesel_usd_per_litre
                + m["battery_stolen_kwh"] * economics.battery_usd_per_kwh
                + m["trip_km"] * economics.crew_cost_usd_per_km
                + m["revenue_lost_usd"]
            )
            m["total_cost_usd"] = cost
            result[key] = {k: round(v, 2) if isinstance(v, float) else v for k, v in m.items()}
        base, pilot = result["baseline"], result["powerpilot"]
        result["savings"] = {
            "outage_hours": round(base["outage_site_hours"] - pilot["outage_site_hours"], 2),
            "subscriber_hours": round(base["subscriber_hours_lost"] - pilot["subscriber_hours_lost"], 0),
            "diesel_l": round(
                base["diesel_burned_l"] + base["diesel_stolen_l"] - pilot["diesel_burned_l"] - pilot["diesel_stolen_l"], 1
            ),
            "cost_usd": round(base["total_cost_usd"] - pilot["total_cost_usd"], 2),
            "trip_km": round(base["trip_km"] - pilot["trip_km"], 1),
        }
        hours = max(self.step * STEP_HOURS, STEP_HOURS)
        site_hours = hours * len(self.sites)
        result["availability"] = {
            "baseline": round(1 - base["outage_site_hours"] / site_hours, 5),
            "powerpilot": round(1 - pilot["outage_site_hours"] / site_hours, 5),
        }
        result["elapsed_hours"] = hours
        return result

    def fleet(self) -> dict:
        states = self.pilot.states
        return {
            "up": sum(s.status == "up" for s in states),
            "dark": sum(s.status == "dark" for s in states),
            "link_down": sum(s.status == "link_down" for s in states),
            "on_grid": sum(s.grid_on for s in states),
            "on_generator": sum(s.gen_on for s in states),
            "on_battery": sum((not s.grid_on) and (not s.gen_on) and s.status == "up" for s in states),
            "sleeping": sum(s.sleeping for s in states),
            "at_risk": sum(i.risk >= 0.5 for i in self.insights),
        }

    def site_view(self, i: int, detail: bool = False) -> dict:
        site, state, insight = self.sites[i], self.pilot.states[i], self.insights[i]
        view = {
            "id": site.id,
            "name": site.name,
            "town": site.town,
            "lat": site.lat,
            "lon": site.lon,
            "area": site.area,
            "zone": site.zone,
            "subscribers": site.subscribers,
            "layers": list(site.layers),
            "status": state.status,
            "power_source": _power_source(state),
            "soc": round(state.soc_reading, 3),
            "fuel_l": round(state.fuel_reading, 1),
            "tank_l": state.tank_l,
            "battery_kwh": round(state.battery_reading, 1),
            "battery_rated_kwh": site.battery_kwh,
            "generator_kva": state.gen_kva,
            "solar_kw": site.solar_kw,
            "sleeping": state.sleeping,
            "traffic": round(state.traffic, 3),
            "load_kw": round(state.load_kw, 2),
            "guarded": site.guarded,
            "has_grid": site.has_grid,
            "risk": insight.risk,
            "dark_in_hours": insight.dark_in_hours,
            "fuel_runway_hours": insight.fuel_runway_hours,
            "diesel_24h_l": insight.diesel_24h_l,
            "theft_score": insight.theft_score,
            "open_recommendations": [r.id for r in self.open_recommendations() if r.site_index == i],
            "jobs": [
                {"id": j.id, "kind": j.kind, "eta": self.time_at(j.arrive).isoformat(), "done": self.time_at(j.done).isoformat()}
                for j in self.pilot.open_jobs(i)
            ],
        }
        if detail:
            view["history"] = list(state.history)
            view["baseline_soc"] = list(self.baseline_soc[i])
            view["baseline_status"] = self.baseline.states[i].status
            view["schedule"] = [
                {"step": self.step + k, "grid": not off}
                for k, off in enumerate(expected_offgrid(self.world, i, self.step, 24 * STEPS_PER_HOUR), start=1)
            ]
            view["forecast_traffic"] = [
                round(self.models.forecaster.predict(i, self.step + k), 3) for k in range(1, 24 * STEPS_PER_HOUR + 1)
            ]
        return view

    def recommendation_view(self, rec: Recommendation) -> dict:
        site = None if rec.site_index is None else self.sites[rec.site_index]
        return {
            "id": rec.id,
            "site_id": site.id if site else None,
            "site_name": site.name if site else "All sites",
            "kind": rec.kind,
            "title": rec.title,
            "urgency": rec.urgency,
            "status": rec.status,
            "created": self.time_at(rec.created_step).isoformat(),
            "age_minutes": int((self.step - rec.created_step) * STEP_HOURS * 60),
            "trail": rec.trail,
            "benefit": rec.benefit,
            "eta": None if rec.eta_step is None else self.time_at(rec.eta_step).isoformat(),
            "goal_id": rec.goal_id,
            "note": rec.note,
        }

    def recommendations_view(self, include_closed: bool = False) -> list[dict]:
        recs = list(self.recommendations.values())
        if not include_closed:
            recs = [r for r in recs if r.status in OPEN]
        recs.sort(key=lambda r: (r.status != "pending", URGENCY_ORDER[r.urgency], -r.created_step))
        return [self.recommendation_view(r) for r in recs]

    def goal_view(self, record: GoalRecord) -> dict:
        goal = record.goal
        return {
            "id": record.id,
            "text": goal.text,
            "intent": goal.intent,
            "scope": goal.scope_label,
            "window": goal.window_label,
            "sites": [self.sites[i].id for i in goal.site_indices],
            "summary": record.summary,
            "steps": record.steps,
            "recommendations": record.recommendation_ids,
            "created": self.time_at(record.created_step).isoformat(),
        }

    def meta(self) -> dict:
        return {
            "time": self.time_at(self.step).isoformat(),
            "step": self.step,
            "step_minutes": int(STEP_HOURS * 60),
            "stage": self.stage,
            "autonomy": self.autonomy,
            "autonomy_levels": list(AUTONOMY_LEVELS),
            "models": [self.models.risk.card.as_dict(), self.models.theft.card.as_dict()],
            "depots": [{"id": d.id, "name": d.name, "lat": d.lat, "lon": d.lon, "crews": d.crews} for d in DEPOTS],
            "economics": asdict(self.settings.economics),
        }


def _power_source(state) -> str:
    if state.grid_on:
        return "grid"
    if state.gen_on:
        return "generator"
    return "battery" if state.status == "up" else "none"


def _hours(value: float) -> str:
    if value < 1:
        return f"{max(1, round(value * 60))} min"
    if value < 48:
        whole = int(value)
        minutes = int(round((value - whole) * 60 / 15) * 15)
        if minutes == 60:
            whole, minutes = whole + 1, 0
        return f"{whole} h {minutes:02d} min" if minutes else f"{whole} h"
    return f"{value / 24:.1f} days"
