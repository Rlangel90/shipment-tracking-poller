"""Reads and writes the tracked_shipments table."""

import psycopg
from psycopg.rows import dict_row


def fetch_all_shipments(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM tracked_shipments")
        return cur.fetchall()


def update_shipment_status(conn: psycopg.Connection, shipment_id: str, new_status: str, now) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT status FROM tracked_shipments WHERE shipment_id = %s", (shipment_id,)
        )
        current = cur.fetchone()
        changed = current["status"] != new_status

        if changed:
            cur.execute(
                """
                UPDATE tracked_shipments
                SET status = %s, last_status_change_at = %s, last_polled_at = %s,
                    poll_count = poll_count + 1
                WHERE shipment_id = %s
                """,
                (new_status, now, now, shipment_id),
            )
        else:
            cur.execute(
                """
                UPDATE tracked_shipments
                SET last_polled_at = %s, poll_count = poll_count + 1
                WHERE shipment_id = %s
                """,
                (now, shipment_id),
            )

    conn.commit()
    return changed
