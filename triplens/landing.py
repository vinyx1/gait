"""Figures for the landing page, computed from the same trip engine and change files as the map (nothing typed in by hand)."""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

from . import access, changes, trip as tripmod

ROOT = Path(__file__).resolve().parent.parent

# The same sample trips as the map (templates/map.html SAMPLES). Public landmarks, not anyone's home.
CASES = {
    "bathurst": {"a": (43.68897, -79.42036), "b": (43.66554, -79.41166), "ride": ("7", 1, "107", "14617"), "rider": "senior_walker",
                 "change": "rapidto-7-bathurst-stops", "photo": "bathurst-street-toronto.jpg",
                 "photo_alt": "Bathurst Street, Toronto, in an early 1900s photograph", "title": "7 Bathurst"},
    "stclair": {"a": (43.68626, -79.40464), "b": (43.68778, -79.39435), "ride": ("512", None, "14351", "15305"), "rider": "senior_walker",
                "change": "ttc-512-stop-removals", "photo": "pcc-coming-back-up-to-street-level.jpg",
                "photo_alt": "A red streetcar rising from the St Clair West station tunnel onto St Clair Avenue", "title": "512 St Clair"},
    "harbord": {"a": (43.66012, -79.41720), "b": (43.66497, -79.38606), "ride": ("94", 1, "16790", "8625"), "rider": "wheelchair",
                "change": "past-94-harbord-bikeway-stops", "photo": "sherbourne-cycletrack.jpg",
                "photo_alt": "A Toronto cycle track running beside the curb, separated from traffic", "title": "94 on Harbord"},
    "frontst": {"a": (43.64661, -79.37812), "b": (43.64429, -79.36849), "ride": ("114", 0, "16754", "15320"), "rider": "senior_walker",
                "band": "late", "change": "front-st-layby-shelter", "photo": "rooftop-view-of-union-station-toronto-at.jpg",
                "photo_alt": "Union Station on Front Street West at night, seen from a rooftop", "title": "114 at Union"},
}


def _variant(route: str, board: str) -> int:
    for i, v in enumerate(tripmod.load_routes()[route]["variants"]):
        if board in [s["id"] for s in v["stops"]]:
            return i
    raise ValueError(route)


def _walk(legs) -> int:
    return tripmod.walk_estimate_m(legs[0])


@lru_cache(maxsize=None)
def case(key: str, rider: str | None = None) -> dict:
    c = CASES[key]
    rider = rider or c["rider"]
    route, vi, board, alight = c["ride"]
    vi = _variant(route, board) if vi is None else vi
    legs = tripmod.build_trip(c["a"], c["b"], [(route, vi, board, alight)], avoid_no_sidewalk=rider in ("wheelchair", "senior_walker"))
    ch = changes.load_changes()[c["change"]]
    cmp = changes.compare(legs, ch, rider, c.get("band", "day"), "weekday")
    before, after = _walk(cmp["before_legs"]), _walk(cmp["after_legs"])
    p = access.PERSONAS[rider]
    return {"key": key, "title": c["title"], "decision": ch["title"], "status": ch["status"], "phase": ch.get("phase", "proposed"),
            "simulated": ch["simulated"], "quote": ch["quotes"][0], "source_url": ch["source_url"], "item_url": ch.get("item_url"),
            "item_id": (ch.get("item_url") or "").rsplit("=", 1)[-1] or None,
            "rider": rider, "rider_label": p.label, "limit_m": p.max_walk_m, "before_m": before, "after_m": after,
            "new_issues": [f["text"] for f in cmp["new_issues"]], "improvements": [f["text"] for f in cmp["improvements"]],
            "photo": c["photo"], "photo_alt": c["photo_alt"],
            "board_before": cmp["before_legs"][1].board["name"], "board_after": cmp["after_legs"][1].board["name"]}


def hero() -> dict:
    return {r: case("bathurst", r) for r in ("senior_walker", "wheelchair", "shift_worker")}


def torn(seed: int, w: int = 1440, h: int = 40, step: int = 6, rough: float = 0.35, top: bool = True) -> str:
    """An SVG path for a torn paper edge: a filled band whose upper edge is ragged. Deterministic per seed."""
    rnd = random.Random(seed)
    pts, x = [], 0
    while x <= w:
        pts.append((x, h * (0.25 + rough * rnd.random() * (0.5 if rnd.random() < 0.8 else 1.2))))
        x += step * (0.5 + rnd.random())
    pts.append((w, h * 0.4))
    d = "M0," + f"{h}" + " " + " ".join(f"L{px:.0f},{py:.1f}" for px, py in pts) + f" L{w},{h} Z"
    return d


@lru_cache(maxsize=1)
def credits() -> list[dict]:
    p = ROOT / "triplens/static/img/credits.json"
    return json.loads(p.read_text()) if p.exists() else []


def counts() -> dict:
    corpus = ROOT / "data/corpus/index.sqlite"
    import sqlite3
    out = {"reports": None, "n_items": None, "requests311": None}
    if corpus.exists():
        con = sqlite3.connect(f"file:{corpus}?mode=ro", uri=True)
        out["reports"] = con.execute("SELECT COUNT(DISTINCT url) FROM pages").fetchone()[0]
        out["n_items"] = con.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        con.close()
    from . import reports
    out["requests311"] = len(reports.load_311()["requests"])
    return out


def sheet_clip(seed: int = 7, n: int = 140) -> str:
    """CSS polygon for a sheet of paper torn down its left side (right, top and bottom run off the screen)."""
    rnd = random.Random(seed)
    x = 1.2
    pts = ["100% 0%", "100% 100%"]
    for i in range(n, -1, -1):
        y = 100 * i / n
        x = (x if i < n else 1.2) * 0.55 + rnd.uniform(0, 1.6) * 0.45 if i < n else 1.2
        x = x + (1.1 if rnd.random() < .12 else 0)
        pts.append(f"{x:.2f}% {y:.2f}%")
    return "polygon(" + ", ".join(pts) + ")"


def brush(seed: int = 3, w: int = 300, h: int = 64) -> str:
    """SVG path for a dry-brush stroke: a band with ragged ends and a slightly uneven top and bottom."""
    rnd = random.Random(seed)
    top = [(x, rnd.uniform(4, 10)) for x in range(18, w - 17, 22)]
    bot = [(x, h - rnd.uniform(4, 10)) for x in range(w - 18, 17, -22)]
    right = [(w - rnd.uniform(0, 16), y) for y in range(8, h - 7, 7)]
    left = [(rnd.uniform(0, 16), y) for y in range(h - 8, 7, -7)]
    pts = top + right + bot + left
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
