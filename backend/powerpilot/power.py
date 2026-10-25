"""Energy balance for a single base station over one time step."""

from dataclasses import dataclass

from .config import PowerRules, SleepRules


@dataclass(frozen=True)
class PowerInput:
    battery_kwh: float
    soc: float
    fuel_l: float
    gen_kva: float
    gen_on: bool
    smart: bool
    grid_on: bool
    solar_kw: float
    load_kw: float
    hours_to_grid: float | None
    dark: bool


@dataclass(frozen=True)
class PowerResult:
    soc: float
    gen_on: bool
    fuel_burned_l: float
    gen_kw: float
    grid_kwh: float
    powered: bool


def site_load_kw(idle_kw: float, traffic_kw: float, sleepable_kw: float,
                 traffic: float, sleeping: bool, rules: SleepRules) -> float:
    saving = sleepable_kw * (1 - rules.residual_share) if sleeping else 0.0
    return idle_kw + traffic * traffic_kw - saving


def generator_max_kw(gen_kva: float) -> float:
    return gen_kva * 0.8


def generator_lph(gen_kva: float, output_kw: float, rules: PowerRules) -> float:
    return gen_kva * rules.gen_fixed_lph_per_kva + rules.gen_variable_l_per_kwh * output_kw


def battery_runway_hours(battery_kwh: float, soc: float, net_kw: float, rules: PowerRules) -> float:
    usable = max(0.0, soc - rules.dark_soc) * battery_kwh
    return usable / max(net_kw, 0.1)


def _generator_decision(p: PowerInput, net_kw: float, rules: PowerRules) -> bool:
    can_run = p.gen_kva > 0 and p.fuel_l > rules.gen_min_fuel_l
    if not can_run:
        return False
    no_battery = p.battery_kwh < 1.0
    if not p.smart:
        return p.gen_on or no_battery or p.soc <= rules.baseline_gen_start_soc
    if p.gen_on:
        return no_battery or p.soc < rules.smart_gen_stop_soc
    if no_battery or p.soc <= rules.smart_gen_floor_soc:
        return True
    if p.soc <= rules.baseline_gen_start_soc:
        runway = battery_runway_hours(p.battery_kwh, p.soc - (rules.smart_gen_floor_soc - rules.dark_soc), net_kw, rules)
        return p.hours_to_grid is None or runway < p.hours_to_grid
    return False


def step_power(p: PowerInput, rules: PowerRules, dt: float) -> PowerResult:
    cap = max(p.battery_kwh, 1e-6)
    max_charge = p.battery_kwh * rules.max_charge_c_rate
    load = 0.0 if p.dark else p.load_kw

    if p.grid_on:
        headroom = max(0.0, (1 - p.soc) * cap / dt / rules.charge_efficiency)
        charge = min(max_charge, headroom)
        soc = min(1.0, p.soc + charge * dt * rules.charge_efficiency / cap) if p.battery_kwh >= 1 else p.soc
        return PowerResult(soc, False, 0.0, 0.0, (p.load_kw + charge) * dt, True)

    net = p.load_kw - p.solar_kw
    gen_on = _generator_decision(p, net, rules)
    fuel = 0.0
    gen_kw = 0.0
    if gen_on:
        charge_target = max_charge if p.smart else (1.0 if p.soc < 0.98 else 0.0)
        gen_kw = min(generator_max_kw(p.gen_kva), max(net, 0.0) + charge_target)
        fuel = min(p.fuel_l, generator_lph(p.gen_kva, gen_kw, rules) * dt)
        surplus = gen_kw - net
    else:
        surplus = -(load - p.solar_kw)

    if p.battery_kwh < 1.0:
        return PowerResult(p.soc, gen_on, fuel, gen_kw, 0.0, gen_on and surplus >= -1e-6)

    delta = min(surplus, max_charge) * rules.charge_efficiency if surplus > 0 else surplus
    soc = min(1.0, max(0.0, p.soc + delta * dt / cap))
    threshold = rules.recover_soc if p.dark else rules.dark_soc
    powered = gen_on or soc > threshold
    return PowerResult(soc, gen_on, fuel, gen_kw, 0.0, powered)
