"""
Unit tests for CarsService using mocked HTTP requests.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient
from duffel.models.cars import CarOffer, CarOrder


class TestCarsService(unittest.TestCase):
    def setUp(self):
        self.client = DuffelClient(api_token="test_token_mock")

    @patch("urllib.request.urlopen")
    def test_search_cars(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "offers": [
                    {
                        "id": "caroff_00001",
                        "supplier": {"name": "Hertz"},
                        "vehicle": {"name": "Tesla Model 3", "category": "sedan", "transmission": "automatic"},
                        "pickup_location": {"name": "Los Angeles Intl Airport"},
                        "dropoff_location": {"name": "Los Angeles Intl Airport"},
                        "pickup_datetime": "2026-09-01T10:00:00Z",
                        "dropoff_datetime": "2026-09-05T10:00:00Z",
                        "total_amount": "320.00",
                        "total_currency": "USD"
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        offers = self.client.cars.search(
            pickup_location="LAX",
            dropoff_location="LAX",
            pickup_datetime="2026-09-01T10:00:00Z",
            dropoff_datetime="2026-09-05T10:00:00Z",
            driver_age=30
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].id, "caroff_00001")
        self.assertEqual(offers[0].supplier["name"], "Hertz")
        self.assertEqual(offers[0].vehicle["name"], "Tesla Model 3")

    @patch("urllib.request.urlopen")
    def test_create_car_order(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "id": "carord_00001",
                "booking_reference": "CAR-554433",
                "offer_id": "caroff_00001",
                "driver_details": {"given_name": "Bob", "family_name": "Builder"},
                "pickup_datetime": "2026-09-01T10:00:00Z",
                "dropoff_datetime": "2026-09-05T10:00:00Z",
                "total_amount": "320.00",
                "total_currency": "USD",
                "status": "confirmed",
                "created_at": "2026-08-23T10:15:00Z"
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        order = self.client.cars.create_order(
            offer_id="caroff_00001",
            driver_details={"given_name": "Bob", "family_name": "Builder"},
            payments=[{"type": "balance", "currency": "USD", "amount": "320.00"}]
        )

        self.assertEqual(order.id, "carord_00001")
        self.assertEqual(order.booking_reference, "CAR-554433")
        self.assertEqual(order.status, "confirmed")


if __name__ == "__main__":
    unittest.main()
