"""Walking routes on the City of Toronto Pedestrian Network (sidewalks, walkways, crossings).

Builds a graph once (data/geo/pednet_graph.pkl) and finds walking paths with Dijkstra. For riders using a wheelchair
or walker, segments with no sidewalk or laneways cost three times their length, so the path prefers sidewalks.
The City notes the network has known gaps; when no path is found the caller falls back to a straight line.
"""
from __future__ import annotations

import csv
import heapq
import json
import math
import pickle
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data/geo/pednet.csv"
PKL = ROOT / "data/geo/pednet_graph.pkl"
NO_SIDEWALK = ("No sidewalk", "Laneway without")
CROSS = {"ts": "traffic signal", "pc": "pedestrian crossover", "ns": "no signal"}


def _key(lon, lat):
    return (round(lon, 5), round(lat, 5))


def build() -> None:
    csv.field_size_limit(10 ** 8)
    nodes, edges = {}, []          # node key -> id ; edges: (a, b, length, desc, cross, coords)
    def nid(k):
        if k not in nodes:
            nodes[k] = len(nodes)
        return nodes[k]
    with open(CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                g = json.loads(r["geometry"])
            except Exception:
                continue
            lines = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            for line in lines:
                if len(line) < 2:
                    continue
                L = sum(_hav(a[1], a[0], b[1], b[0]) for a, b in zip(line, line[1:]))
                edges.append((nid(_key(*line[0][:2])), nid(_key(*line[-1][:2])), L, r["SIDEWALK_DESCRIPTION"],
                              (r["CROSSWALK_TYPE"] or "").strip(), [(round(p[1], 6), round(p[0], 6)) for p in line]))
    coords = [None] * len(nodes)
    for (lon, lat), i in nodes.items():
        coords[i] = (lat, lon)
    adj = [[] for _ in nodes]
    for ei, (a, b, *_rest) in enumerate(edges):
        adj[a].append((b, ei)); adj[b].append((a, ei))
    grid = {}
    for i, (lat, lon) in enumerate(coords):
        grid.setdefault((int(lat / 0.002), int(lon / 0.003)), []).append(i)
    PKL.write_bytes(pickle.dumps({"coords": coords, "edges": edges, "adj": adj, "grid": grid}))


def _hav(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111320
    dx = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


@lru_cache(maxsize=1)
def graph():
    return pickle.loads(PKL.read_bytes()) if PKL.exists() else None


def available() -> bool:
    return PKL.exists()


def nearest(lat, lon, max_m=150):
    g = graph()
    gy, gx = int(lat / 0.002), int(lon / 0.003)
    best, bi = 1e18, None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for i in g["grid"].get((gy + dy, gx + dx), []):
                d = _hav(lat, lon, *g["coords"][i])
                if d < best:
                    best, bi = d, i
    return (bi, best) if bi is not None and best <= max_m else (None, None)


def route(a: tuple[float, float], b: tuple[float, float], avoid_no_sidewalk: bool, max_m: float = 4000, blocked: frozenset = frozenset()):
    """Return dict(points, length_m, no_sidewalk_m, crossings{type:count}, snap_m) or None."""
    if not available():
        return None
    g = graph()
    s, ds = nearest(*a); t, dt = nearest(*b)
    if s is None or t is None:
        return None
    dist, prev = {s: 0.0}, {}
    pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            break
        if d > dist.get(u, 1e18) or d > max_m * 3:
            continue
        for v, ei in g["adj"][u]:
            e = g["edges"][ei]
            if ei in blocked:
                continue
            w = e[2] * (3 if avoid_no_sidewalk and e[3].startswith(NO_SIDEWALK) else 1)
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, (u, ei)
                heapq.heappush(pq, (nd, v))
    if t not in prev and s != t:
        return None
    path, node = [], t
    while node != s:
        u, ei = prev[node]
        path.append((u, node, ei)); node = u
    path.reverse()
    pts = [a]
    length, nosw, cross = ds + dt, 0.0, {}
    for u, v, ei in path:
        e = g["edges"][ei]
        seg = e[5] if e[0] == u else list(reversed(e[5]))
        pts.extend(seg)
        length += e[2]
        if e[3].startswith(NO_SIDEWALK):
            nosw += e[2]
        if e[4] in CROSS:
            cross[CROSS[e[4]]] = cross.get(CROSS[e[4]], 0) + 1
    pts.append(b)
    if length > max_m:
        return None
    return {"points": pts, "length_m": round(length), "no_sidewalk_m": round(nosw), "crossings": cross, "snap_m": round(ds + dt)}


def edges_near(points: list[tuple[float, float]], radius_m: float = 20) -> frozenset:
    """Edge ids with any vertex within radius of the given points (used to close a sidewalk stretch)."""
    g = graph()
    if not g:
        return frozenset()
    out = set()
    for ei, e in enumerate(g["edges"]):
        c = e[5]
        # vertices and segment midpoints: a two-vertex sidewalk edge can be closed by a point at its middle
        for (la, lo) in c + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(c, c[1:])]:
            if any(_hav(la, lo, p[0], p[1]) <= radius_m for p in points):
                out.add(ei)
                break
    return frozenset(out)
