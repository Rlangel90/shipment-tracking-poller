"""Seed a synthetic tracked-shipments scenario: some shipments already
terminal, some fresh non-terminal ones with a plausible next status waiting
in the mock carrier API, and some non-terminal ones stale enough that the
poller should correctly skip them. Deterministic for a given --seed.

The generated tracked_shipments rows and the mock_carrier tracking fixture
are produced together so every tracking_number in the DB has a matching
entry the mock API can serve.

Usage:
    python scripts/seed_warehouse.py --seed 42 --count 60
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

CARRIERS = ["UPS", "FedEx", "USPS", "DHL"]
STATUS_PROGRESSION = ["label_created", "in_transit", "out_for_delivery", "delivered"]
TERMINAL_STATUSES = ["delivered", "returned_to_sender", "cancelled"]
STALE_NON_TERMINAL_STATUSES = ["label_created", "in_transit", "exception_open"]

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/warehouse"
DEFAULT_TRACKING_PATH = Path(__file__).parent.parent / "mock_carrier" / "fixtures" / "tracking.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_shipments (
    shipment_id TEXT PRIMARY KEY,
    carrier TEXT NOT NULL,
    tracking_number TEXT NOT NULL,
    status TEXT NOT NULL,
    poll_count INTEGER NOT NULL DEFAULT 0,
    last_polled_at TIMESTAMPTZ,
    last_status_change_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
)
"""


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def generate(seed: int, count: int, reference_now: datetime) -> tuple[list[dict], dict[str, dict]]:
    rng = random.Random(seed)
    rows = []
    tracking = {}

    for i in range(1, count + 1):
        shipment_id = f"SHP-{i:06d}"
        tracking_number = f"TRK-{i:08d}"
        carrier = rng.choice(CARRIERS)
        bucket = rng.choices(["terminal", "fresh", "stale"], weights=[0.4, 0.4, 0.2], k=1)[0]

        if bucket == "terminal":
            status = rng.choice(TERMINAL_STATUSES)
            last_change = reference_now - timedelta(days=rng.randint(1, 10))
            tracking_status = status
            description = "final status"
        elif bucket == "fresh":
            status = rng.choice(STATUS_PROGRESSION[:-1])
            last_change = reference_now - timedelta(hours=rng.randint(1, 48))
            idx = STATUS_PROGRESSION.index(status)
            advances = rng.random() < 0.7 and idx < len(STATUS_PROGRESSION) - 1
            tracking_status = STATUS_PROGRESSION[idx + 1] if advances else status
            description = "latest scan"
        else:  # stale
            status = rng.choice(STALE_NON_TERMINAL_STATUSES)
            last_change = reference_now - timedelta(days=rng.randint(20, 60))
            tracking_status = status
            description = "no recent movement"

        tracking[tracking_number] = {
            "status": tracking_status,
            "last_event_at": _iso(reference_now),
            "description": description,
        }

        rows.append(
            {
                "shipment_id": shipment_id,
                "carrier": carrier,
                "tracking_number": tracking_number,
                "status": status,
                "poll_count": rng.randint(0, 5),
                "last_polled_at": last_change,
                "last_status_change_at": last_change,
                "created_at": last_change - timedelta(days=rng.randint(1, 5)),
            }
        )

    return rows, tracking


def seed(conn: psycopg.Connection, rows: list[dict]) -> int:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
        for row in rows:
            cur.execute(
                """
                INSERT INTO tracked_shipments (
                    shipment_id, carrier, tracking_number, status, poll_count,
                    last_polled_at, last_status_change_at, created_at
                ) VALUES (%(shipment_id)s, %(carrier)s, %(tracking_number)s, %(status)s,
                    %(poll_count)s, %(last_polled_at)s, %(last_status_change_at)s, %(created_at)s)
                ON CONFLICT (shipment_id) DO NOTHING
                """,
                row,
            )
    conn.commit()
    return len(rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--tracking-out", type=Path, default=DEFAULT_TRACKING_PATH)
    args = parser.parse_args(argv)

    database_url = args.database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    rows, tracking = generate(args.seed, args.count, reference_now=datetime.now(timezone.utc))

    conn = psycopg.connect(database_url)
    try:
        inserted = seed(conn, rows)
    finally:
        conn.close()

    args.tracking_out.parent.mkdir(parents=True, exist_ok=True)
    args.tracking_out.write_text(json.dumps(tracking, indent=2) + "\n")

    print(f"seeded {inserted} shipments into {database_url}")
    print(f"wrote tracking fixture to {args.tracking_out}")


if __name__ == "__main__":
    main()
