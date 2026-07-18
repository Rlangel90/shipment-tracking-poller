from datetime import datetime, timedelta, timezone

import pytest

from poller import carrier_client, db, pipeline
from poller.policy import STALE_AFTER_DAYS

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def _shipment(shipment_id, status="in_transit", tracking_number=None, last_status_change_at=None):
    return {
        "shipment_id": shipment_id,
        "carrier": "UPS",
        "tracking_number": tracking_number or f"TRK-{shipment_id}",
        "status": status,
        "poll_count": 0,
        "last_polled_at": None,
        "last_status_change_at": last_status_change_at or (NOW - timedelta(days=1)),
        "created_at": NOW - timedelta(days=10),
    }


@pytest.fixture
def fake_shipments(monkeypatch):
    def _set(shipments):
        monkeypatch.setattr(db, "fetch_all_shipments", lambda conn: shipments)

    return _set


@pytest.fixture
def captured_updates(monkeypatch):
    calls = []

    def fake_update(conn, shipment_id, new_status, now):
        calls.append((shipment_id, new_status))
        return True  # pretend every update actually changed the status

    monkeypatch.setattr(db, "update_shipment_status", fake_update)
    return calls


def test_run_skips_terminal_shipments_without_calling_the_carrier(
    fake_shipments, captured_updates, monkeypatch
):
    fake_shipments([_shipment("SHP-000001", status="delivered")])
    monkeypatch.setattr(
        carrier_client, "fetch_tracking", lambda base_url, tn: pytest.fail("should not be called")
    )

    result = pipeline.run("fake-conn", "http://carrier.test", now=NOW)

    assert result.skipped == 1
    assert result.polled == 0
    assert captured_updates == []


def test_run_skips_stale_shipments_without_calling_the_carrier(
    fake_shipments, captured_updates, monkeypatch
):
    stale_change = NOW - timedelta(days=STALE_AFTER_DAYS + 5)
    fake_shipments([_shipment("SHP-000001", last_status_change_at=stale_change)])
    monkeypatch.setattr(
        carrier_client, "fetch_tracking", lambda base_url, tn: pytest.fail("should not be called")
    )

    result = pipeline.run("fake-conn", "http://carrier.test", now=NOW)

    assert result.skipped == 1
    assert result.polled == 0


def test_run_polls_fresh_non_terminal_shipments_and_updates_status(
    fake_shipments, captured_updates, monkeypatch
):
    fake_shipments([_shipment("SHP-000001", status="in_transit")])
    monkeypatch.setattr(
        carrier_client,
        "fetch_tracking",
        lambda base_url, tn: {"status": "out_for_delivery", "last_event_at": "2026-07-18T09:00:00Z"},
    )

    result = pipeline.run("fake-conn", "http://carrier.test", now=NOW)

    assert result.polled == 1
    assert result.updated == 1
    assert captured_updates == [("SHP-000001", "out_for_delivery")]


def test_run_counts_newly_terminal_transitions(fake_shipments, captured_updates, monkeypatch):
    fake_shipments([_shipment("SHP-000001", status="out_for_delivery")])
    monkeypatch.setattr(
        carrier_client,
        "fetch_tracking",
        lambda base_url, tn: {"status": "delivered", "last_event_at": "2026-07-18T09:00:00Z"},
    )

    result = pipeline.run("fake-conn", "http://carrier.test", now=NOW)

    assert result.newly_terminal == 1


def test_run_force_ids_bypasses_terminal_skip(fake_shipments, captured_updates, monkeypatch):
    fake_shipments([_shipment("SHP-000001", status="delivered")])
    monkeypatch.setattr(
        carrier_client,
        "fetch_tracking",
        lambda base_url, tn: {"status": "delivered", "last_event_at": "2026-07-18T09:00:00Z"},
    )

    result = pipeline.run(
        "fake-conn", "http://carrier.test", now=NOW, force_ids=["SHP-000001"]
    )

    assert result.polled == 1
    assert result.skipped == 0


def test_run_continues_past_a_single_tracking_lookup_failure(
    fake_shipments, captured_updates, monkeypatch
):
    fake_shipments(
        [
            _shipment("SHP-000001", tracking_number="BROKEN"),
            _shipment("SHP-000002", tracking_number="OK"),
        ]
    )

    def fake_fetch(base_url, tracking_number):
        if tracking_number == "BROKEN":
            raise carrier_client.TrackingUnavailableError("boom")
        return {"status": "delivered", "last_event_at": "2026-07-18T09:00:00Z"}

    monkeypatch.setattr(carrier_client, "fetch_tracking", fake_fetch)

    result = pipeline.run("fake-conn", "http://carrier.test", now=NOW)

    assert result.failed == 1
    assert result.polled == 1
    assert captured_updates == [("SHP-000002", "delivered")]
