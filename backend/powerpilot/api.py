"""HTTP API for the PowerPilot console.

    uvicorn powerpilot.api:app --reload
"""

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import AUTONOMY_LEVELS, Engine

BASE_INTERVAL_SECONDS = float(os.getenv("POWERPILOT_TICK_SECONDS", "1.0"))
SPEEDS = (1, 2, 4, 8)


class Clock:
    def __init__(self):
        self.running = os.getenv("POWERPILOT_AUTOPLAY", "1") == "1"
        self.speed = 2

    def as_dict(self) -> dict:
        return {"running": self.running, "speed": self.speed, "speeds": list(SPEEDS)}


engine = Engine(autonomy=os.getenv("POWERPILOT_AUTONOMY", "assist"))
clock = Clock()


async def _run_clock() -> None:
    while True:
        if clock.running:
            engine.tick()
        await asyncio.sleep(BASE_INTERVAL_SECONDS / clock.speed)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_run_clock())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="PowerPilot", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("POWERPILOT_CORS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClockUpdate(BaseModel):
    running: bool | None = None
    speed: int | None = Field(default=None, description=f"one of {SPEEDS}")


class SettingsUpdate(BaseModel):
    autonomy: Literal["advise", "assist", "autopilot"] | None = None
    stage: int | None = Field(default=None, ge=0, le=6)


class ScenarioRequest(BaseModel):
    kind: Literal["battery_theft", "fuel_theft", "link_fault", "grid_fault", "stage"]
    site_id: str | None = None
    hours: float = Field(default=4.0, gt=0, le=48)
    stage: int | None = Field(default=None, ge=0, le=6)


class GoalRequest(BaseModel):
    text: str = Field(min_length=3, max_length=200)


def _state() -> dict:
    return {
        "meta": {**engine.meta(), "clock": clock.as_dict()},
        "fleet": engine.fleet(),
        "kpis": engine.kpis(),
        "sites": [engine.site_view(i) for i in range(len(engine.sites))],
        "recommendations": engine.recommendations_view(),
        "log": list(engine.log)[:60],
        "goals": [engine.goal_view(g) for g in engine.goals[:5]],
        "jobs": engine.jobs_view(),
        "loadshedding": engine.loadshedding_view(),
    }


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "step": engine.step}


@app.get("/api/state")
async def state() -> dict:
    return _state()


@app.get("/api/meta")
async def meta() -> dict:
    return {**engine.meta(), "clock": clock.as_dict()}


@app.get("/api/sites")
async def sites() -> list[dict]:
    return [engine.site_view(i) for i in range(len(engine.sites))]


@app.get("/api/sites/{site_id}")
async def site(site_id: str) -> dict:
    try:
        return engine.site_view(engine.site_index(site_id), detail=True)
    except KeyError:
        raise HTTPException(404, f"unknown site {site_id}") from None


@app.get("/api/kpis")
async def kpis() -> dict:
    return engine.kpis()


@app.get("/api/recommendations")
async def recommendations(include_closed: bool = False) -> list[dict]:
    return engine.recommendations_view(include_closed)


def _act(action, rec_id: str) -> dict:
    try:
        return engine.recommendation_view(action(rec_id))
    except KeyError:
        raise HTTPException(404, f"unknown recommendation {rec_id}") from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@app.post("/api/recommendations/{rec_id}/approve")
async def approve(rec_id: str) -> dict:
    return _act(engine.approve, rec_id)


@app.post("/api/recommendations/{rec_id}/reject")
async def reject(rec_id: str) -> dict:
    return _act(engine.reject, rec_id)


@app.post("/api/recommendations/approve-all")
async def approve_all() -> dict:
    return {"approved": engine.approve_all()}


@app.post("/api/goals")
async def goal(request: GoalRequest) -> dict:
    return engine.goal_view(engine.set_goal(request.text))


@app.post("/api/scenarios")
async def scenario(request: ScenarioRequest) -> dict:
    try:
        label = engine.inject(request.kind, request.site_id, request.hours, request.stage)
    except KeyError:
        raise HTTPException(404, f"unknown site {request.site_id}") from None
    return {"applied": label}


@app.put("/api/settings")
async def update_settings(update: SettingsUpdate) -> dict:
    if update.autonomy:
        engine.set_autonomy(update.autonomy)
    if update.stage is not None:
        engine.set_stage(update.stage)
    return {"autonomy": engine.autonomy, "stage": engine.stage, "levels": list(AUTONOMY_LEVELS)}


@app.put("/api/clock")
async def update_clock(update: ClockUpdate) -> dict:
    if update.running is not None:
        clock.running = update.running
    if update.speed is not None:
        if update.speed not in SPEEDS:
            raise HTTPException(422, f"speed must be one of {SPEEDS}")
        clock.speed = update.speed
    return clock.as_dict()


@app.post("/api/clock/step")
async def step(count: int = 1) -> dict:
    engine.tick(max(1, min(count, 96)))
    return {"step": engine.step, "time": engine.meta()["time"]}


@app.post("/api/reset")
async def reset() -> dict:
    engine.reset()
    return {"step": engine.step, "time": engine.meta()["time"]}
