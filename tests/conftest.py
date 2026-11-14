import pytest


@pytest.fixture(autouse=True)
def _fresh_limits():
    """Each test starts with empty rate-limit counters and a full daily AI budget."""
    from gait import limits
    limits.reset()
    yield
    limits.reset()
