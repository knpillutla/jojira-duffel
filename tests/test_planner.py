"""
Unit tests for AI Travel Planner Service and REST API Endpoint.
"""

from datetime import datetime, timedelta
import unittest
from fastapi.testclient import TestClient

from src.duffel.api.app import app
from src.duffel.client import DuffelClient


class TestTravelPlanner(unittest.TestCase):
    """Test suite for TravelPlannerService and /api/v1/planner/itinerary endpoint."""

    def setUp(self):
        self.client = DuffelClient(provider_name="mock")
        self.test_api_client = TestClient(app)

    def test_generate_itinerary_success(self):
        """Test generating a valid 5-day trip itinerary with geo-coordinates and top 3 package bundles."""
        start_date = "2026-10-01"
        end_date = "2026-10-05"

        res = self.client.planner.generate_itinerary(
            prompt="Plan a 5 day culture and food trip to Paris",
            origin="ATL",
            destination="CDG",
            start_date=start_date,
            end_date=end_date,
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["trip_duration_days"], 5)
        self.assertEqual(len(res["itinerary"]), 5)
        self.assertIn("map_center", res)
        self.assertIn("latitude", res["map_center"])
        self.assertIn("longitude", res["map_center"])

        # Check day 1 activity geo coordinates
        day1_activities = res["itinerary"][0]["activities"]
        self.assertGreaterEqual(len(day1_activities), 1)
        self.assertIn("geo_location", day1_activities[0])
        self.assertIn("latitude", day1_activities[0]["geo_location"])
        self.assertIn("longitude", day1_activities[0]["geo_location"])

        # Check Top 3 Bundles
        self.assertIn("top_3_bundles", res)
        self.assertLessEqual(len(res["top_3_bundles"]), 3)

    def test_generate_itinerary_exceeds_30_days_guardrail(self):
        """Test that requesting a trip longer than 30 days immediately raises ValueError."""
        start_date = "2026-10-01"
        end_date = "2026-11-15"  # 46 days > 30 days

        with self.assertRaises(ValueError) as ctx:
            self.client.planner.generate_itinerary(
                prompt="Plan a 46 day long trip around Europe",
                start_date=start_date,
                end_date=end_date,
            )

        self.assertIn("30 days", str(ctx.exception))

    def test_planner_endpoint_success(self):
        """Test POST /api/v1/planner/itinerary returns 200 OK for valid 5-day request."""
        payload = {
            "prompt": "Plan a 5 day romantic trip to Paris",
            "origin": "ATL",
            "destination": "Paris",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
        }
        resp = self.test_api_client.post("/api/v1/planner/itinerary", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["trip_duration_days"], 5)
        self.assertEqual(len(data["itinerary"]), 5)

    def test_planner_endpoint_30_day_limit_exceeded(self):
        """Test POST /api/v1/planner/itinerary returns 400 Bad Request when trip > 30 days."""
        payload = {
            "prompt": "Plan a 40 day vacation",
            "start_date": "2026-10-01",
            "end_date": "2026-11-10",  # 41 days
        }
        resp = self.test_api_client.post("/api/v1/planner/itinerary", json=payload)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("detail", data)
        self.assertIn("30 days", data["detail"])


if __name__ == "__main__":
    unittest.main()
