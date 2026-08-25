"""
Unit tests for FastAPI REST API endpoints.
"""

import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.duffel.api.app import app


class TestDuffelAPI(unittest.TestCase):
    """Test suite for Duffel REST API endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_health_check_endpoint(self):
        """Test GET /api/v1/health returns status ok."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("duffel_token_configured", data)
        self.assertIn("redis_cache_status", data)

    @patch("src.duffel.api.routes.get_duffel_client")
    def test_analyze_queries_endpoint(self, mock_get_client):
        """Test POST /api/v1/flights/analyze-queries endpoint."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.flights.analyze_candidate_queries.return_value = {
            "is_tier1_hit": True,
            "tier1_cache_key": "duffel:flights:search_optimized:...",
            "total_batches": 1,
            "duffel_api_calls": 0,
            "redis_cache_hits": 1,
            "aggregated_cache_hits": 1,
            "individual_cache_hits": 0,
            "details": []
        }

        payload = {
            "origin": "LHR",
            "destination": "JFK",
            "target_date": "2026-09-22",
            "target_return_date": "2026-09-29",
            "min_duration_days": 7,
            "max_duration_days": 7,
            "flex_days": 0
        }
        response = self.client.post("/api/v1/flights/analyze-queries", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_tier1_hit"])
        self.assertEqual(data["aggregated_cache_hits"], 1)

    @patch("src.duffel.api.routes.get_duffel_client")
    def test_search_optimized_endpoint(self, mock_get_client):
        """Test POST /api/v1/flights/search-optimized endpoint."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.flights.search_optimized.return_value = []
        mock_client.flights.compute_category_highlights.return_value = {}
        mock_client.http_client.get_metrics_summary.return_value = {}
        mock_client.cache.get_metrics_summary.return_value = {}

        payload = {
            "origin": "LHR",
            "destination": "JFK",
            "target_date": "2026-09-22",
            "target_return_date": "2026-09-29",
            "min_duration_days": 7,
            "max_duration_days": 7,
            "flex_days": 0
        }
        response = self.client.post("/api/v1/flights/search-optimized", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["search_prompt"], "")
        self.assertEqual(data["search_params"]["origin"], "LHR")
        self.assertEqual(data["search_params"]["destination"], "JFK")
        self.assertIn("force_refresh", data["search_params"])

    @patch("src.duffel.api.routes.get_duffel_client")
    @patch("src.duffel.cli.parser.PromptExtractor.extract_flight_info")
    def test_natural_language_search_endpoint(self, mock_extract, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_extract.return_value = {
            "slices": [{"origin": "ATL", "destination": "OSL", "departure_date": "2026-10-01"}],
            "target_return_date": "2026-10-31",
            "duration_days": 4,
            "cabin_class": "economy",
            "passengers_count": 1,
        }
        mock_client.flights.search_optimized.return_value = []
        mock_client.flights.compute_category_highlights.return_value = {}
        mock_client.http_client.get_metrics_summary.return_value = {}
        mock_client.cache.get_metrics_summary.return_value = {}

        response = self.client.post(
            "/api/v1/flights/search-natural-language",
            json={"prompt": "cheapest nonstop to oslo in october from atl for 4 days"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["search_prompt"],
            "cheapest nonstop to oslo in october from atl for 4 days",
        )
        self.assertEqual(data["search_params"]["origin"], "ATL")
        self.assertEqual(data["search_params"]["destination"], "OSL")
        self.assertEqual(data["search_params"]["target_date"], "2026-10-01")

    @patch("src.duffel.api.routes.get_duffel_client")
    @patch("src.duffel.cli.parser.PromptExtractor.extract_flight_info")
    def test_natural_language_search_reports_missing_fields(self, mock_extract, mock_get_client):
        mock_extract.return_value = {
            "slices": [{"destination": "OSL", "departure_date": "2026-10-01"}],
            "duration_days": 7,
        }

        response = self.client.post(
            "/api/v1/flights/search-natural-language",
            json={"prompt": "cheapest nonstop to oslo in october for 7 days"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["missing_fields"], ["origin"])

    @patch("src.duffel.api.routes.get_duffel_client")
    @patch("src.duffel.cli.parser.PromptExtractor.extract_flight_info")
    def test_search_optimized_endpoint_accepts_natural_language(self, mock_extract, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_extract.return_value = {
            "slices": [{"origin": "ATL", "destination": "OSL", "departure_date": "2026-10-01"}],
            "target_return_date": "2026-10-31",
            "duration_days": 4,
            "cabin_class": "economy",
            "passengers_count": 1,
        }
        mock_client.flights.search_optimized.return_value = []
        mock_client.flights.compute_category_highlights.return_value = {}
        mock_client.http_client.get_metrics_summary.return_value = {}
        mock_client.cache.get_metrics_summary.return_value = {}

        response = self.client.post(
            "/api/v1/flights/search-optimized",
            json={"prompt": "cheapest nonstop to oslo in october from atl for 4 days"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["search_prompt"],
            "cheapest nonstop to oslo in october from atl for 4 days",
        )
        self.assertEqual(data["search_params"]["origin"], "ATL")
        self.assertEqual(data["search_params"]["destination"], "OSL")
        self.assertEqual(data["search_params"]["target_date"], "2026-10-01")
        self.assertEqual(data["search_params"]["target_return_date"], "2026-10-31")
        self.assertEqual(data["search_params"]["min_duration_days"], 4)
        self.assertEqual(data["search_params"]["max_duration_days"], 4)
        mock_client.flights.search_optimized.assert_called_once()
        self.assertEqual(mock_client.flights.search_optimized.call_args.kwargs["target_return_date"], "2026-10-31")

    @patch("src.duffel.api.routes.get_duffel_client")
    def test_book_flight_endpoint_with_payment(self, mock_get_client):
        """Test POST /api/v1/flights/book forwards passenger and payment info to create_order."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_order = MagicMock()
        mock_order.id = "ord_12345"
        mock_order.booking_reference = "PNR999"
        mock_order.total_amount = "613.33"
        mock_order.total_currency = "USD"
        mock_order.created_at = "2026-08-23T12:00:00Z"
        mock_order.passengers = []
        mock_order.slices = []

        mock_real_offer = MagicMock()
        mock_real_offer.total_amount = "613.33"
        mock_real_offer.total_currency = "USD"
        mock_client.flights.get_offer.return_value = mock_real_offer
        mock_client.flights.create_order.return_value = mock_order

        payload = {
            "offer_id": "off_0000B9xyz",
            "passengers": [
                {
                    "type": "adult",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                    "phone_number": "+14155551234",
                    "born_on": "1992-05-15",
                }
            ],
            "payment": {
                "type": "balance",
                "currency": "USD",
                "amount": "613.33"
            }
        }

        response = self.client.post("/api/v1/flights/book", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "confirmed")
        self.assertEqual(data["order_id"], "ord_12345")
        self.assertEqual(data["booking_reference"], "PNR999")
        self.assertEqual(data["total_amount"], "613.33")

        mock_client.flights.create_order.assert_called_once()
        call_kwargs = mock_client.flights.create_order.call_args.kwargs
        self.assertEqual(call_kwargs["selected_offers"], ["off_0000B9xyz"])
        self.assertIsNotNone(call_kwargs["payments"])
        self.assertEqual(call_kwargs["payments"][0].amount, "613.33")

    def test_get_supported_payment_methods_endpoint(self):
        """Test GET /api/v1/payments/methods and GET /api/v1/flights/payment-methods."""
        res1 = self.client.get("/api/v1/payments/methods")
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["status"], "ok")
        self.assertEqual(data1["default_method"], "balance")
        methods = data1["supported_payment_methods"]
        self.assertGreaterEqual(len(methods), 7)
        method_ids = [m["id"] for m in methods]
        self.assertIn("balance", method_ids)
        self.assertIn("card", method_ids)
        self.assertIn("customer_card", method_ids)
        self.assertIn("arc_bsp_one_step", method_ids)
        self.assertIn("bank_transfer", method_ids)
        self.assertIn("instant_bank_transfer", method_ids)
        self.assertIn("hold", method_ids)

        res2 = self.client.get("/api/v1/flights/payment-methods")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "ok")

    @patch("src.duffel.api.routes.get_duffel_client")
    def test_search_exact_flights_endpoint(self, mock_get_client):
        """Test POST /api/v1/flights/search exact date search endpoint."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        class OfferList(list):
            pass

        mock_offer = MagicMock()
        mock_offers = OfferList([mock_offer])
        mock_offers.output_json = {
            "category_highlights": {"cheapest_overall": {"total_amount": "250.00"}},
            "cheapest_non_stop_offers": [],
            "shortest_non_stop_offers": [],
            "top_offers": []
        }
        mock_client.flights.search_exact.return_value = mock_offers
        mock_client.flights.compute_category_highlights.return_value = {"cheapest_overall": {"total_amount": "250.00"}}
        mock_client.flights._build_offer_summary.return_value = {
            "id": "off_1",
            "total_amount": "250.00",
            "total_currency": "USD",
            "slices": []
        }
        mock_client.http_client.get_metrics_summary.return_value = {"latency": "100ms"}
        mock_client.cache.get_metrics_summary.return_value = {"hits": 1}

        payload = {
            "origin": "ATL",
            "destination": "CDG",
            "departure_date": "2026-10-01",
            "return_date": "2026-10-22",
            "passengers_count": 1,
            "cabin_class": "economy"
        }

        response = self.client.post("/api/v1/flights/search", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_offers_found"], 1)
        self.assertEqual(data["search_params"]["origin"], "ATL")
        self.assertEqual(data["search_params"]["destination"], "CDG")
        self.assertEqual(data["search_params"]["departure_date"], "2026-10-01")
        self.assertEqual(data["search_params"]["return_date"], "2026-10-22")

        # Test GET /api/v1/flights/search with Query parameters
        get_response = self.client.get("/api/v1/flights/search?origin=ATL&destination=CDG&departure_date=2026-10-01&return_date=2026-10-22")
        self.assertEqual(get_response.status_code, 200)
        get_data = get_response.json()
        self.assertEqual(get_data["search_params"]["origin"], "ATL")

    def test_health_and_help_endpoints(self):
        """Test GET /health, GET /help, GET /api/v1/health, and GET /api/v1/help."""
        h1 = self.client.get("/health")
        self.assertEqual(h1.status_code, 200)
        self.assertEqual(h1.json()["status"], "healthy")
        self.assertIn("timestamp", h1.json())

        h2 = self.client.get("/api/v1/health")
        self.assertEqual(h2.status_code, 200)
        self.assertEqual(h2.json()["status"], "healthy")

        hp1 = self.client.get("/help")
        self.assertEqual(hp1.status_code, 200)
        data1 = hp1.json()
        self.assertIn("endpoints", data1)
        self.assertGreater(data1["total_endpoints"], 5)

        ep0 = data1["endpoints"][0]
        self.assertIn("name", ep0)
        self.assertIn("method", ep0)
        self.assertIn("url", ep0)
        self.assertIn("description", ep0)

    @patch("glob.glob")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{"status": "ok", "total_offers_found": 10}')
    @patch("os.path.exists")
    @patch("os.path.getmtime")
    def test_get_latest_results_endpoint(self, mock_mtime, mock_exists, mock_file, mock_glob):
        """Test GET /api/v1/flights/results/latest."""
        mock_glob.return_value = ["outputs/ATL_CDG_latest_search_results.json"]
        mock_exists.return_value = True
        mock_mtime.return_value = 1000

        res = self.client.get("/api/v1/flights/results/latest")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["total_offers_found"], 10)


if __name__ == "__main__":
    unittest.main()
