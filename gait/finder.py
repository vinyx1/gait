"""Free, rule-based search for past decisions that may change a TTC route (no AI, no cost).

1. Retrieve: full-text search (SQLite FTS5) over staff-report pages for the route's main street(s).
2. Extract: keep sentences that match a change pattern (stop removed, relocated or closed; shelter removed; service cut;
   sidewalk closed; diversion) and mention the route's street, number or one of its cross streets.
3. Name stops: match cross streets in the sentence against the route's real stops (from the TTC schedule).
Each finding is an exact sentence from a page, with the rule that matched it, so it is explainable and checkable.
Findings are candidates for a person to review.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .trip import load_routes

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/corpus/index.sqlite"

STOPW = r"(?:bus |streetcar |transit |TTC )?stops?"
PATTERNS = [
    ("remove_stop", re.compile(rf"\b{STOPW}\b[^.]{{0,90}}\b(?:remov|eliminat|consolidat|discontinu)\w*|\b(?:remov|eliminat|consolidat)\w*\b[^.]{{0,60}}\b{STOPW}\b", re.I)),
    ("relocate_stop", re.compile(rf"\b{STOPW}\b[^.]{{0,70}}\brelocat\w*|\brelocat\w*[^.]{{0,60}}\b{STOPW}\b|\bfar[- ]side\b", re.I)),
    ("close_stop_temporary", re.compile(rf"\b{STOPW}\b[^.]{{0,70}}\b(?:temporar\w*\s+clos\w*|out of service|not be in service)", re.I)),
    ("remove_shelter", re.compile(r"\b(?:transit|bus|TTC) shelters?\b[^.]{0,70}\b(?:remov|relocat)\w*|\b(?:remov|relocat)\w*\b[^.]{0,60}\b(?:transit|bus|TTC) shelters?\b|\bbench(?:es)?\b[^.]{0,40}\bremov\w*", re.I)),
    ("service_change", re.compile(r"\b(?:service|frequency|headways?|trips)\b[^.]{0,60}\b(?:reduc|cut|eliminat|discontinu)\w*", re.I)),
    ("close_sidewalk", re.compile(r"\bsidewalks?\b[^.]{0,60}\b(?:clos|remov)\w*|\bpedestrian\w*\b[^.]{0,40}\bdetour\w*", re.I)),
    ("reroute", re.compile(r"\b(?:divert\w*|diversion|detour\w*|re-?rout\w*)\b", re.I)),
]
ABBR = {"Avenue": "Ave", "Street": "St", "Road": "Rd", "Drive": "Dr", "Boulevard": "Blvd", "Crescent": "Cres", "Court": "Ct", "Place": "Pl"}


def _short(s: str) -> str:
    return " ".join(ABBR.get(w, w) for w in s.split())


@lru_cache(maxsize=None)
def route_terms(route: str) -> dict:
    """Main street(s) and cross streets of a route, taken from its stop names ('Bathurst St at Heathdale Rd')."""
    e = load_routes()[route]
    mains, cross = Counter(), set()
    for v in e["variants"]:
        for s in v["stops"]:
            if " at " in s["name"]:
                a, b = s["name"].split(" at ", 1)
                mains[re.sub(r"\s+(West|East|North|South)$", "", a.strip())] += 1
                b = re.sub(r"\b(North|South|East|West) Side\b|\(.*?\)|-.*$", "", b).strip()
                if b:
                    cross.add(b)
    main = [m for m, n in mains.most_common(3) if n >= 4]
    return {"route": route, "name": e["long"], "main": main, "cross": sorted(cross)}


def _long_forms(short_name: str) -> list[str]:
    inv = {v: k for k, v in ABBR.items()}
    words = short_name.split()
    full = " ".join(inv.get(w, w) for w in words)
    base = " ".join(words[:-1]) if len(words) > 1 and words[-1] in inv else short_name
    return list(dict.fromkeys([short_name, full, base]))


@lru_cache(maxsize=4096)
def street_meets_route(route: str, street: str, within_m: float = 250) -> bool:
    """True if any City address point on `street` lies within `within_m` of the route's line (free, local data)."""
    from . import geocode
    from .access import haversine_m
    if not geocode.available():
        return False
    con = sqlite3.connect(f"file:{geocode.DB}?mode=ro", uri=True)
    pts = con.execute("SELECT lat, lon FROM addr WHERE street = ? LIMIT 400", (geocode.normalize(street),)).fetchall()
    con.close()
    shape = [p for v in load_routes()[route]["variants"][:2] for p in v["shape"][::2]]
    return any(haversine_m(a, b, c, d) <= within_m for a, b in pts for c, d in shape)


def sentences(text: str):
    for m in re.finditer(r"[^.;•]{20,600}[.;]", text):
        yield m.group(0).strip()


def find(route: str, limit_pages: int = 400) -> dict:
    t = route_terms(route)
    if not DB.exists() or not t["main"]:
        return {"route": route, "name": t["name"], "terms": t, "findings": [], "note": "No index or no main street found."}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    main_words = sorted({w for m in t["main"] for w in _long_forms(m)[-1].split() if len(w) > 3})
    q = " OR ".join(f'"{w}"' for w in main_words)
    rows = con.execute("SELECT text, url, item, page FROM pages WHERE pages MATCH ? ORDER BY rank LIMIT ?", (q, limit_pages)).fetchall()
    titles = dict(con.execute("SELECT item, title FROM items").fetchall())
    con.close()
    cross_forms = {c: _long_forms(c) for c in t["cross"]}
    main_forms = [f for m in t["main"] for f in _long_forms(m)]
    out, seen = [], set()
    STRONG = {"remove_stop", "relocate_stop", "close_stop_temporary", "remove_shelter"}
    street_re = re.compile(r"\b((?:[A-Z][a-z]+ ){0,2}[A-Z][a-z]+ (?:Road|Avenue|Street|Boulevard|Drive|Crescent|Court|Place|Rd|Ave|St|Blvd|Dr))\b")
    for text, url, item, page in rows:
        page_on_route = any(f in text for f in main_forms)
        for s in sentences(text):
            mentions_route = any(f in s for f in main_forms) or re.search(rf"\b{re.escape(route)}\s+{re.escape(t['name'].split()[0])}", s)
            named = [c for c, forms in cross_forms.items() if any(re.search(rf"\b{re.escape(f)}\b", s) for f in forms if len(f) > 3)]
            strong_here = any(k in STRONG and p.search(s) for k, p in PATTERNS)
            if not (mentions_route or named or (page_on_route and strong_here)):
                continue
            if not named and strong_here:
                found = list(dict.fromkeys(street_re.findall(s)))[:8]
                named = [n for n in found if street_meets_route(route, n)]
                if found and not named and not mentions_route:
                    continue          # the streets named are somewhere else
            for kind, pat in PATTERNS:
                m = pat.search(s)
                if not m:
                    continue
                key = (kind, s[:120])
                if key in seen:
                    break
                seen.add(key)
                score = 2 * bool(named) + bool(mentions_route) + 2 * (kind in STRONG) + (len(named) >= 2)
                out.append({"item_id": item, "item_title": titles.get(item, ""), "document_url": url, "page": page,
                            "change_type": kind, "stops_named": named, "quote": s[:600], "rule": m.group(0)[:120], "score": score})
                break
    out.sort(key=lambda f: (-f["score"], f["item_id"]))
    return {"route": route, "name": t["name"], "terms": t, "findings": out[:40]}
