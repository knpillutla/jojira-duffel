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

    def test_category_highlight_includes_stop_details(self):
        offer = {
            "id": "off_two_stops",
            "total_amount": "500.00",
            "total_currency": "USD",
            "owner": {"name": "Test Airline"},
            "slices": [{
                "origin": {"name": "Hartsfield-Jackson Atlanta International Airport", "iata_code": "ATL"},
                "destination": {"name": "Oslo Airport", "iata_code": "OSL"},
                "duration": "PT10H",
                "segments": [
                    {"destination": {"name": "Reykjavik Airport", "iata_code": "KEF"}},
                    {"destination": {"name": "Paris Charles de Gaulle", "iata_code": "CDG"}},
                    {"destination": {"name": "John F. Kennedy International", "iata_code": "JFK"}},
                ],
            }],
        }

        highlights = self.client.flights.compute_category_highlights([offer])

        summary = highlights["cheapest_2_stop"]
        self.assertEqual(summary["origin"], "Atlanta (ATL)")
        self.assertEqual(summary["origin_name"], "Atlanta")
        self.assertEqual(summary["origin_code"], "ATL")
        self.assertEqual(summary["destination"], "Oslo (OSL)")
        self.assertEqual(summary["destination_name"], "Oslo")
        self.assertEqual(summary["destination_code"], "OSL")
        self.assertEqual(summary["legs"], "2 stops")
        self.assertEqual(summary["leg_names"], "Reykjavik, Paris")
        self.assertEqual(summary["leg_codes"], "KEF, CDG")
        self.assertEqual(summary["duration_hours"], 10.0)

    def test_offer_summary_includes_departure_and_arrival_datetime(self):
        """Verify offer summary extracts departure date/time and arrival date/time for outbound and return slices."""
        offer = {
            "id": "off_dt_test",
            "total_amount": "750.00",
            "total_currency": "USD",
            "owner": {"name": "Delta Air Lines"},
            "slices": [
                {
                    "origin": {"name": "Atlanta Airport", "iata_code": "ATL"},
                    "destination": {"name": "Charles de Gaulle", "iata_code": "CDG"},
                    "duration": "PT8H30M",
                    "segments": [
                        {
                            "departing_at": "2026-10-01T17:40:00Z",
                            "arriving_at": "2026-10-02T08:10:00Z",
                            "destination": {"name": "Charles de Gaulle", "iata_code": "CDG"},
                        }
                    ],
                },
                {
                    "origin": {"name": "Charles de Gaulle", "iata_code": "CDG"},
                    "destination": {"name": "Atlanta Airport", "iata_code": "ATL"},
                    "duration": "PT9H15M",
                    "segments": [
                        {
                            "departing_at": "2026-10-22T11:30:00Z",
                            "arriving_at": "2026-10-22T15:45:00Z",
                            "destination": {"name": "Atlanta Airport", "iata_code": "ATL"},
                        }
                    ],
                },
            ],
        }

        summary = self.client.flights._build_offer_summary(offer)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["departure_at"], "2026-10-01T17:40:00Z")
        self.assertEqual(summary["departure_date"], "2026-10-01")
        self.assertEqual(summary["departure_time"], "17:40:00")
        self.assertEqual(summary["arrival_at"], "2026-10-02T08:10:00Z")
        self.assertEqual(summary["arrival_date"], "2026-10-02")
        self.assertEqual(summary["arrival_time"], "08:10:00")
        self.assertEqual(summary["return_departure_at"], "2026-10-22T11:30:00Z")
        self.assertEqual(summary["return_departure_date"], "2026-10-22")
        self.assertEqual(summary["return_departure_time"], "11:30:00")
        self.assertEqual(summary["return_arrival_at"], "2026-10-22T15:45:00Z")
        self.assertEqual(summary["return_arrival_date"], "2026-10-22")
        self.assertEqual(summary["return_arrival_time"], "15:45:00")
        self.assertEqual(len(summary["slice_details"]), 2)
        self.assertEqual(summary["slice_details"][0]["departure_date"], "2026-10-01")
        self.assertEqual(summary["slice_details"][1]["departure_date"], "2026-10-22")


    @patch("urllib.request.urlopen")
    def test_get_offer_success(self, mock_urlopen):
        """Test GET /air/offers/{id} succeeds and returns FlightOffer with generated pas_ passenger IDs."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "id": "off_0000AMxZ123",
                "total_amount": "250.00",
                "total_currency": "USD",
                "owner": {"name": "Delta Air Lines", "iata_code": "DL"},
                "passengers": [{"id": "pas_0000AMxZ123P1", "type": "adult"}],
                "slices": []
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        offer = self.client.flights.get_offer("off_0000AMxZ123")
        self.assertIsInstance(offer, FlightOffer)
        self.assertEqual(offer.id, "off_0000AMxZ123")
        self.assertEqual(offer.total_amount, "250.00")
        self.assertEqual(offer.total_currency, "USD")
        self.assertTrue(hasattr(offer, "passengers"))
        self.assertEqual(offer.passengers[0]["id"], "pas_0000AMxZ123P1")

    @patch("urllib.request.urlopen")
    def test_list_offers_success(self, mock_urlopen):
        """Test GET /air/offers?offer_request_id=... succeeds and returns list of FlightOffer objects."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": [
                {
                    "id": "off_00001",
                    "total_amount": "199.99",
                    "total_currency": "USD",
                    "owner": {"name": "Frontier Airlines"},
                    "slices": []
                },
                {
                    "id": "off_00002",
                    "total_amount": "249.99",
                    "total_currency": "USD",
                    "owner": {"name": "Delta Air Lines"},
                    "slices": []
                }
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        offers = self.client.flights.list_offers("orq_00001")
        self.assertIsInstance(offers, list)
        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0].id, "off_00001")
        self.assertEqual(offers[1].id, "off_00002")

    @patch("urllib.request.urlopen")
    def test_offers_api_3step_integration_flow(self, mock_urlopen):
        """Test 3-step integration flow: 1. Offer Request -> 2. GET Offer & Pas ID -> 3. Create Order."""
        def side_effect(req, timeout=None):
            url = req.full_url
            mock_res = MagicMock()
            if "/air/offers/off_0000AMxZ999" in url:
                mock_res.read.return_value = json.dumps({
                    "data": {
                        "id": "off_0000AMxZ999",
                        "total_amount": "320.00",
                        "total_currency": "USD",
                        "owner": {"name": "Delta Air Lines"},
                        "passengers": [{"id": "pas_0000AMxZ999P1", "type": "adult"}],
                        "slices": []
                    }
                }).encode("utf-8")
            elif "/air/orders" in url:
                mock_res.read.return_value = json.dumps({
                    "data": {
                        "id": "ord_0000999",
                        "booking_reference": "PNR3StepOK",
                        "total_amount": "320.00",
                        "total_currency": "USD",
                        "passengers": [{"id": "pas_0000AMxZ999P1", "given_name": "John", "family_name": "Doe"}],
                        "slices": [],
                        "created_at": "2026-08-24T12:00:00Z",
                        "status": "confirmed"
                    }
                }).encode("utf-8")
            else:
                mock_res.read.return_value = json.dumps({"data": {}}).encode("utf-8")
            mock_res.__enter__.return_value = mock_res
            return mock_res

        mock_urlopen.side_effect = side_effect

        # Step 2: Fetch offer and pas_ ID
        offer = self.client.flights.get_offer("off_0000AMxZ999")
        self.assertEqual(offer.id, "off_0000AMxZ999")

        # Step 3: Create order mapping passenger onto pas_0000AMxZ999P1
        order = self.client.flights.create_order(
            selected_offers=["off_0000AMxZ999"],
            passengers=[Passenger(id=offer.passengers[0]["id"], given_name="John", family_name="Doe")],
            payments=[Payment(type="balance", currency="USD", amount="320.00")]
        )
        self.assertIsInstance(order, FlightOrder)
        self.assertEqual(order.id, "ord_0000999")
        self.assertEqual(order.booking_reference, "PNR3StepOK")


if __name__ == "__main__":
    unittest.main()
