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

    def test_rental_vehicle_return_in_itinerary(self):
        """Test that rental vehicle return card is included on the final day when cars are selected."""
        res = self.client.planner.generate_itinerary(
            prompt="Plan a 4 day trip to Paris with rental car",
            origin="ATL",
            destination="CDG",
            include_cars=True,
            is_test=True,
        )
        self.assertEqual(res["status"], "success")
        final_day = res["daily_itinerary"][-1]
        car_ret_items = [item for item in final_day.get("items", []) if item.get("type") == "car" and "Return" in item.get("name", "")]
        self.assertEqual(len(car_ret_items), 1)
        self.assertIn("Rental Vehicle Return", car_ret_items[0]["name"])

    def test_default_dates_calculation(self):
        """Test default start date is today + 15 days and end date is today + 15 + 4 days when omitted."""
        res = self.client.planner.generate_itinerary(
            prompt="Plan a trip to Paris",
            origin="ATL",
            destination="CDG",
            is_test=True,
        )
        self.assertEqual(res["status"], "success")
        meta = res.get("meta_data", {})
        expected_start = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        expected_end = (datetime.now() + timedelta(days=19)).strftime("%Y-%m-%d")
        self.assertEqual(meta.get("start_date"), expected_start)
        self.assertEqual(meta.get("end_date"), expected_end)

    def test_trip_title_international_vacation(self):
        """Test that cross-country trips with flights receive 'International Vacation Travel' title."""
        res = self.client.planner.generate_itinerary(
            prompt="Plan a trip to Paris",
            origin="ATL",
            destination="CDG",
            include_flights=True,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "International Vacation Travel")
        self.assertEqual(res["meta_data"]["title"], "International Vacation Travel")
        self.assertEqual(res["meta_data"]["is_international"], True)
        self.assertEqual(res["meta_data"]["trip_type"], "vacation_travel")

    def test_trip_title_domestic_vacation(self):
        """Test that domestic trips with flights receive 'Vacation Travel' title."""
        res = self.client.planner.generate_itinerary(
            prompt="Plan a vacation to Orlando",
            origin="ATL",
            destination="MCO",
            include_flights=True,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Vacation Travel")
        self.assertEqual(res["meta_data"]["title"], "Vacation Travel")
        self.assertEqual(res["meta_data"]["is_international"], False)
        self.assertEqual(res["meta_data"]["trip_type"], "vacation_travel")

    def test_trip_title_domestic_road_trip(self):
        """Test that city-to-city trips without flights receive 'Road Trip' title."""
        res = self.client.planner.generate_itinerary(
            prompt="Road trip from Atlanta to Savannah",
            origin="ATL",
            destination="SAV",
            include_flights=False,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Road Trip")
        self.assertEqual(res["meta_data"]["title"], "Road Trip")
        self.assertEqual(res["meta_data"]["is_international"], False)
        self.assertEqual(res["meta_data"]["trip_type"], "road_trip")

    def test_trip_title_international_road_trip(self):
        """Test that cross-border city-to-city trips without flights receive 'International Road Trip' title."""
        res = self.client.planner.generate_itinerary(
            prompt="Drive from Seattle to Vancouver",
            origin="SEA",
            destination="YVR",
            include_flights=False,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "International Road Trip")
        self.assertEqual(res["meta_data"]["title"], "International Road Trip")
        self.assertEqual(res["meta_data"]["is_international"], True)

    def test_road_trip_bundle_corridor_itinerary(self):
        """Test that non-flight road trip generates corridor waypoints and road trip bundle contents."""
        res = self.client.planner.generate_itinerary(
            prompt="Plan a 4-day road trip from Atlanta to Columbus, Ohio",
            origin="ATL",
            destination="CMH",
            include_flights=False,
            include_cars=True,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Road Trip")
        self.assertEqual(res["meta_data"]["trip_type"], "road_trip")
        self.assertFalse(res["meta_data"]["is_international"])

        # Check bundle contents reflect no flights
        opt1_cheap = res["data"]["itinerary_options"][0]["category_highlights"]["cheapest"]
        self.assertFalse(opt1_cheap["bundle_contents"]["flights"]["included"])
        self.assertTrue(opt1_cheap["bundle_contents"]["cars"]["included"])

        # Check daily itinerary themes & waypoints
        day1 = res["daily_itinerary"][0]
        self.assertIn("Corridor Waypoints", day1["title"])
        self.assertGreaterEqual(len(day1["items"]), 3)

    def test_fly_and_drive_bundle_itinerary(self):
        """Test that fly & drive request (flights + road trip in destination) maintains both flight and car components."""
        res = self.client.planner.generate_itinerary(
            prompt="Fly from Atlanta to Paris and do a 4-day road trip with rental car",
            origin="ATL",
            destination="CDG",
            include_flights=True,
            include_cars=True,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "International Vacation Travel")
        self.assertEqual(res["meta_data"]["trip_type"], "fly_and_drive")
        self.assertTrue(res["meta_data"]["is_international"])

        # Check bundle contents include both flights and cars
        opt1_mod = res["data"]["itinerary_options"][0]["category_highlights"]["moderate"]
        self.assertTrue(opt1_mod["bundle_contents"]["flights"]["included"])
        self.assertTrue(opt1_mod["bundle_contents"]["cars"]["included"])

    def test_planner_road_trip_endpoint_alias(self):
        """Test POST /api/v1/planner/road-trip endpoint returns 200 OK with road trip payload."""
        payload = {
            "prompt": "Road trip from Atlanta to Savannah",
            "origin": "ATL",
            "destination": "SAV",
            "include_flights": False,
            "include_cars": True,
            "days": 3,
        }
        resp = self.test_api_client.post("/api/v1/planner/road-trip", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")

    def test_llm_failure_in_non_test_mode_raises_error(self):
        """Test that if test_mode is False and LLM fails, generate_itinerary raises an error without falling back to synthetic data."""
        self.client.config.test_mode = False
        self.client.config.openai_api_key = "invalid_openai_key"
        self.client.config.gemini_api_key = ""
        self.client.config.llm_provider = "openai"

        with self.assertRaises(RuntimeError) as ctx:
            self.client.planner.generate_itinerary(
                prompt="Trip to Paris",
                origin="ATL",
                destination="CDG",
                force_refresh=True,
            )
        self.assertIn("Failed generating AI travel itinerary", str(ctx.exception))

    def test_llm_failure_in_test_mode_uses_synthetic_data(self):
        """Test that if test_mode is True and LLM fails, generate_itinerary falls back to synthetic data."""
        self.client.config.test_mode = True
        self.client.config.openai_api_key = "invalid_openai_key"
        self.client.config.gemini_api_key = ""
        self.client.config.llm_provider = "openai"

        res = self.client.planner.generate_itinerary(
            prompt="Trip to Paris",
            origin="ATL",
            destination="CDG",
            force_refresh=True,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["meta_data"]["service_execution_summary"]["itinerary_planner"]["source"], "synthetic_template")

    def test_dynamic_destination_highlights_not_static(self):
        """Test that itinerary options highlights are dynamically constructed and do not contain static Paris landmarks for other destinations."""
        self.client.config.test_mode = True
        res = self.client.planner.generate_itinerary(
            prompt="Road trip from Atlanta to Columbus, Ohio",
            origin="ATL",
            destination="CMH",
            include_flights=False,
            include_cars=True,
            force_refresh=True,
        )
        self.assertEqual(res["status"], "success")
        options = res["data"]["itinerary_options"]
        for opt in options:
            highlights = opt.get("highlights", [])
            for hl in highlights:
                self.assertNotIn("Louvre", hl)
                self.assertNotIn("Eiffel Tower", hl)
                self.assertNotIn("Montmartre", hl)
                self.assertNotIn("Seine", hl)

    def test_extract_days_from_nested_llm_payload(self):
        """Test that _extract_days_from_llm_payload extracts days from arbitrary nested LLM responses."""
        from src.duffel.services.planner import _extract_days_from_llm_payload

        # 1. Nested under {"trip": {"itinerary": [...]}}
        p1 = {
            "trip": {
                "origin": "ATL",
                "destination": "New York",
                "itinerary": [
                    {"day_number": 1, "theme": "Arrival & Central Park", "activities": []},
                    {"day_number": 2, "theme": "Museums & Times Square", "activities": []}
                ]
            }
        }
        res1 = _extract_days_from_llm_payload(p1)
        self.assertIsNotNone(res1)
        self.assertEqual(len(res1), 2)
        self.assertEqual(res1[0]["day_number"], 1)

        # 2. Standard top-level {"days": [...]}
        p2 = {
            "days": [
                {"day_number": 1, "theme": "Day 1", "activities": []}
            ]
        }
        res2 = _extract_days_from_llm_payload(p2)
        self.assertIsNotNone(res2)
        self.assertEqual(len(res2), 1)

        # 3. Direct array [...]
        p3 = [
            {"day": 1, "theme": "Day 1", "activities": []}
        ]
        res3 = _extract_days_from_llm_payload(p3)
        self.assertIsNotNone(res3)
        self.assertEqual(len(res3), 1)


if __name__ == "__main__":
    unittest.main()


