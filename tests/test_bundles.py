"""
Unit tests for Duffel REST API Bundled Travel Packages (/api/v1/bundles).
"""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from src.duffel.api.app import app


class TestBundledAPI(unittest.TestCase):
    """Test suite for travel package bundle search, booking, and order persistence."""

    def setUp(self):
        self.client = TestClient(app)

    @patch("src.duffel.api.routes.common.get_duffel_client")
    def test_search_bundles_endpoint(self, mock_get_client):
        """Test POST /api/v1/bundles/search endpoint."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.bundles.search_bundle.return_value = {
            "status": "success",
            "timestamp": "2026-08-25 18:45:00",
            "search_params": {
                "origin": "ATL",
                "destination": "CDG",
                "departure_date": "2026-10-01",
                "return_date": "2026-10-05",
            },
            "category_highlights": {
                "overall_lowest": {"bundle_id": "bnd_0001", "total_package_price": 850.0},
                "nonstop_flight_bundle": {"bundle_id": "bnd_0002", "total_package_price": 920.0},
                "best_value_bundle": {"bundle_id": "bnd_0001", "total_package_price": 850.0},
                "luxury_bundle": {"bundle_id": "bnd_0003", "total_package_price": 1400.0},
            },
            "total_bundles_found": 3,
            "top_bundles": [
                {"bundle_id": "bnd_0001", "total_package_price": 850.0},
                {"bundle_id": "bnd_0002", "total_package_price": 920.0},
                {"bundle_id": "bnd_0003", "total_package_price": 1400.0},
            ],
            "cache_metrics": {"hits": 1, "misses": 0},
            "output_file": "outputs/ATL_CDG_2026-10-01_2026-10-05_bundle_results.json",
        }

        response = self.client.post(
            "/api/v1/bundles/search",
            json={
                "origin": "ATL",
                "destination": "CDG",
                "departure_date": "2026-10-01",
                "return_date": "2026-10-05",
                "passengers_count": 1,
                "cabin_class": "economy",
                "rooms": 1,
                "driver_age": 30,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("category_highlights", data)
        self.assertEqual(data["total_bundles_found"], 3)
        self.assertEqual(data["category_highlights"]["overall_lowest"]["bundle_id"], "bnd_0001")

    @patch("src.duffel.api.routes.common.get_duffel_client")
    def test_book_bundle_endpoint(self, mock_get_client):
        """Test POST /api/v1/bundles/book endpoint."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_client.bundles.create_bundle_order.return_value = {
            "status": "confirmed",
            "message": "Travel package bundle booked successfully.",
            "bundle_order_id": "ord_bnd_12345678",
            "flight_order_id": "ord_fl_99",
            "flight_booking_reference": "PNRFL99",
            "stay_order_id": "ord_stay_88",
            "stay_booking_reference": "HOTEL88",
            "car_order_id": "ord_car_77",
            "car_booking_reference": "CAR77",
            "combined_total_amount": "850.00",
            "total_currency": "USD",
            "created_at": "2026-08-25T18:45:00",
        }

        response = self.client.post(
            "/api/v1/bundles/book",
            json={
                "flight_offer_id": "off_fl_123",
                "stay_quote_id": "quo_st_456",
                "car_offer_id": "off_cr_789",
                "passengers": [
                    {
                        "given_name": "Alice",
                        "family_name": "Smith",
                        "email": "alice@example.com",
                        "phone_number": "+14155550100",
                        "born_on": "1992-05-15",
                    }
                ],
                "guests": [{"given_name": "Alice", "family_name": "Smith"}],
                "driver_details": {"given_name": "Alice", "family_name": "Smith", "age": 30},
                "payment": {"type": "balance", "currency": "USD", "amount": "850.00"},
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "confirmed")
        self.assertEqual(data["bundle_order_id"], "ord_bnd_12345678")
        self.assertEqual(data["flight_booking_reference"], "PNRFL99")


if __name__ == "__main__":
    unittest.main()
