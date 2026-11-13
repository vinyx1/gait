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
from .trip import Leg, load_routes, stop_records

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_changes() -> dict[str, dict]:
    out = {}
    for p in sorted((ROOT / "data/changes").glob("*.json")):
        c = json.loads(p.read_text())
        if not c["simulated"]:
            src = (ROOT / c["source_file"]).read_text()
            for q in c["quotes"] + [e["quote"] for e in c["effects"] if e.get("quote")]:
                if q not in src:
                    raise ValueError(f"{p.name}: quote not found in source: {q[:60]}")
        out[c["id"]] = c
    return out


def affecting(legs: list[Leg]) -> list[dict]:
    routes = {l.route for l in legs if l.kind == "transit"}
    return [c for c in load_changes().values() if any(e["route"] in routes for e in c["effects"])]


def _removed(change: dict, route: str) -> set[str]:
    return {s for e in change["effects"] if e["type"] == "remove_stop" and e["route"] == route for s in e["stop_ids"]}


def apply(legs: list[Leg], change: dict) -> tuple[list[Leg], list[str]]:
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

        def nearest(j, lo, hi):
            cand = [k for k in keep if lo <= k <= hi]
            s0 = var["stops"][j]
            return min(cand, key=lambda k: access.haversine_m(s0["lat"], s0["lon"], var["stops"][k]["lat"], var["stops"][k]["lon"])) if cand else None

        nb = bi if var["stops"][bi]["id"] not in gone else nearest(bi, 0, ai - 1)
        na = ai if var["stops"][ai]["id"] not in gone else nearest(ai, (nb or 0) + 1, len(ids) - 1)
        if nb is None or na is None or na <= nb:
            notes.append(f"Route {l.route}: after this change no stop in your direction remains between your start and end.")
            continue
        for old, nj, role in ((bi, nb, "get on"), (ai, na, "get off")):
            if old != nj:
                notes.append(f"Your stop to {role}, {var['stops'][old]['name']}, is removed. The nearest remaining stop in your direction is {var['stops'][nj]['name']}.")
        b, a = var["stops"][nb], var["stops"][na]
        l.board = copy.deepcopy(recs.get(b["id"], {"stop_id": b["id"], "name": b["name"], "lat": b["lat"], "lon": b["lon"]}))
        l.alight = copy.deepcopy(recs.get(a["id"], {"stop_id": a["id"], "name": a["name"], "lat": a["lat"], "lon": a["lon"]}))
        l.points = [tuple(p) for p in var["shape"][b["v"]:a["v"] + 1]]
        # walking legs either side follow the new stops
        if i > 0 and new[i - 1].kind == "walk":
            new[i - 1].points = [new[i - 1].points[0], (l.board["lat"], l.board["lon"])]
            new[i - 1].label = f"Walk to {l.board['name']}"
        if i + 1 < len(new) and new[i + 1].kind == "walk":
            new[i + 1].points = [(l.alight["lat"], l.alight["lon"]), new[i + 1].points[-1]]
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


def compare(legs: list[Leg], change: dict, rider: str, band: str, day: str) -> dict:
    after_legs, notes = apply(legs, change)
    before = exposure.analyze(legs, rider, band, day, stop_override=_overrides(legs))
    after = exposure.analyze(after_legs, rider, band, day, stop_override=_overrides(after_legs))
    key = lambda f: (f["severity"], f["text"])
    bset = {key(f) for f in before["flags"] if f["kind"] == "rule"}
    new_issues = [f for f in after["flags"] if f["kind"] == "rule" and f["severity"] in ("barrier", "watch") and key(f) not in bset]
    rows = []
    for lb, la in zip(legs, after_legs):
        if lb.kind == "walk":
            rows.append({"what": lb.label, "before": f"about {round(lb.length_m * access.DETOUR)} m walk",
                         "after": f"about {round(la.length_m * access.DETOUR)} m walk", "changed": lb.length_m != la.length_m})
        else:
            for role, sb, sa in (("Get on at", lb.board, la.board), ("Get off at", lb.alight, la.alight)):
                fb = lambda s: f"{s['name']} (shelter {'listed' if s.get('shelter_listed') else 'not listed'}, bench {'listed' if s.get('bench_listed') else 'not listed'})"
                rows.append({"what": role, "before": fb(sb), "after": fb(sa), "changed": fb(sb) != fb(sa)})
    return {"change": change, "notes": notes, "rows": rows, "new_issues": new_issues, "after_legs": after_legs}


def _overrides(legs: list[Leg]) -> dict:
    return {st["stop_id"]: st for l in legs if l.kind == "transit" for st in (l.board, l.alight)}
