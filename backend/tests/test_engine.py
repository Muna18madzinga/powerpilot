from powerpilot.config import STEPS_PER_DAY, STEPS_PER_HOUR
from powerpilot.engine import Engine


def test_models_are_trained_with_useful_accuracy(models):
    assert models.risk.card.metrics["roc_auc"] > 0.85
    assert models.theft.card.metrics["recall_on_tamper_steps"] > 0.7
    assert models.theft.card.metrics["false_alarm_rate"] < 0.01


def test_battery_theft_raises_a_security_recommendation(engine):
    engine.inject("battery_theft", "SIL-001")
    engine.tick(3)
    security = [r for r in engine.open_recommendations() if r.kind == "security"]
    assert security and engine.sites[security[0].site_index].id == "SIL-001"
    assert security[0].urgency == "critical"
    assert [stage["stage"] for stage in security[0].trail] == ["Monitor", "Diagnose", "Plan", "Dispatch"]


def test_approving_dispatches_a_crew_and_closes_when_done(engine):
    engine.inject("link_fault", "GWE-002")
    engine.tick(2)
    rec = next(r for r in engine.open_recommendations() if r.kind == "repair_link")
    engine.approve(rec.id)
    assert rec.status == "approved" and rec.job_id
    engine.tick(6 * STEPS_PER_HOUR)
    assert rec.status == "done"
    assert engine.pilot.states[engine.site_index("GWE-002")].status != "link_down"


def test_rejecting_holds_the_recommendation_back(engine):
    engine.inject("link_fault", "KWE-002")
    engine.tick(2)
    rec = next(r for r in engine.open_recommendations() if r.kind == "repair_link")
    engine.reject(rec.id)
    engine.tick(2)
    assert not any(r.kind == "repair_link" and r.status == "pending" for r in engine.open_recommendations())


def test_advise_mode_waits_for_approval_before_changing_controls(settings, models):
    engine = Engine(settings, autonomy="advise", models=models)
    assert not any(s.sleep_enabled for s in engine.pilot.states)
    rec = next(r for r in engine.open_recommendations() if r.kind == "enable_controls")
    engine.approve(rec.id)
    assert all(s.sleep_enabled and s.smart_genset for s in engine.pilot.states)


def test_goal_creates_a_plan(engine):
    record = engine.set_goal("Keep Gweru CBD up for the next 8 hours")
    view = engine.goal_view(record)
    assert view["scope"] == "Gweru CBD"
    assert view["sites"] == ["GWE-001"]
    assert len(view["steps"]) == 3


def test_powerpilot_beats_legacy_operations_over_two_days(settings, models):
    engine = Engine(settings, autonomy="autopilot", models=models)
    engine.tick(2 * STEPS_PER_DAY)
    kpis = engine.kpis()
    assert kpis["powerpilot"]["outage_site_hours"] <= kpis["baseline"]["outage_site_hours"]
    assert kpis["powerpilot"]["diesel_burned_l"] < kpis["baseline"]["diesel_burned_l"]
    assert kpis["savings"]["cost_usd"] > 0


def test_site_detail_contains_history_and_schedule(engine):
    engine.tick(8)
    view = engine.site_view(0, detail=True)
    assert len(view["history"]) == 9
    assert len(view["schedule"]) == 24 * STEPS_PER_HOUR
    assert len(view["forecast_traffic"]) == 24 * STEPS_PER_HOUR
