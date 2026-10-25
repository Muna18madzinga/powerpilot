from powerpilot.config import PowerRules
from powerpilot.power import PowerInput, step_power

RULES = PowerRules()


def make(**overrides) -> PowerInput:
    values = dict(
        battery_kwh=20.0, soc=0.5, fuel_l=200.0, gen_kva=12.0, gen_on=False, smart=False,
        grid_on=False, solar_kw=0.0, load_kw=4.0, hours_to_grid=2.0, dark=False,
    )
    values.update(overrides)
    return PowerInput(**values)


def test_grid_charges_battery_and_stops_generator():
    result = step_power(make(grid_on=True, gen_on=True, soc=0.4), RULES, 0.25)
    assert result.soc > 0.4
    assert not result.gen_on
    assert result.fuel_burned_l == 0


def test_legacy_control_starts_generator_at_threshold():
    result = step_power(make(soc=0.34), RULES, 0.25)
    assert result.gen_on
    assert result.fuel_burned_l > 0


def test_smart_control_waits_when_battery_reaches_the_grid_window():
    result = step_power(make(soc=0.34, smart=True, hours_to_grid=0.5), RULES, 0.25)
    assert not result.gen_on


def test_smart_control_runs_when_battery_cannot_bridge():
    result = step_power(make(soc=0.30, smart=True, hours_to_grid=6.0), RULES, 0.25)
    assert result.gen_on


def test_smart_cycle_charging_burns_less_per_kwh_than_follow_load():
    legacy = step_power(make(soc=0.3, gen_on=True), RULES, 1.0)
    smart = step_power(make(soc=0.3, gen_on=True, smart=True, hours_to_grid=None), RULES, 1.0)
    assert smart.gen_kw > legacy.gen_kw
    assert smart.fuel_burned_l / smart.gen_kw < legacy.fuel_burned_l / legacy.gen_kw


def test_battery_only_site_goes_dark_when_empty():
    result = step_power(make(gen_kva=0.0, fuel_l=0.0, soc=0.06), RULES, 0.25)
    assert not result.powered
