"""A tile-free SVG schematic of the trip. No map service is contacted, so no location leaves the machine."""
from __future__ import annotations

import math
from html import escape

COLORS = ["#0b4f9c", "#9333ea", "#15803d", "#b45309"]


def render(legs, items, works, w: int = 640, h: int = 420, pad: int = 28) -> str:
    pts = [p for l in legs for p in l.points] + [(i["lat"], i["lon"]) for i in items]
    lat0 = sum(p[0] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    minx = min(p[1] for p in pts) * k; maxx = max(p[1] for p in pts) * k
    miny = min(p[0] for p in pts); maxy = max(p[0] for p in pts)
    dx, dy = max(maxx - minx, 1e-6), max(maxy - miny, 1e-6)
    s = min((w - 2 * pad) / dx, (h - 2 * pad) / dy)
    ox = pad + ((w - 2 * pad) - dx * s) / 2; oy = pad + ((h - 2 * pad) - dy * s) / 2

    def P(lat, lon):
        return ox + (lon * k - minx) * s, oy + (maxy - lat) * s

    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="mt md" xmlns="http://www.w3.org/2000/svg" class="tripmap">',
           '<title id="mt">Schematic map of your trip</title>',
           '<desc id="md">A simplified drawing of your trip with markers for decisions and works near it. The same information is listed in text below.</desc>',
           f'<rect width="{w}" height="{h}" fill="none" stroke="currentColor" stroke-opacity=".25"/>']
    ti = 0
    for l in legs:
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in (P(a, b) for a, b in l.points))
        if l.kind == "walk":
            out.append(f'<polyline points="{d}" fill="none" stroke="currentColor" stroke-opacity=".6" stroke-width="2" stroke-dasharray="5 4"/>')
        else:
            out.append(f'<polyline points="{d}" fill="none" stroke="{COLORS[ti % 4]}" stroke-width="4" stroke-linejoin="round"/>')
            ti += 1
            for st in (l.board, l.alight):
                x, y = P(st["lat"], st["lon"]); out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#fff" stroke="#000" stroke-width="1.5"/>')
    for n, wk in enumerate(works[:8], 1):
        x, y = P(wk["lat"], wk["lon"])
        out.append(f'<path d="M{x:.1f},{y-6:.1f} l6,6 l-6,6 l-6,-6 z" fill="#f59e0b" stroke="#000" stroke-width="1"><title>Works: {escape(wk["project"])}, {escape(wk["location"])}</title></path>')
    for n, it in enumerate(items, 1):
        x, y = P(it["lat"], it["lon"])
        out.append(f'<rect x="{x-8:.1f}" y="{y-8:.1f}" width="16" height="16" fill="{"#dc2626" if it["upcoming"] else "#6b7280"}" stroke="#fff"><title>Decision: {escape(it["title"])}</title></rect>'
                   f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="11" text-anchor="middle" fill="#fff" font-weight="700">{n}</text>')
    for lab, (a, b) in (("A", legs[0].points[0]), ("B", legs[-1].points[-1])):
        x, y = P(a, b)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#111" stroke="#fff" stroke-width="2"/><text x="{x:.1f}" y="{y+4:.1f}" font-size="12" text-anchor="middle" fill="#fff" font-weight="700">{lab}</text>')
    out.append("</svg>")
    return "".join(out)
