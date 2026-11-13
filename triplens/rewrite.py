"""Plain-language rewrites of official text, written by Claude and checked mechanically.

Rules the code enforces (not just asks for):
* Every sentence must carry an exact quote copied from the source passage. A sentence whose quote
  is not found in the source (whitespace-insensitive) is dropped.
* Every number, date and dollar amount in a sentence must also appear in the source passage.
  Otherwise the sentence is dropped.
* Nothing is shown unless it passes. Dropped sentences are kept for review.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

MODEL = "claude-opus-5-5"
MAX_SOURCE_CHARS = 12000

SYSTEM = """You rewrite short passages from Toronto City Council and committee documents in plain language \
for residents, including people who are new to council processes, have limited English or lower literacy.

Write 2 to 6 short sentences (about a grade 8 reading level). For each sentence give the exact words from the \
source passage that support it.

Rules:
- Use only what the source passage says. Do not add facts, reasons, predictions or opinions.
- Keep every condition, date, deadline, number, dollar amount, place name and the name of who must act. \
Keep uncertainty ("may", "if", "subject to", "pending") and say who recommends versus who decides.
- Never say or imply that something has been decided if the passage only recommends it.
- Keep the strength of every verb. If the source says "request", "recommend", "authorize", "may" or "if", \
write "ask", "recommend", "allow", "may" or "if". Never turn a request or recommendation into "will", "must", \
"has to" or "is required". Do not add words such as "only", "just", "always", "never" or "all" unless the \
source has them.
- Neutral tone. Do not argue for or against the proposal. No advice about what residents should do.
- Prefer short words. Explain a technical term in a few words the first time you use it, but only if the \
source passage itself makes the meaning clear.
- "quote" must be copied exactly, character for character, from the source passage, as one continuous \
stretch of text. Keep each quote under 300 characters. Do not alter spelling or punctuation in the quote."""

SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "plain": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["plain", "quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sentences"],
    "additionalProperties": False,
}

# Words that make a statement stronger or more final. They may appear in a rewrite only if the quote has them.
STRONG_WORDS = ("must", "will", "shall", "only", "required", "requires", "always", "never", "has to",
                "have to", "guarantee", "guaranteed", "promise", "promised", "definitely", "all")

NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def _numbers(s: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(s)}


def check_sentence(plain: str, quote: str, source: str) -> str | None:
    """Return None if the sentence passes, else a short reason string."""
    if not plain.strip() or not quote.strip():
        return "empty"
    src = _norm(source)
    if _norm(quote) not in src:
        return "quote not found in source"
    def words(s: str) -> str:
        return " " + re.sub(r"[^a-z0-9' ]", " ", _norm(s)) + " "
    pl, q = words(plain), words(quote)
    for w in STRONG_WORDS:
        if f" {w} " in pl and f" {w} " not in q:
            return f"stronger wording than source: '{w}'"
    # numbers in the rewrite must come from the source passage
    missing = _numbers(plain) - _numbers(source)
    if missing:
        return "number not in source: " + ", ".join(sorted(missing))
    return None


@dataclass
class Rewrite:
    label: str
    page: int | None
    source: str
    sentences: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    model: str = MODEL
    generated_at: str = ""
    note: str | None = None


def load_env(path: Path) -> None:
    """Minimal .env reader (no extra dependency). Does not override existing variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def rewrite_passage(client, label: str, page: int | None, source: str) -> Rewrite:
    rw = Rewrite(label=label, page=page, source=source,
                 generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if len(source) > MAX_SOURCE_CHARS:
        rw.note = f"Passage is {len(source)} characters, too long to rewrite here; read the original."
        return rw
    prompt = f"Passage label: {label}\n\nSource passage:\n\"\"\"\n{source}\n\"\"\""
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        rw.note = "The model declined to rewrite this passage."
        return rw
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        rw.note = "The model returned an unreadable answer."
        return rw
    for s in data.get("sentences", []):
        reason = check_sentence(s.get("plain", ""), s.get("quote", ""), source)
        (rw.dropped if reason else rw.sentences).append({**s, **({"reason": reason} if reason else {})})
    if not rw.sentences:
        rw.note = rw.note or "No sentence passed the checks, so nothing is shown for this passage."
    return rw


def rewrite_to_dict(rw: Rewrite) -> dict:
    return asdict(rw)
