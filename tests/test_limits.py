"""Abuse limits for a public deployment: per-visitor rates, body size, daily AI budget."""
from fastapi.testclient import TestClient

from gait import limits
from gait.app import app


def test_heavy_paths_have_tighter_limits_than_pages():
    assert limits.rule_for("/api/research_trip")[1] < limits.rule_for("/api/trip")[1] < limits.rule_for("/")[1]


def test_visitor_is_blocked_after_the_limit_then_allowed_again():
    _, limit, window = limits.rule_for("/api/trip")
    for i in range(limit):
        assert limits.allow("1.2.3.4", "/api/trip", now=100.0 + i * 0.01)[0]
    ok, wait = limits.allow("1.2.3.4", "/api/trip", now=101.0)
    assert not ok and wait > 0
    assert limits.allow("5.6.7.8", "/api/trip", now=101.0)[0]          # other visitors are not affected
    assert limits.allow("1.2.3.4", "/api/trip", now=100.0 + window + 1)[0]


def test_forwarded_address_is_used_behind_a_proxy():
    assert limits.client_ip({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "10.0.0.1") == "9.9.9.9"
    assert limits.client_ip({}, "10.0.0.1") == "10.0.0.1"


def test_app_answers_429_with_a_plain_message():
    c = TestClient(app)
    _, limit, _ = limits.rule_for("/api/research_trip")
    codes = [c.post("/api/research_trip", json={}).status_code for _ in range(limit + 1)]
    assert codes[:limit] == [400] * limit and codes[-1] == 429
    r = c.post("/api/research_trip", json={})
    assert "Too many requests" in r.json()["error"] and r.headers["retry-after"]


def test_oversized_body_is_refused():
    c = TestClient(app)
    assert c.post("/api/trip", content=b"x" * (limits.MAX_BODY + 1), headers={"content-type": "application/json"}).status_code == 413


def test_daily_ai_budget():
    for _ in range(limits.AI_PER_DAY):
        assert limits.take_ai_call()
    assert not limits.take_ai_call()
