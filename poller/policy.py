"""The polling policy: which shipments are worth spending an API call on
right now. A shipment is only polled if it's neither reached a terminal
state nor gone stale - unless an operator explicitly forces it.
"""

from datetime import datetime, timedelta

TERMINAL_STATUSES = {"delivered", "returned_to_sender", "cancelled"}
STALE_AFTER_DAYS = 14


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def is_stale(last_status_change_at: datetime, now: datetime, stale_after_days: int = STALE_AFTER_DAYS) -> bool:
    return (now - last_status_change_at) > timedelta(days=stale_after_days)


def should_poll(shipment: dict, now: datetime, force: bool = False) -> bool:
    if force:
        return True
    if is_terminal(shipment["status"]):
        return False
    if is_stale(shipment["last_status_change_at"], now):
        return False
    return True
