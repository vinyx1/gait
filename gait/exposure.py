"""Find what sits along a resident's trip and turn it into rider-specific flags.

Only fixed rules are used here. Every flag lists the source lines it rests on. Distances use the trip lines built in
trip.py. Nothing is stored.
"""
from __future__ import annotations

import datetime
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from . import access, labels
from .trip import Leg, load_routes, stop_records, walk_estimate_m

ROOT = Path(__file__).resolve().parent.parent
ITEM_BUFFER_M = 150
WORKS_BUFFER_M = 120

BANDS = {"early": ("Early morning (4:00 to 6:00)", range(4, 6)), "day": ("Daytime (6:00 to 20:00)", range(6, 20)),
         "evening": ("Evening (20:00 to 23:00)", range(20, 23)), "late": ("Late night (from 23:00)", range(23, 29))}
DAYS = {"weekday": "weekday", "saturday": "Saturday", "sunday": "Sunday"}


@lru_cache(maxsize=1)
def _items() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in (ROOT / "data/items").glob("*.json")}


@lru_cache(maxsize=1)
def _locations() -> list[dict]:
    p = ROOT / "data/locations.json"
    return json.loads(p.read_text()) if p.exists() else []


def _line(leg: Leg):
    return [(p[1], p[0]) for p in leg.points]


def _min_dist(lat: float, lon: float, legs: list[Leg]):
    best, best_leg = 1e12, None
    for leg in legs:
        d = access._dist_point_to_line_m(lat, lon, _line(leg))
        if d < best:
            best, best_leg = d, leg
    return best, best_leg


def sample(legs: list[Leg], step_m: float = 80.0):
    """Points along the trip about step_m apart: (lat, lon, leg)."""
    out = []
    for leg in legs:
        out.append((leg.points[0][0], leg.points[0][1], leg))
        carry = 0.0
        for a, b in zip(leg.points, leg.points[1:]):
            seg = access.haversine_m(a[0], a[1], b[0], b[1])
            d = step_m - carry
            while d < seg:
                f = d / seg
                out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), leg))
                d += step_m
            carry = (carry + seg) % step_m
        out.append((leg.points[-1][0], leg.points[-1][1], leg))
    return out


def items_near(legs: list[Leg]) -> list[dict]:
    out = []
    for loc in _locations():
        d, leg = _min_dist(loc["lat"], loc["lon"], legs)
        if d > ITEM_BUFFER_M:
            continue
        for iid in loc["item_ids"]:
            it = _items().get(iid)
            if not it:
                continue
            st = labels.latest_stage(it)
            out.append({"item_id": iid, "title": it["title"], "upcoming": it.get("upcoming", False),
                        "label": labels.item_plain(it)[0], "when": st["dates_text"], "body": st["body"],
                        "actions": it.get("actions", []), "loc_label": loc["label"], "lat": loc["lat"], "lon": loc["lon"],
                        "distance_m": round(d), "leg": leg.label if leg else ""})
    out.sort(key=lambda x: (not x["upcoming"], x["distance_m"]))
    return out


@lru_cache(maxsize=1)
def _works_bbox() -> list[tuple]:
    m = WORKS_BUFFER_M / 111320 * 1.5
    boxes = []
    for w in access._works():
        xs = [p[0] for seg in w["segments"] for p in seg]; ys = [p[1] for seg in w["segments"] for p in seg]
        boxes.append((min(ys) - m, max(ys) + m, min(xs) - m * 1.5, max(xs) + m * 1.5) if xs else None)
    return boxes


def works_along(legs: list[Leg]) -> list[dict]:
    pts = sample(legs)
    res = []
    for w, box in zip(access._works(), _works_bbox()):
        if box is None:
            continue
        best, bp = 1e12, None
        for lat, lon, leg in pts:
            if not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
                continue
            d = min(access._dist_point_to_line_m(lat, lon, seg) for seg in w["segments"])
            if d < best:
                best, bp = d, (lat, lon, leg)
        if bp and best <= WORKS_BUFFER_M:
            rec = {k: v for k, v in w.items() if k != "segments"} | {"distance_m": round(best), "lat": bp[0], "lon": bp[1], "leg": bp[2].label}
            rec["line"] = access.works_line(rec)
            res.append(rec)
    res.sort(key=lambda r: r["distance_m"])
    return res


def route_mentions(shorts: list[str]) -> list[dict]:
    out = []
    for s in shorts:
        long = load_routes()[s]["long"]
        first = re.escape(long.split()[0])
        pat = re.compile(rf"\b{re.escape(s)}\s+{first}", re.I)
        for iid, it in _items().items():
            texts = [it["title"]] + [x for st in it["stages"] for x in (st.get("decision_text"), st.get("summary"), st.get("origin")) if x]
            for t in texts:
                m = pat.search(t)
                if m:
                    a = max(0, m.start() - 90); b = min(len(t), m.end() + 110)
                    out.append({"route": s, "item_id": iid, "title": it["title"], "snippet": t[a:b].strip(),
                                "upcoming": it.get("upcoming", False), "label": labels.item_plain(it)[0]})
                    break
    return out


def _band_count(stop: dict, day: str, band: str) -> tuple[int, int]:
    svc = (stop.get("service") or {}).get(day)
    hours = BANDS[band][1]
    n = sum(c for h, c in (svc or {}).get("per_hour", {}).items() if int(h) in hours)
    return n, len(hours)


def analyze(legs: list[Leg], persona_key: str, band: str, day: str, today_year: int | None = None, stop_override: dict | None = None) -> dict:
    p = access.PERSONAS[persona_key]
    transit = [l for l in legs if l.kind == "transit"]
    walks = [l for l in legs if l.kind == "walk"]
    items = items_near(legs)
    works = works_along(legs)
    mentions = route_mentions([l.route for l in transit])
    flags: list[dict] = []

    def flag(sev, text, evidence, kind="rule", code=None, leg=None, data=None):
        flags.append({"severity": sev, "text": text, "evidence": evidence, "kind": kind, "code": code, "leg": leg, "data": data or {}})

    # walking legs
    careful = persona_key in ("wheelchair", "senior_walker")
    for w in walks:
        est = walk_estimate_m(w)
        how = (f"{w.label}: about {est} m along the City's sidewalk network" if w.stats
               else f"{w.label}: {w.length_m} m straight line, times {access.DETOUR} = about {est} m of walking (no sidewalk path found)")
        ev = [how]
        wd = {"m": est, "limit": p.max_walk_m, "who": p.label.lower(), "label": w.label}
        if est > p.max_walk_m:
            flag("barrier" if careful else "watch", code="walk_over_limit", leg=walks.index(w), text=
                 f"{w.label}: about {est} m of walking, longer than the {p.max_walk_m} m assumed for a {p.label.lower()}.", evidence=ev, data=wd)
        elif est > 0.8 * p.max_walk_m:
            flag("watch", code="walk_near_limit", leg=walks.index(w), text=f"{w.label}: about {est} m of walking, close to the {p.max_walk_m} m assumed for a {p.label.lower()}.", evidence=ev, data=wd)
        if w.stats and w.stats["no_sidewalk_m"] > 0:
            flag("barrier" if careful and w.stats["no_sidewalk_m"] >= 50 else "watch", code="no_sidewalk", leg=walks.index(w), text=
                 f"{w.label}: about {w.stats['no_sidewalk_m']} m of the walk is on a street or laneway with no sidewalk in the City's data.", evidence=ev, data={**wd, "no_sidewalk_m": w.stats["no_sidewalk_m"]})
        if w.stats and w.stats["crossings"].get("no signal") and careful:
            flag("watch", code="unsignalled", leg=walks.index(w), text=f"{w.label}: the path crosses at {w.stats['crossings']['no signal']} crossing(s) the City lists with no signal.", evidence=ev, data={**wd, "n": w.stats['crossings']['no signal']})
        if not w.stats:
            flag("info", code="straight", leg=walks.index(w), text=f"{w.label}: no sidewalk path was found in the City's network, so this walk is a straight-line estimate.", evidence=ev)

    # stops and service
    for t in transit:
        rt = load_routes()[t.route]
        for role, st in (("Boarding", t.board), ("Getting off at", t.alight)):
            rec = (stop_override or {}).get(st.get("stop_id")) or stop_records().get(st.get("stop_id"), st)
            line = access.stop_line(rec) if "service" in rec else f"stop {st['stop_id']} | {st['name']}"
            if persona_key == "wheelchair" and "wheelchair_boarding" in rec:
                wb = rec["wheelchair_boarding"]
                if wb == "2":
                    flag("barrier", f"{role} {rec['name']}: boarding is listed as not possible.", [line], code="boarding_no:" + role, data={"stop": rec["name"], "role": role})
                elif wb == "0":
                    flag("watch", f"{role} {rec['name']}: the TTC file has no wheelchair boarding information for this stop.", [line], code="boarding_unknown:" + role, data={"stop": rec["name"], "role": role})
            if careful and rec.get("platform"):
                flag("watch", f"{role} {rec['name']}: you board from a {rec['platform']}, crossing the cycle track to reach it. Raised platforms can make boarding more level; check how the crossing is marked.", [line], code="platform:" + role, data={"stop": rec["name"], "role": role, "platform": rec["platform"]})
            if careful and role == "Boarding" and "shelter_listed" in rec and not rec["shelter_listed"] and not rec.get("reconstructed") and rec.get("service"):
                n_w, nh_w = _band_count(rec, day, band)
                if n_w:
                    wait = round(60 * nh_w / n_w / 2)
                    if wait >= 4:
                        flag("watch", f"{role} {rec['name']}: no shelter is listed, and the average wait at your travel time is about {wait} minutes, outdoors in winter weather.", [line], code="shelter_wait", data={"stop": rec["name"], "role": role, "wait": wait})
            if persona_key == "senior_walker" and role == "Boarding" and "shelter_listed" in rec and not rec.get("reconstructed") \
                    and not rec["shelter_listed"] and not rec["bench_listed"]:
                flag("watch", f"{role} {rec['name']}: no shelter or bench is listed in City data (the data may be incomplete).", [line], code="no_seat", data={"stop": rec["name"], "role": role})
        tf = rt["trip_flags"]
        if persona_key == "wheelchair":
            ev = [f"route {t.route} {rt['long']}: trips flagged accessible {round(tf['accessible'] * 100)}%, "
                  f"not accessible {round(tf['not_accessible'] * 100)}%, no information {round(tf['no_information'] * 100)}%"]
            if tf["accessible"] == 0:
                flag("barrier", code="route_wc:" + t.route, evidence=ev, text=f"Route {t.route} {rt['long']}: none of its scheduled trips are flagged wheelchair accessible in the TTC schedule file.")
            elif tf["accessible"] < 1:
                flag("watch", code="route_wc:" + t.route, evidence=ev, text=f"Route {t.route} {rt['long']}: {round(tf['accessible'] * 100)}% of its scheduled trips are flagged wheelchair accessible.")
        b = (stop_override or {}).get(t.board.get("stop_id")) or stop_records().get(t.board.get("stop_id"))
        if b and "service" not in b:
            b = None
        if b:
            n, nh = _band_count(b, day, band)
            ev = [access.stop_line(b)]
            if n == 0:
                flag("barrier", code="no_service", evidence=ev, data={"stop": b["name"], "role": "Boarding", "day": day, "band": band}, text=f"{b['name']}: no {DAYS[day]} departures in the {BANDS[band][0].lower()} in the base schedule.")
            else:
                gap = round(60 * nh / n)
                flag("info", f"{b['name']}: {n} {DAYS[day]} departures in the {BANDS[band][0].lower()}, about one every {gap} minutes on average (all routes at the stop).", ev)

    # decisions and works
    for it in items:
        if it["upcoming"]:
            acts = ", ".join(it["actions"]) or "none shown"
            flag("watch", f"A decision is coming up near your trip: {it['title']} ({it['body']}, {it['when']}). The official page shows: {acts}.",
                 [f"{it['title']} | {it['loc_label']} | {it['distance_m']} m from your trip | {it['label']}"], kind="act")
        else:
            flag("info", f"A decision near your trip has already been made or referred: {it['title']} ({it['label']}).",
                 [f"{it['title']} | {it['loc_label']} | {it['distance_m']} m from your trip | {it['label']}"], kind="item")
    this_year = today_year or datetime.date.today().year
    for w in works:
        years = [int(y) for y in re.findall(r"20\d\d", w["timeline"] or "")]
        w["ended"] = bool(years) and max(years) < this_year
    works.sort(key=lambda w: (w["ended"], w["distance_m"]))
    for w in works[:6]:
        if w["ended"]:
            flag("info", f"Works listed near your trip have a timeline that has ended: {w['project']} on {w['location']}, {w['timeline']}, "
                         f"{w['distance_m']} m away. They may be finished, or the City list may be out of date.", [w["line"]], kind="works")
        else:
            flag("watch", f"Planned works near your trip: {w['project']} on {w['location']}, {w['timeline'] or 'timeline not stated'}, "
                          f"{w['distance_m']} m away (last updated {w['updated']}).", [w["line"]], kind="works")
    for m in mentions:
        flag("watch", f"A decision mentions your route {m['route']}: {m['title']}.", [m["snippet"]], kind="mention")

    order = {"barrier": 0, "watch": 1, "info": 2}
    flags.sort(key=lambda f: (order[f["severity"]], f["kind"] != "act"))
    return {"persona": p.label, "band": BANDS[band][0], "day": DAYS[day], "flags": flags, "decisions": items, "works": works,
            "mentions": mentions, "walk_m": [w.length_m for w in walks], "legs": [(l.kind, l.label, l.length_m) for l in legs]}


# ---------- what Gait checked for this rider, on this trip, as a short list ----------
# The same fixed checks as analyze(), written as one line each, including the ones that pass,
# so the rider can see what was looked at. "ok" passed, "warn" is worth knowing, "bad" is past a fixed limit.

def _where(label: str) -> str:
    if not label.startswith("Walk to "):
        return label.lower()
    t = label[len("Walk to "):]
    if t.startswith("your "):
        return t
    t = t.split(" (")[0]
    return f"the stop at {t.replace(' at ', ' and ', 1)}" if " at " in t else f"the {t} stop"


def checklist(legs: list[Leg], persona_key: str, band: str, day: str, stop_override: dict | None = None) -> list[dict]:
    p = access.PERSONAS[persona_key]
    careful = persona_key in ("wheelchair", "senior_walker")
    out = []
    add = lambda state, text: out.append({"state": state, "text": text})
    walks = [l for l in legs if l.kind == "walk"]
    transit = [l for l in legs if l.kind == "transit"]
    rec = lambda st: (stop_override or {}).get(st.get("stop_id")) or stop_records().get(st.get("stop_id"), st)

    for w in walks:
        m, where = walk_estimate_m(w), _where(w.label)
        if m > p.max_walk_m:
            add("bad", f"Walk to {where}: about {m} m, more than your {p.max_walk_m} m limit")
        elif m > 0.8 * p.max_walk_m:
            add("warn", f"Walk to {where}: about {m} m, close to your {p.max_walk_m} m limit")
        else:
            add("ok", f"Walk to {where}: about {m} m, within your {p.max_walk_m} m limit")

    routed = [w for w in walks if w.stats]
    if len(routed) < len(walks):
        add("warn", "No sidewalk path was found for one walk, so its distance is a straight-line estimate")
    no_sw = sum(w.stats["no_sidewalk_m"] for w in routed)
    if routed:
        add("ok", "Sidewalk the whole way, in the City's data") if no_sw == 0 else \
            add("bad" if careful and no_sw >= 50 else "warn", f"About {no_sw} m of walking on streets with no sidewalk, in the City's data")
    if careful and routed:
        ns = sum(w.stats["crossings"].get("no signal", 0) for w in routed)
        add("ok", "No crossings without a traffic signal") if ns == 0 else \
            add("warn", f"{ns} crossing{'s' if ns > 1 else ''} with no traffic signal")

    for t in transit:
        b, a = rec(t.board), rec(t.alight)
        bn = b["name"].split(" (")[0]
        gone = " (the stop has since been removed)"
        if careful:
            if b.get("reconstructed") or "shelter_listed" not in b:
                add("warn", f"Shelter and bench at {bn} are not known" + (gone if b.get("reconstructed") else ""))
            elif b["shelter_listed"] and b.get("bench_listed"):
                add("ok", f"Your stop, {bn}, has a shelter and a bench listed")
            elif b["shelter_listed"]:
                add("ok", f"Your stop, {bn}, has a shelter listed")
            elif b.get("bench_listed"):
                add("warn", f"Your stop, {bn}, has a bench but no shelter listed")
            else:
                add("warn", f"Your stop, {bn}, has no shelter or bench listed")
            if b.get("platform"):
                add("warn", f"At {bn} you board from a {b['platform']}, crossing the cycle track to reach it")
        if persona_key == "wheelchair":
            wb = [s.get("wheelchair_boarding") for s in (b, a)]
            if b.get("reconstructed"):
                add("warn", f"Wheelchair boarding at {bn} is not known{gone}")
            elif "2" in wb:
                add("bad", "The TTC lists wheelchair boarding as not possible at one of your stops")
            elif "0" in wb or None in wb:
                add("warn", "The TTC has no wheelchair boarding information for one of your stops")
            else:
                add("ok", "The TTC lists wheelchair boarding at both of your stops")
            acc = load_routes()[t.route]["trip_flags"]["accessible"]
            add("ok", f"All {t.route} trips are flagged wheelchair accessible") if acc >= 1 else \
                add("bad" if acc == 0 else "warn", f"{round(acc * 100)}% of {t.route} trips are flagged wheelchair accessible in the TTC schedule file")
        if b.get("reconstructed"):
            add("warn", f"Bus times at {bn} are not in the current schedule{gone}")
        elif b.get("service"):
            n, nh = _band_count(b, day, band)
            when = BANDS[band][0].split(" (")[0].lower()
            if n == 0:
                add("bad", f"No {DAYS[day]} buses leave {bn} in the {when}, in the regular schedule")
            else:
                add("ok" if 60 * nh / n <= 15 else "warn", f"About one departure every {round(60 * nh / n)} minutes from {bn} ({DAYS[day]}, {when}, all routes at the stop)")
    return out
