"""Run both twins side by side and print what PowerPilot changes.

    python -m powerpilot.benchmark --days 7 --stage 4
"""

import argparse
import json
import time
from dataclasses import replace

from .config import STEPS_PER_DAY, Settings
from .engine import Engine


def run(days: int, stage: int, seed: int, autonomy: str = "autopilot") -> dict:
    settings = replace(Settings(), loadshedding_stage=stage, seed=seed)
    engine = Engine(settings, autonomy=autonomy)
    engine.tick(days * STEPS_PER_DAY - 1)
    report = engine.kpis()
    report["days"] = days
    report["stage"] = stage
    report["seed"] = seed
    report["models"] = engine.meta()["models"]
    return report


def _row(label: str, base: float, pilot: float, unit: str = "", invert: bool = False) -> str:
    change = pilot - base
    pct = (change / base * 100) if base else 0.0
    sign = "-" if change < 0 else "+"
    better = (change < 0) != invert
    mark = "better" if better and change != 0 else ("worse" if change != 0 else "same")
    return f"  {label:<28}{base:>12,.1f}{pilot:>12,.1f}  {sign}{abs(pct):5.1f}% {unit:<6} {mark}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--stage", type=int, default=4)
    parser.add_argument("--seed", type=int, default=Settings().seed)
    parser.add_argument("--json", action="store_true", help="print the raw report as JSON")
    args = parser.parse_args()

    started = time.perf_counter()
    report = run(args.days, args.stage, args.seed)
    if args.json:
        print(json.dumps(report, indent=2))
        return

    base, pilot, saved = report["baseline"], report["powerpilot"], report["savings"]
    print(f"\nPowerPilot benchmark: {args.days} days, Stage {args.stage} load-shedding, 30 simulated Midlands sites\n")
    print(f"  {'':<28}{'Legacy ops':>12}{'PowerPilot':>12}")
    print(_row("Site outage hours", base["outage_site_hours"], pilot["outage_site_hours"], "h"))
    print(_row("Subscriber-hours lost", base["subscriber_hours_lost"] / 1000, pilot["subscriber_hours_lost"] / 1000, "k"))
    print(_row("Diesel burned", base["diesel_burned_l"], pilot["diesel_burned_l"], "L"))
    print(_row("Diesel stolen", base["diesel_stolen_l"], pilot["diesel_stolen_l"], "L"))
    print(_row("Battery stolen", base["battery_stolen_kwh"], pilot["battery_stolen_kwh"], "kWh"))
    print(_row("Generator run hours", base["generator_hours"], pilot["generator_hours"], "h"))
    print(_row("Crew km driven", base["trip_km"], pilot["trip_km"], "km"))
    print(_row("Revenue lost", base["revenue_lost_usd"], pilot["revenue_lost_usd"], "USD"))
    print(_row("Total cost", base["total_cost_usd"], pilot["total_cost_usd"], "USD"))
    availability = report["availability"]
    print(f"\n  Availability  legacy {availability['baseline']:.3%}, PowerPilot {availability['powerpilot']:.3%}")
    print(f"  Net saving    ${saved['cost_usd']:,.0f} over {args.days} days on 30 sites")
    for card in report["models"]:
        metrics = ", ".join(f"{k}={v}" for k, v in card["metrics"].items())
        print(f"  Model         {card['name']}: {metrics}")
    print(f"\n  Ran in {time.perf_counter() - started:.1f} s\n")


if __name__ == "__main__":
    main()
