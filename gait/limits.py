"""Simple abuse limits for a public deployment, kept in memory (they reset when the server restarts).

1. Per-visitor rate limits: each IP address gets a fixed number of requests per window for each kind of path.
   Heavy paths (trip calculations) get fewer than cheap ones (pages, static files).
2. Request size cap: request bodies over MAX_BODY bytes are refused (every real request is a few hundred bytes).
3. Daily AI budget: at most AI_PER_DAY new (uncached) Claude calls per day across all visitors, so the paid
   "live research" button cannot run up a bill. Cached answers are free and not counted.

Nothing about a visitor is stored beyond the timestamps of their recent requests, held in memory only.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from datetime import date

MAX_BODY = 64 * 1024                                  # bytes
AI_PER_DAY = int(os.environ.get("GAIT_AI_PER_DAY", "25"))

# (path prefix, max requests, window in seconds). The first matching prefix wins; the last entry is the default.
RULES = [
    ("/api/research_trip", 3, 3600),                  # paid AI: 3 per visitor per hour
    ("/api/trip", 20, 60),                            # trip calculations on the sidewalk network
    ("/route/", 20, 60),                              # form version of the same calculation
    ("/api/", 120, 60),                               # small lookups for the map
    ("/static/", 600, 60),                            # fonts, images, styles
    ("/", 120, 60),                                   # pages
]

_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_ai = {"day": date.today(), "used": 0}


def rule_for(path: str) -> tuple[str, int, int]:
    return next(r for r in RULES if path.startswith(r[0]))


def client_ip(headers, fallback: str) -> str:
    """Behind Railway's proxy the visitor's address is the first entry of X-Forwarded-For."""
    fwd = headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or fallback


def allow(ip: str, path: str, now: float | None = None) -> tuple[bool, int]:
    """Record one request; return (allowed, seconds to wait if not)."""
    now = time.monotonic() if now is None else now
    prefix, limit, window = rule_for(path)
    q = _hits[(ip, prefix)]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= limit:
        return False, int(q[0] + window - now) + 1
    q.append(now)
    if len(_hits) > 50_000:                           # keep memory bounded: drop visitors with no recent requests
        for k in [k for k, v in _hits.items() if not v or v[-1] <= now - 3600]:
            del _hits[k]
    return True, 0


def take_ai_call() -> bool:
    """Use one of today's AI calls. False when today's budget is spent."""
    if _ai["day"] != date.today():
        _ai.update(day=date.today(), used=0)
    if _ai["used"] >= AI_PER_DAY:
        return False
    _ai["used"] += 1
    return True


def reset() -> None:
    """For tests."""
    _hits.clear()
    _ai.update(day=date.today(), used=0)
