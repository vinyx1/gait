"""Generate checked plain-language rewrites for each item and store them in data/plain/.

Usage: python scripts/build_plain.py [item_id ...]
Needs ANTHROPIC_API_KEY (read from .env). Rewrites cost a few cents in total for the demo items.
Only sentences that pass gait.rewrite.check_sentence are kept.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gait.rewrite import load_env, rewrite_passage, rewrite_to_dict  # noqa: E402

OUT = ROOT / "data/plain"


def passages_for(item: dict, reports: dict) -> list[tuple[str, int | None, str]]:
    """(label, page, source text) for the passages worth rewriting on an item page."""
    out = []
    primary = None
    for st in item["stages"]:
        for b in st["background"]:
            r = reports.get(b["url"])
            if r and r["recommendations"]:
                primary = r
                break
        if primary:
            break
    if primary:
        for f in primary["facts"]:
            if f["label"] == "Summary":
                out.append(("What the report says (summary)", f["page"], f["quote"]))
            if f["label"] == "Recommendations":
                out.append(("What the report recommends", f["page"], f["quote"]))
    last = item["stages"][-1]
    if last.get("decision_text") and not item.get("upcoming"):
        out.append(("What was decided", None, last["decision_text"]))
    return out


def main() -> None:
    load_env(ROOT / ".env")
    client = anthropic.Anthropic()
    OUT.mkdir(parents=True, exist_ok=True)
    idx = json.loads((ROOT / "data/reports/index.json").read_text())
    reports = {u: json.loads((ROOT / f"data/reports/{n}.json").read_text()) for u, n in idx.items()}
    wanted = set(sys.argv[1:])
    jobs = []
    for p in sorted((ROOT / "data/items").glob("*.json")):
        item = json.loads(p.read_text())
        if wanted and item["item_id"] not in wanted:
            continue
        for label, page, src in passages_for(item, reports):
            jobs.append((item["item_id"], label, page, src))

    def run(job):
        item_id, label, page, src = job
        return item_id, rewrite_passage(client, label, page, src)

    results: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for item_id, rw in ex.map(run, jobs):
            results.setdefault(item_id, []).append(rewrite_to_dict(rw))
            print(f"{item_id} | {rw.label}: kept {len(rw.sentences)}, dropped {len(rw.dropped)}"
                  + (f" | {rw.note}" if rw.note else ""))
    for item_id, rws in results.items():
        (OUT / f"{item_id}.json").write_text(json.dumps(rws, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
