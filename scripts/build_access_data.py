"""Build compact access data from the TTC GTFS feed and City street-furniture datasets.

Output: data/geo/stops.json  (one record per surface stop/platform)
Run:    python scripts/build_access_data.py
Inputs (open data, Open Government Licence - Toronto): data/gtfs/ttc_gtfs.zip, data/geo/*.csv
Limits: only the three base service patterns (weekday, Saturday, Sunday: service_ids 1, 2, 3) are counted;
special and partial weekday patterns are ignored. Shelter and bench data come from the City's street-furniture
program and may not list every shelter or bench, so "not listed" never means "none".
"""
import csv
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "data/gtfs/ttc_gtfs.zip"
DAYTYPES = {"1": "weekday", "2": "saturday", "3": "sunday"}


def secs(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def fmt(sec: int) -> str:
    h, m = divmod(sec // 60, 60)
    return f"{h:02d}:{m:02d}"  # hours >= 24 mean after midnight on the same service day


def read(zf, name):
    return csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig"))


def main() -> None:
    zf = zipfile.ZipFile(ZIP)
    feed = list(read(zf, "feed_info.txt"))[0]
    routes = {r["route_id"]: r for r in read(zf, "routes.txt")}
    stops = {}
    for r in read(zf, "stops.txt"):
        if r["location_type"] in ("0", ""):
            stops[r["stop_id"]] = {
                "stop_id": r["stop_id"], "code": r["stop_code"], "name": r["stop_name"],
                "lat": float(r["stop_lat"]), "lon": float(r["stop_lon"]),
                "wheelchair_boarding": r.get("wheelchair_boarding") or "0",
                "parent_station": r.get("parent_station") or None,
            }
    trips = {}
    for r in read(zf, "trips.txt"):
        if r["service_id"] in DAYTYPES:
            trips[r["trip_id"]] = (r["route_id"], DAYTYPES[r["service_id"]], r.get("wheelchair_accessible") or "0")
    print("stops", len(stops), "trips(base)", len(trips), file=sys.stderr)

    per = defaultdict(lambda: {"hours": defaultdict(int), "first": None, "last": None})
    routes_at = defaultdict(set)
    wc_trips = defaultdict(lambda: defaultdict(int))
    n = 0
    rdr = csv.reader(io.TextIOWrapper(zf.open("stop_times.txt"), encoding="utf-8-sig"))
    head = next(rdr)
    i_trip, i_dep, i_stop = head.index("trip_id"), head.index("departure_time"), head.index("stop_id")
    for row in rdr:
        t = trips.get(row[i_trip])
        if not t or row[i_stop] not in stops:
            continue
        route_id, day, wc = t
        sec = secs(row[i_dep])
        d = per[(row[i_stop], day)]
        d["hours"][sec // 3600] += 1
        d["first"] = sec if d["first"] is None or sec < d["first"] else d["first"]
        d["last"] = sec if d["last"] is None or sec > d["last"] else d["last"]
        routes_at[row[i_stop]].add(route_id)
        wc_trips[row[i_stop]][wc] += 1
        n += 1
    print("stop_time rows used", n, file=sys.stderr)

    # amenities from City street-furniture datasets
    def points(path):
        out = []
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (r.get("STATUS") or "").strip().lower() != "existing":
                    continue
                try:
                    c = json.loads(r["geometry"])["coordinates"][0]
                    out.append((c[1], c[0]))
                except Exception:
                    pass
        return out

    def grid(pts):
        g = defaultdict(list)
        for lat, lon in pts:
            g[(round(lat / 0.0006), round(lon / 0.0008))].append((lat, lon))
        return g

    def near(g, lat, lon, meters=30):
        cnt = 0
        gy, gx = round(lat / 0.0006), round(lon / 0.0008)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for plat, plon in g.get((gy + dy, gx + dx), []):
                    dy_m = (plat - lat) * 111320
                    dx_m = (plon - lon) * 111320 * math.cos(math.radians(lat))
                    if math.hypot(dx_m, dy_m) <= meters:
                        cnt += 1
        return cnt

    shelters, benches = grid(points(ROOT / "data/geo/street-furniture-transit-shelter.csv")), grid(points(ROOT / "data/geo/street-furniture-bench.csv"))

    out = []
    for sid, s in stops.items():
        rec = dict(s)
        rec["routes"] = sorted({routes[r]["route_short_name"] for r in routes_at.get(sid, [])},
                               key=lambda x: (len(x), x))
        rec["service"] = {}
        for day in DAYTYPES.values():
            d = per.get((sid, day))
            if d:
                rec["service"][day] = {"first": fmt(d["first"]), "last": fmt(d["last"]),
                                       "departures": sum(d["hours"].values()),
                                       "per_hour": {str(h): c for h, c in sorted(d["hours"].items())}}
        tw = wc_trips.get(sid, {})
        tot = sum(tw.values())
        # GTFS trip flag: 1 = accessible, 2 = not accessible, 0/empty = no information
        rec["trip_flags"] = ({"accessible": round(tw.get("1", 0) / tot, 2), "not_accessible": round(tw.get("2", 0) / tot, 2),
                              "no_information": round(tw.get("0", 0) / tot, 2)} if tot else None)
        rec["shelter_listed"] = near(shelters, s["lat"], s["lon"]) > 0
        rec["bench_listed"] = near(benches, s["lat"], s["lon"]) > 0
        out.append(rec)
    meta = {"feed_version": feed.get("feed_version"), "feed_start": feed.get("feed_start_date"),
            "feed_end": feed.get("feed_end_date"), "service_patterns": "weekday(1), saturday(2), sunday(3) only",
            "source": "TTC GTFS via City of Toronto Open Data; Street Furniture - Transit Shelter and Bench datasets"}
    (ROOT / "data/geo/stops.json").write_text(json.dumps({"meta": meta, "stops": out}, separators=(",", ":")))
    sh = sum(1 for r in out if r["shelter_listed"]); be = sum(1 for r in out if r["bench_listed"])
    print(f"wrote {len(out)} stops; shelter listed at {sh}, bench listed at {be}", file=sys.stderr)


if __name__ == "__main__":
    main()
