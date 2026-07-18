import os

import psycopg
import pytest


@pytest.fixture
def pg_conn():
    """A live Postgres connection with a fresh tracked_shipments table.

    Skips (rather than fails) when no reachable Postgres is configured, so
    the suite still runs on a machine without Docker/Postgres available; CI
    wires a real Postgres service container so this fixture runs for real
    there.
    """
    database_url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    try:
        conn = psycopg.connect(database_url, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("no reachable Postgres instance for TEST_DATABASE_URL")

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS tracked_shipments")
        cur.execute(
            """
            CREATE TABLE tracked_shipments (
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
        )
    conn.commit()

    yield conn

    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS tracked_shipments")
    conn.commit()
    conn.close()
