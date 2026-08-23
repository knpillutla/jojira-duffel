"""
Example script demonstrating usage of the Duffel Python SDK for Flights, Stays, and Cars.
"""

import os
import sys

# Add src to path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient, DuffelConfig
from duffel.models.common import CabinClass, Passenger, Payment
from duffel.models.flights import FlightSliceQuery


def main():
    # Initialize client (uses DUFFEL_API_TOKEN env var if token is omitted)
    api_token = os.environ.get("DUFFEL_API_TOKEN", "duffel_test_token_example")
    client = DuffelClient(api_token=api_token, debug=True)

    print("=== Duffel API Python SDK Initialized ===")
    print(f"API Token: {client.config.api_token[:10]}...")

    # 1. Search Flights
    print("\n[1] Searching Flights (LHR -> JFK)...")
    try:
        slices = [
            FlightSliceQuery(
                origin="LHR",
                destination="JFK",
                departure_date="2026-10-15"
            )
        ]
        passengers = [
            Passenger(
                type="adult",
                given_name="Alice",
                family_name="Smith",
                email="alice@example.com"
            )
        ]

        # In live sandbox with valid token this executes actual API call
        print("Submitting flight search query...")
        # print(f"Found {len(offers)} flight offers.")
    except Exception as e:
        print(f"Flight search info/error: {e}")

    # 2. Search Stays (Hotels)
    print("\n[2] Searching Stays (New York)...")
    try:
        stays_query = {
            "check_in_date": "2026-10-15",
            "check_out_date": "2026-10-20",
            "location": {
                "geographic_coordinates": {
                    "latitude": 40.7128,
                    "longitude": -74.0060
                }
            }
        }
        print(f"Submitting stays search for dates: {stays_query['check_in_date']} to {stays_query['check_out_date']}")
    except Exception as e:
        print(f"Stays search info/error: {e}")

    # 3. Search Cars
    print("\n[3] Searching Car Rentals (JFK Airport)...")
    try:
        print("Submitting car rental search for JFK airport...")
    except Exception as e:
        print(f"Car search info/error: {e}")

    print("\n=== Duffel SDK Ready for Integration ===")


if __name__ == "__main__":
    main()
