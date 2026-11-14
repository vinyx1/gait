"""New buildings approved by the City, from the indexed staff reports (data/corpus/index.sqlite).

For each report that recommends a rezoning "to permit a N-storey" building, keep:
  - the address from the report heading, placed with the City Address Points dataset (exact address only),
  - the summary sentence (storeys, homes) and, when present, the traffic sentence (peak-hour vehicle trips),
    each copied word for word with its page number and checked against that page,
  - the Council item's status line.
Reports whose address cannot be placed, or whose sentences cannot be found again on their page, are dropped.
Gait does not compute anything from these: they are shown as "being built near your trip", in the City's words.

Writes data/developments.json. Run: .venv/bin/python scripts/build_developments.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gait import geocode  # noqa: E402

DB = ROOT / "data/corpus/index.sqlite"
OUT = ROOT / "data/developments.json"

SUFFIX = r"(?:Street|Avenue|Road|Boulevard|Drive|Crescent|Place|Lane|Way|Court|Parkway|Trail|Square|Gate|Circle|Terrace|Park|Gardens|Heights)"
ADDR = re.compile(r"\b(\d{1,5})[A-Z]?(?:[-–]\d+[A-Z]?)?(?:(?:,| and| &)\s*\d{1,5}[A-Z]?(?:[-–]\d+[A-Z]?)?)*\s+((?:[A-Z][a-zA-Z'.]+\s){1,4}?" + SUFFIX + r"(?:\s(?:East|West|North|South))?)\b")
PERMIT = re.compile(r"\bto permit (?:a|an|two|three|four)\b.*?\b\d{1,3}-storey\b")
TRIPS = re.compile(r"\b(?:generate|generating)\b.*\b(?:vehicular|vehicle) trips\b")
SENT = re.compile(r"(?<=[a-z0-9)%])\.\s+(?=[A-Z])")      # a full stop then a capital: a sentence break ("137.5 metres" is not)


def sentence(text: str, pat: re.Pattern) -> str | None:
    """The whole sentence of `text` that contains `pat`, ending with its full stop."""
    for sn in SENT.split(text):
        if pat.search(sn):
            sn = sn.strip()
            return sn if sn.endswith(".") else sn + "."
    return None
STOREYS = re.compile(r"\b(\d{1,3})-storey")
UNITS = re.compile(r"\b([\d,]{1,6}) (?:new )?(?:residential |dwelling |rental )*units\b")


# City buildings named in meeting notices and letterheads, never a development site
CIVIC = {"100 Queen Street West", "55 John Street", "399 The West Mall", "150 Borough Drive", "5100 Yonge Street", "2 Civic Centre Court",
         "333 Bay Street", "100 King Street West", "40 King Street West"}
HEADINGS = re.compile(r".*\b(?:SUMMARY|DECISION HISTORY|HISTORY|PROPOSAL|Background|Proposal|Page \d+ of \d+|RECOMMENDATIONS|COMMENTS)\s+")


def norm(t: str) -> str:
    return " ".join(t.split())


def clean(sentence: str) -> str:
    """Cut a run-on page heading off the front of a sentence (PDF headings carry no full stop)."""
    head = HEADINGS.match(sentence)
    out = sentence[head.end():] if head else sentence
    return out if out[:1].isupper() or out[:1].isdigit() else sentence


def address(*texts: str) -> tuple[str, str] | None:
    for t in texts:
        for a in ADDR.finditer(t):
            if f"{a.group(1)} {a.group(2)}" not in CIVIC:
                return a.group(1), a.group(2)
    return None


def main() -> None:
    con = sqlite3.connect(DB)
    items = con.execute("SELECT DISTINCT item FROM pages WHERE pages MATCH '\"zoning by-law amendment\" AND storey'").fetchall()
    status = dict(con.execute("SELECT item, status FROM items").fetchall())
    out, dropped = [], {"no_permit_sentence": 0, "no_address": 0, "not_placed": 0, "not_adopted": 0}
    for (item,) in items:
        pages = con.execute("SELECT url, page, text FROM pages WHERE item = ? ORDER BY url, CAST(page AS INTEGER)", (item,)).fetchall()
        hit = None
        for url, page, text in pages:
            m = sentence(norm(text), PERMIT)
            if m and STOREYS.search(m):
                hit = (url, int(page), clean(m), norm(text))
                break
        if not hit:
            dropped["no_permit_sentence"] += 1
            continue
        url, page, permit, text = hit
        st = status.get(item) or ""
        if "adopted" not in st.lower():
            dropped["not_adopted"] += 1
            continue
        first = norm(next((t for u, p, t in pages if u == url and int(p) == 1), text))
        title = first.split("REPORT FOR ACTION", 1)[1][:300] if "REPORT FOR ACTION" in first else ""
        a = address(permit, title, first, text)        # the sentence itself first, then the report's own title
        if not a:
            dropped["no_address"] += 1
            continue
        num, street = a
        place, _ = geocode.lookup(f"{num} {street}")
        if not place:
            dropped["not_placed"] += 1
            continue
        quotes = [{"text": permit, "page": page}]
        for u, p, t in pages:
            if u != url:
                continue
            tm = sentence(norm(t), TRIPS)
            if tm:
                quotes.append({"text": clean(tm), "page": int(p)})
                break
        # every quote must be found again, word for word, on its page
        by_page = {int(p): norm(t) for u, p, t in pages if u == url}
        quotes = [q for q in quotes if q["text"] in by_page.get(q["page"], "")]
        if not quotes:
            continue
        s, u = STOREYS.findall(permit), UNITS.search(permit)
        out.append({"id": item, "address": f"{num} {street}", "lat": place.lat, "lon": place.lon, "ward": place.ward,
                    "storeys": max(int(x) for x in s), "units": int(u.group(1).replace(",", "")) if u else None,
                    "quotes": quotes, "source_url": url, "item_url": f"https://secure.toronto.ca/council/agenda-item.do?item={item}",
                    "status": st.split(".")[0].strip(), "located_by": "City Address Points dataset (exact address match)"})
    latest = {}                                   # one entry per site: the latest item wins
    for d in sorted(out, key=lambda d: d["id"]):
        latest[d["address"]] = d
    out = sorted(latest.values(), key=lambda d: d["id"])
    OUT.write_text(json.dumps({"source": "City of Toronto staff reports (indexed), Council item status", "items": out}, indent=1, ensure_ascii=False))
    print(f"{len(out)} new buildings kept from {len(items)} reports; dropped: {dropped}")


if __name__ == "__main__":
    main()
