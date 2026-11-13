"""Parse a saved Toronto council/committee agenda-item page into structured data.

The parser is deliberately conservative: it copies decision text verbatim, never
paraphrases, and records the official item URL so every statement can be traced.
Names of members of the public who sent communications are dropped; only the
count and dates are kept. Vote results keep totals, not individual member names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}

STAGE_RE = re.compile(r"^(?P<body>.+?) consideration on (?P<dates>.+)$")
DATE_RE = re.compile(r"(?P<month>[A-Z][a-z]+) (?P<d1>\d{1,2})(?: and (?P<d2>\d{1,2}))?, (?P<year>\d{4})")

DECISION_HEAD_RE = re.compile(
    r"^(?:(City Council|Committee|Community Council|Board|Executive Committee)\s+"
    r"(Decision|Recommendations?)|Recommendations?)$")
OTHER_HEADS = {
    "Origin", "Summary", "Decision Advice and Other Information", "Declared Interests",
    "Vote", "Public Notice", "Report History",
}
SECTION_RE = re.compile(r"^(Background Information|Communications|Motions)(?: \((?P<scope>.+)\))?$")


def _is_head(line: str) -> bool:
    return bool(DECISION_HEAD_RE.match(line) or line in OTHER_HEADS or SECTION_RE.match(line)
                or STAGE_RE.match(line))


def parse_date_span(text: str) -> tuple[str | None, str | None]:
    """'July 29 and 30, 2026' -> ('2026-07-29', '2026-07-30'). None if unparseable."""
    m = DATE_RE.search(text)
    if not m or m.group("month") not in MONTHS:
        return None, None
    mo, y = MONTHS[m.group("month")], int(m.group("year"))
    first = date(y, mo, int(m.group("d1"))).isoformat()
    last = date(y, mo, int(m.group("d2") or m.group("d1"))).isoformat()
    return first, last


@dataclass
class Motion:
    motion_type: str
    moved_by: str | None
    result: str | None
    text: str


@dataclass
class VoteResult:
    motion: str
    when: str | None
    result: str | None
    required: str | None
    yes: int | None
    no: int | None
    absent: int | None


@dataclass
class Stage:
    body: str
    dates_text: str
    first_date: str | None
    last_date: str | None
    item_line: str | None = None
    decision_type: str | None = None
    status: str | None = None
    wards: str | None = None
    decision_heading: str | None = None
    decision_text: str | None = None
    origin: str | None = None
    summary: str | None = None
    background: list[dict] = field(default_factory=list)
    communications_count: int = 0
    communication_dates: list[str] = field(default_factory=list)
    motions: list[Motion] = field(default_factory=list)
    votes: list[VoteResult] = field(default_factory=list)


@dataclass
class Item:
    item_id: str
    url: str
    title: str
    tracking_status: list[str]
    stages: list[Stage]
    documents: list[dict]
    bylaws: list[dict]
    fetched_at: str | None = None
    actions: list[str] = field(default_factory=list)
    upcoming: bool = False


def _count(lines: list[str], label: str) -> int | None:
    for ln in lines:
        m = re.match(rf"^Total members that (?:voted )?{label}: (\d+)$", ln) or \
            re.match(rf"^Total members that were {label}: (\d+)$", ln)
        if m:
            return int(m.group(1))
    return None


def _parse_votes(lines: list[str]) -> list[VoteResult]:
    votes: list[VoteResult] = []
    i = 0
    while i < len(lines):
        if lines[i] == "Vote" and i + 1 < len(lines) and lines[i + 1].startswith("("):
            motion = lines[i + 1].strip("() ")
            j, block = i + 2, []
            while j < len(lines) and not (lines[j] == "Vote" or lines[j] == "Motion"
                                          or STAGE_RE.match(lines[j])):
                block.append(lines[j])
                j += 1
            when = next((b for b in block if re.match(r"^[A-Z][a-z]{2}-\d{2}-\d{4}", b)), None)
            result = next((b[len("Result: "):] for b in block if b.startswith("Result: ")), None)
            req = next((b for b in block if b.startswith("Majority Required")), None)
            votes.append(VoteResult(motion, when, result, req.strip() if req else None,
                                    _count(block, "Yes"), _count(block, "No"),
                                    _count(block, "Absent")))
            i = j
        else:
            i += 1
    return votes


def _parse_motions(lines: list[str]) -> list[Motion]:
    motions: list[Motion] = []
    i = 0
    while i < len(lines):
        if lines[i] == "Motion" and i + 1 < len(lines) and lines[i + 1].startswith("to "):
            mtype = lines[i + 1][3:].strip()
            j, moved, result, body = i + 2, None, None, []
            if j < len(lines) and lines[j] == "moved by":
                moved = lines[j + 1].strip() if j + 1 < len(lines) else None
                j += 2
            if j < len(lines) and re.match(r"^\((Carried|Lost|Ruled.*|Withdrawn.*)\)$", lines[j]):
                result = lines[j].strip("()")
                j += 1
            while j < len(lines) and not (lines[j] in ("Motion", "Vote") or STAGE_RE.match(lines[j])
                                          or re.match(r"^\d+$", lines[j]) and j + 1 < len(lines)
                                          and lines[j + 1].startswith("- Motion")):
                body.append(lines[j])
                j += 1
            motions.append(Motion(mtype, moved, result, "\n".join(body).strip()))
            i = j
        else:
            i += 1
    return motions


def _parse_stage(body: str, dates_text: str, lines: list[str]) -> Stage:
    first, last = parse_date_span(dates_text)
    st = Stage(body=body, dates_text=dates_text, first_date=first, last_date=last)

    # header facts
    for k, ln in enumerate(lines[:12]):
        if re.match(r"^[A-Z]{1,4}\d+\.\d+ - ", ln) and st.item_line is None:
            st.item_line = ln
        elif ln.startswith("Decision Type:") or ln.startswith("Consideration Type:"):
            st.decision_type = ln.split(":", 1)[1].strip()
        elif ln.startswith("Status:"):
            st.status = ln.split(":", 1)[1].strip()
        elif ln.startswith("Ward:") or ln.startswith("Wards:"):
            st.wards = ln.split(":", 1)[1].strip()

    # sections
    cur, buf = None, []
    sections: list[tuple[str, str | None, list[str]]] = []

    def flush():
        if cur is not None:
            sections.append((cur[0], cur[1], buf[:]))

    for ln in lines:
        m_dec = DECISION_HEAD_RE.match(ln)
        m_sec = SECTION_RE.match(ln)
        if m_dec:
            flush(); cur, buf = ("decision", ln), []
        elif m_sec:
            flush(); cur, buf = (m_sec.group(1), m_sec.group("scope")), []
        elif ln in OTHER_HEADS and ln != "Vote":
            flush(); cur, buf = (ln, None), []
        else:
            buf.append(ln)
    flush()

    for name, tag, content in sections:
        text = "\n".join(content).strip()
        if name == "decision":
            st.decision_heading, st.decision_text = tag, text
        elif name == "Origin":
            st.origin = text
        elif name == "Summary":
            st.summary = text
        elif name == "Background Information":
            dates = [c for c in content if re.match(r"^\(.*\d{4}\)", c)]
            links = [c for c in content if c.startswith("https://")]
            labels = [c for c in content if c not in dates and c not in links]
            for n, link in enumerate(links):
                st.background.append({
                    "date": dates[n] if n < len(dates) else None,
                    "label": labels[n] if n < len(labels) else None,
                    "url": link})
        elif name == "Communications":
            # Keep only count and dates; drop sender names and organisations.
            stamps = [c for c in content if re.match(r"^\(.*\d{4}\)", c)]
            st.communications_count = len(stamps)
            st.communication_dates = [re.match(r"^\((.*?)\)", s).group(1) for s in stamps]
        elif name == "Motions":
            st.motions = _parse_motions(content)

    st.votes = _parse_votes(lines)
    return st


def parse_item(item_id: str, url: str, text: str, links: list[dict], fetched_at: str | None = None,
               actions: list[str] | None = None) -> Item:
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Numbered motions render as "1" / "- Motion" / "to Amend Item"; normalise to "Motion".
    lines: list[str] = []
    for ln in raw_lines:
        if ln == "- Motion":
            if lines and re.fullmatch(r"\d+", lines[-1]):
                lines.pop()
            lines.append("Motion")
        else:
            lines.append(ln)

    # tracking status block
    tracking: list[str] = []
    if "Tracking Status" in lines:
        k = lines.index("Tracking Status") + 1
        while k < len(lines) and not lines[k].startswith("Expand All"):
            tracking.append(lines[k]); k += 1
    start = next((n for n, ln in enumerate(lines) if ln.startswith("Collapse All")), 0) + 1
    body = lines[start:]

    # split into stages
    idxs = [n for n, ln in enumerate(body) if STAGE_RE.match(ln) and not ln.startswith("Total")]
    stages: list[Stage] = []
    for a, idx in enumerate(idxs):
        end = idxs[a + 1] if a + 1 < len(idxs) else len(body)
        m = STAGE_RE.match(body[idx])
        stages.append(_parse_stage(m.group("body"), m.group("dates"), body[idx + 1:end]))
    stages.sort(key=lambda s: s.first_date or "")

    bylaws = [{"label": l["text"], "url": l["href"]} for l in links if "/legdocs/bylaws/" in l["href"]]
    docs, seen = [], set()
    for l in links:
        if "/legdocs/mmis/" in l["href"] and l["href"] not in seen:
            seen.add(l["href"])
            docs.append({"label": l["text"] if not l["text"].startswith("https://") else None,
                         "url": l["href"]})

    title = ""
    for st in stages:
        if st.item_line:
            title = st.item_line.split(" - ", 1)[1]
            break
    upcoming = any("will be considered" in x and "was considered" not in x and "adopted" not in x.lower()
                   for x in tracking) and not any(s.status for s in stages)
    return Item(item_id, url, title, tracking, stages, docs, bylaws, fetched_at,
                actions=sorted(set(actions or [])), upcoming=upcoming)


def item_to_dict(item: Item) -> dict:
    return asdict(item)
