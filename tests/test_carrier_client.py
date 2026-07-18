import pytest
import requests

from poller.carrier_client import TrackingUnavailableError, fetch_tracking

BASE_URL = "http://mock-carrier.test"


def test_fetch_tracking_returns_parsed_json(requests_mock):
    payload = {
        "status": "in_transit",
        "last_event_at": "2026-07-17T10:00:00Z",
        "description": "Departed facility",
    }
    requests_mock.get(f"{BASE_URL}/track/1Z999AA1", json=payload)

    result = fetch_tracking(BASE_URL, "1Z999AA1")

    assert result == payload


def test_fetch_tracking_raises_on_unknown_tracking_number(requests_mock):
    requests_mock.get(f"{BASE_URL}/track/BOGUS", status_code=404)

    with pytest.raises(TrackingUnavailableError):
        fetch_tracking(BASE_URL, "BOGUS")


def test_fetch_tracking_raises_on_connection_error(requests_mock):
    requests_mock.get(f"{BASE_URL}/track/1Z999AA1", exc=requests.exceptions.ConnectionError)

    with pytest.raises(TrackingUnavailableError):
        fetch_tracking(BASE_URL, "1Z999AA1")


def test_fetch_tracking_raises_on_timeout(requests_mock):
    requests_mock.get(f"{BASE_URL}/track/1Z999AA1", exc=requests.exceptions.Timeout)

    with pytest.raises(TrackingUnavailableError):
        fetch_tracking(BASE_URL, "1Z999AA1")
