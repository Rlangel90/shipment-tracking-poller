from datetime import datetime, timedelta, timezone

from poller.policy import STALE_AFTER_DAYS, is_stale, is_terminal, should_poll

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def test_is_terminal_true_for_delivered():
    assert is_terminal("delivered") is True


def test_is_terminal_true_for_returned_to_sender():
    assert is_terminal("returned_to_sender") is True


def test_is_terminal_true_for_cancelled():
    assert is_terminal("cancelled") is True


def test_is_terminal_false_for_in_transit():
    assert is_terminal("in_transit") is False


def test_is_stale_false_just_under_the_window():
    changed_at = NOW - timedelta(days=STALE_AFTER_DAYS - 1)

    assert is_stale(changed_at, NOW) is False


def test_is_stale_true_past_the_window():
    changed_at = NOW - timedelta(days=STALE_AFTER_DAYS + 1)

    assert is_stale(changed_at, NOW) is True


def _shipment(status="in_transit", last_status_change_at=None):
    return {
        "status": status,
        "last_status_change_at": last_status_change_at or NOW - timedelta(days=1),
    }


def test_should_poll_true_for_fresh_non_terminal_shipment():
    assert should_poll(_shipment(), NOW) is True


def test_should_poll_false_for_terminal_shipment():
    shipment = _shipment(status="delivered", last_status_change_at=NOW - timedelta(days=1))

    assert should_poll(shipment, NOW) is False


def test_should_poll_false_for_stale_non_terminal_shipment():
    shipment = _shipment(last_status_change_at=NOW - timedelta(days=STALE_AFTER_DAYS + 5))

    assert should_poll(shipment, NOW) is False


def test_should_poll_true_when_forced_even_if_terminal():
    shipment = _shipment(status="delivered", last_status_change_at=NOW - timedelta(days=1))

    assert should_poll(shipment, NOW, force=True) is True


def test_should_poll_true_when_forced_even_if_stale():
    shipment = _shipment(last_status_change_at=NOW - timedelta(days=STALE_AFTER_DAYS + 5))

    assert should_poll(shipment, NOW, force=True) is True
