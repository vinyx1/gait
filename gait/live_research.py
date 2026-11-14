"""Live, opt-in research for one trip: retrieve, generate, verify (RAG with a checker). Costs a few cents per new trip.

1. Retrieve (free, local): candidate sentences from staff reports about the trip's routes (finder.py over the FTS5
   index), sentences naming the rider's own stop streets first, plus the full text of each cited page.
2. Generate (Claude): read the numbered passages and the trip summary; return 0-4 findings, each quoting a passage.
3. Verify (code, not AI): a finding is shown only if its quote is on the cited page, its summary passes the
   rewrite checker (no number missing from the page, no stronger wording than the quote) and the agent banned words.
Results are cached per trip in data/research_live/, so a repeat click costs nothing. The resident's addresses are
never sent: only route numbers, stop names, rider type and the retrieved passages.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import finder
from .agents import BANNED
from .rewrite import check_sentence, load_env

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/research_live"
MODEL = "claude-opus-5-5"
MAX_PASSAGES = 14

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["findings"], "properties": {"findings": {"type": "array", "items": {
    "type": "object", "additionalProperties": False,
    "required": ["passage", "quote", "summary", "why_it_matters", "kind"],
    "properties": {"passage": {"type": "integer"}, "quote": {"type": "string"}, "summary": {"type": "string"},
                   "why_it_matters": {"type": "string"},
                   "kind": {"type": "string", "enum": ["stop_change", "shelter_or_bench", "service", "sidewalk_or_crossing", "construction", "other"]}}}}}}

SYSTEM = """You help a transit rider with accessibility needs understand City of Toronto decisions that may affect their usual trip.
You get numbered passages from City staff reports (found by a keyword search, so many are not relevant) and a short trip summary.
Return at most 4 findings, only from passages that plausibly concern this rider's route, stops or walk. For each:
- passage: the passage number; quote: one exact sentence copied character for character from that passage (under 300 characters);
- summary: one plain sentence saying what the passage says, using no number that is not in the passage, and no stronger wording than the quote;
- why_it_matters: one plain sentence on how it could touch this trip for this rider, phrased as "could" or "may", never as advice.
Do not use the words always, never, guarantee, impossible, unsafe, dangerous, definitely, certainly, must, safe.
If no passage is relevant, return an empty list. Do not guess."""


def _key(trip: dict) -> str:
    return hashlib.sha1(json.dumps(trip, sort_keys=True).encode()).hexdigest()[:16]


def trip_summary(legs, rider_label: str) -> dict:
    rides = [{"route": l.route, "board": l.board["name"], "alight": l.alight["name"]} for l in legs if l.kind == "transit"]
    return {"rider": rider_label, "rides": rides}


def retrieve(trip: dict) -> list[dict]:
    """Candidate passages: finder sentences for each route, own-stop streets first, with the full page text."""
    cands = []
    for r in trip["rides"]:
        mine = {p.strip().replace(" West", "").replace(" East", "") for s in (r["board"], r["alight"]) for p in s.split(" at ")}
        for f in finder.find(r["route"])["findings"]:
            f["own_stop"] = any(n in mine for n in f["stops_named"])
            cands.append({**f, "route": r["route"]})
    con = sqlite3.connect(f"file:{finder.DB}?mode=ro", uri=True)
    # broader search: pages naming the rider's own stop streets together with transit words
    def base(street: str) -> str:
        return re.sub(r"(\s+(St|Ave|Rd|Blvd|Dr|West|East|W|E|North|South))+$", "", re.sub(r"\(.*?\)", "", street)).strip()
    for r in trip["rides"]:
        for stop in (r["board"], r["alight"]):
            if " at " not in stop:
                continue
            main, other = (base(x) for x in stop.split(" at ", 1))
            if len(main) < 4 or len(other) < 4:
                continue
            q = f'"{main}" AND "{other}" AND (stop OR stops OR shelter OR TTC OR sidewalk OR transit)'
            for text, url, item, page in con.execute("SELECT text, url, item, page FROM pages WHERE pages MATCH ? ORDER BY rank LIMIT 6", (q,)):
                for s in finder.sentences(text):
                    if other in s and len(s) < 500 and re.search(r"\b(stops?|shelters?|TTC|sidewalks?|platforms?)\b", s, re.I):
                        cands.append({"item_id": item, "document_url": url, "page": page, "quote": s[:600], "stops_named": [other],
                                      "change_type": "mentions your stop street", "score": 5, "own_stop": True, "route": r["route"]})
                        break
    cands.sort(key=lambda f: (-f["own_stop"], -f["score"]))
    out, seen = [], set()
    for f in cands:
        k = (f["document_url"], f["page"], f["quote"][:80])
        if k in seen:
            continue
        seen.add(k)
        row = con.execute("SELECT text FROM pages WHERE url = ? AND page = ?", (f["document_url"], f["page"])).fetchone()
        if row:
            out.append({**f, "page_text": row[0]})
        if len(out) >= MAX_PASSAGES:
            break
    con.close()
    return out


def _window(page: str, quote: str, n: int = 700) -> str:
    """The quoted sentence with some text either side, so the model sees context."""
    i = page.find(quote[:60])
    return page[max(0, i - n):i + len(quote) + n] if i >= 0 else page[:2 * n]


def verify(f: dict, passages: list[dict], trip: dict | None = None) -> str | None:
    if not (1 <= f["passage"] <= len(passages)):
        return "no such passage"
    page = passages[f["passage"] - 1]["page_text"]
    for field in ("summary", "why_it_matters"):
        low = " " + re.sub(r"[^a-z ]", " ", f[field].lower()) + " "
        bad = [w for w in BANNED if f" {w} " in low]
        if bad:
            return f"banned word in {field}: {bad[0]}"
    allowed = set(re.findall(r"\d+", page + json.dumps(trip or {})))      # numbers from the page or the trip (route numbers)
    extra = set(re.findall(r"\d+", f["summary"] + " " + f["why_it_matters"])) - allowed
    if extra:
        return "number not in source: " + ", ".join(sorted(extra))
    return check_sentence(f["summary"], f["quote"], page + " " + json.dumps(trip or {}))


def run(legs, rider_label: str, client=None) -> dict:
    trip = trip_summary(legs, rider_label)
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{_key(trip)}.json"
    if path.exists():
        return {**json.loads(path.read_text()), "cached": True}
    passages = retrieve(trip)
    trace = [f"Retrieved {len(passages)} passages from the indexed staff reports for route "
             f"{', '.join(r['route'] for r in trip['rides'])} ({sum(p['own_stop'] for p in passages)} name a street at your stops)."]
    if not passages:
        res = {"trip": trip, "kept": [], "dropped": [], "trace": trace + ["Nothing to read, so the AI was not called."], "usage": None}
        path.write_text(json.dumps(res))
        return res
    if client is None:
        import os
        import anthropic
        from . import limits
        load_env(ROOT / ".env")
        if not os.environ.get("ANTHROPIC_API_KEY"):    # not cached, so it runs if a key is added later
            return {"trip": trip, "kept": [], "dropped": [], "usage": None,
                    "trace": trace + ["Live AI research is turned off on this server (no API key), so the AI was not called."]}
        if not limits.take_ai_call():
            return {"trip": trip, "kept": [], "dropped": [], "usage": None,
                    "trace": trace + ["Today's limit for live AI research on this server has been reached, so the AI was not called. Try again tomorrow."]}
        client = anthropic.Anthropic()
    text = "\n\n".join(f"[{i}] item {p['item_id']}, page {p['page']}:\n{_window(p['page_text'], p['quote'])}" for i, p in enumerate(passages, 1))
    msg = client.messages.create(model=MODEL, max_tokens=4000, system=SYSTEM,
                                 output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                                 messages=[{"role": "user", "content": f"Trip: {json.dumps(trip)}\n\nPassages:\n{text}"}])
    out = next((b.text for b in msg.content if b.type == "text"), "{}")
    try:
        found = json.loads(out)["findings"]
    except (ValueError, KeyError):
        found = []
    kept, dropped = [], []
    for f in found:
        why = verify(f, passages, trip)
        p = passages[f["passage"] - 1] if 1 <= f["passage"] <= len(passages) else {}
        rec = {**f, "item_id": p.get("item_id"), "document_url": p.get("document_url"), "page": p.get("page")}
        (dropped if why else kept).append({**rec, **({"reason": why} if why else {})})
    trace += [f"Claude ({MODEL}) read them and proposed {len(found)} finding(s).",
              f"The checker kept {len(kept)} and dropped {len(dropped)} (quote must be on the cited page; no new numbers; no stronger wording)."]
    res = {"trip": trip, "kept": kept, "dropped": dropped, "trace": trace, "model": MODEL,
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "usage": {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}}
    path.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return res
