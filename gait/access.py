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
    "senior_walker": Persona("senior_walker", "Person using a cane or walker", 250,
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
                            "web": (r.get("INV_WEB_SITE") or "").strip(),
                            "segments": list(_segments(geom))})
    return out


def works_near(lat: float, lon: float, radius_m: float) -> list[dict]:
    res = []
    for w in _works():
        d = min((_dist_point_to_line_m(lat, lon, seg) for seg in w["segments"]), default=1e12)
        if d <= radius_m:
            res.append({k: v for k, v in w.items() if k not in ("segments", "web")} | {"distance_m": round(d)})
    res.sort(key=lambda w: w["distance_m"])
    return res


def works_line(w: dict) -> str:
    return (f"{w['program']} | {w['project']} | {w['location']} | status: {w['status']} | timeline: {w['timeline']} | "
            f"{w['distance_m']} m from the point | last updated {w['updated']} | details: {w['details']}")


# ---------- City works that touch the trip itself ----------
# Only works whose own street segment meets the rider's walks or stops, or runs along their ride, are kept.
# The City's words (what the work is, that it may close lanes or the road) are shown as written; nothing is predicted.

TOUCH_WALK_M, TOUCH_STOP_M, TOUCH_RIDE_M, ALONG_RIDE_M = 20, 30, 18, 80


def _quarter_end(timeline: str) -> tuple[int, int] | None:
    """The last quarter a City timeline names: 'Q2 2026 - Q4 2026' -> (2026, 4); '2027' -> (2027, 4)."""
    qs = re.findall(r"Q([1-4])\s*(\d{4})", timeline)
    if qs:
        return max((int(y), int(q)) for q, y in qs)
    ys = re.findall(r"\b(20\d\d)\b", timeline)
    return (max(int(y) for y in ys), 4) if ys else None


def _place(t: str) -> str:
    t = t.replace("[END]", "").strip()
    m = re.match(r"\[(\d+)\s*M\s*([NSEW])\]\s*(.*)", t, re.I)
    sides = {"N": "north", "S": "south", "E": "east", "W": "west"}
    nice = lambda x: " ".join(w.capitalize() if w.isalpha() else w for w in x.split())
    return f"{m.group(1)} m {sides[m.group(2).upper()]} of {nice(m.group(3))}" if m else nice(t)


def _where(location: str) -> dict:
    parts = [p.strip() for p in location.split(";") if p.strip()]
    out = {"street": _place(parts[0]) if parts else location}
    for p in parts[1:]:
        k, _, v = p.partition(":")
        if k.strip().lower() in ("from", "to"):
            out[k.strip().lower()] = _place(v)
    return out


def _sample(line, step_m: float = 8):
    """Points every few metres along a line of [lon, lat] pairs."""
    for (x1, y1), (x2, y2) in zip(line, line[1:]):
        n = max(1, int(haversine_m(y1, x1, y2, x2) / step_m))
        for i in range(n):
            yield y1 + (y2 - y1) * i / n, x1 + (x2 - x1) * i / n
    if line:
        yield line[-1][1], line[-1][0]


def works_on_trip(legs, today=None) -> list[dict]:
    """City road and sidewalk works that meet this trip, with the part of the trip each one touches."""
    from datetime import date
    today = today or date.today()
    now_q = (today.year, (today.month - 1) // 3 + 1)
    trip = [(l, [(lon, lat) for lat, lon in l.points]) for l in legs]
    allpts = [p for _, pts in trip for p in pts]
    if not allpts:
        return []
    pad = 0.0015
    x0, x1 = min(p[0] for p in allpts) - pad, max(p[0] for p in allpts) + pad
    y0, y1 = min(p[1] for p in allpts) - pad, max(p[1] for p in allpts) + pad
    stops = []
    for l in legs:
        if l.kind == "transit":
            stops += [("board", l, l.board), ("alight", l, l.alight)]
    out = []
    for w in _works():
        if w["status"].lower() != "active":
            continue
        end = _quarter_end(w["timeline"])
        if end and end < now_q:                       # the City's own timeline has already ended
            continue
        segs = [s for s in w["segments"] if len(s) > 1]
        if not segs or not any(x0 <= x <= x1 and y0 <= y <= y1 for s in segs for x, y in s):
            continue
        touches = []
        for li, (l, pts) in enumerate(trip):
            if l.kind == "walk":
                near = sum(1 for s in segs for la, lo in _sample(s) if _dist_point_to_line_m(la, lo, pts) <= TOUCH_WALK_M)
                if near:
                    along = near * 8
                    touches.append({"part": "walk", "label": l.label, "along_m": round(along / 10) * 10 if along >= 40 else 0, "seq": li * 3})
            else:
                near = sum(1 for s in segs for la, lo in _sample(s) if _dist_point_to_line_m(la, lo, pts) <= TOUCH_RIDE_M)
                if near * 8 >= ALONG_RIDE_M:
                    touches.append({"part": "ride", "label": l.label, "along_m": round(near * 8 / 10) * 10, "seq": li * 3})
        for role, l, st in stops:
            if st and min(_dist_point_to_line_m(st["lat"], st["lon"], s) for s in segs) <= TOUCH_STOP_M:
                touches.append({"part": "stop", "role": role, "label": st["name"], "seq": legs.index(l) * 3 + (-1 if role == "board" else 1)})
        if touches:
            mid = segs[0][len(segs[0]) // 2]
            out.append({"from_start_m": min(range(len(allpts)), key=lambda i: haversine_m(allpts[i][1], allpts[i][0], mid[1], mid[0])),"program": w["program"], "project": w["project"], "where": _where(w["location"]),
                        "details": w["details"], "timeline": w["timeline"], "updated": w["updated"], "web": w["web"],
                        "touches": touches,
                        "geometry": {"type": "MultiLineString", "coordinates": segs}})
    return _group_works(out)


def _group_works(found: list[dict]) -> list[dict]:
    """One entry per project and street: the City lists a long job block by block."""
    groups: dict = {}
    for w in found:
        g = groups.setdefault((w["project"], w["where"]["street"], w["details"]), {
            "program": w["program"], "project": w["project"], "street": w["where"]["street"], "details": w["details"],
            "web": w["web"], "blocks": [], "touches": [], "updated": w["updated"],
            "geometry": {"type": "MultiLineString", "coordinates": []}})
        g["blocks"].append({"from": w["where"].get("from", ""), "to": w["where"].get("to", ""), "timeline": w["timeline"], "_d": w["from_start_m"]})
        g["geometry"]["coordinates"] += w["geometry"]["coordinates"]
        g["updated"] = max(g["updated"] or "", w["updated"] or "")
        g["touches"] += w["touches"]
    order = {"stop": 0, "walk": 1, "ride": 2}
    out = []
    for g in groups.values():
        merged, seen = [], {}
        for t in g["touches"]:                    # the same walk or ride met by several blocks: add up the metres
            k = (t["part"], t["label"], t.get("role"))
            if k in seen:
                seen[k]["along_m"] = seen[k].get("along_m", 0) + t.get("along_m", 0)
            else:
                seen[k] = dict(t)
                merged.append(seen[k])
        g["touches"] = sorted(merged, key=lambda t: t["seq"])
        g["blocks"].sort(key=lambda b: b.pop("_d"))       # in the order the trip passes them
        g["timelines"] = sorted({b["timeline"] for b in g["blocks"]}, key=lambda t: _quarter_end(t) or (0, 0))
        out.append(g)
    out.sort(key=lambda g: (min(order[t["part"]] for t in g["touches"]), -len(g["touches"])))
    return out
