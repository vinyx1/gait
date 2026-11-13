"""Group duplicate findings in stored audits (adds a 'groups' list to each file in data/audits/)."""
import json
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from triplens import agents  # noqa: E402
from triplens.rewrite import load_env  # noqa: E402


def main() -> None:
    load_env(ROOT / ".env")
    client = anthropic.Anthropic()
    for p in sorted((ROOT / "data/audits").glob("*.json")):
        a = json.loads(p.read_text())
        a["groups"] = agents.consolidate(client, a)
        p.write_text(json.dumps(a, indent=2, ensure_ascii=False))
        n = sum(len(r["kept"]) for r in a["roles"])
        print(f"{p.name}: {n} findings -> {len(a['groups'])} distinct", flush=True)


if __name__ == "__main__":
    main()
