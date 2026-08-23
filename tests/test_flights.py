"""
Unit tests for FlightsService using mocked HTTP requests.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient
from duffel.models.common import CabinClass, Passenger, Payment
from duffel.models.flights import FlightOffer, FlightOrder, FlightSliceQuery


class TestFlightsService(unittest.TestCase):
    def setUp(self):
        self.client = DuffelClient(api_token="test_token_mock")
        self.client.config.enable_cache = False
        self.client.cache.enabled = False

    @patch("urllib.request.urlopen")
    def test_search_flights(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "id": "orq_00001",
                "offers": [
                    {
                        "id": "off_00001",
                        "total_amount": "250.00",
                        "total_currency": "USD",
                        "owner": {"name": "British Airways", "iata_code": "BA"},
                        "slices": [
                            {
                                "id": "sli_00001",
                                "origin": {"iata_code": "LHR"},
                                "destination": {"iata_code": "JFK"},
                                "duration": "PT8H",
                                "segments": [
                                    {
                                        "id": "seg_00001",
                                        "origin": {"iata_code": "LHR"},
                                        "destination": {"iata_code": "JFK"},
                                        "departing_at": "2026-09-01T10:00:00Z",
                                        "arriving_at": "2026-09-01T13:00:00Z",
                                        "marketing_carrier": {"name": "British Airways"},
                                        "operating_carrier": {"name": "British Airways"},
                                        "flight_number": "BA175"
                                    }
                                ]
                            }
                        ],
                        "passengers": [{"id": "pas_00001", "type": "adult"}],
                        "expires_at": "2026-09-01T12:00:00Z",
                        "created_at": "2026-08-23T10:00:00Z"
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        slices = [FlightSliceQuery(origin="LHR", destination="JFK", departure_date="2026-09-01")]
        passengers = [Passenger(type="adult", given_name="John", family_name="Doe")]

        offers = self.client.flights.search(slices=slices, passengers=passengers, cabin_class=CabinClass.ECONOMY)

        self.assertIsInstance(offers, list)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].id, "off_00001")
        self.assertEqual(offers[0].total_amount, "250.00")
        self.assertEqual(offers[0].slices[0].segments[0].flight_number, "BA175")

    @patch("urllib.request.urlopen")
    def test_create_order(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "id": "ord_00001",
                "booking_reference": "ABC123XYZ",
                "total_amount": "250.00",
                "total_currency": "USD",
                "passengers": [{"id": "pas_00001", "given_name": "John", "family_name": "Doe"}],
                "slices": [],
                "created_at": "2026-08-23T10:05:00Z",
                "live_mode": False,
                "status": "confirmed"
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        order = self.client.flights.create_order(
            selected_offers=["off_00001"],
            passengers=[Passenger(id="pas_00001", given_name="John", family_name="Doe")],
            payments=[Payment(type="balance", currency="USD", amount="250.00")]
        )

        self.assertIsInstance(order, FlightOrder)
        self.assertEqual(order.id, "ord_00001")
        self.assertEqual(order.booking_reference, "ABC123XYZ")
        self.assertEqual(order.status, "confirmed")

    @patch("urllib.request.urlopen")
    def test_search_optimized(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "offers": [
                    {
                        "id": "off_opt_1",
                        "total_amount": "613.33",
                        "total_currency": "USD",
                        "owner": {"name": "Virgin Atlantic"},
                        "slices": []
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        offers = self.client.flights.search_optimized(
            origin="LHR",
            destination="JFK",
            target_date="2026-09-22",
            target_return_date="2026-09-29",
            min_duration_days=5,
            max_duration_days=7,
            flex_days=1
        )
        self.assertIsInstance(offers, list)
        self.assertTrue(len(offers) > 0)
        self.assertEqual(offers[0].total_amount, "613.33")

    @patch("urllib.request.urlopen")
    def test_search_optimized_sorting_lowest_price(self, mock_urlopen):
        """Confirm search_optimized sorts offers strictly by price ascending and finds the cheapest deal."""
        call_count = 0

        def side_effect(req, timeout=None):
            nonlocal call_count
            call_count += 1
            prices = ["750.00", "608.33", "685.13", "613.33", "720.00"]
            price = prices[call_count % len(prices)]
            mock_res = MagicMock()
            mock_res.read.return_value = json.dumps({
                "data": {
                    "offers": [
                        {
                            "id": f"off_price_{call_count}",
                            "total_amount": price,
                            "total_currency": "USD",
                            "owner": {"name": "Virgin Atlantic"},
                            "slices": []
                        }
                    ]
                }
            }).encode("utf-8")
            mock_res.__enter__.return_value = mock_res
            return mock_res

        mock_urlopen.side_effect = side_effect

        offers = self.client.flights.search_optimized(
            origin="LHR",
            destination="JFK",
            target_date="2026-09-22",
            target_return_date="2026-09-29",
            min_duration_days=5,
            max_duration_days=7,
            flex_days=1
        )

        self.assertTrue(len(offers) > 0)
        # Lowest price must be at index 0
        self.assertEqual(offers[0].total_amount, "608.33")
        # Verify strict ascending order
        for i in range(len(offers) - 1):
            self.assertLessEqual(float(offers[i].total_amount), float(offers[i+1].total_amount))

    @patch("urllib.request.urlopen")
    def test_search_optimized_metrics_recorded(self, mock_urlopen):
        """Confirm Duffel API call metrics (total calls, min, max, avg response latency) are recorded."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"data": {"offers": []}}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        self.client.flights.search_optimized(
            origin="LHR",
            destination="JFK",
            target_date="2026-09-22",
            target_return_date="2026-09-29",
            min_duration_days=7,
            max_duration_days=7,
            flex_days=0
        )

        metrics = self.client.http_client.get_metrics_summary()
        self.assertGreaterEqual(metrics["total_calls"], 1)
        self.assertIn("min_ms", metrics)
        self.assertIn("max_ms", metrics)
        self.assertIn("avg_ms", metrics)


if __name__ == "__main__":
    unittest.main()
