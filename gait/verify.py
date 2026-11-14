"""Check that every displayed quote really appears in the source text."""
from __future__ import annotations

import re


def _n(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def quote_in_source(quote: str, source_pages: list[str]) -> int | None:
    """Return the 1-based page number where the quote appears (whitespace-insensitive), else None."""
    q = _n(quote)
    if not q:
        return None
    for i, page in enumerate(source_pages, start=1):
        if q in _n(page):
            return i
    # a quote may legitimately span a page break
    joined = _n(" ".join(source_pages))
    return 0 if q in joined else None
