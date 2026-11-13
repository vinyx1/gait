"""Download the staff reports linked from collected council items and build a free full-text index (SQLite FTS5).

Inputs: data/corpus/items_*.json (item pages saved through a browser). Output: data/corpus/index.sqlite
Skips files over 10 MB. No AI is used. Run: python scripts/build_corpus.py
"""
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "data/corpus/pdf"
DB = ROOT / "data/corpus/index.sqlite"
MAX_BYTES = 10_000_000


def items():
    out = {}
    for p in sorted((ROOT / "data/corpus").glob("items_*.json")):
        out.update(json.loads(p.read_text())["items"])
    return out


def fetch(url):
    name = url.rsplit("/", 1)[-1]
    dest = PDF / name
    if not dest.exists():
        subprocess.run(["curl", "-sL", "-m", "120", "--max-filesize", str(MAX_BYTES), "-o", str(dest), url], check=False)
    return url, dest


def main():
    PDF.mkdir(parents=True, exist_ok=True)
    its = items()
    doc_item = {}
    for iid, it in its.items():
        for l in it.get("links", []):
            doc_item.setdefault(l["href"], iid)
    with ThreadPoolExecutor(max_workers=8) as ex:
        files = list(ex.map(fetch, doc_item))
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("CREATE VIRTUAL TABLE pages USING fts5(text, url UNINDEXED, item UNINDEXED, page UNINDEXED, tokenize='porter')")
    con.execute("CREATE TABLE items (item TEXT PRIMARY KEY, title TEXT, status TEXT)")
    for iid, it in its.items():
        lines = it.get("text", "").splitlines()
        title = next((l for l in lines if " - " in l and l.split(" - ")[0].replace(".", "").isalnum()), lines[3] if len(lines) > 3 else "")
        con.execute("INSERT OR REPLACE INTO items VALUES (?,?,?)", (iid, title.strip(), " ".join(lines[1:3])))
    n_docs = n_pages = 0
    for url, dest in files:
        if not dest.exists() or dest.stat().st_size < 1000:
            continue
        try:
            pages = [(p.extract_text() or "") for p in PdfReader(str(dest)).pages]
        except Exception:
            continue
        n_docs += 1
        for i, t in enumerate(pages, 1):
            if t.strip():
                con.execute("INSERT INTO pages VALUES (?,?,?,?)", (" ".join(t.split()), url, doc_item[url], i)); n_pages += 1
    con.commit(); con.close()
    print(f"indexed {n_docs} documents, {n_pages} pages from {len(its)} items", file=sys.stderr)


if __name__ == "__main__":
    main()
