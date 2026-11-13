"""Municipal changes as structured effects, applied to a resident's trip to compare before and after.

A change file (data/changes/*.json) lists effects such as removing stops or shelters. Each real change keeps exact
quotes from its saved source text, checked on load. Simulated changes are labelled as such everywhere.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from . import access, exposure
from .trip import Leg, load_routes, stop_records, walk_leg, walk_estimate_m

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_changes() -> dict[str, dict]:
    out = {}
    for p in sorted((ROOT / "data/changes").glob("*.json")):
        c = json.loads(p.read_text())
        if not c["simulated"]:
            if c.get("source_pages_file"):
                pages = json.loads((ROOT / c["source_pages_file"]).read_text())
                src = " ".join(" ".join(pages[n - 1].split()) for n in c["source_pages"])
                check = lambda q: " ".join(q.split()) in src
            else:
                src = (ROOT / c["source_file"]).read_text()
                check = lambda q: q in src
            for q in c["quotes"] + [e["quote"] for e in c["effects"] if e.get("quote")]:
                if not check(q):
                    raise ValueError(f"{p.name}: quote not found in source: {q[:60]}")
        out[c["id"]] = c
    return out


def affecting(legs: list[Leg]) -> list[dict]:
    routes = {l.route for l in legs if l.kind == "transit"}
    return [c for c in load_changes().values() if any(e["route"] in routes for e in c["effects"])]


def _reconstruct(route: str, street: str, label: str) -> list[dict]:
    """Put a removed stop back where `street` meets the route line, per direction. Uses City address points on the
    cross street; the point nearest the route line is projected onto it. Marked as reconstructed everywhere."""
    import sqlite3
    from . import geocode
    con = sqlite3.connect(f"file:{geocode.DB}?mode=ro", uri=True)
    pts = con.execute("SELECT lat, lon FROM addr WHERE street = ?", (geocode.normalize(street),)).fetchall()
    con.close()
    out = []
    import math
    for vi, v in enumerate(load_routes()[route]["variants"]):
        sh, best = v["shape"], None
        for lat, lon in pts:
            k = 111320 * math.cos(math.radians(lat))
            for s in range(len(sh) - 1):
                (ay, ax), (by, bx) = sh[s], sh[s + 1]
                dx, dy = (bx - ax) * k, (by - ay) * 111320
                L = dx * dx + dy * dy
                tt = 0.0 if L == 0 else max(0.0, min(1.0, ((lon - ax) * k * dx + (lat - ay) * 111320 * dy) / L))
                qy, qx = ay + tt * (by - ay), ax + tt * (bx - ax)
                d = access.haversine_m(lat, lon, qy, qx)
                if best is None or d < best[0]:
                    best = (d, s + tt, qy, qx)
        if best and best[0] <= 150:
            out.append({"variant": vi, "v": best[1], "lat": best[2], "lon": best[3], "stop_id": f"restored:{route}:{street}:{vi}",
                        "name": f"{label} (removed stop; location reconstructed)", "wheelchair_boarding": "0",
                        "shelter_listed": False, "bench_listed": False, "reconstructed": True})
    return out


def restored_stops(change: dict, route: str) -> list[dict]:
    out = []
    for e in change["effects"]:
        if e["type"] == "restore_removed_stops" and e["route"] == route:
            for street, label in e["cross_streets"]:
                out += _reconstruct(route, street, label)
    return out


def _removed(change: dict, route: str) -> set[str]:
    return {s for e in change["effects"] if e["type"] == "remove_stop" and e["route"] == route for s in e["stop_ids"]}


def apply(legs: list[Leg], change: dict, avoid_no_sidewalk: bool = False) -> tuple[list[Leg], list[str]]:
    """Return the trip after the change, and plain notes on what moved."""
    notes, new = [], [copy.deepcopy(l) for l in legs]
    recs = stop_records()
    for i, l in enumerate(new):
        if l.kind != "transit":
            continue
        gone = _removed(change, l.route)
        var = next(v for v in load_routes()[l.route]["variants"]
                   if any(s["id"] == l.board["stop_id"] for s in v["stops"]) and any(s["id"] == l.alight["stop_id"] for s in v["stops"]))
        ids = [s["id"] for s in var["stops"]]
        bi, ai = ids.index(l.board["stop_id"]), ids.index(l.alight["stop_id"])
        keep = [j for j, s in enumerate(var["stops"]) if s["id"] not in gone]

        walk_from = new[i - 1].points[0] if i > 0 and new[i - 1].kind == "walk" else (l.board["lat"], l.board["lon"])
        walk_to = new[i + 1].points[-1] if i + 1 < len(new) and new[i + 1].kind == "walk" else (l.alight["lat"], l.alight["lon"])

        def options(j, lo, hi):
            """The remaining stops just before and just after stop j (within lo..hi), in route order."""
            before = [k for k in keep if lo <= k < j]
            after = [k for k in keep if j < k <= hi]
            return [x for x in ((before[-1] if before else None), (after[0] if after else None)) if x is not None]

        def walk_m(point, k):
            r = walk_leg(point, (var["stops"][k]["lat"], var["stops"][k]["lon"]), "", avoid_no_sidewalk)
            return walk_estimate_m(r)

        def choose(j, lo, hi, point, role):
            opts = options(j, lo, hi)
            if not opts:
                return None
            dist = {k: walk_m(point, k) for k in opts}
            pick = min(opts, key=lambda k: dist[k])
            desc = " or ".join(f"{var['stops'][k]['name']} ({'the stop before' if k < j else 'the stop after'}, about {dist[k]} m walk)" for k in opts)
            notes.append(f"Your stop to {role}, {var['stops'][j]['name']}, is removed. Remaining options: {desc}. "
                         f"The comparison uses the shorter walk, {var['stops'][pick]['name']}.")
            return pick

        nb = bi if var["stops"][bi]["id"] not in gone else choose(bi, 0, ai - 1, walk_from, "get on")
        na = ai if var["stops"][ai]["id"] not in gone else choose(ai, (nb or 0) + 1, len(ids) - 1, walk_to, "get off")
        if nb is None or na is None or na <= nb:
            notes.append(f"Route {l.route}: after this change no stop in your direction remains between your start and end.")
            continue
        b, a = var["stops"][nb], var["stops"][na]
        l.board = copy.deepcopy(recs.get(b["id"], {"stop_id": b["id"], "name": b["name"], "lat": b["lat"], "lon": b["lon"]}))
        l.alight = copy.deepcopy(recs.get(a["id"], {"stop_id": a["id"], "name": a["name"], "lat": a["lat"], "lon": a["lon"]}))
        l.points = [tuple(p) for p in var["shape"][b["v"]:a["v"] + 1]]
        # walking legs either side are re-routed to the new stops
        if i > 0 and new[i - 1].kind == "walk":
            new[i - 1] = walk_leg(new[i - 1].points[0], (l.board["lat"], l.board["lon"]), f"Walk to {l.board['name']}", avoid_no_sidewalk)
        if i + 1 < len(new) and new[i + 1].kind == "walk":
            new[i + 1] = walk_leg((l.alight["lat"], l.alight["lon"]), new[i + 1].points[-1], new[i + 1].label, avoid_no_sidewalk)
    for e in change["effects"]:
        field = {"remove_shelter": "shelter_listed", "remove_bench": "bench_listed"}.get(e["type"])
        if not field:
            continue
        for l in new:
            if l.kind == "transit" and l.route == e["route"]:
                for st in (l.board, l.alight):
                    if st.get("stop_id") in e["stop_ids"] and st.get(field):
                        st[field] = False
                        notes.append(f"{st['name']}: the {field.split('_')[0]} would be removed.")
    return new, notes


def restore(legs: list[Leg], change: dict, avoid_no_sidewalk: bool = False) -> tuple[list[Leg], list[str]]:
    """For a change that already happened: rebuild the trip as it was, using a removed stop when it gave a shorter walk."""
    notes, new = [], [copy.deepcopy(l) for l in legs]
    for i, l in enumerate(new):
        if l.kind != "transit":
            continue
        var_i, var = next((k, v) for k, v in enumerate(load_routes()[l.route]["variants"])
                          if any(s["id"] == l.board["stop_id"] for s in v["stops"]) and any(s["id"] == l.alight["stop_id"] for s in v["stops"]))
        vb = next(s["v"] for s in var["stops"] if s["id"] == l.board["stop_id"])
        va = next(s["v"] for s in var["stops"] if s["id"] == l.alight["stop_id"])
        cands = [r for r in restored_stops(change, l.route) if r["variant"] == var_i]
        start = new[i - 1].points[0] if i > 0 and new[i - 1].kind == "walk" else (l.board["lat"], l.board["lon"])
        end = new[i + 1].points[-1] if i + 1 < len(new) and new[i + 1].kind == "walk" else (l.alight["lat"], l.alight["lon"])
        now_on = walk_estimate_m(new[i - 1]) if i > 0 and new[i - 1].kind == "walk" else 0
        now_off = walk_estimate_m(new[i + 1]) if i + 1 < len(new) and new[i + 1].kind == "walk" else 0
        best_on = min(((walk_estimate_m(walk_leg(start, (r["lat"], r["lon"]), "", avoid_no_sidewalk)), r) for r in cands if r["v"] < va),
                      key=lambda x: x[0], default=None)
        best_off = min(((walk_estimate_m(walk_leg((r["lat"], r["lon"]), end, "", avoid_no_sidewalk)), r) for r in cands if r["v"] > vb),
                       key=lambda x: x[0], default=None)
        nb, na = vb, va
        if best_on and best_on[0] < now_on:
            r = best_on[1]; nb = r["v"]; l.board = dict(r)
            notes.append(f"Before this decision you could get on at {r['name']}, about {best_on[0]} m walk. Today the stop is gone and you walk about {now_on} m.")
            new[i - 1] = walk_leg(start, (r["lat"], r["lon"]), f"Walk to {r['name']}", avoid_no_sidewalk)
        if best_off and best_off[0] < now_off and best_off[1]["v"] > nb:
            r = best_off[1]; na = r["v"]; l.alight = dict(r)
            notes.append(f"Before this decision you could get off at {r['name']}, about {best_off[0]} m walk. Today you walk about {now_off} m.")
            new[i + 1] = walk_leg((r["lat"], r["lon"]), end, new[i + 1].label, avoid_no_sidewalk)
        import math as _m
        sh = var["shape"]
        pts = [tuple(p) for p in sh[_m.floor(nb) + (1 if nb != int(nb) else 0):_m.floor(na) + 1]]
        if nb != int(nb):
            pts = [(l.board["lat"], l.board["lon"])] + pts
        if na != int(na):
            pts = pts + [(l.alight["lat"], l.alight["lon"])]
        l.points = pts
    return new, notes


def compare(legs: list[Leg], change: dict, rider: str, band: str, day: str) -> dict:
    careful = rider in ("wheelchair", "senior_walker")
    if change.get("phase") == "implemented":
        before_legs, notes = restore(legs, change, careful)
        cmp = _compare(before_legs, legs, rider, band, day)
        return {"change": change, "notes": notes or ["The removed stops were not nearer for this trip, so the decision did not change it."], **cmp}
    after_legs, notes = apply(legs, change, careful)
    return {"change": change, "notes": notes, **_compare(legs, after_legs, rider, band, day)}


def _compare(legs: list[Leg], after_legs: list[Leg], rider: str, band: str, day: str) -> dict:
    before = exposure.analyze(legs, rider, band, day, stop_override=_overrides(legs))
    after = exposure.analyze(after_legs, rider, band, day, stop_override=_overrides(after_legs))
    key = lambda f: (f["severity"], f["text"])
    bset = {key(f) for f in before["flags"] if f["kind"] == "rule"}
    new_issues = [f for f in after["flags"] if f["kind"] == "rule" and f["severity"] in ("barrier", "watch") and key(f) not in bset]
    rows = []
    for lb, la in zip(legs, after_legs):
        if lb.kind == "walk":
            rows.append({"what": la.label, "before": f"about {walk_estimate_m(lb)} m walk",
                         "after": f"about {walk_estimate_m(la)} m walk", "changed": walk_estimate_m(lb) != walk_estimate_m(la)})
        else:
            for role, sb, sa in (("Get on at", lb.board, la.board), ("Get off at", lb.alight, la.alight)):
                fb = lambda s: (f"{s['name']} (shelter and bench unknown)" if s.get("reconstructed") else
                                f"{s['name']} (shelter {'listed' if s.get('shelter_listed') else 'not listed'}, bench {'listed' if s.get('bench_listed') else 'not listed'})")
                rows.append({"what": role, "before": fb(sb), "after": fb(sa), "changed": fb(sb) != fb(sa)})
    return {"rows": rows, "new_issues": new_issues, "after_legs": after_legs, "before_legs": legs}


def _overrides(legs: list[Leg]) -> dict:
    return {st["stop_id"]: st for l in legs if l.kind == "transit" for st in (l.board, l.alight)}
