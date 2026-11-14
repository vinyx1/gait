"""Download background reports linked from parsed items, extract verbatim sections, verify quotes.

Usage: python scripts/build_reports.py
PDFs are cached in data/reports/*.pdf (gitignored). Extracted JSON is written next to them.
"""
import json
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gait.parse_report import parse_report, report_to_dict  # noqa: E402
from gait.verify import quote_in_source  # noqa: E402

OUT = ROOT / "data/reports"
MAX_BYTES = 12_000_000
MAX_PAGES = 80


def fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    r = subprocess.run(["curl", "-sL", "-m", "120", "-o", str(dest), "-w", "%{http_code}", url],
                       capture_output=True, text=True)
    ok = r.stdout.strip() == "200" and dest.exists() and dest.stat().st_size > 1000
    if not ok and dest.exists():
        dest.unlink()
    return ok


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    urls: dict[str, str] = {}
    for p in sorted((ROOT / "data/items").glob("*.json")):
        item = json.loads(p.read_text())
        for st in item["stages"]:
            for b in st["background"]:
                if "/bgrd/" in b["url"]:
                    urls[b["url"]] = b["url"].rsplit("/", 1)[-1].replace(".pdf", "")
    index = {}
    for url, name in urls.items():
        pdf = OUT / f"{name}.pdf"
        if not fetch(url, pdf):
            print("FAILED fetch", url); continue
        if pdf.stat().st_size > MAX_BYTES:
            print("skip (too large)", name, pdf.stat().st_size); continue
        try:
            reader = PdfReader(str(pdf))
        except Exception as e:  # corrupt pdf
            print("skip (unreadable)", name, e); continue
        if len(reader.pages) > MAX_PAGES:
            print("skip (too many pages)", name, len(reader.pages)); continue
        pages = [(pg.extract_text() or "") for pg in reader.pages]
        rep = parse_report(url, pages)
        kept = []
        for f in rep.facts:
            where = quote_in_source(f.quote, pages)
            if where is None:
                print("  DROPPED unverifiable fact:", name, f.label)
                continue
            kept.append(f)
        rep.facts = kept
        (OUT / f"{name}.json").write_text(json.dumps(report_to_dict(rep), indent=2, ensure_ascii=False))
        (OUT / f"{name}.pages.json").write_text(json.dumps(pages, ensure_ascii=False))
        index[url] = name
        print(f"{name}: {len(pages)} pages, facts={[f.label for f in rep.facts]}, recs={len(rep.recommendations)}")
    (OUT / "index.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
