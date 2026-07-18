from datetime import datetime, timezone

from poller.db import fetch_all_shipments, update_shipment_status

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
CREATED = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)


def _insert(conn, shipment_id, status="in_transit", poll_count=0, last_polled_at=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tracked_shipments (
                shipment_id, carrier, tracking_number, status, poll_count,
                last_polled_at, last_status_change_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (shipment_id, "UPS", f"TRK-{shipment_id}", status, poll_count, last_polled_at, CREATED, CREATED),
        )
    conn.commit()


def test_fetch_all_shipments_returns_every_row(pg_conn):
    _insert(pg_conn, "SHP-000001")
    _insert(pg_conn, "SHP-000002", status="delivered")

    shipments = fetch_all_shipments(pg_conn)

    assert {s["shipment_id"] for s in shipments} == {"SHP-000001", "SHP-000002"}


def test_update_shipment_status_returns_true_when_status_changed(pg_conn):
    _insert(pg_conn, "SHP-000001", status="in_transit")

    changed = update_shipment_status(pg_conn, "SHP-000001", "out_for_delivery", NOW)

    assert changed is True
    row = fetch_all_shipments(pg_conn)[0]
    assert row["status"] == "out_for_delivery"
    assert row["last_status_change_at"] == NOW
    assert row["last_polled_at"] == NOW
    assert row["poll_count"] == 1


def test_update_shipment_status_returns_false_when_status_unchanged(pg_conn):
    _insert(pg_conn, "SHP-000001", status="in_transit", poll_count=2)

    changed = update_shipment_status(pg_conn, "SHP-000001", "in_transit", NOW)

    assert changed is False
    row = fetch_all_shipments(pg_conn)[0]
    assert row["status"] == "in_transit"
    assert row["last_polled_at"] == NOW
    assert row["poll_count"] == 3


def test_update_shipment_status_increments_poll_count_each_call(pg_conn):
    _insert(pg_conn, "SHP-000001")

    update_shipment_status(pg_conn, "SHP-000001", "in_transit", NOW)
    update_shipment_status(pg_conn, "SHP-000001", "out_for_delivery", NOW)

    row = fetch_all_shipments(pg_conn)[0]
    assert row["poll_count"] == 2
