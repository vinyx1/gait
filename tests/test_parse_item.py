import json
from pathlib import Path

import pytest

from triplens.parse_item import parse_item, parse_date_span

RAW = Path(__file__).resolve().parent.parent / "data/raw/items_snapshot.json"


def load(item_id):
    raw = json.loads(RAW.read_text())
    rec = raw["items"][item_id]
    return parse_item(item_id, rec["url"], rec["text"], rec["links"], raw.get("fetched_at"))


def test_date_span():
    assert parse_date_span("July 29 and 30, 2026") == ("2026-07-29", "2026-07-30")
    assert parse_date_span("April 30, 2026") == ("2026-04-30", "2026-04-30")
    assert parse_date_span("no date here") == (None, None)


def test_dundas_two_stages_in_order_with_amendment_and_vote():
    item = load("2026.TE34.104")
    assert [s.body for s in item.stages] == [
        "Toronto and East York Community Council", "City Council"]
    council = item.stages[1]
    assert council.status == "Amended"
    assert "4 - Parkdale - High Park" in council.wards
    assert any(m.motion_type == "Amend Item" and m.result == "Carried" for m in council.motions)
    v = council.votes[0]
    assert (v.yes, v.no, v.absent) == (20, 2, 4)
    assert "Majority" in v.required


def test_communications_keep_counts_not_names():
    item = load("2026.TE34.104")
    blob = json.dumps([s.__dict__ for s in item.stages], default=str)
    assert "Macchiusi" not in blob and "Petherbridge" not in blob
    assert sum(s.communications_count for s in item.stages) == 5


def test_referred_is_not_decided():
    item = load("2026.IE31.8")
    st = item.stages[0]
    assert st.status == "Referred"
    assert "without making a decision" in " ".join(item.tracking_status)
    assert "IE29.1" in st.decision_text


def test_spadina_consent_then_reopened():
    first = load("2026.TE32.25")
    assert "without debate" in " ".join(first.tracking_status)
    assert first.stages[-1].status == "Adopted on Consent"
    assert first.bylaws and "law0530" in first.bylaws[0]["url"]
    second = load("2026.MM42.46")
    assert "deleting Parts 1 to 17, 19, and 27" in second.stages[0].decision_text


def test_decision_text_is_verbatim_substring_of_source():
    raw = json.loads(RAW.read_text())
    for item_id, rec in raw["items"].items():
        item = parse_item(item_id, rec["url"], rec["text"], rec["links"])
        flat = " ".join(rec["text"].split())
        for st in item.stages:
            if st.decision_text:
                first_line = " ".join(st.decision_text.splitlines()[0].split())
                assert first_line in flat, (item_id, first_line)
