"""
Tests for unified natural language search across flights, hotels, cars, attractions, and multi-category bundles.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.duffel.api.app import app
from src.duffel.cli.parser import PromptExtractor


class TestNaturalSearch:
    def setup_method(self):
        self.client = TestClient(app)

    def test_prompt_extractor_intent_single_flight(self):
        intent = PromptExtractor.extract_natural_intent("Flight from ATL to CDG on Oct 1")
        assert "flights" in intent["selected_types"]
        assert intent["origin"] == "ATL"
        assert intent["destination"] == "CDG"

    def test_prompt_extractor_intent_single_hotel(self):
        intent = PromptExtractor.extract_natural_intent("Book a luxury hotel in Paris from Oct 1 to Oct 8")
        assert "hotels" in intent["selected_types"]
        assert intent["destination"] == "Paris"

    def test_prompt_extractor_intent_single_car(self):
        intent = PromptExtractor.extract_natural_intent("Rent an SUV car in London from Oct 1 to Oct 8")
        assert "cars" in intent["selected_types"]

    def test_prompt_extractor_intent_single_attraction(self):
        intent = PromptExtractor.extract_natural_intent("Top attractions and things to do in Paris")
        assert "attractions" in intent["selected_types"]

    def test_prompt_extractor_intent_multi_bundle(self):
        intent = PromptExtractor.extract_natural_intent("Flight from ATL to CDG on Oct 1 returning Oct 8 with hotel in Paris and rental car")
        assert "flights" in intent["selected_types"]
        assert "hotels" in intent["selected_types"]
        assert "cars" in intent["selected_types"]
        assert len(intent["selected_types"]) == 3

    @patch("src.duffel.api.routes.common.get_duffel_client")
    def test_natural_search_api_single_flight(self, mock_get_client):
        mock_duffel = MagicMock()
        mock_get_client.return_value = mock_duffel

        mock_duffel.natural_search.search_natural.return_value = {
            "status": "success",
            "timestamp": "2026-08-25 20:00:00",
            "search_type": "flights",
            "meta": {
                "search_type": "flights",
                "selected_types": ["flights"],
                "is_bundle": False,
                "bundle_for": "Flight Search from ATL to CDG",
                "bundle_description": "Specific single-category search for flights from ATL to CDG.",
                "prompt": "Flight from ATL to CDG on Oct 1",
                "ttl_seconds": 3600,
                "expires_at": "2026-08-25T21:00:00Z",
                "timestamp": "2026-08-25 20:00:00",
            },
            "search_params": {"origin": "ATL", "destination": "CDG"},
            "category_highlights": {
                "cheapest_flight": {"price": "USD 350.00"},
                "fastest_flight": {"duration": "7h 30m"},
            },
            "total_results": 1,
            "results": [{"offer_id": "off_1"}],
        }

        response = self.client.post(
            "/api/v1/search/natural",
            json={"prompt": "Flight from ATL to CDG on Oct 1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "flights"
        assert data["meta"]["search_type"] == "flights"
        assert data["meta"]["is_bundle"] is False
        assert data["meta"]["ttl_seconds"] == 3600
        assert "expires_at" in data["meta"]
        assert "category_highlights" in data
        assert "cheapest_flight" in data["category_highlights"]

    @patch("src.duffel.api.routes.common.get_duffel_client")
    def test_natural_search_api_multi_type_bundle(self, mock_get_client):
        mock_duffel = MagicMock()
        mock_get_client.return_value = mock_duffel

        mock_duffel.natural_search.search_natural.return_value = {
            "status": "success",
            "timestamp": "2026-08-25 20:00:00",
            "search_type": "bundle",
            "meta": {
                "search_type": "bundle",
                "selected_types": ["flights", "hotels"],
                "is_bundle": True,
                "bundle_for": "Flights + Hotels Package for CDG",
                "bundle_description": "Combined package bundling Flights + Hotels with 5% discount.",
                "prompt": "Flight and hotel in Paris for Oct 1",
                "ttl_seconds": 3600,
                "expires_at": "2026-08-25T21:00:00Z",
                "timestamp": "2026-08-25 20:00:00",
            },


            "search_params": {"origin": "ATL", "destination": "CDG"},
            "category_highlights": {
                "lowest_fare_package": {"total_package_price": 700.0},
                "best_value": {"total_package_price": 750.0},
            },
            "total_results": 2,
            "results": [
                {"bundle_id": "bnd_1", "total_package_price": 700.0},
                {"bundle_id": "bnd_2", "total_package_price": 750.0},
            ],
        }

        response = self.client.post(
            "/api/v1/search/natural",
            json={"prompt": "Flight and hotel in Paris for Oct 1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "bundle"
        assert data["meta"]["search_type"] == "bundle"
        assert data["meta"]["is_bundle"] is True
        assert "category_highlights" in data
        assert "lowest_fare_package" in data["category_highlights"]
