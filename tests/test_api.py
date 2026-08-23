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
        self.assertEqual(data["status"], "ok")
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


if __name__ == "__main__":
    unittest.main()
