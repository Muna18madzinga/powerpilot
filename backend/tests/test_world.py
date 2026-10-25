import pytest

from powerpilot.config import STEPS_PER_DAY, STEPS_PER_HOUR
from powerpilot.environment import World, grid_scheduled_on, scheduled_off_hours_per_day
from powerpilot.goals import parse_goal
from powerpilot.sites import build_sites


@pytest.mark.parametrize("stage", [0, 1, 2, 3, 4])
def test_schedule_matches_stage_hours(stage):
    off = sum(not grid_scheduled_on("B", step, stage) for step in range(STEPS_PER_DAY))
    assert off / STEPS_PER_HOUR == scheduled_off_hours_per_day(stage)


def test_world_is_deterministic(settings):
    sites = build_sites(settings.seed)
    first, second = World(sites, 5, 4), World(sites, 5, 4)
    assert [first.traffic(3, s) for s in range(200)] == [second.traffic(3, s) for s in range(200)]


def test_catalogue_has_thirty_sites(settings):
    sites = build_sites(settings.seed)
    assert len(sites) == 30
    assert len({s.id for s in sites}) == 30


def test_goal_parsing_scope_and_window(settings):
    sites = build_sites(settings.seed)
    goal = parse_goal("Keep Kwekwe up tonight", sites, step=0)
    assert goal.intent == "protect_uptime"
    assert {sites[i].town for i in goal.site_indices} == {"Kwekwe"}
    assert goal.window_label.startswith("tonight")
    assert goal.end - goal.start == 12 * STEPS_PER_HOUR


def test_goal_parsing_savings_on_rural_sites(settings):
    sites = build_sites(settings.seed)
    goal = parse_goal("Cut diesel on rural sites for the next 6 hours", sites, step=10)
    assert goal.intent == "save_diesel"
    assert all(sites[i].area == "rural" for i in goal.site_indices)
    assert goal.end - goal.start == 6 * STEPS_PER_HOUR
