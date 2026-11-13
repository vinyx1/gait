"""Run the free rule-based finder on every TTC route (or the ones given). No AI, no cost.
Usage: python scripts/run_free_research.py [route ...]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from triplens import finder  # noqa: E402
from triplens.trip import load_routes  # noqa: E402


def main():
    routes = sys.argv[1:] or list(load_routes())
    total = 0
    for r in routes:
        res = finder.find(r)
        (ROOT / f"data/research_free/route-{r}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        strong = [f for f in res["findings"] if f["score"] >= 3]
        total += len(res["findings"])
        if strong:
            print(f"route {r} {res['name']}: {len(res['findings'])} candidates, {len(strong)} strong; top: {strong[0]['change_type']} {strong[0]['stops_named'][:4]} | {strong[0]['quote'][:110]}")
    print(f"{len(routes)} routes, {total} candidate sentences")


if __name__ == "__main__":
    main()
