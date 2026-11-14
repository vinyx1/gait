"""Build data/geo/address.sqlite from the City's Address Points CSV (Open Government Licence - Toronto).

Download the CSV first (see README): data/geo/address_points.csv. Run: python scripts/build_address_index.py
"""
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gait.geocode import normalize, split_key  # noqa: E402

CSV = ROOT / "data/geo/address_points.csv"
DB = ROOT / "data/geo/address.sqlite"
csv.field_size_limit(10_000_000)


def main() -> None:
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE addr (key TEXT, full TEXT, lat REAL, lon REAL, ward TEXT, num INTEGER, street TEXT)")
    seen, batch, n = set(), [], 0
    with open(CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            full = r["ADDRESS_FULL"]
            if not full:
                continue
            key = normalize(full)
            if key in seen:
                continue
            seen.add(key)
            try:
                c = json.loads(r["geometry"])["coordinates"]
                lon, lat = (c[0] if isinstance(c[0], list) else c)[:2]
            except Exception:
                continue
            num, street = split_key(key)
            batch.append((key, full, lat, lon, r.get("WARD_NAME") or None, num, street))
            if len(batch) >= 50000:
                con.executemany("INSERT INTO addr VALUES (?,?,?,?,?,?,?)", batch); n += len(batch); batch = []
    con.executemany("INSERT INTO addr VALUES (?,?,?,?,?,?,?)", batch); n += len(batch)
    con.execute("CREATE INDEX i_key ON addr(key)")
    con.execute("CREATE INDEX i_street ON addr(street, num)")
    con.commit(); con.close()
    print(f"indexed {n} addresses -> {DB}")


if __name__ == "__main__":
    main()
