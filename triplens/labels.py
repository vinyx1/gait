"""Fixed plain-language labels for official item statuses. Not AI-generated."""
from __future__ import annotations

# Deterministic plain-language labels for official statuses. Not AI-generated.
PLAIN_STATUS = {
    "Adopted": ("Approved", "The body voted to approve it as written."),
    "Adopted on Consent": ("Approved without debate",
                           "It was approved together with other items without a separate discussion."),
    "Amended": ("Approved with changes", "The body changed the recommendations, then approved them."),
    "Referred": ("Sent for more work, no decision yet",
                 "The body did not decide on the request. It asked staff or another body to look into it."),
    "Deferred": ("Postponed", "The decision was put off to a later meeting."),
    "Received": ("Received for information", "The body noted the item. It did not approve an action."),
}
UPCOMING = ("Coming up, not decided yet",
            "A meeting is scheduled. What you see below is a recommendation, not a decision.")




def latest_stage(item: dict) -> dict:
    return item["stages"][-1]


def plain(item_or_status, upcoming: bool = False) -> tuple[str, str]:
    if upcoming:
        return UPCOMING
    status = item_or_status
    if status in PLAIN_STATUS:
        return PLAIN_STATUS[status]
    return (status or "Status not shown", "See the official wording below.")


def item_plain(item: dict) -> tuple[str, str]:
    return plain(latest_stage(item)["status"], item.get("upcoming", False))


