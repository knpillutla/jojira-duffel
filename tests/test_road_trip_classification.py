"""
Unit tests for road_trip and fly_and_drive parameters in travel classification and API schema.
"""

import unittest
from src.duffel.api.schemas.planner import ItineraryPlannerRequest
from src.duffel.services.planner.classifier import classify_travel_scope_and_type


class TestRoadTripClassification(unittest.TestCase):
    """Tests for road_trip and fly_and_drive parameter logic."""

    def test_road_trip_param_forces_flights_false(self):
        """When road_trip is True, include_flights must be False internally."""
        res = classify_travel_scope_and_type(
            prompt="4 day trip from atlanta to orlando",
            resolved_origin="atlanta",
            dest_clean="orlando",
            include_flights=True,
            include_cars=True,
            road_trip=True,
        )
        self.assertTrue(res["is_road_trip"])
        self.assertFalse(res["include_flights"])
        self.assertEqual(res["trip_type"], "road_trip")

    def test_domestic_respects_include_flights_true(self):
        """Domestic trip with include_flights=True and no road_trip flag retains flights."""
        res = classify_travel_scope_and_type(
            prompt="4 day trip from atlanta to orlando",
            resolved_origin="atlanta",
            dest_clean="orlando",
            include_flights=True,
            include_cars=True,
            road_trip=None,
        )
        self.assertTrue(res["include_flights"])
        self.assertFalse(res["is_road_trip"])
        self.assertEqual(res["trip_type"], "vacation_travel")

    def test_schema_accepts_road_trip_and_no_fly_and_drive(self):
        """ItineraryPlannerRequest schema accepts road_trip and rejects/omits fly_and_drive."""
        req = ItineraryPlannerRequest(
            prompt="Trip to Orlando",
            road_trip=True,
        )
        self.assertTrue(req.road_trip)
        self.assertNotIn("fly_and_drive", req.model_fields)

    def test_cache_insights_metadata(self):
        """Verify build_execution_and_cache_insights generates correct flags and insights list."""
        from src.duffel.services.planner.cache import build_execution_and_cache_insights
        summary_fields, insights = build_execution_and_cache_insights(
            src_type="modular_postgres_assembly",
            dest_clean="Orlando",
            duration_days=4,
            start_date="2026-10-01",
            end_date="2026-10-04",
            include_flights=True,
            is_road_trip=False,
            component_pricing={"flight_cost": 250.0},
            outbound_dep="08:30 AM",
            outbound_arr="12:30 PM",
            return_dep="05:00 PM",
            return_arr="11:00 PM",
        )
        self.assertTrue(summary_fields["is_read_from_postgres"])
        self.assertEqual(summary_fields["itinerary_source"], "postgres_database")
        self.assertTrue(summary_fields["interpolated_dates"])
        self.assertTrue(summary_fields["interpolated_flights"])
        self.assertFalse(summary_fields["interpolated_road_trip"])
        self.assertGreaterEqual(len(insights), 3)
        self.assertIn("PostgreSQL", insights[0])
        self.assertIn("Dates interpolated", insights[1])
        self.assertIn("Flights interpolated", insights[2])

    def test_origin_destination_uppercase_when_flights_included(self):
        """When flights are included, origin and destination must be capital airport codes."""
        from src.duffel.services.planner.timeline import build_flight_item
        from src.duffel.services.planner.summary import build_trip_summary

        fl_item = build_flight_item(
            item_id="item_fl_1", title="Flight Arrival", dest_clean="Orlando",
            origin_code="atl", dest_upper="mco", passengers_count=2,
            dep_time="08:30 AM", arr_time="12:30 PM", price=500.0,
            base_lat=28.5383, base_lng=-81.3792, is_return=False,
        )
        self.assertEqual(fl_item["origin"], "ATL")
        self.assertEqual(fl_item["destination"], "MCO")
        self.assertEqual(fl_item["origin_code"], "ATL")
        self.assertEqual(fl_item["destination_code"], "MCO")
        self.assertEqual(fl_item["airline"], "Delta Air Lines")
        self.assertEqual(fl_item["airline_name"], "Delta Air Lines")

        summary = build_trip_summary(
            dest_clean="mco", origin_code="atl", start_date="2026-10-01", end_date="2026-10-04",
            duration_days=4, passengers_count=2, rooms_count=1, cars_count=1,
            include_flights=True, include_hotels=True, include_cars=True, is_road_trip=False, is_cruise=False,
            outbound_dep="08:30 AM", return_arr="09:00 PM",
            component_pricing={"flight_cost": 250.0, "airline_name": "Delta Air Lines"},
            daily_itinerary=[], top_3_bundles=[], adults_count=2, children_count=0, children_ages=[],
        )
        self.assertEqual(summary["origin"], "ATL")
        self.assertEqual(summary["destination"], "MCO")
        self.assertEqual(summary["airline"], "Delta Air Lines")
        self.assertEqual(summary["airline_name"], "Delta Air Lines")
        self.assertEqual(summary["flights"]["origin"], "ATL")
        self.assertEqual(summary["flights"]["destination"], "MCO")
        self.assertEqual(summary["flights"]["airline"], "Delta Air Lines")
        self.assertEqual(summary["flights"]["airline_name"], "Delta Air Lines")

    def test_bundle_and_flight_airline_included(self):
        """Verify airline_name is populated in bundle summary, bundle root, and flight items."""
        from src.duffel.services.planner.bundles import build_top_3_bundles
        bundles = build_top_3_bundles(
            dest_clean="Orlando", origin_code="ATL", prompt="Trip to Orlando",
            opt_highlights=["Disney World"], is_road_trip=False, is_cruise=False,
            duration_days=4, passengers_count=2, rooms_count=1, cars_count=1,
            flight_cost=250.0, hotel_cost_per_night=140.0, car_cost_total=180.0,
            is_hotel_tbd=False, is_car_tbd=False, include_flights=True,
            airline_name="Delta Air Lines",
        )
        self.assertEqual(len(bundles), 3)
        for b in bundles:
            self.assertIn("Delta Air Lines", b["airline_name"])
            self.assertIn("Delta Air Lines", b["summary"]["flights"]["airline_name"])


if __name__ == "__main__":
    unittest.main()
