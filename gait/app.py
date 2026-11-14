"""Gait web app: explain layer (v0). Server-rendered, text-first, no JavaScript required."""
from __future__ import annotations

from functools import lru_cache

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

app = FastAPI(title="Gait")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

from . import access, changes, exposure, geocode, reports, svgmap, trip as tripmod
from .agents import dedupe, flatten_kept, valid_partition, ROLES

PARTICIPATE_URL = "https://www.toronto.ca/city-government/council/council-committee-meetings/participate/"

from .labels import PLAIN_STATUS, UPCOMING, latest_stage, plain, item_plain  # noqa: F401


def load_items() -> dict[str, dict]:
    items = {}
    for p in sorted((DATA / "items").glob("*.json")):
        d = json.loads(p.read_text())
        items[d["item_id"]] = d
    return items


def load_reports() -> dict[str, dict]:
    idx_path = DATA / "reports" / "index.json"
    if not idx_path.exists():
        return {}
    out = {}
    for url, name in json.loads(idx_path.read_text()).items():
        out[url] = json.loads((DATA / "reports" / f"{name}.json").read_text())
    return out


def load_plain(item_id: str) -> list[dict]:
    """Checked plain-language rewrites written by Claude. See gait/rewrite.py for the checks."""
    import re
    path = DATA / "plain" / f"{item_id}.json"
    if not path.exists():
        return []
    out = []
    for rw in json.loads(path.read_text()):
        if not rw["sentences"]:
            continue
        parts = len(re.findall(r"(?m)(?:^|\s)\d{1,2}\.\s+[A-Z]", rw["source"]))
        rw["long"] = parts > 8 or len(rw["source"]) > 4000
        rw["parts"] = parts
        out.append(rw)
    return out


def load_notes(item_id: str) -> list[dict]:
    path = DATA / "notes" / f"{item_id}.json"
    return json.loads(path.read_text()) if path.exists() else []


def item_reports(item: dict, reports: dict[str, dict]) -> list[dict]:
    out, seen = [], set()
    for st in item["stages"]:
        for b in st["background"]:
            r = reports.get(b["url"])
            if r and b["url"] not in seen:
                seen.add(b["url"])
                out.append({"stage": st["body"], "when": b.get("date"), "url": b["url"], **r})
    return out


def open_window_note(item: dict) -> dict:
    """Never infer a deadline. Say only what the saved official page shows."""
    st = latest_stage(item)
    if item.get("upcoming"):
        acts = item.get("actions") or []
        return {
            "kind": "upcoming",
            "meeting": f"{st['body']}, {st['dates_text']}",
            "actions": acts,
            "text": ("The official page lists these ways to take part: " + (", ".join(acts) if acts else "none shown") +
                     ". It shows no deadline for this item. The City's participation page says to register "
                     "to speak by 12:00 p.m. the day before the meeting at the latest, but you should confirm "
                     "that on the live item page. Comments that arrive too late are not distributed."),
        }
    return {"kind": "closed", "meeting": None, "actions": [],
            "text": ("The saved copy of the official page shows a decision or referral already recorded, "
                     "and no open comment or speaking window. Check the live item page for 'Request to Speak' "
                     "or 'Submit Comments' buttons before acting.")}


def caveats(item: dict, reports: list[dict]) -> list[str]:
    out = []
    st = latest_stage(item)
    if item.get("upcoming"):
        out.append("This item has not been decided. The recommendation can change before or at the meeting.")
    if st["status"] == "Referred":
        out.append("This item was referred, so the request itself was not decided. "
                   "The outcome depends on a later report from staff.")
    if any("without debate" in t for t in item["tracking_status"]):
        out.append("Council approved this on consent, without a separate discussion.")
    if item["stages"] and not any(s["votes"] for s in item["stages"]) and not item.get("upcoming"):
        out.append("No recorded vote appears on the saved page. Not every decision has a recorded vote.")
    if not reports:
        out.append("The linked report could not be read here, so only the official item page text is shown.")
    out.append("Report text is copied exactly from the PDF with page numbers. Nothing here is rewritten or summarised by AI. "
               "Tables, maps and attachments are not read.")
    out.append("Public letters and e-mails are counted but not shown, to avoid displaying personal information.")
    return out


@app.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    from . import landing
    cases = [landing.case(k) for k in ("bathurst", "harbord", "frontst")]
    return templates.TemplateResponse(request, "landing.html", {"hero": landing.hero(), "cases": cases, "counts": landing.counts(),
                                                                "credits": landing.credits(), "torn": landing.torn,
                                                                "sheet_clip": landing.sheet_clip(), "brush": landing.brush()})


@app.get("/decisions", response_class=HTMLResponse)
def index(request: Request):
    items = load_items()
    upcoming, decided = [], []
    for it in items.values():
        st = latest_stage(it)
        label, _ = item_plain(it)
        row = {"id": it["item_id"], "title": it["title"], "body": st["body"],
               "date": st["dates_text"], "label": label}
        (upcoming if it.get("upcoming") else decided).append(row)
    return templates.TemplateResponse(request, "index.html", {"upcoming": upcoming, "decided": decided})


@app.get("/item/{item_id}", response_class=HTMLResponse)
def item_page(request: Request, item_id: str):
    items = load_items()
    item = items.get(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    reports = item_reports(item, load_reports())
    st = latest_stage(item)
    label, explain = item_plain(item)
    primary = next((r for r in reports if r["recommendations"]), None)
    ctx = {"item": item, "latest": st, "label": label, "explain": explain,
           "window": open_window_note(item), "caveats": caveats(item, reports),
           "participate_url": PARTICIPATE_URL, "reports": reports, "primary": primary,
           "plain": lambda s: plain(s), "rewrites": load_plain(item_id), "notes": load_notes(item_id),
           "access_locs": [l for l in load_locations().values() if item_id in l["item_ids"]]}
    return templates.TemplateResponse(request, "item.html", ctx)


def load_locations() -> dict[str, dict]:
    p = DATA / "locations.json"
    return {l["id"]: l for l in json.loads(p.read_text())} if p.exists() else {}


def audit_for(loc_id: str, persona: str) -> dict | None:
    p = DATA / "audits" / f"{loc_id}__{persona}.json"
    if not p.exists():
        return None
    a = json.loads(p.read_text())
    flat = flatten_kept(a)
    if a.get("groups") and valid_partition(a["groups"], len(flat)):
        kept = [flat[g[0]] for g in a["groups"]]          # first finding of each group of duplicates
    else:
        kept = dedupe(flat)
    # only the fixed rules may mark a barrier, so any older 'barrier' label from an agent is shown as 'worth knowing'
    kept = [(r, {**f, "severity": "watch"} if f.get("severity") == "barrier" else f) for r, f in kept]
    order = {"watch": 0, "info": 1}
    kept.sort(key=lambda x: order.get(x[1]["severity"], 2))
    calls = {cid: c for r in a["roles"] for cid, c in r["calls"].items()}
    a["findings"] = [{"role": ROLES[role]["label"], **f} for role, f in kept]
    a["shown"], a["more"] = a["findings"][:8], a["findings"][8:]
    a["dropped_count"] = sum(len(r["dropped"]) for r in a["roles"])
    a["tool_calls"] = sum(len(r["calls"]) for r in a["roles"])
    return a


@app.get("/access/{loc_id}", response_class=HTMLResponse)
def access_page(request: Request, loc_id: str, persona: str = Query("wheelchair")):
    locs = load_locations()
    loc = locs.get(loc_id)
    if loc is None:
        raise HTTPException(404, "Location not found")
    if persona not in access.PERSONAS:
        persona = "wheelchair"
    snaps = {k: access.snapshot(loc["lat"], loc["lon"], k) for k in access.PERSONAS}
    ctx = {"loc": loc, "persona": persona, "personas": access.PERSONAS, "snaps": snaps, "snap": snaps[persona],
           "audit": audit_for(loc_id, persona), "wc": access.WC_TEXT, "meta": access.load_stops()["meta"],
           "items": load_items()}
    return templates.TemplateResponse(request, "access.html", ctx)


# ---------- route check: the resident tells us the route they take ----------

EXAMPLES = {
    "queen-beverley": {"title": "Parkdale to Beverley St on the 501 Queen streetcar (wheelchair user)", "origin": "1337 Queen St W",
                       "destination": "106 Beverley St", "rider": "wheelchair", "band": "day", "day": "weekday",
                       "routes": ["501"], "stops": [(1, "6835", "6829")]},
    "dundas-505": {"title": "Along Dundas St W on the 505 streetcar (wheelchair user): a decision names this route", "origin": "1000 Dundas St W",
                   "destination": "201 Dundas St W", "rider": "wheelchair", "band": "day", "day": "weekday",
                   "routes": ["505"], "stops": [(0, "10181", "2153")]},
    "spadina-127": {"title": "Spadina Rd to Bathurst St on the 127 bus (someone using a walker): a decided item and works nearby",
                    "origin": "250 Spadina Rd", "destination": "800 Bathurst St", "rider": "senior_walker", "band": "day", "day": "weekday",
                    "routes": ["127"], "stops": [(0, "7956", "14777")]},
    "bathurst-7-past": {"title": "PAST DECISION: 7 Bathurst after RapidTO (July 2025) removed the Heathdale Rd stop (someone using a walker)",
                        "origin": "1599 Bathurst St", "destination": "800 Bathurst St", "rider": "senior_walker", "band": "day", "day": "weekday",
                        "routes": ["7"], "stops": [(1, "107", "14617")]},
    "transfer-late": {"title": "Spadina Rd to Gerrard St E with a transfer, late night (shift worker)", "origin": "250 Spadina Rd",
                      "destination": "66 Gerrard St E", "rider": "shift_worker", "band": "late", "day": "weekday",
                      "routes": ["127", "506"], "stops": [(0, "7956", "14777"), (0, "14776", "751")]},
}


def _route_key(text: str) -> str | None:
    """Accept '505', '505 Dundas' or '505 - Dundas' from the route list."""
    tok = (text or "").strip().replace("\u2014", " ").replace("-", " ").split()
    if not tok:
        return None
    routes = tripmod.load_routes()
    for cand in (tok[0], tok[0].upper()):
        if cand in routes:
            return cand
    return None


def _form_ctx(**kw):
    base = {"routes": tripmod.route_choices(), "personas": access.PERSONAS, "bands": {k: v[0] for k, v in exposure.BANDS.items()},
            "days": exposure.DAYS, "examples": EXAMPLES, "errors": [], "v": {}, "have_geo": geocode.available()}
    base.update(kw)
    return base


def make_report(origin_text, dest_text, rider, band, day, route_keys, chosen):
    """Return (report dict, errors). chosen = [(variant, board_id, alight_id), ...], one per route, exactly as the resident picked them."""
    errors = []
    o, so = geocode.lookup(origin_text)
    d, sd = geocode.lookup(dest_text)
    if not o:
        errors.append(f"We could not find the start address '{origin_text}'." + (" Did you mean: " + "; ".join(p.label for p in so) + "?" if so else ""))
    if not d:
        errors.append(f"We could not find the destination '{dest_text}'." + (" Did you mean: " + "; ".join(p.label for p in sd) + "?" if sd else ""))
    if errors:
        return None, errors
    try:
        legs = tripmod.build_trip((o.lat, o.lon), (d.lat, d.lon),
                                  [(r, vi, b, a) for r, (vi, b, a) in zip(route_keys, chosen)],
                                  avoid_no_sidewalk=rider in ("wheelchair", "senior_walker"))
    except ValueError as e:
        return None, [str(e)]
    res = exposure.analyze(legs, rider, band, day)
    res["comparisons"] = [changes.compare(legs, c, rider, band, day) for c in changes.affecting(legs)]
    res.update({"origin": o, "dest": d, "svg": svgmap.render(legs, res["decisions"], res["works"]), "routes": route_keys,
                "stops": [(l.board["name"], l.alight["name"], l.route, tripmod.load_routes()[l.route]["long"]) for l in legs if l.kind == "transit"]})
    return res, []


@app.get("/route", response_class=HTMLResponse)
def route_form(request: Request):
    return templates.TemplateResponse(request, "route_form.html", _form_ctx())


@app.get("/route/example/{key}", response_class=HTMLResponse)
def route_example(request: Request, key: str):
    ex = EXAMPLES.get(key)
    if not ex:
        raise HTTPException(404, "Example not found")
    rep, errs = make_report(ex["origin"], ex["destination"], ex["rider"], ex["band"], ex["day"], ex["routes"], ex["stops"])
    if errs:
        return templates.TemplateResponse(request, "route_form.html", _form_ctx(errors=errs))
    return templates.TemplateResponse(request, "route_result.html", {"rep": rep, "persona": ex["rider"], "personas": access.PERSONAS,
                                                                       "example": ex, "q": ex["origin"] + " to " + ex["destination"]})


@app.post("/route/stops", response_class=HTMLResponse)
def route_stops(request: Request, origin: str = Form(...), destination: str = Form(...), rider: str = Form("wheelchair"),
                band: str = Form("day"), day: str = Form("weekday"), route1: str = Form(...), route2: str = Form("")):
    v = {"origin": origin, "destination": destination, "rider": rider, "band": band, "day": day, "route1": route1, "route2": route2}
    errors = []
    if not geocode.available():
        errors.append("The local address file has not been built. Run scripts/build_address_index.py.")
    keys = [_route_key(route1)] + ([_route_key(route2)] if route2.strip() else [])
    if keys[0] is None:
        errors.append(f"We do not recognise the route '{route1}'. Pick one from the list.")
    if route2.strip() and keys[-1] is None:
        errors.append(f"We do not recognise the route '{route2}'. Pick one from the list.")
    if rider not in access.PERSONAS or band not in exposure.BANDS or day not in exposure.DAYS:
        errors.append("Please choose a rider, a day and a time of day.")
    if not errors:
        o, so = geocode.lookup(origin); d, sd = geocode.lookup(destination)
        if not o:
            errors.append(f"We could not find the start address '{origin}'." + (" Did you mean: " + "; ".join(p.label for p in so) + "?" if so else ""))
        if not d:
            errors.append(f"We could not find the destination '{destination}'." + (" Did you mean: " + "; ".join(p.label for p in sd) + "?" if sd else ""))
    if errors:
        return templates.TemplateResponse(request, "route_form.html", _form_ctx(errors=errors, v=v))
    rides = []
    for i, r in enumerate(keys):
        entry = tripmod.load_routes()[r]
        groups = []
        for vi, var in enumerate(entry["variants"]):
            stops = []
            for s in var["stops"]:
                near_o = round(access.haversine_m(o.lat, o.lon, s["lat"], s["lon"])) if i == 0 else None
                near_d = round(access.haversine_m(d.lat, d.lon, s["lat"], s["lon"])) if i == len(keys) - 1 else None
                stops.append({"value": f"{vi}:{s['id']}", "name": s["name"],
                              "note_on": f"{near_o} m from your start" if near_o is not None else "",
                              "note_off": f"{near_d} m from your destination" if near_d is not None else ""})
            groups.append({"label": var["headsign"] or f"Direction {var['direction']}", "stops": stops})
        rides.append({"index": i, "route": r, "long": entry["long"], "groups": groups})
    return templates.TemplateResponse(request, "route_stops.html", {"v": v, "rides": rides, "o": o, "d": d, "keys": keys, "personas": access.PERSONAS})


@app.post("/route/result", response_class=HTMLResponse)
async def route_result(request: Request):
    f = await request.form()
    origin, dest = f.get("origin", ""), f.get("destination", "")
    rider, band, day = f.get("rider", "wheelchair"), f.get("band", "day"), f.get("day", "weekday")
    keys, chosen, errors = [], [], []
    i = 0
    while f.get(f"route{i}"):
        keys.append(f.get(f"route{i}"))
        b, a = f.get(f"board{i}", ""), f.get(f"alight{i}", "")
        try:
            bv, bid = b.split(":", 1); av, aid = a.split(":", 1)
            if bv != av:
                errors.append(f"For route {keys[-1]}, the two stops must be in the same direction of travel.")
            chosen.append((int(bv), bid, aid))
        except Exception:
            errors.append(f"Please choose both stops for route {keys[-1]}.")
        i += 1
    if not keys:
        errors.append("No route was given.")
    if rider not in access.PERSONAS or band not in exposure.BANDS or day not in exposure.DAYS:
        errors.append("Please choose a rider, a day and a time of day.")
    if errors:
        return templates.TemplateResponse(request, "route_form.html", _form_ctx(errors=errors))
    rep, errs = make_report(origin, dest, rider, band, day, keys, chosen)
    if errs:
        return templates.TemplateResponse(request, "route_form.html", _form_ctx(errors=errs))
    return templates.TemplateResponse(request, "route_result.html", {"rep": rep, "persona": rider, "personas": access.PERSONAS,
                                                                       "example": None, "q": origin + " to " + dest})


# ---------- interactive map (JSON endpoints used by /map) ----------

def _ll(points):
    return [[round(p[1], 6), round(p[0], 6)] for p in points]


def _legs_geojson(legs):
    feats = []
    for l in legs:
        props = {"kind": l.kind, "label": l.label, "length_m": tripmod.walk_estimate_m(l) if l.kind == "walk" else l.length_m,
                 "route": l.route, "routed": bool(l.stats), "no_sidewalk_m": (l.stats or {}).get("no_sidewalk_m"),
                 "crossings": (l.stats or {}).get("crossings")}
        feats.append({"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": _ll(l.points)}})
    return {"type": "FeatureCollection", "features": feats}


def _removed_stop_ids():
    out = {}
    for c in changes.load_changes().values():
        for e in c["effects"]:
            if e["type"] == "remove_stop":
                for s in e["stop_ids"]:
                    out[s] = c["title"]
    return out


@app.get("/map", response_class=HTMLResponse)
def map_page(request: Request):
    return templates.TemplateResponse(request, "map.html", {"personas": access.PERSONAS,
                                                            "bands": {k: v[0] for k, v in exposure.BANDS.items()}, "days": exposure.DAYS})


@app.get("/api/routes_near")
def routes_near(alat: float, alon: float, blat: float, blon: float, radius: float = 800):
    """Routes with a stop within `radius` of A and a later stop within `radius` of B. Listed by route number, not ranked."""
    out = []
    for short, e in tripmod.load_routes().items():
        for vi, v in enumerate(e["variants"]):
            st = v["stops"]
            da = [access.haversine_m(alat, alon, s["lat"], s["lon"]) for s in st]
            db = [access.haversine_m(blat, blon, s["lat"], s["lon"]) for s in st]
            ok = any(da[i] <= radius and any(db[j] <= radius for j in range(i + 1, len(st))) for i in range(len(st)))
            if ok:
                out.append({"route": short, "name": e["long"], "variant": vi, "headsign": v["headsign"], "type": e["type"]})
    out.sort(key=lambda r: (len(r["route"]), r["route"], r["variant"]))
    return out


@app.get("/api/route_stops")
def route_stops_api(route: str, variant: int):
    e = tripmod.load_routes().get(route)
    if not e or not (0 <= variant < len(e["variants"])):
        raise HTTPException(404, "route not found")
    v, recs, gone = e["variants"][variant], tripmod.stop_records(), _removed_stop_ids()
    feats = []
    for s in v["stops"]:
        r = recs.get(s["id"], {})
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                      "properties": {"id": s["id"], "name": s["name"], "shelter": bool(r.get("shelter_listed")), "bench": bool(r.get("bench_listed")),
                                     "boarding": access.WC_TEXT.get(r.get("wheelchair_boarding", "0"), "unknown"), "removed_by": gone.get(s["id"])}})
    line = {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": _ll(v["shape"])}}
    return {"stops": {"type": "FeatureCollection", "features": feats}, "line": line, "route": route, "name": e["long"], "headsign": v["headsign"]}


def _headline(cmp: dict, rider: str) -> dict | None:
    """The one walk this decision changes most, for the verdict at the top of its card (None if no walk changes)."""
    best, k = None, -1
    for lb, la in zip(cmp["before_legs"], cmp["after_legs"]):
        if lb.kind == "walk":
            k += 1
            b, a = tripmod.walk_estimate_m(lb), tripmod.walk_estimate_m(la)
            if a != b and (best is None or abs(a - b) > abs(best["after_m"] - best["before_m"])):
                best = {"what": "Your walk to the stop" if la is cmp["after_legs"][0] else "Your walk from the stop",
                        "before_m": b, "after_m": a, "leg": k}
    if best:
        p = access.PERSONAS[rider]
        best["limit_m"] = p.max_walk_m
        # the same sentence the findings use: where you walk today, where you would walk, against the limit
        best["say"] = changes.walk_change_say(cmp["before_legs"], cmp["after_legs"], best["leg"], p.max_walk_m, p.label.lower(),
                                              cmp["change"].get("phase") == "implemented")
    return best


def _hull(pts: list[tuple[float, float]]) -> list[list[float]]:
    """Convex hull (lon, lat) of the points, closed ring."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return [list(p) for p in pts + pts[:1]]
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    ring = lo[:-1] + up[:-1]
    return [list(p) for p in ring + ring[:1]]


def _bubble(latlons: list[tuple[float, float]], pad_m: float = 70) -> list[list[float]]:
    """A rounded area round the affected places: each point grown into a small circle, then wrapped."""
    import math
    out = []
    for lat, lon in latlons:
        k = 111320 * math.cos(math.radians(lat))
        out += [(round(lon + pad_m * math.cos(a) / k, 6), round(lat + pad_m * math.sin(a) / 111320, 6))
                for a in (i * math.pi / 8 for i in range(16))]
    return _hull(out)


@lru_cache(maxsize=None)
def decision_area(cid: str) -> dict:
    """Where a decision lands: its bubble, the stops it removes, closes, moves or changes, and the sidewalks and roads it closes."""
    from . import walk
    c = changes.load_changes()[cid]
    routes, recs = tripmod.load_routes(), tripmod.stop_records()
    stop_at = lambda route, sid: next(((s["lat"], s["lon"], s["name"]) for v in routes[route]["variants"] for s in v["stops"] if s["id"] == sid), None)
    pts, stops, lines, seen = [], [], [], set()
    verb = {"remove_stop": "would be removed" if c.get("phase") != "implemented" else "removed", "close_stop": "closed for a time",
            "remove_shelter": "shelter removed", "remove_bench": "bench removed", "add_shelter": "new shelter", "bus_bike_platform": "bus/bike platform"}
    for e in c["effects"]:
        t = e["type"]
        if t in verb:
            for sid in e["stop_ids"]:
                s = stop_at(e["route"], sid)
                if s and (s[0], s[1], t) not in seen:
                    seen.add((s[0], s[1], t)); pts.append(s[:2])
                    stops.append({"lat": s[0], "lon": s[1], "name": s[2], "what": verb[t], "gone": t in ("remove_stop", "close_stop")})
        elif t == "restore_removed_stops":
            for r in changes.restored_stops(c, e["route"]):
                still = any(access.haversine_m(r["lat"], r["lon"], s["lat"], s["lon"]) < 40 for s in routes[e["route"]]["variants"][r["variant"]]["stops"])
                if still or any(access.haversine_m(r["lat"], r["lon"], x["lat"], x["lon"]) < 15 for x in stops):
                    continue                     # a stop is still there in this direction (or already drawn): not removed here
                pts.append((r["lat"], r["lon"]))
                stops.append({"lat": r["lat"], "lon": r["lon"], "name": r["name"].split(" (")[0], "what": "removed (location reconstructed)", "gone": True})
        elif t == "relocate_stop":
            for sid in e["stop_ids"]:
                s = stop_at(e["route"], sid)
                if s:
                    pts += [s[:2], (e["to"]["lat"], e["to"]["lon"])]
                    stops.append({"lat": s[0], "lon": s[1], "name": s[2], "what": "moves away", "gone": True})
                    stops.append({"lat": e["to"]["lat"], "lon": e["to"]["lon"], "name": e["to"]["name"], "what": "new spot", "gone": False})
        elif t == "close_sidewalk":
            g = walk.graph()
            for ei in sorted(walk.edges_near([tuple(p) for p in e["points"]], e.get("radius_m", 20))):
                ln = g["edges"][ei][5]; pts += ln
                lines.append({"kind": "sidewalk", "label": "Sidewalk closed" + (f" ({e['from']} to {e['to']})" if e.get("from") else ""), "coords": [[lo, la] for la, lo in ln]})
        elif t == "map_line":
            pts += [tuple(p) for p in e["line"]]
            lines.append({"kind": e.get("kind", "road"), "label": e["label"], "coords": [[lo, la] for la, lo in e["line"]]})
    phase = "simulation" if c["simulated"] else "in effect" if c.get("phase") == "implemented" else "approved" if c["status"].lower().startswith("approved") else "proposed"
    props = {"id": cid, "title": c["title"].replace("SIMULATED: ", ""), "phase": phase}
    feats = []
    # places close together share one bubble; a long corridor (nine stops over kilometres) gets one bubble per cluster
    groups = []
    for p in pts:
        near = [g for g in groups if any(access.haversine_m(p[0], p[1], q[0], q[1]) < 450 for q in g)]
        merged = [p] + [q for g in near for q in g]
        groups = [g for g in groups if g not in near] + [merged]
    for g in groups:
        feats.append({"type": "Feature", "properties": {**props, "kind": "area"}, "geometry": {"type": "Polygon", "coordinates": [_bubble(g)]}})
    feats += [{"type": "Feature", "properties": {**props, "kind": "line", "line": l["kind"], "label": l["label"]},
               "geometry": {"type": "LineString", "coordinates": l["coords"]}} for l in lines]
    feats += [{"type": "Feature", "properties": {**props, "kind": "stop", "name": s["name"], "what": s["what"], "gone": s["gone"]},
               "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]}} for s in stops]
    return {"type": "FeatureCollection", "features": feats}


@app.get("/api/decision_areas")
def decision_areas(include_sim: bool = False):
    """Every decision on file drawn where it lands (simulations only on request)."""
    feats = [f for cid, c in changes.load_changes().items() if include_sim or not c["simulated"] for f in decision_area(cid)["features"]]
    return {"type": "FeatureCollection", "features": feats}


@lru_cache(maxsize=1)
def developments() -> list[dict]:
    """New buildings the City approved (scripts/build_developments.py): site, storeys and the City's own sentences."""
    p = DATA / "developments.json"
    return json.loads(p.read_text())["items"] if p.exists() else []


def _dev_feature(d: dict) -> dict:
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [_bubble([(d["lat"], d["lon"])], 55)]},
            "properties": {"id": d["id"], "address": d["address"], "storeys": d["storeys"], "status": d["status"]}}


@app.get("/api/developments")
def developments_api():
    return {"type": "FeatureCollection", "features": [_dev_feature(d) for d in developments()]}


def developments_near(legs, radius_m: float = 300) -> list[dict]:
    """Approved buildings within radius of the rider's stops and walks, nearest first. Nothing is computed from them."""
    pts = [p for l in legs if l.kind == "walk" for p in l.points] + \
          [(s["lat"], s["lon"]) for l in legs if l.kind == "transit" for s in (l.board, l.alight)]
    out = []
    for d in developments():
        m = min((access.haversine_m(d["lat"], d["lon"], a, b) for a, b in pts), default=1e9)
        if m <= radius_m:
            out.append({**d, "distance_m": round(m / 10) * 10})
    return sorted(out, key=lambda d: d["distance_m"])


@app.post("/api/trip")
async def trip_api(request: Request):
    body = await request.json()
    try:
        a, b = tuple(body["a"]), tuple(body["b"])
        rider, band, day = body.get("rider", "wheelchair"), body.get("band", "day"), body.get("day", "weekday")
        rides = [(r["route"], int(r["variant"]), str(r["board"]), str(r["alight"])) for r in body["rides"]]
        if rider not in access.PERSONAS or band not in exposure.BANDS or day not in exposure.DAYS or not rides:
            raise ValueError("bad options")
        legs = tripmod.build_trip(a, b, rides, avoid_no_sidewalk=rider in ("wheelchair", "senior_walker"))
    except (KeyError, ValueError, TypeError) as e:
        return JSONResponse({"error": str(e) or "Please check your points, route and stops."}, status_code=400)
    res = exposure.analyze(legs, rider, band, day)
    comps, all_legs = [], list(legs)
    only = body.get("only")                      # an example asks for its own decision only
    for c in [c for c in changes.affecting(legs) if not only or c["id"] == only]:
        cmp = changes.compare(legs, c, rider, band, day)
        all_legs += [l for l in cmp["after_legs"] if l not in legs]
        removed = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]}, "properties": {"name": s["name"]}}
                   for e in c["effects"] if e["type"] == "remove_stop"
                   for v in tripmod.load_routes()[e["route"]]["variants"] for s in v["stops"] if s["id"] in e["stop_ids"]]
        if c.get("phase") == "implemented":
            removed = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]}, "properties": {"name": r["name"]}}
                       for l in legs if l.kind == "transit" for r in changes.restored_stops(c, l.route)]
        comps.append({"id": c["id"], "title": c["title"], "simulated": c["simulated"], "status": c["status"], "status_note": c["status_note"],
                      "phase": c.get("phase", "proposed"), "item_url": c.get("item_url"), "before": _legs_geojson(cmp["before_legs"]),
                      "source_url": c["source_url"], "quotes": c["quotes"], "notes": cmp["notes"], "rows": cmp["rows"],
                      "new_issues": cmp["new_issues"], "improvements": cmp["improvements"], "after": _legs_geojson(cmp["after_legs"]),
                      "removed": {"type": "FeatureCollection", "features": removed},
                      "pages": c.get("source_pages") or [], "headline": _headline(cmp, rider),
                      # ground evidence on the stops and walks this decision changes (not already listed for the trip)
                      "changed_evidence": reports.search_changed(cmp["before_legs"], cmp["after_legs"])})
    # what Gait checked for this rider, on the trip the first page shows (for a decision already in effect, the trip before it)
    first = next((c for c in changes.affecting(legs) if not only or c["id"] == only), None)
    page0 = changes.compare(legs, first, rider, band, day)["before_legs"] if first and first.get("phase") == "implemented" else legs
    checks = exposure.checklist(page0, rider, band, day, stop_override=changes._overrides(page0))
    pts = lambda items, kind: [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [i["lon"], i["lat"]]},
                                "properties": {"kind": kind, **{k: i.get(k) for k in ("title", "label", "upcoming", "item_id", "project", "location", "timeline", "distance_m")}}}
                               for i in items]
    ev = reports.search(legs)
    ev_pts = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [x["lon"], x["lat"]]},
               "properties": {"src": "311", "label": f"311: {x['label']} ({x['count']}, latest {x['latest']})"}}
              for g in ev["groups"] for x in g["s311"]]
    ev_pts += [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [x["lon"], x["lat"]]},
                "properties": {"src": "rider", "label": f"Rider report: {x['label']} ({x['day']})"}}
               for g in ev["groups"] for x in g["riders"]]
    return {"before": _legs_geojson(legs), "flags": res["flags"], "checks": checks, "comparisons": comps, "persona": access.PERSONAS[rider].label,
            "works_on_trip": access.works_on_trip(all_legs),
            "evidence": ev, "evidence_pts": {"type": "FeatureCollection", "features": ev_pts},
            "wards": {"start": geocode.ward_near(*a), "destination": geocode.ward_near(*b)},
            "decisions": {"type": "FeatureCollection", "features": pts(res["decisions"], "decision")},
            "works": {"type": "FeatureCollection", "features": pts(res["works"][:10], "works")}}


@app.post("/api/research_trip")
async def research_trip_api(request: Request):
    """Opt-in live research for this trip (retrieve, Claude, verify). Cached per trip. Addresses are not sent to the AI."""
    from . import live_research
    body = await request.json()
    try:
        rider = body.get("rider", "wheelchair")
        rides = [(r["route"], int(r["variant"]), str(r["board"]), str(r["alight"])) for r in body["rides"]]
        legs = tripmod.build_trip(tuple(body["a"]), tuple(body["b"]), rides)
        return live_research.run(legs, access.PERSONAS[rider].label)
    except (KeyError, ValueError, TypeError) as e:
        return JSONResponse({"error": str(e) or "Please check the trip."}, status_code=400)
    except Exception as e:  # API or network problem: say so plainly
        return JSONResponse({"error": f"The research agent could not run: {type(e).__name__}."}, status_code=502)


@app.get("/api/report_categories")
def report_categories():
    return {k: v[0] for k, v in reports.RIDER_CATS.items()}


@app.post("/api/report")
async def report_api(request: Request):
    """A rider adds one fixed-category report at a place. Stored: category, rounded point, stop id, date. Nothing else."""
    body = await request.json()
    try:
        r = reports.add_report(str(body["cat"]), float(body["lat"]), float(body["lon"]), body.get("stop_id"))
    except (KeyError, ValueError, TypeError) as e:
        return JSONResponse({"error": str(e) or "Please check the report."}, status_code=400)
    return r


@app.get("/research/{route}", response_class=HTMLResponse)
def research_page(request: Request, route: str):
    pa, pf = DATA / "research" / f"route-{route}.json", DATA / "research_free" / f"route-{route}.json"
    if not pa.exists() and not pf.exists():
        raise HTTPException(404, "No research has been run for that route.")
    r = json.loads(pa.read_text()) if pa.exists() else None
    free = json.loads(pf.read_text()) if pf.exists() else None
    return templates.TemplateResponse(request, "research.html", {"r": r, "free": free, "route": route})


def _norm(t: str) -> str:
    return " ".join(t.split())


def _find_on_pages(quote: str, pages: list[str], hint: int | None) -> dict:
    """Look for `quote` word for word; try the cited page first. Returns the page and a little of the text around it."""
    q = _norm(quote)
    order = ([hint - 1] if hint and 0 < hint <= len(pages) else []) + [i for i in range(len(pages)) if i != (hint or 0) - 1]
    for i in order:
        t = _norm(pages[i])
        k = t.find(q)
        if k >= 0:
            a, b = max(0, k - 140), k + len(q) + 140
            return {"found": True, "page": i + 1, "before": ("…" if a else "") + t[a:k], "after": t[k + len(q):b] + ("…" if b < len(t) else "")}
    return {"found": False, "page": hint}


@app.get("/api/source_check")
def source_check(change: str | None = None, bld: str = ""):
    """Re-read each quote on its source page now, so the page can show the check as it happens. Nothing is written."""
    out = {"change": None, "buildings": []}
    c = changes.load_changes().get(change) if change else None
    if c and not c.get("simulated"):
        root = DATA.parent
        if c.get("source_pages_file") and (root / c["source_pages_file"]).exists():
            pages, kind = json.loads((root / c["source_pages_file"]).read_text()), "pdf"
        elif c.get("source_file") and (root / c["source_file"]).exists():
            pages, kind = [(root / c["source_file"]).read_text()], "web"
        else:
            pages, kind = [], None
        hints = c.get("source_pages") or []
        out["change"] = {"kind": kind, "n_pages": len(pages), "item": (c.get("item_url") or "").rsplit("=", 1)[-1] or None,
                         "quotes": [{"text": q, **(_find_on_pages(q, pages, hints[k] if k < len(hints) else None) if pages else {"found": False})}
                                    for k, q in enumerate(c.get("quotes", []))]}
    ids = [x for x in bld.split(",") if x][:6]
    if ids:
        import sqlite3
        con = sqlite3.connect(DATA / "corpus/index.sqlite")
        for d in developments():
            if d["id"] not in ids:
                continue
            rows = con.execute("SELECT page, text FROM pages WHERE url = ? ORDER BY CAST(page AS INTEGER)", (d["source_url"],)).fetchall()
            pages = [""] * max((int(p) for p, _ in rows), default=0)
            for p, t in rows:
                pages[int(p) - 1] = t
            out["buildings"].append({"id": d["id"], "n_pages": len(pages),
                                     "quotes": [{"text": q["text"], **_find_on_pages(q["text"], pages, q["page"])} for q in d["quotes"]]})
        con.close()
    return out
