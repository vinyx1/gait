"""Run the access-audit agents and store checked findings in data/audits/.

Usage: python scripts/run_audits.py [location_id ...] [--persona wheelchair --persona senior_walker ...]
Needs ANTHROPIC_API_KEY in .env. Each location x persona runs three agents (a few cents each).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gait import access, agents  # noqa: E402
from gait.rewrite import load_env  # noqa: E402


def main() -> None:
    load_env(ROOT / ".env")
    args = sys.argv[1:]
    personas = []
    while "--persona" in args:
        i = args.index("--persona"); personas.append(args[i + 1]); del args[i:i + 2]
    personas = personas or list(access.PERSONAS)
    locs = [l for l in json.loads((ROOT / "data/locations.json").read_text()) if not args or l["id"] in args]
    client = anthropic.Anthropic()
    jobs = [(l, p) for l in locs for p in personas]
    out = ROOT / "data/audits"
    out.mkdir(exist_ok=True)

    def run(job):
        loc, persona = job
        res = agents.audit(client, loc, persona)
        (out / f"{loc['id']}__{persona}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
        kept = sum(len(r["kept"]) for r in res["roles"]); dropped = sum(len(r["dropped"]) for r in res["roles"])
        calls = sum(len(r["calls"]) for r in res["roles"])
        tin = sum(r["usage"]["input"] for r in res["roles"]); tout = sum(r["usage"]["output"] for r in res["roles"])
        cost = tin * 4 / 1e6 + tout * 20 / 1e6  # claude-opus-5-5 list prices, $ per million tokens
        return f"{loc['id']} | {persona}: kept {kept}, dropped {dropped}, tool calls {calls}, tokens in/out {tin}/{tout}, about ${cost:.2f}"

    with ThreadPoolExecutor(max_workers=3) as ex:
        for line in ex.map(run, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
