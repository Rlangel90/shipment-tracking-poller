from mock_carrier.server import create_app

TRACKING = {
    "TRK-SHP-000001": {
        "status": "in_transit",
        "last_event_at": "2026-07-17T10:00:00Z",
        "description": "Departed facility",
    }
}


def test_track_returns_known_tracking_number():
    client = create_app(TRACKING).test_client()

    resp = client.get("/track/TRK-SHP-000001")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "in_transit"


def test_track_returns_404_for_unknown_tracking_number():
    client = create_app(TRACKING).test_client()

    resp = client.get("/track/UNKNOWN")

    assert resp.status_code == 404
