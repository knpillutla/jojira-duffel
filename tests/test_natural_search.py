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

    def test_hotel_strict_brand_filtering(self):
        """Verify strict case-insensitive filtering for hotel brand names."""
        from src.duffel.cli.parser import PromptExtractor
        from src.duffel.services.natural_search import NaturalSearchService
        from unittest.mock import MagicMock

        intent = PromptExtractor.extract_natural_intent("stay at ritz-carlton in paris from 2026-10-01 to 2026-10-05")
        self.assertEqual(intent.get("preferred_hotel_brand"), "Ritz-Carlton")

        mock_app = MagicMock()
        mock_app.stays.search.return_value = [
            MagicMock(to_dict=lambda: {"id": "h1", "accommodation": {"name": "Ritz-Carlton Paris"}, "cheapest_rate_total_amount": "500.00"}),
            MagicMock(to_dict=lambda: {"id": "h2", "accommodation": {"name": "Holiday Inn Paris"}, "cheapest_rate_total_amount": "150.00"}),
        ]

        svc = NaturalSearchService(http_client=MagicMock(), client=mock_app)
        res = svc._execute_hotel_search(
            destination="CDG", check_in_date="2026-10-01", check_out_date="2026-10-05",
            rooms=1, passengers_count=1, force_refresh=True, meta={}, search_params={}, intent=intent, overrides={}
        )

        self.assertEqual(res["total_results"], 1)
        self.assertEqual(res["results"][0]["accommodation"]["name"], "Ritz-Carlton Paris")

    def test_car_strict_vendor_filtering(self):
        """Verify strict case-insensitive filtering for car rental vendor names."""
        from src.duffel.cli.parser import PromptExtractor
        from src.duffel.services.natural_search import NaturalSearchService
        from unittest.mock import MagicMock

        intent = PromptExtractor.extract_natural_intent("rental car from hertz in orlando from 2026-09-15 to 2026-09-22")
        self.assertEqual(intent.get("preferred_car_vendor"), "Hertz")

        mock_app = MagicMock()
        mock_app.cars.search.return_value = [
            MagicMock(to_dict=lambda: {"id": "c1", "supplier": {"name": "Hertz"}, "vehicle": {"name": "SUV"}, "total_amount": "120.00"}),
            MagicMock(to_dict=lambda: {"id": "c2", "supplier": {"name": "Avis"}, "vehicle": {"name": "Sedan"}, "total_amount": "100.00"}),
        ]

        svc = NaturalSearchService(http_client=MagicMock(), client=mock_app)
        res = svc._execute_car_search(
            origin="MCO", destination="MCO", pickup_datetime="2026-09-15T10:00:00Z",
            dropoff_datetime="2026-09-22T10:00:00Z", driver_age=30, force_refresh=True,
            meta={}, search_params={}, intent=intent, overrides={}
        )

        self.assertEqual(res["total_results"], 1)
        self.assertEqual(res["results"][0]["supplier"]["name"], "Hertz")

    def test_bundle_strict_provider_filtering(self):
        """Verify strict carrier, hotel brand, and car vendor filtering in travel bundles."""
        from src.duffel.cli.parser import PromptExtractor
        from src.duffel.services.natural_search import NaturalSearchService
        from unittest.mock import MagicMock

        intent = PromptExtractor.extract_natural_intent("flight with delta, stay at marriott, and car with hertz from atl to mco from 2026-09-15 to 2026-09-22")
        self.assertEqual(intent.get("preferred_airline"), "Delta Air Lines")
        self.assertEqual(intent.get("preferred_hotel_brand"), "Marriott")
        self.assertEqual(intent.get("preferred_car_vendor"), "Hertz")

        mock_app = MagicMock()
        mock_fl = MagicMock()
        mock_fl.owner.name = "Delta Air Lines"
        mock_fl.owner.iata_code = "DL"
        mock_fl.total_amount = "300.00"
        mock_fl.to_dict.return_value = {"id": "fl1", "total_amount": "300.00", "airline_name": "Delta Air Lines"}

        mock_fl_other = MagicMock()
        mock_fl_other.owner.name = "Frontier Airlines"
        mock_fl_other.owner.iata_code = "F9"
        mock_fl_other.total_amount = "50.00"
        mock_fl_other.to_dict.return_value = {"id": "fl2", "total_amount": "50.00", "airline_name": "Frontier Airlines"}

        mock_app.flights.search_exact.return_value = [mock_fl, mock_fl_other]
        mock_app.stays.search.return_value = [
            MagicMock(to_dict=lambda: {"id": "h1", "accommodation": {"name": "Marriott Marquis"}, "cheapest_rate_total_amount": "200.00"}),
            MagicMock(to_dict=lambda: {"id": "h2", "accommodation": {"name": "Hilton Garden"}, "cheapest_rate_total_amount": "150.00"}),
        ]
        mock_app.cars.search.return_value = [
            MagicMock(to_dict=lambda: {"id": "c1", "supplier": {"name": "Hertz"}, "total_amount": "100.00"}),
            MagicMock(to_dict=lambda: {"id": "c2", "supplier": {"name": "Avis"}, "total_amount": "90.00"}),
        ]

        svc = NaturalSearchService(http_client=MagicMock(), client=mock_app)
        res = svc._execute_bundle_search(
            selected_types=["flights", "hotels", "cars"], origin="ATL", destination="MCO",
            departure_date="2026-09-15", return_date="2026-09-22", passengers_count=1, cabin_class="economy",
            rooms=1, driver_age=30, force_refresh=True, hash_key="test12", meta={}, search_params={},
            intent=intent, overrides={}
        )

        self.assertEqual(res["total_results"], 1)
        bnd = res["results"][0]
        self.assertEqual(bnd["flight_offer"]["airline_name"], "Delta Air Lines")
        self.assertEqual(bnd["hotel_stay"]["accommodation"]["name"], "Marriott Marquis")
        self.assertEqual(bnd["car_rental"]["supplier"]["name"], "Hertz")
