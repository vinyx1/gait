"""Access-audit agents.

Three specialist agents (Claude with tools) investigate one location for one rider persona. Their tools are
local, deterministic functions over open data, so every claim an agent makes can be traced to text a tool
returned. A mechanical verifier then keeps a finding only if:
  * it cites at least one tool result by id,
  * every quote it cites is an exact substring of that tool result,
  * every number in its sentence appears in the cited results (or in the persona assumptions),
  * it avoids absolute or alarming words.
Findings that fail are stored with the reason and never shown to residents.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import access

MODEL = "claude-opus-5-5"
BETA = "server-side-fallback-2026-07-01"
ROOT = Path(__file__).resolve().parent.parent
MAX_TURNS = 8

BANNED = ("always", "never", "guarantee", "guaranteed", "impossible", "unsafe", "dangerous", "definitely",
          "certainly", "must", "safe", "accessible route")  # 'accessible route' implies a checked path we do not have

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "watch"]},
                    "cites": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"call": {"type": "string"}, "quote": {"type": "string"}},
                            "required": ["call", "quote"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "detail", "severity", "cites"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

ROLES = {
    "stops_boarding": {
        "label": "Stops and boarding auditor",
        "tools": ["nearby_stops", "stop_detail"],
        "focus": "Whether this rider can actually use the stops near the location: boarding accessibility flags, "
                 "distance versus the walking limit, and shelter or bench listings. Compare the nearest stop with the nearest stop that works for this rider.",
    },
    "walking_winter": {
        "label": "Walking and winter auditor",
        "tools": ["nearby_stops", "planned_works", "winter_rules"],
        "focus": "Problems on the walk to and from stops: planned road or sidewalk works near the location, and what the City's "
                 "winter-maintenance report says about sidewalk and laneway clearing that could matter for this rider.",
    },
    "service_hours": {
        "label": "Service and schedule auditor",
        "tools": ["nearby_stops", "stop_detail"],
        "focus": "Whether service runs when this rider needs it: first and last weekday departures, late-night departures, "
                 "weekend service, and how many departures there are at the nearest usable stops.",
    },
}

TOOL_DEFS = {
    "nearby_stops": {
        "name": "nearby_stops",
        "description": "List transit stops near the location, nearest first, as text lines with distance, wheelchair boarding flag, "
                       "shelter and bench listings, routes and weekday service times.",
        "input_schema": {"type": "object", "properties": {"max_results": {"type": "integer", "description": "1 to 15"}},
                         "additionalProperties": False},
    },
    "stop_detail": {
        "name": "stop_detail",
        "description": "Detail for one stop near the location: the stop line plus weekday departures per hour.",
        "input_schema": {"type": "object", "properties": {"stop_id": {"type": "string"}},
                         "required": ["stop_id"], "additionalProperties": False},
    },
    "planned_works": {
        "name": "planned_works",
        "description": "City road resurfacing and sidewalk construction programs near the location, with status and timeline text.",
        "input_schema": {"type": "object", "properties": {"radius_m": {"type": "integer", "description": "50 to 800"}},
                         "additionalProperties": False},
    },
    "winter_rules": {
        "name": "winter_rules",
        "description": "Exact sentences from the City's 2025-2026 Annual Winter Maintenance Report about sidewalk, laneway and transit-stop clearing.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def _nums(s: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", s)}


class Toolbox:
    """Tools bound to one location and persona. The model cannot choose a different location."""

    def __init__(self, loc: dict, persona_key: str):
        self.loc, self.persona = loc, access.PERSONAS[persona_key]
        self.calls: dict[str, dict] = {}
        self._n = 0

    def run(self, name: str, args: dict) -> str:
        fn = getattr(self, "t_" + name, None)
        out = fn(**args) if fn else "unknown tool"
        self._n += 1
        cid = f"C{self._n}"
        text = f"[{cid}] {out}"
        self.calls[cid] = {"tool": name, "args": args, "text": text}
        return text

    def t_nearby_stops(self, max_results: int = 10) -> str:
        n = max(1, min(int(max_results or 10), 15))
        near = access.stops_near(self.loc["lat"], self.loc["lon"], self.persona.max_walk_m * 1.6 / access.DETOUR)[:n]
        if not near:
            return "No stops found within the search area."
        return "\n".join(access.stop_line(s) for s in near)

    def t_stop_detail(self, stop_id: str) -> str:
        near = {s["stop_id"]: s for s in access.stops_near(self.loc["lat"], self.loc["lon"], 1500)}
        s = near.get(str(stop_id))
        if not s:
            return "That stop is not within 1500 m of the location."
        wd = s["service"].get("weekday", {}).get("per_hour", {})
        per = ", ".join(f"{int(h):02d}:00 has {c}" for h, c in sorted(wd.items(), key=lambda x: int(x[0])))
        return access.stop_line(s) + "\nWeekday departures per hour (hours 24 and above mean after midnight): " + (per or "none")

    def t_planned_works(self, radius_m: int = 300) -> str:
        r = max(50, min(int(radius_m or 300), 800))
        w = access.works_near(self.loc["lat"], self.loc["lon"], r)[:8]
        if not w:
            return f"No road resurfacing or sidewalk construction program entries within {r} m."
        return "\n".join(access.works_line(x) for x in w)

    def t_winter_rules(self) -> str:
        facts = json.loads((ROOT / "data/notes/winter_rules.json").read_text())
        return "\n".join(f"{f['id']} | {f['text']} | source: {f['source']}, PDF page {f['page']}" for f in facts)


def system_prompt(role_key: str, persona: access.Persona) -> str:
    role = ROLES[role_key]
    return f"""You are the {role['label']} for a public tool that explains how municipal decisions and places affect \
different people. You are investigating one location for one rider: {persona.label}. {persona.note}

Your focus: {role['focus']}

Use your tools to gather evidence, then report findings. Rules:
- Use only what the tool results say. If the data does not show something, say "the data does not show" rather than guessing.
- Tool results are text. Each starts with an id like [C2]. In each finding, cite the result id and copy a short exact quote \
(under 200 characters) from that result that supports it. Copy it character for character.
- Copy numbers exactly as the tool results give them. Do not round, convert or compute new numbers.
- Do not say a place is safe, accessible overall, or suitable. Only describe what the data lists. "Not listed" in the \
City's shelter or bench data can mean the dataset is incomplete, not that none exists.
- Walking distances are straight-line times {access.DETOUR}, an estimate. The real sidewalk network was not checked.
- Write each finding in plain language a resident can follow (1 to 3 short sentences). Neutral tone. No advice to the resident.
- GTFS wheelchair flags: 1 = possible or accessible, 2 = not possible, 0 = no information. "No information" is not the same as "not accessible"; \
say which one the data shows. A stop can list boarding as possible while every trip serving it is flagged not accessible \
(in this feed every streetcar trip is flagged not accessible); both matter for a wheelchair user, so check the trip flags too. \
Do not explain why the feed does this; the feed does not say.
- severity: "watch" = a limit, gap or uncertainty worth knowing (including anything about works, winter rules or possible incompleteness); \
"info" = a useful fact with no problem. Do not use any stronger label; overall barriers are decided by fixed rules, not by you.
- Give 2 to 8 findings, each about a different fact (do not repeat the same fact in other words). If you cannot find any problem, say so as an "info" finding with evidence."""


def verify_findings(findings: list[dict], calls: dict[str, dict], persona: access.Persona) -> tuple[list[dict], list[dict]]:
    kept, dropped = [], []
    assumptions = f"{persona.max_walk_m} {access.DETOUR} 23:00 05:30"
    for f in findings:
        reason = None
        cites = f.get("cites") or []
        text = f.get("title", "") + " " + f.get("detail", "")
        if not cites:
            reason = "no citation"
        corpus = ""
        for c in cites:
            call = calls.get(c.get("call"))
            if not call:
                reason = reason or f"unknown tool result {c.get('call')}"
                continue
            if _norm(c.get("quote", "")) not in _norm(call["text"]):
                reason = reason or "quote not found in the cited result"
            corpus += " " + call["text"]
        if not reason:
            missing = _nums(text) - _nums(corpus + " " + assumptions)
            if missing:
                reason = "number not in cited results: " + ", ".join(sorted(missing))
        if not reason:
            low = " " + re.sub(r"[^a-z0-9' ]", " ", _norm(text)) + " "
            for w in BANNED:
                if f" {w} " in low:
                    reason = f"disallowed word: {w}"
                    break
        if not reason and f.get("severity") == "barrier":
            f = {**f, "severity": "watch",
                 "note": "Labelled 'worth knowing': only the fixed rules on this page can mark a barrier."}
        (dropped if reason else kept).append({**f, **({"reason": reason} if reason else {})})
    return kept, dropped


def dedupe(all_kept: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Drop a later finding when its cited quotes overlap an earlier one by 40% or more (same fact, different words)."""
    sets, out = [], []
    for role, f in all_kept:
        key = {_norm(c["quote"]) for c in f["cites"]}
        dup = any(key and s and len(key & s) / len(key | s) >= 0.4 for s in sets)
        if dup:
            continue
        sets.append(key)
        out.append((role, f))
    return out


def run_auditor(client, loc: dict, persona_key: str, role_key: str) -> dict:
    persona = access.PERSONAS[persona_key]
    tb = Toolbox(loc, persona_key)
    tools = [TOOL_DEFS[t] for t in ROLES[role_key]["tools"]]
    messages = [{"role": "user", "content": f"Investigate this location: {loc['label']}. Start by calling your tools, then report findings."}]
    system = system_prompt(role_key, persona)
    final_text, use_format = "", True
    usage = {"input": 0, "output": 0}
    for _ in range(MAX_TURNS):
        kwargs = dict(model=MODEL, max_tokens=8000, betas=[BETA], fallbacks="default", system=system,
                      tools=tools, messages=messages)
        kwargs["output_config"] = ({"effort": "medium", "format": {"type": "json_schema", "schema": FINDINGS_SCHEMA}}
                                   if use_format else {"effort": "medium"})
        try:
            resp = client.beta.messages.create(**kwargs)
        except Exception as e:  # structured output with tools unsupported: retry once without it
            if use_format:
                use_format = False
                system += "\n\nWhen you are finished, reply with only a JSON object: {\"findings\": [{\"title\",\"detail\",\"severity\",\"cites\":[{\"call\",\"quote\"}]}]}."
                continue
            raise
        usage["input"] += resp.usage.input_tokens + (resp.usage.cache_read_input_tokens or 0) + (resp.usage.cache_creation_input_tokens or 0)
        usage["output"] += resp.usage.output_tokens
        if resp.stop_reason == "refusal":
            return {"role": role_key, "kept": [], "dropped": [], "calls": tb.calls, "note": "The model declined.", "usage": usage}
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": tb.run(b.name, b.input or {})})
            messages.append({"role": "user", "content": results})
            continue
        final_text = next((b.text for b in resp.content if b.type == "text"), "")
        break
    findings = []
    try:
        m = re.search(r"\{.*\}", final_text, re.S)
        findings = json.loads(m.group(0)).get("findings", []) if m else []
    except Exception:
        return {"role": role_key, "kept": [], "dropped": [], "calls": tb.calls, "note": "Unreadable answer.", "usage": usage}
    kept, dropped = verify_findings(findings, tb.calls, persona)
    return {"role": role_key, "kept": kept, "dropped": dropped, "calls": tb.calls, "note": None, "usage": usage}


def audit(client, loc: dict, persona_key: str) -> dict:
    with ThreadPoolExecutor(max_workers=3) as ex:
        roles = list(ex.map(lambda r: run_auditor(client, loc, persona_key, r), ROLES))
    return {"location": loc["id"], "label": loc["label"], "persona": persona_key,
            "persona_label": access.PERSONAS[persona_key].label, "model": MODEL,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "feed": access.load_stops()["meta"], "roles": roles}


# ---------- consolidation: group duplicate findings (groups only, no new text) ----------

GROUP_SCHEMA = {
    "type": "object",
    "properties": {"groups": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}},
    "required": ["groups"], "additionalProperties": False,
}


def flatten_kept(audit: dict) -> list[tuple[str, dict]]:
    return [(r["role"], f) for r in audit["roles"] for f in r["kept"]]


def valid_partition(groups: list[list[int]], n: int) -> bool:
    flat = [i for g in groups for i in g]
    return sorted(flat) == list(range(n)) and all(g for g in groups)


def consolidate(client, audit: dict) -> list[list[int]]:
    """Ask the model which findings state the same fact. It returns index groups only, never new wording."""
    flat = flatten_kept(audit)
    if len(flat) < 2:
        return [[i] for i in range(len(flat))]
    listing = "\n".join(f"{i}. {f['title']} - {f['detail']}" for i, (_, f) in enumerate(flat))
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=4000, betas=[BETA], fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": GROUP_SCHEMA}},
        system=("You group findings that state the same fact about a place and a rider, even when worded differently or "
                "citing different parts of the same stop's data. Findings about different facts (for example a shelter "
                "listing versus trip accessibility flags at the same stop) must stay in different groups. Every finding "
                "number must appear in exactly one group. Put the clearest finding first in each group. Do not write any new text."),
        messages=[{"role": "user", "content": listing}])
    try:
        groups = json.loads(next(b.text for b in resp.content if b.type == "text"))["groups"]
    except Exception:
        groups = []
    return groups if valid_partition(groups, len(flat)) else [[i] for i in range(len(flat))]
