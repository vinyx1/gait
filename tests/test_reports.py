"""311 requests and rider reports along a trip."""
from datetime import date, timedelta

import pytest

from gait import reports, trip

HARBORD = ((43.66012, -79.41720), (43.66497, -79.38606), [("94", 1, "16790", "8625")])


def legs():
    a, b, rides = HARBORD
    return trip.build_trip(a, b, rides, avoid_no_sidewalk=True)


@pytest.fixture
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "DB", tmp_path / "r.sqlite")


def test_311_found_at_the_riders_own_stop_with_trace(tmpdb):
    r = reports.search(legs())
    board = next(g for g in r["groups"] if g["place"].startswith("Boarding stop: Harbord St at Clinton St"))
    assert any(x["label"] == "Sidewalk snow not cleared" for x in board["s311"])
    assert any("within 60 m" in t for t in r["trace"])           # the search explains itself


def test_rider_report_shows_then_expires(tmpdb):
    stop = legs()[1].board
    reports.add_report("stop_blocked", stop["lat"], stop["lon"], stop["stop_id"], today=date(2026, 11, 13))
    near = lambda d: [x for g in reports.search(legs(), today=d)["groups"] for x in g["riders"]]
    assert near(date(2026, 11, 14))[0]["label"].startswith("Stop blocked")
    assert near(date(2026, 11, 13) + timedelta(days=10)) == []    # temporary problems expire


def test_rider_report_rejects_free_text_and_far_places(tmpdb):
    with pytest.raises(ValueError):
        reports.add_report("my neighbour is rude", 43.66, -79.41)
    with pytest.raises(ValueError):
        reports.add_report("no_seat", 45.0, -75.0)


def test_report_api_stores_only_category_place_and_date(tmpdb):
    from fastapi.testclient import TestClient
    from gait.app import app
    c = TestClient(app)
    assert c.post("/api/report", json={"cat": "no_seat", "lat": 43.66, "lon": -79.41, "stop_id": "16790", "name": "x"}).status_code == 200
    import sqlite3
    cols = [r[1] for r in sqlite3.connect(reports.DB).execute("PRAGMA table_info(r)")]
    assert cols == ["cat", "lat", "lon", "stop_id", "day"]
    assert c.post("/api/report", json={"cat": "bad", "lat": 43.66, "lon": -79.41}).status_code == 400


def test_staff_report_leads_are_labelled_unchecked_and_quoted():
    r = reports.search(legs())
    assert r["leads"] and all(l["quote"] and l["document_url"].startswith("https://www.toronto.ca/legdocs/") for l in r["leads"])


def test_landing_page_numbers_come_from_the_engine():
    from fastapi.testclient import TestClient
    from gait.app import app
    from gait import landing
    html = TestClient(app).get("/").text
    c = landing.case("cosburn", "senior_walker")
    assert c["item_id"] and f"item {c['item_id']}" in html
    assert f"{c['before_m']}<small>" in html and f"{c['after_m']}<small>" in html    # both walks, before and after, from the engine
    assert "built-in method" not in html                  # the Jinja dict.items trap
    assert TestClient(app).get("/decisions").status_code == 200


def test_cosburn_construction_lengthens_the_walk():
    """The landing example: Ontario Line Cosburn Station works close the Pape west sidewalk and move the stop."""
    from gait import landing
    c = landing.case("cosburn", "senior_walker")
    assert c["item_id"] == "2025.EX27.3" and c["page"] == 17
    assert c["board_after"] == "Pape Ave at Gamble Ave" and c["after_m"] > c["before_m"] + 100


def test_changed_part_is_searched_without_repeats():
    """311 reports are also searched along the stops and walks a decision adds, and none repeats the trip's own list."""
    from gait import landing, changes, reports, trip as T
    c = landing.CASES["cosburn"]
    legs = T.build_trip(c["a"], c["b"], [c["ride"]], avoid_no_sidewalk=True)
    cmp = changes.compare(legs, changes.load_changes()[c["change"]], "senior_walker", "day", "weekday")
    places = reports.changed_places(legs, cmp["after_legs"])
    assert places and all(p[0] == "walk" for p in places)          # the detour round the closed sidewalk
    _g, _t, seen = reports._search_places(reports._places(legs))
    extra, _t2, seen2 = reports._search_places(places, seen=set(seen))
    added = seen2 - seen                                            # only reports not already near the trip as entered
    assert sum(x["count"] for g in extra for x in g["s311"]) == len([s for s in added if isinstance(s, int)])


def test_decision_areas_mark_where_decisions_land():
    """Real decisions are drawn with a bubble and their removed stops; simulations only on request; a stop still
    served in the other direction is not marked as removed."""
    from fastapi.testclient import TestClient
    from gait.app import app
    fc = TestClient(app).get("/api/decision_areas").json()["features"]
    assert not any(f["properties"]["phase"] == "simulation" for f in fc)
    st = [f for f in fc if f["properties"]["id"] == "rapidto-7-bathurst-stops"]
    assert sum(f["properties"]["kind"] == "stop" for f in st) == 3 and any(f["properties"]["kind"] == "area" for f in st)
    cos = [f["properties"] for f in fc if f["properties"]["id"] == "ontario-line-cosburn-construction"]
    assert sum(p["kind"] == "stop" and p["gone"] for p in cos) == 1          # southbound only
    assert any(p["kind"] == "line" and p["line"] == "sidewalk" for p in cos) and any(p["kind"] == "line" and p["line"] == "road" for p in cos)


def test_approved_buildings_are_quoted_and_placed():
    """Every approved building has an exact address point and quotes found word for word on their cited page."""
    import json, sqlite3
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    items = json.loads((root / "data/developments.json").read_text())["items"]
    assert len(items) > 20 and len({d["address"] for d in items}) == len(items)
    con = sqlite3.connect(root / "data/corpus/index.sqlite")
    for d in items:
        assert 43.5 < d["lat"] < 43.9 and d["storeys"] > 0
        for q in d["quotes"]:
            page = con.execute("SELECT text FROM pages WHERE url = ? AND page = ?", (d["source_url"], q["page"])).fetchone()
            assert page and q["text"] in " ".join(page[0].split()), (d["id"], q["text"][:60])
