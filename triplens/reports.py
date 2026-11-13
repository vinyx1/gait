"""Ground-level evidence along a trip: City 311 service requests and rider reports (no AI, no cost).

Two sources, always kept apart and labelled:
  * 311: City of Toronto open data, placed at the nearest intersection (scripts/build_311.py). Shows that
    residents asked the City to fix something there, with dates and status. It is history, not current state.
  * Rider reports: fixed categories a rider can add at a stop or along a walk. No free text, no names, no
    account; stored as category, place and date only. Temporary problems expire.

`search(legs)` is a small retrieval step with a visible trace: what it searched, how far, what it found.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .access import haversine_m

ROOT = Path(__file__).resolve().parent.parent
F311 = ROOT / "data/geo/reports311.json"
DB = ROOT / "data/rider_reports.sqlite"

STOP_M, WALK_M = 60, 35          # how close a report must be to a stop or to the walking line

# rider categories: key -> (label, days it stays shown, roles it matters for)
RIDER_CATS = {
    "no_seat": ("No seat at the stop", 180),
    "shelter_damaged": ("Shelter damaged or missing", 90),
    "stop_blocked": ("Stop blocked (snow, construction, parked vehicle)", 3),
    "stop_dirty": ("Stop very dirty", 7),
    "shelter_full": ("Shelter often full", 30),
    "sidewalk_broken": ("Sidewalk broken or uneven", 180),
    "sidewalk_snow": ("Sidewalk not cleared of snow or ice", 3),
    "curb_ramp": ("Curb ramp missing or blocked", 180),
}

# who each 311 category matters most for (wording stays neutral; this only orders the list)
CAREFUL = {"stop_snow", "sidewalk_snow", "sidewalk_ice", "crossing_snow", "sidewalk_damaged", "curb_damaged"}


@lru_cache(maxsize=1)
def load_311() -> dict:
    if not F311.exists():
        return {"source": None, "requests": []}
    return json.loads(F311.read_text())


def _con():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS r (cat TEXT, lat REAL, lon REAL, stop_id TEXT, day TEXT)")
    return con


def add_report(cat: str, lat: float, lon: float, stop_id: str | None = None, today: date | None = None) -> dict:
    if cat not in RIDER_CATS:
        raise ValueError("unknown category")
    if not (43.5 < lat < 43.9 and -79.7 < lon < -79.1):
        raise ValueError("outside Toronto")
    d = (today or date.today()).isoformat()
    with _con() as con:
        con.execute("INSERT INTO r VALUES (?,?,?,?,?)", (cat, round(lat, 5), round(lon, 5), stop_id, d))
    return {"cat": cat, "label": RIDER_CATS[cat][0], "day": d}


def rider_reports(today: date | None = None) -> list[dict]:
    today = today or date.today()
    if not DB.exists():
        return []
    with _con() as con:
        rows = con.execute("SELECT cat, lat, lon, stop_id, day FROM r").fetchall()
    out = []
    for cat, lat, lon, sid, day in rows:
        label, keep = RIDER_CATS.get(cat, (cat, 0))
        if date.fromisoformat(day) >= today - timedelta(days=keep):
            out.append({"cat": cat, "label": label, "lat": lat, "lon": lon, "stop_id": sid, "day": day})
    return out


def _near_line(lat, lon, pts, r):
    return min((haversine_m(lat, lon, a, b) for a, b in pts), default=1e9) <= r


def _places(legs):
    """Places to search: the boarding and exit stop of each ride, and each walking leg's line."""
    out = []
    for l in legs:
        if l.kind == "transit":
            for role, s in (("Boarding stop", l.board), ("Exit stop", l.alight)):
                out.append(("stop", f"{role}: {s['name']} ({l.route})", [(s["lat"], s["lon"])], STOP_M))
        else:
            out.append(("walk", l.label, _densify(l.points), WALK_M))
    return out


def _densify(pts, step_m: float = 20):
    """Add points every `step_m` so a straight two-point walk is searched along its length, not just its ends."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(haversine_m(a[0], a[1], b[0], b[1]) // step_m))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def council_candidates(legs, per_route: int = 4) -> list[dict]:
    """Unchecked sentences from staff reports found by the free search (data/research_free) for the routes in
    this trip. Sentences naming a street at the rider's own stops come first. These are leads, not results."""
    out = []
    for l in legs:
        if l.kind != "transit":
            continue
        p = ROOT / "data/research_free" / f"route-{l.route}.json"
        if not p.exists():
            continue
        mine = {w for s in (l.board, l.alight) for w in s["name"].replace(" at ", "|").split("|")}
        mine = {m.strip().replace(" West", "").replace(" East", "") for m in mine}
        fs = json.loads(p.read_text())["findings"]
        for f in fs:
            f["at_your_stops"] = [n for n in f["stops_named"] if n in mine]
        fs.sort(key=lambda f: (-bool(f["at_your_stops"]), -f["score"]))
        out += [{**f, "route": l.route} for f in fs[:per_route]]
    return out


def search(legs, today: date | None = None) -> dict:
    trace, groups = [], []
    reqs, riders = load_311()["requests"], rider_reports(today)
    seen = set()                                   # a request near a stop is not listed again for the walk beside it
    for kind, name, pts, r in sorted(_places(legs), key=lambda p: p[0] != "stop"):
        lat0 = sum(p[0] for p in pts) / len(pts)
        box = max(abs(p[0] - lat0) for p in pts) + r / 111320 + 1e-4
        near = [q for q in reqs if id(q) not in seen and abs(q["lat"] - lat0) <= box and _near_line(q["lat"], q["lon"], pts, r)]
        rr = [q for q in riders if (q["lat"], q["lon"], q["cat"], q["day"]) not in seen
              and abs(q["lat"] - lat0) <= box and _near_line(q["lat"], q["lon"], pts, r)]
        seen |= {id(q) for q in near} | {(q["lat"], q["lon"], q["cat"], q["day"]) for q in rr}
        by = defaultdict(list)
        for q in near:
            by[q["label"]].append(q)
        s311 = [{"label": k, "count": len(v), "latest": max(x["date"] for x in v), "open": sum(x["status"] not in ("Completed", "Closed") for x in v),
                 "at": sorted({x["at"] for x in v})[:3], "careful": v[0]["cat"] in CAREFUL, "lat": v[0]["lat"], "lon": v[0]["lon"]}
                for k, v in by.items()]
        s311.sort(key=lambda g: (-g["careful"], -g["count"]))
        trace.append(f"{name}: searched 311 requests within {r} m ({len(near)} found) and rider reports ({len(rr)} found).")
        if s311 or rr:
            groups.append({"place": name, "kind": kind, "radius_m": r, "s311": s311, "riders": rr})
    leads = council_candidates(legs)
    routes = sorted({l.route for l in legs if l.kind == "transit"})
    trace.append(f"Staff reports: {len(leads)} unchecked sentences from the free search of indexed reports for route {', '.join(routes)}.")
    src = load_311()
    return {"groups": groups, "trace": trace, "leads": leads, "source_311": src.get("source"), "files_311": src.get("files", [])}
