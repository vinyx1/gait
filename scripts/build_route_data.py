"""Build data/geo/routes.json: for every TTC route and direction, the line the vehicle follows and its stops in order.

Source: TTC GTFS (shapes.txt, trips.txt, stop_times.txt, stops.txt). For each route and direction we keep the one or two most
common shapes. Each stop is projected onto its shape and inserted as a vertex, so the line between any two stops can be cut out exactly.
Run: python scripts/build_route_data.py
"""
import csv
import io
import json
import math
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "data/gtfs/ttc_gtfs.zip"
TOL_M = 6.0


def rd(zf, name):
    return csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig"))


def xy(lat, lon, lat0):
    return lon * 111320 * math.cos(math.radians(lat0)), lat * 111320


def rdp(pts, tol):
    """Douglas-Peucker simplification in metres (iterative)."""
    if len(pts) < 3:
        return pts
    lat0 = pts[0][0]
    P = [xy(a, b, lat0) for a, b in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        s, e = stack.pop()
        ax, ay = P[s]; bx, by = P[e]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1e-9
        best, bi = -1, -1
        for i in range(s + 1, e):
            d = abs((P[i][0] - ax) * dy - (P[i][1] - ay) * dx) / L
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(s, bi), (bi, e)]
    return [p for p, k in zip(pts, keep) if k]


def project(line, lat, lon):
    """Nearest point on the polyline: (segment index, t, point)."""
    lat0 = lat
    px, py = xy(lat, lon, lat0)
    best = (1e18, 0, 0.0, line[0])
    for i in range(len(line) - 1):
        ax, ay = xy(*line[i], lat0); bx, by = xy(*line[i + 1], lat0)
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
        qx, qy = ax + t * dx, ay + t * dy
        d = math.hypot(px - qx, py - qy)
        if d < best[0]:
            best = (d, i, t, (line[i][0] + t * (line[i + 1][0] - line[i][0]), line[i][1] + t * (line[i + 1][1] - line[i][1])))
    return best[1], best[2], best[3]


def main() -> None:
    zf = zipfile.ZipFile(ZIP)
    routes = {r["route_id"]: r for r in rd(zf, "routes.txt")}
    stops = {r["stop_id"]: (r["stop_name"], float(r["stop_lat"]), float(r["stop_lon"])) for r in rd(zf, "stops.txt") if r["stop_lat"] and r["stop_lon"]}
    count = Counter(); rep = {}; head = {}; wc = defaultdict(Counter)
    for t in rd(zf, "trips.txt"):
        wc[t["route_id"]][t.get("wheelchair_accessible") or "0"] += 1
        k = (t["route_id"], t.get("direction_id") or "0", t["shape_id"])
        count[k] += 1
        rep.setdefault(k, t["trip_id"]); head.setdefault(k, t.get("trip_headsign", ""))
    chosen = []  # (route_id, direction, shape_id)
    by = defaultdict(list)
    for (r, d, s), n in count.items():
        by[(r, d)].append((n, s))
    for (r, d), lst in by.items():
        lst.sort(reverse=True)
        top = lst[0][0]
        for n, s in lst[:2]:
            if n >= 0.15 * top and s:
                chosen.append((r, d, s))
    want_shapes = {s for _, _, s in chosen}
    pts = defaultdict(list)
    for r in rd(zf, "shapes.txt"):
        if r["shape_id"] in want_shapes:
            pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
    trip_ids = {rep[(r, d, s)] for r, d, s in chosen}
    seq = defaultdict(list)
    rdr = csv.reader(io.TextIOWrapper(zf.open("stop_times.txt"), encoding="utf-8-sig"))
    h = next(rdr); it, iss, iq = h.index("trip_id"), h.index("stop_id"), h.index("stop_sequence")
    for row in rdr:
        if row[it] in trip_ids:
            seq[row[it]].append((int(row[iq]), row[iss]))
    out = {}
    for r, d, s in chosen:
        line = [(a, b) for _, a, b in sorted(pts[s])]
        if len(line) < 2:
            continue
        line = rdp(line, TOL_M)
        order = [sid for _, sid in sorted(seq[rep[(r, d, s)]]) if sid in stops]
        # project every stop and insert its projected point as a vertex
        proj = [(sid,) + project(line, stops[sid][1], stops[sid][2]) for sid in order]  # (sid, seg, t, point)
        ins = defaultdict(list)
        for sid, seg, t, p in proj:
            ins[seg].append((t, sid, p))
        new, where = [], {}
        for i, v in enumerate(line):
            new.append(v)
            for t, sid, p in sorted(ins.get(i, [])):
                new.append(p); where.setdefault(sid, len(new) - 1)
        r_short = routes[r]["route_short_name"]
        tot = sum(wc[r].values()) or 1
        ent = out.setdefault(r_short, {"short": r_short, "long": routes[r]["route_long_name"], "type": int(routes[r]["route_type"]),
                                       "trip_flags": {"accessible": round(wc[r]["1"] / tot, 2), "not_accessible": round(wc[r]["2"] / tot, 2),
                                                      "no_information": round(wc[r]["0"] / tot, 2)}, "variants": []})
        ent["variants"].append({
            "direction": int(d), "headsign": head[(r, d, s)], "trips": count[(r, d, s)],
            "shape": [[round(a, 5), round(b, 5)] for a, b in new],
            "stops": [{"id": sid, "name": stops[sid][0], "lat": stops[sid][1], "lon": stops[sid][2], "v": where[sid]}
                      for sid in order if sid in where]})
    data = {"meta": {"source": "TTC GTFS via City of Toronto Open Data", "simplification_m": TOL_M,
                     "note": "Most common one or two shapes per route and direction. Stops are projected onto the shape."},
            "routes": sorted(out.values(), key=lambda e: (e["type"] != 1, len(e["short"]), e["short"]))}
    (ROOT / "data/geo/routes.json").write_text(json.dumps(data, separators=(",", ":")))
    nv = sum(len(e["variants"]) for e in data["routes"])
    print(f"{len(data['routes'])} routes, {nv} variants", file=sys.stderr)


if __name__ == "__main__":
    main()
