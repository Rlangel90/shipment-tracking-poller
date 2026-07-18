"""Client for the carrier tracking API. A lookup failure for one shipment
shouldn't abort the whole run - the caller decides what to do with this
exception per shipment, not this module.
"""

import requests


class TrackingUnavailableError(RuntimeError):
    """Raised when a tracking lookup fails or the number is unknown."""


def fetch_tracking(base_url: str, tracking_number: str, timeout: int = 10) -> dict:
    try:
        response = requests.get(f"{base_url}/track/{tracking_number}", timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TrackingUnavailableError(
            f"tracking lookup failed for {tracking_number}: {exc}"
        ) from exc

    return response.json()
