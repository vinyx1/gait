"""Live research: retrieval finds the decision at the rider's stop; the checker drops unsupported AI text. No API calls."""
import json
from types import SimpleNamespace

import pytest

from gait import geocode, live_research as L, trip

LEGS = lambda: trip.build_trip((43.66012, -79.41720), (43.66497, -79.38606), [("94", 1, "16790", "8625")])
QUOTE = "Raised bus/bike platforms at TTC bus stops are proposed for installation."


class FakeClient:
    def __init__(self, findings):
        self.sent = None
        self.messages = SimpleNamespace(create=self._create)
        self.findings = findings

    def _create(self, **kw):
        self.sent = kw
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps({"findings": self.findings}))],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "CACHE", tmp_path)


def test_retrieval_finds_the_bikeway_decision_at_the_riders_stop():
    ps = L.retrieve(L.trip_summary(LEGS(), "Wheelchair user"))
    assert any(p["item_id"] == "2024.IE10.2" and p["own_stop"] for p in ps)


def test_checker_keeps_supported_and_drops_invented_findings():
    ps = L.retrieve(L.trip_summary(LEGS(), "Wheelchair user"))
    i = next(k for k, p in enumerate(ps, 1) if p["item_id"] == "2024.IE10.2")
    good = {"passage": i, "quote": QUOTE, "summary": "Raised bus and bike platforms are proposed at TTC bus stops.",
            "why_it_matters": "This could change how the rider on route 94 reaches the bus.", "kind": "stop_change"}
    fake_quote = {**good, "quote": "All stops on Harbord will be removed."}
    new_number = {**good, "summary": "Raised platforms are proposed at 7391 TTC bus stops."}
    stronger = {**good, "summary": "Raised platforms will be installed at TTC bus stops."}
    banned = {**good, "why_it_matters": "The platform is unsafe for wheelchairs."}
    c = FakeClient([good, fake_quote, new_number, stronger, banned])
    r = L.run(LEGS(), "Wheelchair user", client=c)
    assert [f["summary"] for f in r["kept"]] == [good["summary"]]
    assert len(r["dropped"]) == 4
    assert L.run(LEGS(), "Wheelchair user", client=FakeClient([]))["cached"]       # second run is free


def test_addresses_are_not_sent_to_the_ai():
    c = FakeClient([])
    L.run(LEGS(), "Wheelchair user", client=c)
    sent = json.dumps(c.sent["messages"])
    assert "43.66012" not in sent and "-79.4172" not in sent


def test_ward_lookup():
    assert geocode.ward_near(43.66012, -79.41720) == "University-Rosedale"
