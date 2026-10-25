"""Synthetic catalogue of Midlands base stations used by the simulator.

Coordinates are approximate and the power configuration of every site is
generated, not taken from any operator's records.
"""

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Depot:
    id: str
    name: str
    lat: float
    lon: float
    crews: int


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    town: str
    lat: float
    lon: float
    area: str
    zone: str
    subscribers: int
    layers: tuple[str, ...]
    has_grid: bool
    battery_kwh: float
    gen_kva: float
    tank_l: float
    solar_kw: float
    guarded: bool
    idle_kw: float
    traffic_kw: float
    sleepable_kw: float

    @property
    def has_generator(self) -> bool:
        return self.gen_kva > 0


DEPOTS: tuple[Depot, ...] = (
    Depot("DEP-GWE", "Gweru depot", -19.4550, 29.8100, 3),
    Depot("DEP-KWE", "Kwekwe depot", -18.9300, 29.8150, 2),
    Depot("DEP-ZVI", "Zvishavane depot", -20.3270, 30.0660, 2),
    Depot("DEP-GOK", "Gokwe depot", -18.2100, 28.9350, 1),
)

_CATALOGUE = (
    ("GWE-001", "Gweru CBD", "Gweru", -19.4560, 29.8120, "urban", "A", 14000, ("2G", "3G", "4G", "5G")),
    ("GWE-002", "Mkoba", "Gweru", -19.4600, 29.7650, "urban", "B", 12000, ("2G", "3G", "4G")),
    ("GWE-003", "Senga", "Gweru", -19.5160, 29.8350, "urban", "C", 11000, ("2G", "3G", "4G")),
    ("GWE-004", "Mtapa", "Gweru", -19.4420, 29.7900, "urban", "D", 9000, ("2G", "3G", "4G")),
    ("GWE-005", "Ascot", "Gweru", -19.4650, 29.8350, "urban", "A", 7000, ("2G", "3G", "4G")),
    ("GWE-006", "Ivene", "Gweru", -19.4950, 29.7700, "peri", "B", 5000, ("2G", "3G", "4G")),
    ("GWE-007", "Woodlands", "Gweru", -19.4250, 29.8200, "peri", "C", 4500, ("2G", "3G", "4G")),
    ("KWE-001", "Kwekwe CBD", "Kwekwe", -18.9280, 29.8150, "urban", "A", 12000, ("2G", "3G", "4G", "5G")),
    ("KWE-002", "Mbizo", "Kwekwe", -18.9480, 29.7900, "urban", "B", 10000, ("2G", "3G", "4G")),
    ("KWE-003", "Amaveni", "Kwekwe", -18.9150, 29.8350, "urban", "C", 8000, ("2G", "3G", "4G")),
    ("RED-001", "Redcliff", "Redcliff", -19.0330, 29.7830, "peri", "D", 6000, ("2G", "3G", "4G")),
    ("ZVI-001", "Zvishavane CBD", "Zvishavane", -20.3270, 30.0660, "urban", "A", 9000, ("2G", "3G", "4G")),
    ("ZVI-002", "Mandava", "Zvishavane", -20.3400, 30.0450, "urban", "B", 7000, ("2G", "3G", "4G")),
    ("SHU-001", "Shurugwi", "Shurugwi", -19.6700, 30.0000, "peri", "C", 6000, ("2G", "3G", "4G")),
    ("GOK-001", "Gokwe Centre", "Gokwe", -18.2100, 28.9350, "peri", "D", 7000, ("2G", "3G", "4G")),
    ("GOK-002", "Nembudziya", "Gokwe", -17.8950, 28.8600, "rural", "A", 2500, ("2G", "3G")),
    ("GOK-003", "Manoti", "Gokwe", -18.3200, 28.9500, "rural", "B", 1800, ("2G", "3G")),
    ("GOK-004", "Kana", "Gokwe", -18.4500, 28.8200, "rural", "C", 1400, ("2G", "3G")),
    ("MVU-001", "Mvuma", "Mvuma", -19.2790, 30.5280, "peri", "D", 4000, ("2G", "3G", "4G")),
    ("LAL-001", "Lalapanzi", "Lalapanzi", -19.3330, 30.1830, "rural", "A", 1800, ("2G", "3G")),
    ("SIL-001", "Silobela", "Silobela", -18.9540, 29.3580, "rural", "B", 2600, ("2G", "3G", "4G")),
    ("ZHO-001", "Zhombe", "Zhombe", -18.6300, 29.3700, "rural", "C", 2200, ("2G", "3G")),
    ("MBE-001", "Mberengwa", "Mberengwa", -20.4850, 29.9150, "rural", "D", 2400, ("2G", "3G", "4G")),
    ("MAT-001", "Mataga", "Mberengwa", -20.7350, 29.9300, "rural", "A", 2000, ("2G", "3G")),
    ("CHI-001", "Holy Cross", "Chirumhanzu", -19.6900, 30.3600, "rural", "B", 1500, ("2G", "3G")),
    ("LGW-001", "Lower Gweru", "Lower Gweru", -19.3700, 29.5200, "rural", "C", 2000, ("2G", "3G")),
    ("TON-001", "Tongogara", "Shurugwi", -19.7300, 29.9600, "rural", "D", 1700, ("2G", "3G")),
    ("MAB-001", "Maboleni", "Lower Gweru", -19.2700, 29.6200, "rural", "A", 1200, ("2G", "3G")),
    ("CHA-001", "Charandura", "Chirumhanzu", -19.8500, 30.2500, "rural", "B", 1300, ("2G", "3G")),
    ("SEB-001", "Sebakwe", "Kwekwe", -18.9500, 30.0500, "rural", "C", 1600, ("2G", "3G")),
)

_AREA_PROFILE = {
    "urban": dict(battery=(18, 30), kva=(15, 20), tank=(600, 1000), solar=(0, 3), idle=3.2, traffic=2.0, sleep=1.4),
    "peri": dict(battery=(12, 20), kva=(10, 15), tank=(400, 600), solar=(2, 5), idle=2.4, traffic=1.2, sleep=0.8),
    "rural": dict(battery=(8, 16), kva=(8, 12), tank=(250, 450), solar=(3, 8), idle=1.6, traffic=0.8, sleep=0.4),
}


def _build_site(rng: np.random.Generator, row: tuple) -> Site:
    site_id, name, town, lat, lon, area, zone, subscribers, layers = row
    profile = _AREA_PROFILE[area]
    rural = area == "rural"
    has_grid = not (rural and rng.random() < 0.2)
    has_generator = not rural or rng.random() < 0.6 or not has_grid
    return Site(
        id=site_id,
        name=name,
        town=town,
        lat=lat,
        lon=lon,
        area=area,
        zone=zone,
        subscribers=subscribers,
        layers=layers,
        has_grid=has_grid,
        battery_kwh=round(float(rng.uniform(*profile["battery"])), 1),
        gen_kva=round(float(rng.uniform(*profile["kva"]))) if has_generator else 0.0,
        tank_l=round(float(rng.uniform(*profile["tank"])), -1) if has_generator else 0.0,
        solar_kw=round(float(rng.uniform(*profile["solar"])), 1),
        guarded=area == "urban" or rng.random() < 0.25,
        idle_kw=profile["idle"],
        traffic_kw=profile["traffic"],
        sleepable_kw=profile["sleep"] if len(layers) > 2 else profile["sleep"] * 0.5,
    )


def build_sites(seed: int) -> tuple[Site, ...]:
    rng = np.random.default_rng(seed)
    return tuple(_build_site(rng, row) for row in _CATALOGUE)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_depot(site: Site) -> tuple[Depot, float]:
    ranked = sorted(DEPOTS, key=lambda d: haversine_km(site.lat, site.lon, d.lat, d.lon))
    depot = ranked[0]
    return depot, haversine_km(site.lat, site.lon, depot.lat, depot.lon)
