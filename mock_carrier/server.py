"""A local stand-in for a carrier tracking API. Backed by the synthetic
fixture in mock_carrier/fixtures/tracking.json, generated together with the
seeded tracked_shipments rows by scripts/seed_warehouse.py so the two stay
consistent (each seeded shipment has a matching tracking-number entry here).

Run directly for local development: python -m mock_carrier.server
"""

import json
from pathlib import Path

from flask import Flask, abort, jsonify

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_TRACKING_PATH = FIXTURES_DIR / "tracking.json"


def create_app(tracking: dict[str, dict]) -> Flask:
    app = Flask(__name__)

    @app.get("/track/<tracking_number>")
    def track(tracking_number):
        record = tracking.get(tracking_number)
        if record is None:
            abort(404)
        return jsonify(record)

    return app


def create_app_from_fixtures() -> Flask:
    tracking = json.loads(DEFAULT_TRACKING_PATH.read_text())
    return create_app(tracking)


if __name__ == "__main__":
    create_app_from_fixtures().run(port=8300)
