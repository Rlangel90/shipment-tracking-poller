"""Orchestrates one polling run: skip terminal/stale shipments (unless
forced), poll everything else, and keep going even if a single tracking
lookup fails.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from poller import carrier_client, db
from poller.policy import is_terminal, should_poll


@dataclass
class PollResult:
    polled: int
    updated: int
    newly_terminal: int
    skipped: int
    failed: int


def run(conn, carrier_api_url: str, now: datetime | None = None, force_ids: list[str] | None = None) -> PollResult:
    now = now or datetime.now(timezone.utc)
    force_ids = set(force_ids or [])

    polled = updated = newly_terminal = skipped = failed = 0

    for shipment in db.fetch_all_shipments(conn):
        force = shipment["shipment_id"] in force_ids
        if not should_poll(shipment, now, force=force):
            skipped += 1
            continue

        try:
            tracking = carrier_client.fetch_tracking(carrier_api_url, shipment["tracking_number"])
        except carrier_client.TrackingUnavailableError:
            failed += 1
            continue

        polled += 1
        was_terminal = is_terminal(shipment["status"])
        new_status = tracking["status"]
        changed = db.update_shipment_status(conn, shipment["shipment_id"], new_status, now)

        if changed:
            updated += 1
            if not was_terminal and is_terminal(new_status):
                newly_terminal += 1

    return PollResult(
        polled=polled,
        updated=updated,
        newly_terminal=newly_terminal,
        skipped=skipped,
        failed=failed,
    )
