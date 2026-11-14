"""Convert raw item snapshots into parsed JSON files under data/items/.

Usage: python scripts/build_items.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gait.parse_item import parse_item, item_to_dict  # noqa: E402


def main() -> None:
    out = ROOT / "data/items"
    out.mkdir(parents=True, exist_ok=True)
    for snap in sorted((ROOT / "data/raw").glob("*_snapshot.json")):
        raw = json.loads(snap.read_text())
        for item_id, rec in raw["items"].items():
            if rec.get("status") != 200:
                print("skip", item_id, rec.get("status"))
                continue
            item = parse_item(item_id, rec["url"], rec["text"], rec["links"], raw.get("fetched_at"),
                              rec.get("actions"))
            (out / f"{item_id}.json").write_text(json.dumps(item_to_dict(item), indent=2, ensure_ascii=False))
            flag = " [UPCOMING]" if item.upcoming else ""
            print(f"{item_id}: {len(item.stages)} stage(s), {len(item.documents)} doc(s){flag} -> {item.title[:55]}")


if __name__ == "__main__":
    main()
