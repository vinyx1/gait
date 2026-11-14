"""Fill the organizers' one-page Municipal Readiness Report template (Word) and write a matching markdown copy.

Usage:
  python scripts/fill_readiness_report.py --name "Fine Print" --team "Team name" --email you@uwaterloo.ca \
      --member "Your Name|University of Waterloo|Your program" [--member "..."]

Output: docs/readiness-report.docx (open in Word, check it is one page, Save as PDF) and docs/readiness-report-draft.md.
The template is downloaded from the CIVIC Hack page on first use (docs/_template.docx, not committed).
Word limits come from the template. The script refuses to write if a box is over its limit.
"""
import argparse
import re
import urllib.request
import zipfile
from pathlib import Path
from xml.dom import minidom
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs/_template.docx"
URL = "https://fciprojects.ca/hackathons/2026-civic-hack/images/CIVIC-Hack_submission-template.docx"

BOXES = {  # tag -> (limit in words or None, text; {name} is replaced by the project name)
    "problem": (60, "Residents learn what a council decision means for them only after it happens: a stop disappears, a shelter goes, the walk gets longer. "
                    "Reports run hundreds of pages and describe an average rider. We focused on how one decision lands differently on wheelchair users, "
                    "seniors using walkers and shift workers, and on separating what staff recommended from what Council decided."),
    "solution": (60, "{name} shows what Toronto council decisions did, or would do, to a resident's own trip. They pick a start, destination, route, stops and rider. "
                     "{name} compares the walk and stops before and after each decision, shows the City's exact quotes with page numbers, adds 311 reports, "
                     "and helps them write to their councillor, 311 or the TTC."),
    "what_changes": (30, "Today residents dig through PDFs written for an average rider. {name} turns a decision into before-and-after facts for their own trip "
                         "and needs, each checked against the source."),
    "piloted": (40, "Ready: before-and-after for five real Council decisions, walks on the City sidewalk network, quote checking, 311 reports, plain-language "
                    "item pages. Mocked: five labelled simulated changes; live item loading needs a Clerk feed. Next: accessibility-group testing, translation."),
    "scaling": (None, "Each city needs an agenda feed from its clerk, a GTFS transit feed (a national standard), open address and sidewalk data, and its own "
                      "participation rules, since notice rules differ by province. Change effects are entered from reports with exact quotes. Replace the "
                      "illustrative rider limits with advice from local accessibility groups. Pilot with one clerk's office first."),
}

# Data sources and tools: the template provides a Dataset / Source table with four rows and a 60-word limit.
TABLE = [
    ("TTC schedules (GTFS); shelters; benches; 311 requests", "City of Toronto Open Data"),
    ("Pedestrian network; address points; road and sidewalk works", "City of Toronto Open Data"),
    ("Council items, staff reports", "City Clerk meeting system, legdocs (public)"),
    ("Claude (Opus 5.5) rewrites and agents; Claude Code helped code. Rider walking limits are illustrative", "Anthropic; outputs checked against quotes"),
]
TABLE_LIMIT = 60


def words(s: str) -> int:
    return len(s.split())


def run(text: str, size: int = 18) -> str:
    return (f'<w:r><w:rPr><w:color w:val="000000"/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')


def fill_sdt(xml: str, tag: str, text: str) -> str:
    def repl(m):
        blk = m.group(0)
        if f'<w:tag w:val="{tag}"/>' not in blk:
            return blk
        blk = blk.replace("<w:showingPlcHdr/>", "")
        return re.sub(r"<w:sdtContent>.*?</w:sdtContent>", lambda _: f"<w:sdtContent>{run(text)}</w:sdtContent>", blk, flags=re.S)
    return re.sub(r"<w:sdt>.*?</w:sdt>", repl, xml, flags=re.S)


def fill_table(xml: str, rows: list[tuple[str, str]]) -> str:
    """Fill the nested Dataset / Source table. The template nests it inside a layout table, so find the innermost one."""
    idx = xml.find(">Dataset<")
    if idx < 0:
        raise SystemExit("could not find the Dataset table in the template")
    start, end = xml.rfind("<w:tbl>", 0, idx), xml.find("</w:tbl>", idx) + len("</w:tbl>")
    t = xml[start:end]
    trs = re.findall(r"<w:tr[ >].*?</w:tr>", t, flags=re.S)
    new = t
    for tr, (a, b) in zip(trs[1:], rows):
        cells = re.findall(r"<w:tc>.*?</w:tc>", tr, flags=re.S)
        tr_new = tr
        for cell, text in zip(cells, (a, b)):
            cell_new, n = re.subn(r"(<w:p [^>]*>(?:<w:pPr>.*?</w:pPr>)?)(</w:p>)", lambda mm: mm.group(1) + run(text) + mm.group(2), cell, count=1, flags=re.S)
            if n != 1:
                raise SystemExit("unexpected table cell layout; fill the table by hand")
            tr_new = tr_new.replace(cell, cell_new, 1)
        new = new.replace(tr, tr_new, 1)
    return xml[:start] + new + xml[end:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Gait")
    ap.add_argument("--team", default="")
    ap.add_argument("--email", default="")
    ap.add_argument("--member", action="append", default=[], help="Name|School|Program")
    a = ap.parse_args()

    texts = {k: (lim, txt.replace("{name}", a.name)) for k, (lim, txt) in BOXES.items()}
    problems = [f"{k}: {words(t)} words, limit {lim}" for k, (lim, t) in texts.items() if lim and words(t) > lim]
    tw = sum(words(x) for r in TABLE for x in r)
    if tw > TABLE_LIMIT:
        problems.append(f"data table: {tw} words, limit {TABLE_LIMIT}")
    if problems:
        raise SystemExit("Over the word limit:\n  " + "\n  ".join(problems))

    if not TEMPLATE.exists():
        urllib.request.urlretrieve(URL, TEMPLATE)
    zin = zipfile.ZipFile(TEMPLATE)
    xml = zin.read("word/document.xml").decode("utf8")
    xml = fill_sdt(xml, "project_name", a.name)
    for tag, val in (("team_name", a.team), ("contact_email", a.email)):
        if val:
            xml = fill_sdt(xml, tag, val)
    for i, mem in enumerate(a.member[:4], start=1):
        for tag, val in zip((f"m{i}_name", f"m{i}_school", f"m{i}_program"), (mem.split("|") + ["", ""])[:3]):
            if val:
                xml = fill_sdt(xml, tag, val)
    for tag, (_, txt) in texts.items():
        xml = fill_sdt(xml, tag, txt)
    xml = fill_table(xml, TABLE)
    minidom.parseString(xml.encode("utf8"))  # well-formedness check

    out = ROOT / "docs/readiness-report.docx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = xml.encode("utf8") if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)

    md = [f"# Municipal Readiness Report: {a.name}", "", "Generated by `scripts/fill_readiness_report.py` from the organizers' template. "
          "Open `readiness-report.docx` in Word, check it fits one page, then Save as PDF and add it to Devpost and the repo.", ""]
    titles = {"problem": "The problem", "solution": "Your solution", "what_changes": "What changes",
              "piloted": "What could be piloted today", "scaling": "Adopting or scaling it"}
    for k in ("problem", "solution", "what_changes"):
        lim, t = texts[k]
        md += [f"## {titles[k]}", f"*{words(t)} of {lim} words*", "", t, ""]
    md += ["## Data sources and tools", f"*{tw} of {TABLE_LIMIT} words*", "", "| Dataset | Source |", "|---|---|"]
    md += [f"| {x} | {y} |" for x, y in TABLE] + [""]
    for k in ("piloted", "scaling"):
        lim, t = texts[k]
        md += [f"## {titles[k]}", f"*{words(t)}{' of ' + str(lim) if lim else ''} words*", "", t, ""]
    (ROOT / "docs/readiness-report-draft.md").write_text("\n".join(md))
    print("wrote docs/readiness-report.docx and docs/readiness-report-draft.md")
    for k, (lim, t) in texts.items():
        print(f"  {k}: {words(t)} / {lim}")
    print(f"  data table: {tw} / {TABLE_LIMIT}")


if __name__ == "__main__":
    main()
