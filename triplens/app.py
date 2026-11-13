"""TripLens web app: explain layer (v0). Server-rendered, text-first, no JavaScript required."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

app = FastAPI(title="TripLens")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

from . import access, changes, exposure, geocode, svgmap, trip as tripmod
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
    """Checked plain-language rewrites written by Claude. See triplens/rewrite.py for the checks."""
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
    "spadina-127": {"title": "Spadina Rd to Bathurst St on the 127 bus (senior using a walker): a decided item and works nearby",
                    "origin": "250 Spadina Rd", "destination": "800 Bathurst St", "rider": "senior_walker", "band": "day", "day": "weekday",
                    "routes": ["127"], "stops": [(0, "7956", "14777")]},
    "stclair-512": {"title": "BEFORE AND AFTER: St Clair Ave W on the 512 if the TTC removes nine stops (senior using a walker)",
                    "origin": "5 Dunvegan Rd", "destination": "1 St Clair Ave W", "rider": "senior_walker", "band": "day", "day": "weekday",
                    "routes": ["512"], "stops": [(0, "14351", "15305")]},
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
                                  [(r, vi, b, a) for r, (vi, b, a) in zip(route_keys, chosen)])
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
