"""Extract verbatim sections from a City staff report or member letter (PDF).

Everything returned is copied from the PDF text. Each fact carries the page it came from so a
reader can check the original. No paraphrasing happens here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

HEADINGS = ["SUMMARY", "RECOMMENDATIONS", "RECOMMENDATION", "FINANCIAL IMPACT", "DECISION HISTORY",
            "COMMENTS", "BACKGROUND", "CONTACT", "SIGNATURE", "ATTACHMENTS", "ORIGIN"]
HEAD_RE = re.compile(r"^\s*(%s)\s*:?\s*$" % "|".join(HEADINGS), re.I)
HEADER_FIELD_RE = re.compile(r"^(Date|To|From|Wards?)\s*:\s*(.+)$", re.I)


@dataclass
class Fact:
    label: str
    quote: str
    page: int


@dataclass
class Report:
    url: str
    title: str | None
    header: dict
    facts: list[Fact] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    pages: int = 0


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def split_recommendations(text: str) -> list[str]:
    """Split numbered recommendations ('1. ...') while keeping each verbatim."""
    flat = norm(text)
    parts = re.split(r"(?:(?<=\s)|^)(?=\d{1,2}\.\s+[A-Z])", flat)
    items = [p.strip() for p in parts if re.match(r"^\d{1,2}\.\s", p.strip())]
    return items


def parse_report(url: str, page_texts: list[str]) -> Report:
    lines: list[tuple[int, str]] = []
    for pno, txt in enumerate(page_texts, start=1):
        for ln in txt.splitlines():
            if ln.strip():
                lines.append((pno, ln.strip()))

    header: dict = {}
    for _, ln in lines[:60]:
        m = HEADER_FIELD_RE.match(ln)
        if m and m.group(1).lower() not in header:
            header[m.group(1).lower()] = norm(m.group(2))

    title = None
    for i, (_, ln) in enumerate(lines[:40]):
        if re.search(r"REPORT FOR ACTION|REPORT FOR INFORMATION|MOTION", ln, re.I) and i + 1 < len(lines):
            title = norm(" ".join(l for _, l in lines[i + 1:i + 3]))
            break

    # carve sections
    sections: list[tuple[str, int, list[str]]] = []
    cur = None
    for pno, ln in lines:
        m = HEAD_RE.match(ln)
        if m:
            cur = (m.group(1).upper(), pno, [])
            sections.append(cur)
        elif cur is not None:
            cur[2].append(ln)

    rep = Report(url=url, title=title, header=header, pages=len(page_texts))
    label_map = {"SUMMARY": "Summary", "RECOMMENDATIONS": "Recommendations", "RECOMMENDATION": "Recommendations",
                 "FINANCIAL IMPACT": "Financial impact", "DECISION HISTORY": "Decision history"}
    seen = set()
    for name, pno, content in sections:
        label = label_map.get(name)
        if not label or label in seen:
            continue
        seen.add(label)
        text = norm(" ".join(content))
        if not text:
            continue
        rep.facts.append(Fact(label, text, pno))
        if label == "Recommendations":
            rep.recommendations = split_recommendations(text)
    return rep


def report_to_dict(rep: Report) -> dict:
    return asdict(rep)
