"""Look up a Toronto address in a local file built from the City's open Address Points data.

Nothing is sent anywhere: the lookup is a local SQLite query. An address that is not found returns nearby
numbers on the same street so the resident can pick the right one.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data/geo/address.sqlite"

ABBR = {"avenue": "ave", "street": "st", "road": "rd", "drive": "dr", "crescent": "cres", "court": "ct", "boulevard": "blvd",
        "place": "pl", "lane": "ln", "terrace": "terr", "east": "e", "west": "w", "north": "n", "south": "s",
        "parkway": "pkwy", "circle": "cir", "square": "sq", "gardens": "gdns", "heights": "hts", "trail": "trl"}


def normalize(s: str) -> str:
    s = s.lower().replace("#", " ")
    s = re.sub(r",?\s*(toronto|etobicoke|scarborough|north york|york|east york)\b.*$", "", s)
    s = re.sub(r"^\s*(unit|apt|suite)?\s*\d+[a-z]?\s*[-,]\s*(?=\d)", "", s)   # "5-123 Queen" or "Unit 5, 123 Queen"
    s = re.sub(r"[.,]", " ", s)
    words = [ABBR.get(w, w) for w in s.split()]
    return " ".join(words)


def split_key(key: str) -> tuple[int | None, str]:
    m = re.match(r"^(\d+)[a-z]?\s+(.*)$", key)
    return (int(m.group(1)), m.group(2)) if m else (None, key)


@dataclass
class Place:
    label: str
    lat: float
    lon: float
    ward: str | None


def available() -> bool:
    return DB.exists()


def lookup(text: str) -> tuple[Place | None, list[Place]]:
    """Return (match, suggestions). Suggestions are same-street addresses with the nearest numbers."""
    key = normalize(text)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT full, lat, lon, ward FROM addr WHERE key = ? LIMIT 1", (key,)).fetchone()
        if row:
            return Place(*row), []
        num, street = split_key(key)
        sugg: list[Place] = []
        if street:
            if num is not None:
                rows = con.execute("SELECT full, lat, lon, ward FROM addr WHERE street = ? ORDER BY ABS(num - ?) LIMIT 5", (street, num)).fetchall()
            else:
                rows = con.execute("SELECT full, lat, lon, ward FROM addr WHERE street = ? ORDER BY num LIMIT 5", (street,)).fetchall()
            sugg = [Place(*r) for r in rows]
        return None, sugg
    finally:
        con.close()


def ward_near(lat: float, lon: float) -> str | None:
    """Ward name of the closest City address point (within about 300 m), or None."""
    if not available():
        return None
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        d = 0.003
        rows = con.execute("SELECT ward, lat, lon FROM addr WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
                           (lat - d, lat + d, lon - d * 1.4, lon + d * 1.4)).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if r[0]]
    return min(rows, key=lambda r: (r[1] - lat) ** 2 + ((r[2] - lon) * 0.72) ** 2)[0] if rows else None
