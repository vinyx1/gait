"""311 requests and rider reports along a trip."""
from datetime import date, timedelta

import pytest

from triplens import reports, trip

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
    from triplens.app import app
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
    from triplens.app import app
    from triplens import landing
    html = TestClient(app).get("/").text
    c = landing.case("bathurst", "senior_walker")
    assert f"{c['before_m']} m" in html and f"{c['after_m']} m" in html
    assert "built-in method" not in html                  # the Jinja dict.items trap
    assert TestClient(app).get("/decisions").status_code == 200
