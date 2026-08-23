"""
Unit tests for StaysService using mocked HTTP requests.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient
from duffel.models.stays import StayOrder, StaySearchResult


class TestStaysService(unittest.TestCase):
    def setUp(self):
        self.client = DuffelClient(api_token="test_token_mock")

    @patch("urllib.request.urlopen")
    def test_search_stays(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "results": [
                    {
                        "id": "sres_00001",
                        "accommodation": {"name": "Grand Palace Hotel", "rating": 5},
                        "rates": [
                            {
                                "id": "rate_00001",
                                "total_amount": "180.00",
                                "total_currency": "USD",
                                "board_type": "breakfast",
                                "description": "Deluxe King Room",
                                "cancellation_timeline": [],
                                "available_rooms": 3
                            }
                        ],
                        "created_at": "2026-08-23T10:00:00Z"
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        results = self.client.stays.search(
            check_in_date="2026-09-10",
            check_out_date="2026-09-15",
            location={"geographic_coordinates": {"latitude": 40.7128, "longitude": -74.0060}}
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "sres_00001")
        self.assertEqual(results[0].accommodation["name"], "Grand Palace Hotel")
        self.assertEqual(results[0].rates[0].total_amount, "180.00")

    @patch("urllib.request.urlopen")
    def test_create_stay_order(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "id": "sord_00001",
                "booking_reference": "HTL-998877",
                "accommodation": {"name": "Grand Palace Hotel"},
                "check_in_date": "2026-09-10",
                "check_out_date": "2026-09-15",
                "guests": [{"given_name": "Jane", "family_name": "Smith"}],
                "total_amount": "180.00",
                "total_currency": "USD",
                "status": "confirmed",
                "created_at": "2026-08-23T10:10:00Z"
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        order = self.client.stays.create_order(
            quote_id="rate_00001",
            guests=[{"given_name": "Jane", "family_name": "Smith"}],
            payments=[{"type": "balance", "currency": "USD", "amount": "180.00"}]
        )

        self.assertEqual(order.id, "sord_00001")
        self.assertEqual(order.booking_reference, "HTL-998877")


if __name__ == "__main__":
    unittest.main()
