from dataclasses import dataclass, field

STEP_HOURS = 0.25
STEPS_PER_HOUR = int(1 / STEP_HOURS)
STEPS_PER_DAY = 24 * STEPS_PER_HOUR

SIM_START_ISO = "2026-10-26T05:00:00+02:00"
SIM_START_HOUR = 5


@dataclass(frozen=True)
class Economics:
    diesel_usd_per_litre: float = 1.55
    arpu_usd_per_month: float = 3.0
    crew_cost_usd_per_km: float = 0.45
    battery_usd_per_kwh: float = 180.0

    @property
    def revenue_per_subscriber_hour(self) -> float:
        return self.arpu_usd_per_month / 730.0


@dataclass(frozen=True)
class PowerRules:
    dark_soc: float = 0.05
    recover_soc: float = 0.10
    baseline_gen_start_soc: float = 0.35
    smart_gen_floor_soc: float = 0.20
    smart_gen_stop_soc: float = 0.90
    max_charge_c_rate: float = 0.25
    charge_efficiency: float = 0.92
    gen_min_fuel_l: float = 5.0
    gen_fixed_lph_per_kva: float = 0.06
    gen_variable_l_per_kwh: float = 0.26
    gen_max_load_ratio: float = 0.8


@dataclass(frozen=True)
class SleepRules:
    sleep_below_traffic: float = 0.35
    wake_above_traffic: float = 0.55
    residual_share: float = 0.15


@dataclass(frozen=True)
class FieldOps:
    road_factor: float = 1.3
    crew_speed_kmh: float = 55.0
    security_speed_kmh: float = 70.0
    guard_response_hours: float = 0.25
    baseline_detection_hours: float = 1.0
    baseline_onsite_diagnosis_hours: float = 2.0
    baseline_refuel_interval_hours: float = 96.0
    battery_release_hours_baseline: float = 6.0
    battery_release_hours_powerpilot: float = 2.0
    work_hours: dict = field(default_factory=lambda: {
        "refuel": 0.5,
        "replace_battery": 1.5,
        "repair_link": 2.0,
        "security": 0.25,
    })
    predictive_refuel_runway_hours: float = 36.0


@dataclass(frozen=True)
class Settings:
    seed: int = 2611
    loadshedding_stage: int = 4
    economics: Economics = field(default_factory=Economics)
    power: PowerRules = field(default_factory=PowerRules)
    sleep: SleepRules = field(default_factory=SleepRules)
    field_ops: FieldOps = field(default_factory=FieldOps)
