import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from triplens import geocode, trip, exposure
from triplens.app import app, EXAMPLES, make_report

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not geocode.available(), reason="run scripts/build_address_index.py first")


def pt(addr):
    p, _ = geocode.lookup(addr)
    assert p, addr
    return (p.lat, p.lon)


def legs_for(o, d, routes, stops):
    return trip.build_trip(pt(o), pt(d), [(r, v, b, a) for r, (v, b, a) in zip(routes, stops)])


def test_geocode_normalizes_and_suggests():
    for q in ("1337 Queen St W", "1337 queen street west, Toronto", "Unit 5, 1337 Queen Street West"):
        m, _ = geocode.lookup(q)
        assert m and m.label == "1337 Queen St W" and m.ward == "Parkdale-High Park"
    m, s = geocode.lookup("300 Dundas St W")
    assert m is None and s and all("Dundas St W" in p.label for p in s)
    assert geocode.lookup("99999 Nowhere Rd") == (None, [])


def test_transit_leg_follows_route_and_stop_order_is_checked():
    legs = legs_for("1337 Queen St W", "106 Beverley St", ["501"], [(1, "6835", "6829")])
    assert [l.kind for l in legs] == ["walk", "transit", "walk"]
    t = legs[1]
    assert t.length_m > 2000 and len(t.points) > 10 and t.route == "501"
    with pytest.raises(ValueError):
        trip.build_transit_leg("501", 1, t.alight["stop_id"], t.board["stop_id"])


def test_queen_trip_finds_both_open_decisions_and_marks_streetcar_for_wheelchair():
    legs = legs_for("1337 Queen St W", "106 Beverley St", ["501"], [(1, "6835", "6829")])
    r = exposure.analyze(legs, "wheelchair", "day", "weekday")
    ids = {d["item_id"] for d in r["decisions"]}
    assert {"2027.PB1.6", "2027.PB1.2"} <= ids
    assert all(d["actions"] for d in r["decisions"] if d["upcoming"])
    assert any(f["severity"] == "barrier" and "501" in f["text"] for f in r["flags"])


def test_decision_that_names_the_route_is_flagged():
    legs = legs_for("1000 Dundas St W", "201 Dundas St W", ["505"], [(0, "10181", "2153")])
    r = exposure.analyze(legs, "wheelchair", "day", "weekday")
    assert any(m["route"] == "505" and m["item_id"] == "2026.TE34.104" for m in r["mentions"])
    m = r["mentions"][0]
    item = exposure._items()[m["item_id"]]
    blob = " ".join([item["title"]] + [x for st in item["stages"] for x in (st.get("decision_text"), st.get("summary")) if x])
    assert m["snippet"] in blob            # the quoted snippet is real text from the source


def test_far_away_trip_has_no_decisions():
    p = trip.Leg("walk", "w", [pt("32 Nineteenth St"), pt("5 Nineteenth St")])
    assert exposure.items_near([p]) == []


def test_ended_works_are_reported_as_possibly_out_of_date():
    legs = legs_for("1337 Queen St W", "106 Beverley St", ["501"], [(1, "6835", "6829")])
    r = exposure.analyze(legs, "senior_walker", "day", "weekday", today_year=2026)
    ended = [f for f in r["flags"] if f["kind"] == "works" and "has ended" in f["text"]]
    live = [f for f in r["flags"] if f["kind"] == "works" and "has ended" not in f["text"]]
    assert ended and all(f["severity"] == "info" for f in ended)
    assert all(f["severity"] == "watch" for f in live)
    r2 = exposure.analyze(legs, "senior_walker", "day", "weekday", today_year=2020)
    assert not [f for f in r2["flags"] if "has ended" in f["text"]]


def test_every_flag_has_evidence_and_only_rules_say_barrier():
    for ex in EXAMPLES.values():
        rep, errs = make_report(ex["origin"], ex["destination"], ex["rider"], ex["band"], ex["day"], ex["routes"], ex["stops"])
        assert not errs and rep["flags"]
        for f in rep["flags"]:
            assert f["evidence"] and all(e.strip() for e in f["evidence"])
            assert f["severity"] in ("barrier", "watch", "info")
        assert any(f["kind"] == "act" for f in rep["flags"]) or rep["comparisons"] or ex["routes"] == ["127"]


def test_decided_items_never_shown_as_open_for_comment():
    rep, _ = make_report("250 Spadina Rd", "800 Bathurst St", "senior_walker", "day", "weekday", ["127"], [(0, "7956", "14777")])
    for f in rep["flags"]:
        if f["kind"] == "item":
            assert "already been made" in f["text"]
    assert not any(f["kind"] == "act" for f in rep["flags"])


def snapshot_files():
    return sorted((str(p), p.stat().st_mtime_ns) for p in ROOT.rglob("*")
                  if p.is_file() and ".venv" not in p.parts and ".git" not in p.parts and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts)


def test_route_check_stores_nothing_and_sets_no_cookies():
    c = TestClient(app)
    before = snapshot_files()
    r1 = c.get("/route/example/queen-beverley")
    r2 = c.post("/route/stops", data={"origin": "1337 Queen St W", "destination": "106 Beverley St", "rider": "wheelchair",
                                      "band": "day", "day": "weekday", "route1": "501", "route2": ""})
    r3 = c.post("/route/result", data={"origin": "1337 Queen St W", "destination": "106 Beverley St", "rider": "wheelchair",
                                       "band": "day", "day": "weekday", "route0": "501", "board0": "1:6835", "alight0": "1:6829"})
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert all("set-cookie" not in r.headers for r in (r1, r2, r3))
    assert "1337 Queen" not in str(r3.url)           # addresses are not in the URL
    assert snapshot_files() == before


def test_bad_input_gives_clear_errors():
    c = TestClient(app)
    r = c.post("/route/stops", data={"origin": "nowhere rd", "destination": "106 Beverley St", "rider": "wheelchair",
                                     "band": "day", "day": "weekday", "route1": "501", "route2": ""})
    assert "could not find" in r.text
    r = c.post("/route/stops", data={"origin": "1337 Queen St W", "destination": "106 Beverley St", "rider": "wheelchair",
                                     "band": "day", "day": "weekday", "route1": "9999", "route2": ""})
    assert "do not recognise" in r.text
    r = c.post("/route/result", data={"origin": "1337 Queen St W", "destination": "106 Beverley St", "rider": "wheelchair", "band": "day",
                                      "day": "weekday", "route0": "501", "board0": "1:6829", "alight0": "1:6835"})
    assert "must come after" in r.text


def test_tool_never_picks_stops_for_the_resident():
    c = TestClient(app)
    r = c.post("/route/stops", data={"origin": "1337 Queen St W", "destination": "106 Beverley St", "rider": "wheelchair",
                                     "band": "day", "day": "weekday", "route1": "501", "route2": ""})
    assert r.status_code == 200 and "selected" not in r.text and "shortest" not in r.text.lower()
    assert not hasattr(trip, "suggest") and not hasattr(trip, "suggest_chain")


def test_real_stop_removal_shows_before_and_after_and_new_issue():
    from triplens.app import EXAMPLES
    ex = EXAMPLES["stclair-512"]
    rep, errs = make_report(ex["origin"], ex["destination"], ex["rider"], ex["band"], ex["day"], ex["routes"], ex["stops"])
    assert not errs
    cmp = next(c for c in rep["comparisons"] if c["change"]["id"] == "ttc-512-stop-removals")
    assert any("is removed" in n for n in cmp["notes"])
    assert any(r["changed"] for r in cmp["rows"])
    assert any(f["severity"] == "barrier" and "walking" in f["text"] for f in cmp["new_issues"])


def test_change_quotes_are_verbatim_from_saved_source():
    from triplens import changes
    changes.load_changes.cache_clear()
    cs = changes.load_changes()          # raises if any quote is not in the saved source text
    assert not cs["ttc-512-stop-removals"]["simulated"] and cs["sim-queen-shelters"]["simulated"]


def test_simulated_shelter_removal_is_labelled_and_reported():
    rep, _ = make_report("1337 Queen St W", "106 Beverley St", "senior_walker", "day", "weekday", ["501"], [(1, "6835", "6829")])
    cmp = next(c for c in rep["comparisons"] if c["change"]["id"] == "sim-queen-shelters")
    assert cmp["change"]["simulated"] and any("shelter would be removed" in n for n in cmp["notes"])
    assert any("shelter or bench" in f["text"] for f in cmp["new_issues"])


def test_change_does_not_touch_other_routes():
    rep, _ = make_report("1000 Dundas St W", "201 Dundas St W", "wheelchair", "day", "weekday", ["505"], [(0, "10181", "2153")])
    assert [c["change"]["id"] for c in rep["comparisons"]] == ["sim-505-relocate-grace"]   # 512 and 7 changes do not apply


def test_map_api_flow():
    c = TestClient(app)
    assert c.get("/map").status_code == 200
    r = c.get("/api/routes_near", params=dict(alat=43.6862, alon=-79.4046, blat=43.6878, blon=-79.3944)).json()
    assert any(x["route"] == "512" for x in r)
    s = c.get("/api/route_stops", params=dict(route="512", variant=0)).json()
    assert sum(1 for f in s["stops"]["features"] if f["properties"]["removed_by"]) == 5
    t = c.post("/api/trip", json={"a": [43.6862, -79.4046], "b": [43.6878, -79.3944], "rider": "senior_walker", "day": "weekday",
                                  "band": "day", "rides": [{"route": "512", "variant": 0, "board": "14351", "alight": "15305"}]}).json()
    walk = [f for f in t["before"]["features"] if f["properties"]["kind"] == "walk"]
    assert walk and all(f["properties"]["routed"] for f in walk)      # walks follow the sidewalk network
    assert t["comparisons"] and t["comparisons"][0]["new_issues"]
    assert c.post("/api/trip", json={"a": [1, 2]}).status_code == 400


def test_past_decision_rebuilds_before_state_and_flags_new_limit():
    ex = EXAMPLES["bathurst-7-past"]
    rep, errs = make_report(ex["origin"], ex["destination"], ex["rider"], ex["band"], ex["day"], ex["routes"], ex["stops"])
    assert not errs
    cmp = next(c for c in rep["comparisons"] if c["change"]["id"] == "rapidto-7-bathurst-stops")
    assert any("Before this decision" in n for n in cmp["notes"])
    walk = cmp["rows"][0]
    assert walk["changed"] and int(walk["before"].split()[1]) < 150 < int(walk["after"].split()[1])
    assert any(f["severity"] == "barrier" for f in cmp["new_issues"])
    assert "unknown" in cmp["rows"][1]["before"]          # reconstructed stop: shelter not claimed


def test_research_findings_are_verbatim_and_page_exists():
    import json
    from triplens import research
    for r in ("7", "29"):
        d = json.loads((ROOT / f"data/research/route-{r}.json").read_text())
        assert d["kept"]
        for f in d["kept"]:
            pages = research.pages_for(f["document_url"])
            assert research._norm(f["quote"]) in research._norm(pages[f["page"] - 1])
    assert TestClient(app).get("/research/7").status_code == 200


def _cmp(origin, dest, rider, band, routes, stops, cid):
    rep, errs = make_report(origin, dest, rider, band, "weekday", routes, stops)
    assert not errs
    return next(c for c in rep["comparisons"] if c["change"]["id"] == cid)


def test_relocation_moves_stop_and_reroutes_walk():
    c = _cmp("1000 Dundas St W", "201 Dundas St W", "wheelchair", "day", ["505"], [(0, "10181", "2153")], "sim-505-relocate-grace")
    assert c["change"]["simulated"] and any("moves to" in n for n in c["notes"]) and c["new_issues"]


def test_temporary_closure_names_dates():
    c = _cmp("250 Spadina Rd", "800 Bathurst St", "senior_walker", "day", ["127"], [(0, "7956", "14777")], "sim-127-temporary-closure")
    assert any("March 1, 2027" in n for n in c["notes"]) and any(r["changed"] for r in c["rows"])
    # the walk was already over the senior's limit before the closure, so it is not reported as a new issue
    assert not any(f.get("code") == "walk_over_limit" for f in c["new_issues"])


def test_service_cut_reported_for_late_traveller():
    c = _cmp("1599 Bathurst St", "800 Bathurst St", "shift_worker", "late", ["7"], [(1, "107", "14617")], "sim-7-late-cut")
    assert any("drop from" in f["text"] for f in c["new_issues"])


def test_sidewalk_closure_lengthens_walk():
    c = _cmp("1599 Bathurst St", "800 Bathurst St", "shift_worker", "day", ["7"], [(1, "107", "14617")], "sim-bathurst-sidewalk-closure")
    assert any("sidewalk closure" in n for n in c["notes"]) and any(r["changed"] for r in c["rows"])


def test_free_finder_finds_real_removals_without_ai():
    import json, sqlite3
    from triplens import finder
    if not finder.DB.exists():
        pytest.skip("run scripts/build_corpus.py first")
    r7 = json.loads((ROOT / "data/research_free/route-7.json").read_text())
    r29 = json.loads((ROOT / "data/research_free/route-29.json").read_text())
    assert any("Dewbourne Avenue, Ardmore Road, Heathdale Road" in f["quote"] for f in r7["findings"])
    assert any("Croatia Street" in f["quote"] and f["change_type"] == "remove_stop" for f in r29["findings"])
    assert not any("Eversfield Road and Croatia Street" in f["quote"] for f in r7["findings"])   # Dufferin stops not attributed to Bathurst
    con = sqlite3.connect(finder.DB)
    for f in r7["findings"][:5]:                     # every quote is real page text
        txt = con.execute("SELECT text FROM pages WHERE url = ? AND page = ?", (f["document_url"], f["page"])).fetchone()[0]
        assert f["quote"][:200] in txt


def _api(body):
    return TestClient(app).post("/api/trip", json=body).json()


def test_bikeway_decision_flags_platform_crossing_not_unknown_shelter():
    d = _api({"a": [43.66012, -79.4172], "b": [43.66497, -79.38606], "rider": "wheelchair", "day": "weekday", "band": "day",
              "rides": [{"route": "94", "variant": 1, "board": "16790", "alight": "8625"}]})
    c = next(x for x in d["comparisons"] if x["id"] == "past-94-harbord-bikeway-stops")
    codes = {f.get("code") for f in c["new_issues"]}
    assert "platform:Boarding" in codes and "shelter_wait" not in codes


def test_new_shelter_shows_as_improvement():
    d = _api({"a": [43.64661, -79.37812], "b": [43.64429, -79.36849], "rider": "senior_walker", "day": "weekday", "band": "late",
              "rides": [{"route": "114", "variant": 0, "board": "16754", "alight": "15320"}]})
    c = next(x for x in d["comparisons"] if x["id"] == "front-st-layby-shelter")
    assert any(f.get("code") == "shelter_wait" for f in c["improvements"]) and not c["new_issues"]
