"""Transit access for different riders around a location, from open data.

Everything here is deterministic. Numbers come from the TTC GTFS feed and City of Toronto open data.
Walking distance is straight-line distance times a detour factor, because we do not route on the real
sidewalk network. Personas are illustrative assumptions, not medical or legal definitions.
"""
from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "data/geo"
DETOUR = 1.3  # straight-line to walking distance, an assumption


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    max_walk_m: int
    note: str


PERSONAS = {
    "wheelchair": Persona("wheelchair", "Wheelchair user", 400,
                          "Needs a stop where boarding is marked possible. Walk limit is an assumption and varies a lot between people."),
    "senior_walker": Persona("senior_walker", "Senior using a cane or walker", 250,
                             "Shorter walks, and benefits from a shelter or bench. Walk limit is an assumption."),
    "shift_worker": Persona("shift_worker", "Shift worker (late nights and early mornings)", 600,
                            "Needs service after 23:00 and before 05:30. Walk limit is an assumption."),
}

WC_TEXT = {"1": "possible (GTFS 1)", "2": "not possible (GTFS 2)", "0": "unknown, no information (GTFS 0)"}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * 111320
    dx = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


@lru_cache(maxsize=1)
def load_stops() -> dict:
    d = json.loads((GEO / "stops.json").read_text())
    return d


def stops_near(lat: float, lon: float, radius_m: float) -> list[dict]:
    out = []
    for s in load_stops()["stops"]:
        if abs(s["lat"] - lat) > radius_m / 111320 + 1e-4:
            continue
        d = haversine_m(lat, lon, s["lat"], s["lon"])
        if d <= radius_m:
            out.append({**s, "distance_m": round(d)})
    out.sort(key=lambda s: s["distance_m"])
    return out


def _hh(s: str | None) -> str:
    return s or "none"


def stop_line(s: dict) -> str:
    """One text line per stop. Agents cite exact pieces of this text, so keep it stable."""
    wd = s["service"].get("weekday")
    late = sum(c for h, c in (wd or {}).get("per_hour", {}).items() if int(h) >= 23) if wd else 0
    parts = [
        f"stop {s['stop_id']}", s["name"],
        f"{s['distance_m']} m straight-line (about {round(s['distance_m'] * DETOUR)} m walking)" if "distance_m" in s else "",
        f"wheelchair boarding: {WC_TEXT.get(s['wheelchair_boarding'], 'unknown')}",
        f"shelter listed in City data: {'yes' if s['shelter_listed'] else 'no'}",
        f"bench listed in City data: {'yes' if s['bench_listed'] else 'no'}",
        "routes: " + (", ".join(s["routes"]) if s["routes"] else "none"),
    ]
    if wd:
        parts.append(f"weekday first departure {wd['first']}, last departure {wd['last']}, {wd['departures']} departures, {late} departures at or after 23:00")
    else:
        parts.append("no weekday service in the base schedule")
    sat, sun = s["service"].get("saturday"), s["service"].get("sunday")
    parts.append(f"saturday departures {sat['departures'] if sat else 0}, sunday departures {sun['departures'] if sun else 0}")
    tf = s.get("trip_flags")
    if tf:
        parts.append(f"trips flagged wheelchair accessible: {round(tf['accessible'] * 100)}%, flagged not accessible: "
                     f"{round(tf['not_accessible'] * 100)}%, no information: {round(tf['no_information'] * 100)}%")
    return " | ".join(p for p in parts if p)


def snapshot(lat: float, lon: float, persona_key: str) -> dict:
    """Rule-based access summary. Each flag lists the stop records it is based on."""
    p = PERSONAS[persona_key]
    radius_straight = p.max_walk_m / DETOUR
    near = stops_near(lat, lon, radius_straight)
    flags = []

    def flag(code, severity, text, stops):
        flags.append({"code": code, "severity": severity, "text": text, "stops": [s["stop_id"] for s in stops]})

    if not near:
        flag("no_stops", "barrier", f"No stop within about {p.max_walk_m} m of walking from this point.", [])
    if persona_key == "wheelchair" and near:
        def trips_ok(s):
            tf = s.get("trip_flags")
            return bool(tf and tf["accessible"] > 0)
        ok = [s for s in near if s["wheelchair_boarding"] == "1" and trips_ok(s)]
        stop_ok_no_trips = [s for s in near if s["wheelchair_boarding"] == "1" and not trips_ok(s)]
        notok = [s for s in near if s["wheelchair_boarding"] == "2"]
        unk = [s for s in near if s["wheelchair_boarding"] == "0"]
        if not ok:
            far = [s for s in stops_near(lat, lon, 1500) if s["wheelchair_boarding"] == "1" and trips_ok(s)][:1]
            extra = f" The nearest stop with boarding possible and some trips flagged accessible is about {round(far[0]['distance_m'] * DETOUR)} m of walking away." if far else ""
            flag("no_accessible_stop", "barrier",
                 f"No stop within about {p.max_walk_m} m has boarding listed as possible together with trips flagged accessible. "
                 f"{len(notok)} stops are listed as not possible, {len(unk)} unknown, and {len(stop_ok_no_trips)} are listed as possible "
                 f"but none of their trips are flagged accessible.{extra}", (stop_ok_no_trips + notok + unk)[:3] + far)
        else:
            n0 = near[0]
            if n0 is not ok[0]:
                flag("nearest_not_usable", "watch",
                     f"The nearest stop ({n0['name']}) lists boarding as {WC_TEXT[n0['wheelchair_boarding']]}"
                     + (" and none of its trips are flagged accessible" if n0["wheelchair_boarding"] == "1" else "")
                     + f". The nearest stop that works on both counts is {ok[0]['name']}, about {round(ok[0]['distance_m'] * DETOUR)} m of walking.",
                     [n0, ok[0]])
            if not ok[0]["shelter_listed"]:
                flag("no_shelter_listed", "watch",
                     f"No shelter is listed in City data at {ok[0]['name']}. 'Not listed' can mean the dataset is incomplete.", [ok[0]])
            tf = ok[0]["trip_flags"]
            if tf["accessible"] < 1:
                flag("some_trips_not_flagged", "watch",
                     f"At {ok[0]['name']}, {round(tf['accessible'] * 100)}% of scheduled trips are flagged accessible, "
                     f"{round(tf['not_accessible'] * 100)}% flagged not accessible and {round(tf['no_information'] * 100)}% have no information.", [ok[0]])
    if persona_key == "senior_walker" and near:
        comfy = [s for s in near if s["shelter_listed"] or s["bench_listed"]]
        if round(near[0]["distance_m"] * DETOUR) > p.max_walk_m:
            flag("far", "barrier", "The nearest stop is farther than the assumed walking limit.", [near[0]])
        if not comfy:
            flag("no_seating", "watch", "No stop within the walking limit lists a shelter or bench in City data.", near[:3])
    if persona_key == "shift_worker" and near:
        late = [s for s in near if sum(c for h, c in s["service"].get("weekday", {}).get("per_hour", {}).items() if int(h) >= 23) > 0]
        if not late:
            flag("no_late_service", "barrier", "No stop within walking range has weekday departures at or after 23:00.", near[:3])
        early = [s for s in near if s["service"].get("weekday") and s["service"]["weekday"]["first"] < "05:30"]
        if not early:
            flag("no_early_service", "watch", "No stop within walking range has a weekday departure before 05:30.", near[:3])
    return {"persona": persona_key, "label": p.label, "max_walk_m": p.max_walk_m, "note": p.note,
            "radius_straight_m": round(radius_straight), "detour_factor": DETOUR,
            "stops": [{**s, "line": stop_line(s)} for s in near[:10]], "stop_count": len(near), "flags": flags}


# ---------- planned works (road resurfacing and sidewalk construction) ----------

def _segments(geom: dict):
    t, c = geom.get("type"), geom.get("coordinates") or []
    if t == "LineString":
        yield c
    elif t == "MultiLineString":
        yield from c
    elif t == "Point":
        yield [c]
    elif t == "MultiPoint":
        for p in c:
            yield [p]


def _dist_point_to_line_m(lat, lon, line) -> float:
    best = 1e12
    k = 111320 * math.cos(math.radians(lat))
    px, py = lon * k, lat * 111320
    pts = [(x * k, y * 111320) for x, y in line]
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], py - pts[0][1])
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def _clean(s: str | None) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<br\s*/?>", "; ", s, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip(" ;")


@lru_cache(maxsize=1)
def _works() -> list[dict]:
    import csv
    out = []
    for name, prog in (("road-resurfacing-program", "Road resurfacing program"),
                       ("sidewalk-construction-program", "Sidewalk construction program")):
        with open(GEO / f"{name}.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    geom = json.loads(r["geometry"])
                except Exception:
                    continue
                out.append({"program": prog, "project": _clean(r.get("PROJECT")), "location": _clean(r.get("LOCATION")),
                            "status": _clean(r.get("STATUS")), "timeline": _clean(r.get("DURATION/ Construction Timeline")),
                            "details": _clean(r.get("DETAILS"))[:300], "updated": r.get("LAST_UPDATED_DATE"),
                            "segments": list(_segments(geom))})
    return out


def works_near(lat: float, lon: float, radius_m: float) -> list[dict]:
    res = []
    for w in _works():
        d = min((_dist_point_to_line_m(lat, lon, seg) for seg in w["segments"]), default=1e12)
        if d <= radius_m:
            res.append({k: v for k, v in w.items() if k != "segments"} | {"distance_m": round(d)})
    res.sort(key=lambda w: w["distance_m"])
    return res


def works_line(w: dict) -> str:
    return (f"{w['program']} | {w['project']} | {w['location']} | status: {w['status']} | timeline: {w['timeline']} | "
            f"{w['distance_m']} m from the point | last updated {w['updated']} | details: {w['details']}")
