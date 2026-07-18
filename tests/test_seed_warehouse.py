from datetime import datetime, timezone

from scripts.seed_warehouse import generate, seed

REFERENCE_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def test_generate_is_deterministic_for_a_given_seed():
    rows_a, tracking_a = generate(seed=42, count=20, reference_now=REFERENCE_NOW)
    rows_b, tracking_b = generate(seed=42, count=20, reference_now=REFERENCE_NOW)

    assert rows_a == rows_b
    assert tracking_a == tracking_b


def test_generate_produces_requested_count():
    rows, _ = generate(seed=1, count=15, reference_now=REFERENCE_NOW)

    assert len(rows) == 15


def test_generate_shipment_ids_are_unique():
    rows, _ = generate(seed=7, count=50, reference_now=REFERENCE_NOW)

    ids = [r["shipment_id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_generate_every_row_has_a_matching_tracking_fixture_entry():
    rows, tracking = generate(seed=7, count=30, reference_now=REFERENCE_NOW)

    for row in rows:
        assert row["tracking_number"] in tracking


def test_generate_produces_a_mix_of_terminal_and_non_terminal_rows():
    rows, _ = generate(seed=7, count=60, reference_now=REFERENCE_NOW)

    statuses = {r["status"] for r in rows}
    assert "delivered" in statuses or "cancelled" in statuses or "returned_to_sender" in statuses
    assert any(r["status"] not in ("delivered", "cancelled", "returned_to_sender") for r in rows)


def test_different_seeds_produce_different_data():
    rows_a, _ = generate(seed=1, count=20, reference_now=REFERENCE_NOW)
    rows_b, _ = generate(seed=2, count=20, reference_now=REFERENCE_NOW)

    assert rows_a != rows_b


def test_seed_inserts_all_rows_into_the_tracked_shipments_table(pg_conn):
    rows, _ = generate(seed=7, count=10, reference_now=REFERENCE_NOW)

    inserted = seed(pg_conn, rows)

    assert inserted == len(rows)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tracked_shipments")
        assert cur.fetchone()[0] == len(rows)
