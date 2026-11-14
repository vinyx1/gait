import json
from pathlib import Path

from gait.rewrite import check_sentence

ROOT = Path(__file__).resolve().parent.parent


def test_every_stored_sentence_passes_the_checks_against_its_own_source():
    files = list((ROOT / "data/plain").glob("*.json"))
    assert files, "run scripts/build_plain.py first"
    for f in files:
        for rw in json.loads(f.read_text()):
            for s in rw["sentences"]:
                assert check_sentence(s["plain"], s["quote"], rw["source"]) is None, (f.name, s["plain"])


def test_stored_sources_match_current_report_and_decision_text():
    """A rewrite is stale if the official text changed after it was generated."""
    idx = json.loads((ROOT / "data/reports/index.json").read_text())
    texts = []
    for n in idx.values():
        texts += [f["quote"] for f in json.loads((ROOT / f"data/reports/{n}.json").read_text())["facts"]]
    for item_file in (ROOT / "data/items").glob("*.json"):
        item = json.loads(item_file.read_text())
        texts += [s["decision_text"] for s in item["stages"] if s.get("decision_text")]
    pf = ROOT / "data/plain"
    for f in pf.glob("*.json"):
        for rw in json.loads(f.read_text()):
            assert rw["source"] in texts, (f.name, rw["label"])


def test_known_source_problem_is_recorded_for_dundas():
    notes = json.loads((ROOT / "data/notes/2026.TE34.104.json").read_text())
    assert any("November 15, 2026" in n["text"] for n in notes)
