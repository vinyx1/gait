"""Locate accessibility-related 311 service requests (City of Toronto open data) for the trip check.

311 gives the two streets of the nearest intersection, not coordinates. Each intersection is placed by:
  1. a TTC stop named "<street 1> at <street 2>" (either order), else
  2. the closest pair of City address points on the two streets (within 120 m), using their midpoint.
Requests that cannot be placed are counted and dropped. Output: data/geo/reports311.json
Usage: python scripts/build_311.py data/raw/311/SR2026.csv [more CSVs]
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gait import geocode  # noqa: E402
from gait.access import haversine_m, load_stops  # noqa: E402

# 311 type -> (our category, what it means for a rider)
TYPES = {
    "Bus Stops Snow Clearing Required": ("stop_snow", "Snow not cleared at a bus stop"),
    "Sidewalk Snow Clearing Required": ("sidewalk_snow", "Sidewalk snow not cleared"),
    "Icy Sidewalk Needs Salting": ("sidewalk_ice", "Icy sidewalk"),
    "Illegal Snow Dumping & Failure to Clear Snow or Ice on Public Sidewalk": ("sidewalk_snow", "Snow or ice left on the sidewalk"),
    "Snow at Intersections - Impeded Mobility": ("crossing_snow", "Snow blocking an intersection crossing"),
    "Damaged Concrete Sidewalk": ("sidewalk_damaged", "Damaged sidewalk"),
    "Curb - Damaged": ("curb_damaged", "Damaged curb"),
    "Sidewalk - Cleaning": ("sidewalk_dirty", "Sidewalk needs cleaning"),
    "Clean up Litter on Sidewalks and Boulevards": ("sidewalk_dirty", "Litter on the sidewalk"),
    "Traffic Signal Repair": ("signal_broken", "Traffic signal needing repair"),
}


def main(paths):
    con = sqlite3.connect(f"file:{geocode.DB}?mode=ro", uri=True)
    by_name = {}
    for s in load_stops()["stops"]:
        if " at " in s["name"]:
            a, b = (geocode.normalize(x) for x in s["name"].split(" at ", 1))
            by_name.setdefault((a, b), (s["lat"], s["lon"]))
            by_name.setdefault((b, a), (s["lat"], s["lon"]))
    pts_cache, place_cache = {}, {}

    def pts(street):
        if street not in pts_cache:
            pts_cache[street] = con.execute("SELECT lat, lon FROM addr WHERE street = ?", (street,)).fetchall()[::3]
        return pts_cache[street]

    def place(s1, s2):
        k = (s1, s2)
        if k in place_cache:
            return place_cache[k]
        p = by_name.get(k)
        if not p:
            best = None
            for a, b in pts(s1):
                for c, d in pts(s2):
                    if abs(a - c) < 0.0015 and abs(b - d) < 0.002:
                        dist = haversine_m(a, b, c, d)
                        if dist < 120 and (best is None or dist < best[0]):
                            best = (dist, ((a + c) / 2, (b + d) / 2))
            p = best[1] if best else None
        place_cache[k] = p
        return p

    out, dropped = [], 0
    for path in paths:
        for r in csv.DictReader(open(path, encoding="utf-8", errors="ignore")):
            t = TYPES.get(r["Service Request Type"])
            if not t or not r["Intersection Street 1"] or not r["Intersection Street 2"]:
                continue
            s1, s2 = geocode.normalize(r["Intersection Street 1"]), geocode.normalize(r["Intersection Street 2"])
            p = place(s1, s2)
            if not p:
                dropped += 1
                continue
            out.append({"cat": t[0], "label": t[1], "type311": r["Service Request Type"], "date": r["Creation Date"][:10],
                        "status": r["Status"], "at": f"{r['Intersection Street 1']} & {r['Intersection Street 2']}",
                        "lat": round(p[0], 6), "lon": round(p[1], 6)})
    dest = ROOT / "data/geo/reports311.json"
    dest.write_text(json.dumps({"source": "City of Toronto Open Data: 311 Service Requests - Customer Initiated",
                                "files": [Path(p).name for p in paths], "requests": out}))
    print(f"placed {len(out)}, could not place {dropped} -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1:])
