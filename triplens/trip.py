"""Build a resident's trip from the route and stops they tell us they use.

The transit part follows the real line the TTC vehicle runs (from the GTFS shapes), cut between the stop where the
rider gets on and the stop where they get off. Walking parts are straight lines, which is an estimate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import access

ROUTES = Path(__file__).resolve().parent.parent / "data/geo/routes.json"


@lru_cache(maxsize=1)
def load_routes() -> dict[str, dict]:
    return {e["short"]: e for e in json.loads(ROUTES.read_text())["routes"]}


@lru_cache(maxsize=1)
def stop_records() -> dict[str, dict]:
    return {s["stop_id"]: s for s in access.load_stops()["stops"]}


def route_choices() -> list[tuple[str, str]]:
    return [(e["short"], e["long"]) for e in load_routes().values()]


@dataclass
class Leg:
    kind: str                     # "walk" or "transit"
    label: str
    points: list                  # [(lat, lon), ...]
    route: str | None = None
    board: dict | None = None     # stop record from stops.json
    alight: dict | None = None

    @property
    def length_m(self) -> int:
        return round(sum(access.haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(self.points, self.points[1:])))


def variant_stops(route: str, vi: int) -> list[dict]:
    return load_routes()[route]["variants"][vi]["stops"]


def build_transit_leg(route: str, vi: int, board_id: str, alight_id: str) -> Leg:
    v = load_routes()[route]["variants"][vi]
    ids = [s["id"] for s in v["stops"]]
    if board_id not in ids or alight_id not in ids:
        raise ValueError("That stop is not on this route and direction.")
    bi, ai = ids.index(board_id), ids.index(alight_id)
    if ai <= bi:
        raise ValueError("The stop where you get off must come after the stop where you get on, in the direction of travel.")
    b, a = v["stops"][bi], v["stops"][ai]
    pts = [tuple(p) for p in v["shape"][b["v"]:a["v"] + 1]]
    rec = stop_records()
    return Leg("transit", f"{route} {load_routes()[route]['long']}", pts, route,
               rec.get(board_id) or {"stop_id": board_id, "name": b["name"], "lat": b["lat"], "lon": b["lon"]},
               rec.get(alight_id) or {"stop_id": alight_id, "name": a["name"], "lat": a["lat"], "lon": a["lon"]})


def build_trip(origin: tuple[float, float], dest: tuple[float, float], rides: list[tuple[str, int, str, str]]) -> list[Leg]:
    legs: list[Leg] = []
    cur = origin
    for route, vi, board_id, alight_id in rides:
        t = build_transit_leg(route, vi, board_id, alight_id)
        b = (t.board["lat"], t.board["lon"])
        legs.append(Leg("walk", f"Walk to {t.board['name']}", [cur, b]))
        legs.append(t)
        cur = (t.alight["lat"], t.alight["lon"])
    legs.append(Leg("walk", "Walk to your destination", [cur, dest]))
    return legs
