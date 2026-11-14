"""Research agent: find past municipal decisions that changed a transit route, using public City records.

Tools (all local or limited to City of Toronto legdocs PDFs):
  search_records(query)       titles in the Voting Record and Report Request Log (brief datasets)
  list_documents(item_id)     background documents linked from saved item pages
  read_document(url, query)   passages from a staff report PDF that contain the query words, with page numbers
Every finding must quote a document passage exactly; the verifier drops anything else. Findings are proposals for a
person to review before they become a change file.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/reports/cache"
MODEL = "claude-opus-5-5"
BETA = "server-side-fallback-2026-07-01"

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {"type": "object", "properties": {
        "item_id": {"type": "string"}, "decision_summary": {"type": "string"},
        "change_type": {"type": "string", "enum": ["remove_stop", "relocate_stop", "close_stop_temporary", "remove_shelter", "reroute", "service_change", "close_sidewalk", "curb_lane_change", "station_accessibility", "lanes_or_traffic", "other"]},
        "stops_named": {"type": "array", "items": {"type": "string"}},
        "document_url": {"type": "string"}, "page": {"type": "integer"}, "quote": {"type": "string"}},
        "required": ["item_id", "decision_summary", "change_type", "stops_named", "document_url", "page", "quote"], "additionalProperties": False}}},
    "required": ["findings"], "additionalProperties": False}

TOOLS = [
    {"name": "search_records", "description": "Search council and committee item titles (Voting Record 2022-2026) and report requests for words. Returns item ids, dates, bodies, titles.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    {"name": "list_documents", "description": "List the background documents (staff reports, decision letters) linked from a saved item page.",
     "input_schema": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"], "additionalProperties": False}},
    {"name": "read_document", "description": "Return passages (with PDF page numbers) from a City staff report that contain the query words.",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}, "query": {"type": "string"}}, "required": ["url", "query"], "additionalProperties": False}},
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip()


def _records():
    v = json.loads((ROOT / "data/records/voting_items.json").read_text())["items"]
    r = json.loads((ROOT / "data/records/report_requests.json").read_text())["rows"]
    return v, r


def search_records(query: str) -> str:
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    v, r = _records()
    hits = [f"{x['item']} | {x['date']} | {x['body']} | {x['title']} | motions: {'; '.join(x['motions'][:4])}"
            for x in v if all(w in x["title"].lower() for w in words)]
    hits += [f"{x.get('Item Number')} | report request | {x.get('Agenda title')} | {(x.get('Directive') or '')[:160]}"
             for x in r if all(w in ((x.get("Agenda title") or "") + " " + (x.get("Directive") or "")).lower() for w in words)]
    return "\n".join(hits[:20]) or "No matching records."


def _snapshots() -> dict:
    out = {}
    for p in (ROOT / "data/raw").glob("*_snapshot.json"):
        out.update(json.loads(p.read_text())["items"])
    return out


def list_documents(item_id: str) -> str:
    it = _snapshots().get(item_id)
    if not it:
        return "No saved page for that item. Only items saved from the City site can be read."
    seen, lines = set(), []
    for l in it["links"]:
        if "/bgrd/" in l["href"] and l["href"] not in seen:
            seen.add(l["href"])
            lines.append(f"{l['href']} | {l['text'][:120]}")
    return "\n".join(lines) or "No background documents linked."


def pages_for(url: str) -> list[str]:
    if not re.match(r"^https://www\.toronto\.ca/legdocs/", url):
        raise ValueError("Only City of Toronto legdocs documents can be read.")
    CACHE.mkdir(parents=True, exist_ok=True)
    name = url.rsplit("/", 1)[-1].replace(".pdf", "")
    js = CACHE / f"{name}.pages.json"
    if js.exists():
        return json.loads(js.read_text())
    pdf = CACHE / f"{name}.pdf"
    subprocess.run(["curl", "-sL", "-m", "120", "-o", str(pdf), url], check=True)
    pages = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    js.write_text(json.dumps(pages))
    return pages


def read_document(url: str, query: str) -> str:
    try:
        pages = pages_for(url)
    except Exception as e:
        return f"Could not read the document: {e}"
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    out = []
    for i, p in enumerate(pages, 1):
        t = _norm(p)
        for m in re.finditer(r"[^.]*\.", t):
            s = m.group(0).strip()
            if words and sum(w in s.lower() for w in words) >= max(1, len(words) // 2):
                out.append(f"[page {i}] {s}")
    return "\n".join(out[:12]) or "No passages matched."


SYSTEM = """You research past municipal decisions that changed a TTC route, for a tool that helps riders with accessibility needs.
Use the tools to find council, committee or TTC Board items about the route (search by street name, route name, "transit priority",
"RapidTO", "stop"), list their documents, and read passages about stops, shelters, routing or service on the route.
Report only what the documents say. For each finding, copy one exact passage (under 400 characters) from a read_document result
as "quote", with its page number and document URL, and list any stop names it gives. Look for every kind of change that can alter
an accessible trip: stops removed, relocated or temporarily closed; shelters or benches removed; reroutes or diversions; service
cuts (frequency, hours, weekends); sidewalks or crossings closed; curb-lane changes (bike lanes, patios, loading zones) at stops;
station elevator or accessibility work. Search with several queries (street names, route name, "construction", "staging",
"diversion", "service", "RapidTO", "transit priority"). If nothing relevant is found, return an empty list. Do not guess."""


def run(client, route: str, name: str, streets: list[str], max_turns: int = 12) -> dict:
    tools = {"search_records": search_records, "list_documents": list_documents, "read_document": read_document}
    calls = []
    messages = [{"role": "user", "content": f"Route {route} {name}. Streets it runs on: {', '.join(streets)}. Find past decisions that changed this route."}]
    final, usage = "", {"input": 0, "output": 0}
    for _ in range(max_turns):
        resp = client.beta.messages.create(model=MODEL, max_tokens=8000, betas=[BETA], fallbacks="default", system=SYSTEM, tools=TOOLS,
                                           output_config={"effort": "medium", "format": {"type": "json_schema", "schema": FINDINGS_SCHEMA}},
                                           messages=messages)
        usage["input"] += resp.usage.input_tokens; usage["output"] += resp.usage.output_tokens
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            res = []
            for b in resp.content:
                if b.type == "tool_use":
                    out = tools[b.name](**(b.input or {}))
                    calls.append({"tool": b.name, "args": b.input, "result": out[:2000]})
                    res.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
            messages.append({"role": "user", "content": res})
            continue
        final = next((b.text for b in resp.content if b.type == "text"), "")
        break
    try:
        findings = json.loads(re.search(r"\{.*\}", final, re.S).group(0))["findings"]
    except Exception:
        findings = []
    kept, dropped = [], []
    known = {x["item"] for x in _records()[0]} | set(_snapshots())
    for f in findings:
        reason = None
        if f["item_id"] not in known:
            reason = "item not in City records"
        else:
            try:
                pages = pages_for(f["document_url"])
                if not (1 <= f["page"] <= len(pages)) or _norm(f["quote"]) not in _norm(pages[f["page"] - 1]):
                    reason = "quote not found on that page"
            except Exception as e:
                reason = f"document unreadable: {e}"
        (dropped if reason else kept).append({**f, **({"reason": reason} if reason else {})})
    return {"route": route, "name": name, "model": MODEL, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kept": kept, "dropped": dropped, "calls": calls, "usage": usage}
