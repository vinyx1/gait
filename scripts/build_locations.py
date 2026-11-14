"""Locate the demo items on the map and save data/locations.json.

Addresses are matched against the City's open Address Points dataset (public, no personal data).
Items without a single street address use a clearly labelled representative point:
  - Spadina Road work area: the mean position of TTC stops named 'Spadina Rd at Lowther Ave' / 'Kendal Ave'
  - Croft Street: mean position of Croft St address points
  - Dundas 505 corridor: the TTC stop 'Dundas St West at Spadina Ave' area
Run: python scripts/build_locations.py
"""
import json
import re
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

B = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
RID = "0b3756af-9caf-4f0f-ac28-9c6617adede4"  # Address Points datastore resource
ABBR = {"Avenue": "Ave", "Street": "St", "Drive": "Dr", "Crescent": "Cres", "Court": "Ct", "Road": "Rd",
        "Boulevard": "Blvd", "East": "E", "West": "W", "North": "N", "South": "S"}


def abbreviate(s: str) -> str:
    return " ".join(ABBR.get(w, w) for w in s.split())


def query(**params) -> dict:
    url = B + "?" + urllib.parse.urlencode({"resource_id": RID, **params})
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)["result"]


def geocode(address: str):
    res = query(q=address, limit=20)
    for rec in res["records"]:
        if rec["ADDRESS_FULL"].lower() == address.lower():
            lon, lat = json.loads(rec["geometry"])["coordinates"][:2]
            return lat, lon, rec.get("WARD_NAME")
    return None


def main() -> None:
    from gait.access import load_stops
    stops = load_stops()["stops"]
    locs = {}
    for p in sorted((ROOT / "data/items").glob("2027.PB1.*.json")):
        item = json.loads(p.read_text())
        m = re.match(r"^(\d+[A-Za-z]?) ([A-Za-z' ]+?)(?: - |$)", item["title"])
        if not m:
            continue
        addr = abbreviate(f"{m.group(1)} {m.group(2)}")
        g = geocode(addr)
        print(item["item_id"], addr, "->", g)
        if g:
            locs[item["item_id"]] = {"id": item["item_id"], "label": addr + ", Toronto", "lat": g[0], "lon": g[1],
                                     "ward": g[2], "item_ids": [item["item_id"]],
                                     "method": "City Address Points dataset (exact address match)"}

    def centroid(match):
        pts = [(s["lat"], s["lon"]) for s in stops if match(s["name"])]
        return (statistics.mean(p[0] for p in pts), statistics.mean(p[1] for p in pts), len(pts)) if pts else None

    c = centroid(lambda n: re.search(r"Spadina R(d|oad)", n, re.I) and re.search(r"Lowther|Kendal", n, re.I))
    print("spadina centroid", c)
    if c:
        locs["spadina_work_area"] = {"id": "spadina_work_area", "label": "Spadina Road near Lowther Ave and Kendal Ave (work area)",
                                     "lat": c[0], "lon": c[1], "ward": "University-Rosedale", "item_ids": ["2026.TE32.25", "2026.MM42.46"],
                                     "method": f"Mean position of {c[2]} TTC stops named for Spadina Rd at Lowther or Kendal. Approximate."}
    res = query(filters=json.dumps({"LINEAR_NAME_FULL": "Croft St"}), limit=200)
    pts = [json.loads(r["geometry"])["coordinates"][:2] for r in res["records"]]
    if pts:
        locs["croft_st"] = {"id": "croft_st", "label": "Croft Street, Ward 11 (laneway homes)", "lat": statistics.mean(p[1] for p in pts),
                            "lon": statistics.mean(p[0] for p in pts), "ward": "University-Rosedale", "item_ids": ["2026.IE31.8"],
                            "method": f"Mean position of {len(pts)} Croft St address points. Approximate; Shaftesbury Court not separately located."}
    c = centroid(lambda n: re.search(r"Dundas St(reet)? W(est)?", n, re.I) and re.search(r"Spadina", n, re.I))
    print("dundas centroid", c)
    if c:
        locs["dundas_spadina"] = {"id": "dundas_spadina", "label": "Dundas St West at Spadina Ave (a point on the 505 Dundas corridor)",
                                  "lat": c[0], "lon": c[1], "ward": "Spadina-Fort York", "item_ids": ["2026.TE34.104"],
                                  "method": f"Mean position of {c[2]} TTC stops named Dundas St West at Spadina. The decision covers the whole route; this is one representative point."}
    (ROOT / "data/locations.json").write_text(json.dumps(list(locs.values()), indent=2))
    print("saved", len(locs), "locations")


if __name__ == "__main__":
    main()
