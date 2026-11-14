import json
from pathlib import Path

from gait import access
from gait.agents import verify_findings, dedupe

ROOT = Path(__file__).resolve().parent.parent
P = access.PERSONAS["wheelchair"]

CALLS = {
    "C1": {"text": "[C1] stop 817 | College St at Borden St | 201 m straight-line (about 261 m walking) | "
                   "wheelchair boarding: not possible (GTFS 2) | shelter listed in City data: no"},
    "C2": {"text": "[C2] stop 7804 | Harbord St at Brunswick Ave | wheelchair boarding: possible (GTFS 1) | 61 departures"},
}


def f(detail, quote, call="C1", sev="watch", title="t"):
    return {"title": title, "detail": detail, "severity": sev, "cites": [{"call": call, "quote": quote}]}


def test_keeps_supported_finding():
    kept, dropped = verify_findings([f("The nearest stop is about 261 m of walking away.", "about 261 m walking")], CALLS, P)
    assert len(kept) == 1 and not dropped


def test_drops_unknown_call_missing_cite_and_bad_quote():
    kept, dropped = verify_findings([
        f("x", "about 261 m walking", call="C9"),
        {"title": "t", "detail": "x", "severity": "info", "cites": []},
        f("x", "a quote that is not there"),
    ], CALLS, P)
    assert not kept and len(dropped) == 3


def test_drops_invented_number_and_alarming_word():
    kept, dropped = verify_findings([f("It is 300 m away.", "about 261 m walking"),
                                     f("This stop is unsafe in winter.", "wheelchair boarding: not possible (GTFS 2)")], CALLS, P)
    assert not kept
    assert "number not in cited results" in dropped[0]["reason"] and "disallowed word" in dropped[1]["reason"]


def test_agents_cannot_label_a_barrier():
    kept, _ = verify_findings([f("Boarding is not possible here.", "wheelchair boarding: not possible (GTFS 2)", sev="barrier")], CALLS, P)
    assert kept[0]["severity"] == "watch" and "fixed rules" in kept[0]["note"]


def test_dedupe_overlapping_evidence():
    a = f("one", "about 261 m walking"); b = f("two", "about 261 m walking")
    c = {"title": "t", "detail": "x", "severity": "info", "cites": [{"call": "C2", "quote": "61 departures"}]}
    assert len(dedupe([("r1", a), ("r2", b), ("r3", c)])) == 2


def test_streetcar_corridor_wheelchair_flags_barrier_from_trip_flags():
    # Every streetcar trip is flagged not accessible in the published feed, so a stop that lists boarding as
    # possible still does not count unless some of its trips are flagged accessible.
    locs = {l["id"]: l for l in json.loads((ROOT / "data/locations.json").read_text())}
    l = locs["dundas_spadina"]
    snap = access.snapshot(l["lat"], l["lon"], "wheelchair")
    assert any(fl["code"] == "no_accessible_stop" and fl["severity"] == "barrier" for fl in snap["flags"])


def test_personas_use_different_limits_and_rules():
    l = {x["id"]: x for x in json.loads((ROOT / "data/locations.json").read_text())}["2027.PB1.6"]
    w, s, n = (access.snapshot(l["lat"], l["lon"], k) for k in ("wheelchair", "senior_walker", "shift_worker"))
    assert w["max_walk_m"] > s["max_walk_m"] and n["max_walk_m"] > w["max_walk_m"]
    assert s["stop_count"] <= w["stop_count"] <= n["stop_count"]


def test_stored_audits_pass_verification_again():
    files = list((ROOT / "data/audits").glob("*.json"))
    assert files, "run scripts/run_audits.py first"
    for fpath in files:
        a = json.loads(fpath.read_text())
        persona = access.PERSONAS[a["persona"]]
        for r in a["roles"]:
            kept, dropped = verify_findings([{k: v for k, v in x.items() if k not in ("reason", "note")} for x in r["kept"]],
                                            r["calls"], persona)
            assert not dropped, (fpath.name, r["role"], dropped[:1])


def test_stored_groupings_are_valid_partitions_and_page_never_shows_agent_barrier():
    from gait.agents import flatten_kept, valid_partition
    from gait.app import audit_for
    for fpath in (ROOT / "data/audits").glob("*.json"):
        a = json.loads(fpath.read_text())
        assert valid_partition(a["groups"], len(flatten_kept(a))), fpath.name
        page = audit_for(a["location"], a["persona"])
        assert all(x["severity"] in ("watch", "info") for x in page["findings"])
        assert len(page["findings"]) == len(a["groups"])
