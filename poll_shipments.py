"""CLI entrypoint: run one polling pass over the tracked_shipments table.

Usage:
    python poll_shipments.py
    python poll_shipments.py --force-id SHP-000001 --force-id SHP-000002
"""

import argparse
import logging
import os
import sys

import psycopg
from dotenv import load_dotenv

from poller.pipeline import run

logger = logging.getLogger("poll_shipments")

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/warehouse"
DEFAULT_CARRIER_API_URL = "http://localhost:8300"


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force-id",
        action="append",
        default=None,
        help="shipment_id to force a re-poll of, bypassing terminal/staleness skip rules (repeatable)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    force_ids = list(args.force_id or [])
    env_force = os.environ.get("FORCE_REPOLL_IDS", "")
    if env_force.strip():
        force_ids.extend(x.strip() for x in env_force.split(",") if x.strip())

    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    carrier_api_url = os.environ.get("CARRIER_API_URL", DEFAULT_CARRIER_API_URL)

    conn = psycopg.connect(database_url)
    try:
        result = run(conn, carrier_api_url, force_ids=force_ids)
    finally:
        conn.close()

    logger.info(
        "polled %d, updated %d (%d newly terminal), skipped %d, failed %d",
        result.polled,
        result.updated,
        result.newly_terminal,
        result.skipped,
        result.failed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
