"""Run the research agent for routes and save findings to data/research/. Usage: python scripts/run_research.py 7 29"""
import json
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gait import research  # noqa: E402
from gait.rewrite import load_env  # noqa: E402

ROUTES = {"7": ("Bathurst", ["Bathurst Street"]), "29": ("Dufferin", ["Dufferin Street"]), "505": ("Dundas", ["Dundas Street West"]),
          "512": ("St Clair", ["St Clair Avenue West"])}


def main():
    load_env(ROOT / ".env")
    client = anthropic.Anthropic()
    for r in sys.argv[1:] or ["7"]:
        name, streets = ROUTES[r]
        res = research.run(client, r, name, streets)
        (ROOT / f"data/research/route-{r}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
        cost = res["usage"]["input"] * 4e-6 + res["usage"]["output"] * 20e-6
        print(f"route {r}: kept {len(res['kept'])}, dropped {len(res['dropped'])}, tool calls {len(res['calls'])}, about ${cost:.2f}")
        for f in res["kept"]:
            print("  ", f["item_id"], f["change_type"], f["stops_named"], "| p", f["page"], "|", f["quote"][:150])


if __name__ == "__main__":
    main()
