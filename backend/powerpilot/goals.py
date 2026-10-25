"""Plain-language operating goals, e.g. "Keep Gweru up tonight"."""

import re
from dataclasses import dataclass

from .config import STEPS_PER_HOUR
from .environment import hour_of_day
from .sites import Site

PROTECT_WORDS = ("keep", "protect", "up", "online", "uptime", "on air", "priorit", "no outage", "available")
SAVE_WORDS = ("diesel", "fuel", "save", "saving", "cost", "cheap", "cut", "reduce", "economi")


@dataclass(frozen=True)
class Goal:
    text: str
    intent: str
    site_indices: tuple[int, ...]
    start: int
    end: int
    scope_label: str
    window_label: str


def _steps_until_hour(step: int, target_hour: float) -> int:
    delta = (target_hour - hour_of_day(step)) % 24
    return int(round(delta * STEPS_PER_HOUR))


def _window(text: str, step: int) -> tuple[int, int, str]:
    hours = re.search(r"next\s+(\d{1,2})\s*(h|hr|hrs|hour|hours)\b", text)
    if hours:
        span = int(hours.group(1))
        return step, step + span * STEPS_PER_HOUR, f"next {span} h"
    if "tonight" in text or "overnight" in text:
        hour = hour_of_day(step)
        start = step if hour >= 18 or hour < 4 else step + _steps_until_hour(step, 18)
        return start, start + _steps_until_hour(start, 6), "tonight (18:00–06:00)"
    if "tomorrow" in text:
        start = step + _steps_until_hour(step, 6)
        return start, start + 18 * STEPS_PER_HOUR, "tomorrow (06:00–24:00)"
    if "today" in text:
        return step, step + (_steps_until_hour(step, 0) or 24 * STEPS_PER_HOUR), "rest of today"
    if "weekend" in text or "week" in text:
        return step, step + 48 * STEPS_PER_HOUR, "next 48 h"
    return step, step + 12 * STEPS_PER_HOUR, "next 12 h"


def _scope(text: str, sites: tuple[Site, ...]) -> tuple[tuple[int, ...], str]:
    def matches(token: str) -> bool:
        return re.search(rf"\b{re.escape(token.lower())}\b", text) is not None

    named = [i for i, site in enumerate(sites) if matches(site.name) or matches(site.id)]
    if named:
        indices, label = named, ", ".join(sites[i].name for i in named)
    else:
        towns = list(dict.fromkeys(site.town for site in sites if matches(site.town)))
        indices = [i for i, site in enumerate(sites) if site.town in towns]
        label = ", ".join(towns) if towns else "all Midlands sites"
        if not indices:
            indices = list(range(len(sites)))

    areas = [area for area in ("rural", "urban") if area in text]
    if areas:
        allowed = set(areas) | ({"peri"} if "urban" in areas else set())
        indices = [i for i in indices if sites[i].area in allowed]
        label = f"{' and '.join(areas)} sites" + ("" if label == "all Midlands sites" else f" in {label}")
    return tuple(indices), label


def _mentions(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}", text) for word in words)


def parse_goal(text: str, sites: tuple[Site, ...], step: int) -> Goal:
    lowered = " ".join(text.lower().split())
    save = _mentions(lowered, SAVE_WORDS)
    protect = _mentions(lowered, PROTECT_WORDS)
    intent = "save_diesel" if save and not protect else "protect_uptime"
    indices, scope_label = _scope(lowered, sites)
    start, end, window_label = _window(lowered, step)
    return Goal(text.strip(), intent, indices, start, max(end, start + STEPS_PER_HOUR), scope_label, window_label)
