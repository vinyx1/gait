import json
from pathlib import Path

from triplens.parse_report import parse_report, split_recommendations
from triplens.verify import quote_in_source

ROOT = Path(__file__).resolve().parent.parent


def test_split_recommendations_keeps_numbers_and_text():
    recs = split_recommendations("The Director recommends that: 1. Council receive this. 2. Council direct staff to report.")
    assert recs == ["1. Council receive this.", "2. Council direct staff to report."]


def test_parse_report_header_and_sections():
    pages = ["REPORT FOR ACTION\nA Title\nDate: June 1, 2026\nTo: Some Committee\nFrom: A Director\nSUMMARY\nThe summary text.\n"
             "RECOMMENDATIONS\nThe Director recommends that:\n1. Receive the report.\nFINANCIAL IMPACT\nNone.\n"]
    r = parse_report("http://x", pages)
    assert r.header["date"] == "June 1, 2026" and r.header["to"] == "Some Committee"
    labels = {f.label: f.quote for f in r.facts}
    assert labels["Summary"] == "The summary text."
    assert r.recommendations == ["1. Receive the report."]


def test_verify_quote_whitespace_insensitive_and_rejects_made_up():
    pages = ["Council  receives\nthe report.", "Next page text."]
    assert quote_in_source("Council receives the report.", pages) == 1
    assert quote_in_source("Council approves the report.", pages) is None


def test_every_extracted_fact_is_verbatim_in_its_pdf_pages():
    d = ROOT / "data/reports"
    idx = json.loads((d / "index.json").read_text())
    assert idx, "run scripts/build_reports.py first"
    for name in idx.values():
        rep = json.loads((d / f"{name}.json").read_text())
        pages = json.loads((d / f"{name}.pages.json").read_text())
        for f in rep["facts"]:
            assert quote_in_source(f["quote"], pages) is not None, (name, f["label"])


def test_dundas_staff_recommendation_differs_from_decision():
    rep = json.loads((ROOT / "data/reports/backgroundfile-288607.json").read_text())
    assert rep["recommendations"] == ["1. Toronto and East York Community Council receive this report for information."]
    item = json.loads((ROOT / "data/items/2026.TE34.104.json").read_text())
    decision = item["stages"][-1]["decision_text"]
    assert "investigate the feasibility" in decision and "receive this report" not in decision


def test_upcoming_items_flagged_with_actions_and_no_deadline_invented():
    item = json.loads((ROOT / "data/items/2027.PB1.6.json").read_text())
    assert item["upcoming"] is True
    assert set(item["actions"]) == {"Request to Speak", "Submit Comments"}
    blob = json.dumps(item).lower()
    assert "deadline" not in blob
    decided = json.loads((ROOT / "data/items/2026.TE34.104.json").read_text())
    assert decided["upcoming"] is False
