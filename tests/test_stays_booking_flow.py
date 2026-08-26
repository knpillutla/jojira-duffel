"""
Test to verify Duffel stays API response translation with required booking fields.

This test validates:
1. API response keeps current format for UI compatibility
2. Quote IDs are included for booking operations
3. Search request IDs are included for fetching rates
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient
from duffel.models.stays import StaySearchResult, StayRate


class TestStaysBookingFieldsTranslation(unittest.TestCase):
    """Test that API response includes quote_id and search_request_id needed for booking."""
    
    def setUp(self):
        """Initialize test client."""
        self.client = DuffelClient(api_token="test_token_mock")
    
    @patch("urllib.request.urlopen")
    def test_search_stays_includes_quote_id_for_booking(self, mock_urlopen):
        """
        Test that search response includes quote_id which is required for booking.
        
        The API response maintains current UI format but includes:
        - quote_id in each rate (needed for StayBookingRequest.quote_id)
        - search_request_id in each result (optional, for reference)
        """
        # Mock Duffel API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "id": "str_search_123",  # Search request ID
                "results": [
                    {
                        "id": "sres_00001",
                        "search_request_id": "str_search_123",  # Added: search request ID
                        "accommodation": {
                            "id": "acc_123",
                            "name": "Grand Palace Hotel",
                            "location": {
                                "city": "Delhi",
                                "latitude": 28.7041,
                                "longitude": 77.1025
                            },
                            "rating": 5
                        },
                        "rates": [
                            {
                                "id": "rate_00001",
                                "quote_id": "quo_00001",  # Added: Duffel quote ID for booking
                                "total_amount": "180.00",
                                "total_currency": "USD",
                                "board_type": "breakfast",
                                "description": "Deluxe King Room with breakfast",
                                "cancellation_timeline": [
                                    {
                                        "starts_at": "2026-09-10T00:00:00Z",
                                        "ends_at": "2026-09-13T00:00:00Z",
                                        "penalty_amount": "0.00"
                                    }
                                ],
                                "available_rooms": 3
                            },
                            {
                                "id": "rate_00002",
                                "quote_id": "quo_00002",  # Added: Different quote for room-only option
                                "total_amount": "150.00",
                                "total_currency": "USD",
                                "board_type": "room_only",
                                "description": "Deluxe King Room without meals",
                                "cancellation_timeline": [],
                                "available_rooms": 5
                            }
                        ],
                        "created_at": "2026-08-23T10:00:00Z"
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute search
        results = self.client.stays.search(
            check_in_date="2026-09-15",
            check_out_date="2026-09-22",
            rooms=1,
            guests=[{"type": "adult"}],
            location={"place_id": "delhi"}
        )
        
        # Verify results
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Verify result structure (UI format maintained)
        self.assertEqual(result.id, "sres_00001")
        self.assertEqual(result.accommodation["name"], "Grand Palace Hotel")
        self.assertEqual(result.search_request_id, "str_search_123")  # Search request ID for reference
        
        # Verify rates include quote_id (critical for booking)
        self.assertEqual(len(result.rates), 2)
        
        rate_1 = result.rates[0]
        self.assertEqual(rate_1.id, "rate_00001")
        self.assertEqual(rate_1.quote_id, "quo_00001")  # Critical: quote_id for booking
        self.assertEqual(rate_1.total_amount, "180.00")
        self.assertEqual(rate_1.board_type, "breakfast")
        
        rate_2 = result.rates[1]
        self.assertEqual(rate_2.id, "rate_00002")
        self.assertEqual(rate_2.quote_id, "quo_00002")  # Different quote for different board type
        self.assertEqual(rate_2.total_amount, "150.00")
        self.assertEqual(rate_2.board_type, "room_only")
    
    def test_to_dict_serialization_includes_quote_id(self):
        """Test that to_dict() includes quote_id and maintains API response format."""
        # Create rate with quote_id
        rate_dict = {
            "id": "rate_001",
            "quote_id": "quo_001",  # From Duffel API
            "total_amount": "180.00",
            "total_currency": "USD",
            "board_type": "breakfast",
            "description": "Deluxe Room",
            "cancellation_timeline": [],
            "available_rooms": 3
        }
        
        rate = StayRate.from_dict(rate_dict)
        serialized = rate.to_dict()
        
        # Verify quote_id is preserved in serialization
        self.assertEqual(serialized["quote_id"], "quo_001")
        self.assertEqual(serialized["id"], "rate_001")
        self.assertEqual(serialized["total_amount"], "180.00")
        self.assertEqual(serialized["board_type"], "breakfast")
    
    def test_search_result_to_dict_includes_search_request_id(self):
        """Test that StaySearchResult.to_dict() includes search_request_id."""
        result_dict = {
            "id": "sres_001",
            "search_request_id": "str_search_123",  # From Duffel API
            "accommodation": {
                "id": "acc_123",
                "name": "Test Hotel",
                "rating": 4
            },
            "rates": [
                {
                    "id": "rate_001",
                    "quote_id": "quo_001",
                    "total_amount": "150.00",
                    "total_currency": "USD",
                    "board_type": "room_only",
                    "description": "Standard Room",
                    "cancellation_timeline": [],
                    "available_rooms": 5
                }
            ],
            "created_at": "2026-08-23T10:00:00Z"
        }
        
        result = StaySearchResult.from_dict(result_dict)
        serialized = result.to_dict()
        
        # Verify search_request_id is included
        self.assertEqual(serialized["search_request_id"], "str_search_123")
        self.assertEqual(serialized["id"], "sres_001")
        
        # Verify rates are properly serialized with quote_id
        self.assertEqual(len(serialized["rates"]), 1)
        self.assertEqual(serialized["rates"][0]["quote_id"], "quo_001")
        self.assertEqual(serialized["rates"][0]["total_amount"], "150.00")


class TestMockAdapterBookingFields(unittest.TestCase):
    """Test that mock adapter provides all required fields for booking."""
    
    def setUp(self):
        """Initialize client with mock adapter."""
        from duffel.adapters.mock_adapter import MockProviderAdapter
        from duffel.services.stays import StaysService
        from duffel.cache import DuffelCache
        
        self.adapter = MockProviderAdapter()
        self.cache = DuffelCache(enabled=False)  # Disable cache for testing
        self.service = StaysService(adapter=self.adapter, cache=self.cache)
    
    def test_mock_search_provides_quote_id_and_search_request_id(self):
        """Test that mock adapter returns quote_id and search_request_id."""
        results = self.service.search(
            check_in_date="2026-09-15",
            check_out_date="2026-09-22",
            rooms=1,
            guests=[{"type": "adult"}],
            location={"place_id": "delhi"}
        )
        
        # Verify results
        self.assertGreater(len(results), 0)
        result = results[0]
        
        # Verify search_request_id is present
        self.assertIsNotNone(result.search_request_id)
        self.assertTrue(result.search_request_id.startswith("str_mock_"))
        
        # Verify rates have quote_id
        self.assertGreater(len(result.rates), 0)
        for rate in result.rates:
            self.assertIsNotNone(rate.quote_id)
            self.assertTrue(rate.quote_id.startswith("quo_mock_"))
    
    def test_mock_get_rates_provides_quote_id(self):
        """Test that get_rates returns rates with quote_id."""
        rates = self.service.get_rates("sres_test_123")
        
        # Verify rates
        self.assertGreater(len(rates), 0)
        for rate in rates:
            self.assertIsNotNone(rate.quote_id)
            self.assertTrue(rate.quote_id.startswith("quo_mock_"))
            self.assertIsNotNone(rate.total_amount)
            self.assertIsNotNone(rate.board_type)


class TestAPIResponseFormat(unittest.TestCase):
    """Test that REST API response maintains UI format while including booking fields."""
    
    def setUp(self):
        """Set up FastAPI test client."""
        from fastapi.testclient import TestClient
        from duffel.api.app import app
        self.client = TestClient(app)
    
    @patch("duffel.api.routes.common.get_duffel_client")
    def test_api_response_includes_quote_id_in_rates(self, mock_get_client):
        """Test REST API response includes quote_id for UI to use in booking."""
        mock_client = MagicMock()
        
        # Create mock results with quote_id
        mock_rate = MagicMock()
        mock_rate.id = "rate_001"
        mock_rate.quote_id = "quo_001"
        mock_rate.total_amount = "180.00"
        mock_rate.total_currency = "USD"
        mock_rate.board_type = "breakfast"
        mock_rate.description = "Deluxe"
        mock_rate.cancellation_timeline = []
        mock_rate.available_rooms = 3
        mock_rate.to_dict = MagicMock(return_value={
            "id": "rate_001",
            "quote_id": "quo_001",
            "total_amount": "180.00",
            "total_currency": "USD",
            "board_type": "breakfast",
            "description": "Deluxe",
            "cancellation_timeline": [],
            "available_rooms": 3
        })
        
        mock_result = MagicMock()
        mock_result.id = "sres_001"
        mock_result.accommodation = {"name": "Test Hotel", "id": "acc_123"}
        mock_result.rates = [mock_rate]
        mock_result.created_at = "2026-08-23T10:00:00Z"
        mock_result.search_request_id = "str_search_123"
        mock_result.to_dict = MagicMock(return_value={
            "id": "sres_001",
            "accommodation": {"name": "Test Hotel", "id": "acc_123"},
            "rates": [{
                "id": "rate_001",
                "quote_id": "quo_001",
                "total_amount": "180.00",
                "total_currency": "USD",
                "board_type": "breakfast",
                "description": "Deluxe",
                "cancellation_timeline": [],
                "available_rooms": 3
            }],
            "created_at": "2026-08-23T10:00:00Z",
            "search_request_id": "str_search_123"
        })
        
        mock_client.stays.search.return_value = [mock_result]
        mock_get_client.return_value = mock_client
        
        # Make API request
        response = self.client.post(
            "/api/v1/stays/search",
            json={
                "check_in_date": "2026-09-15",
                "check_out_date": "2026-09-22",
                "rooms": 1,
                "guests_count": 1
            }
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["results"]), 1)
        
        result = data["results"][0]
        self.assertEqual(result["id"], "sres_001")
        self.assertEqual(result["accommodation"]["name"], "Test Hotel")
        
        # Verify quote_id is in rates (for UI to pass to booking endpoint)
        self.assertIn("rates", result)
        self.assertEqual(len(result["rates"]), 1)
        self.assertEqual(result["rates"][0]["quote_id"], "quo_001")
        
        # Verify search_request_id is included
        self.assertEqual(result["search_request_id"], "str_search_123")


# Sample request/response documentation
BOOKING_FLOW_DOCUMENTATION = """
## Complete Stays Booking Flow

### Step 1: Search for accommodations (GET quote_id from rates)
```
POST /api/v1/stays/search
{
  "check_in_date": "2026-09-15",
  "check_out_date": "2026-09-22",
  "rooms": 1,
  "guests_count": 2,
  "location_string": "delhi"
}

Response:
{
  "status": "success",
  "total_results": 2,
  "results": [
    {
      "id": "sres_00001",
      "search_request_id": "str_search_123",
      "accommodation": {
        "id": "acc_123",
        "name": "Grand Palace Hotel",
        "rating": 5
      },
      "rates": [
        {
          "id": "rate_00001",
          "quote_id": "quo_00001",  <-- SAVE THIS for booking
          "total_amount": "180.00",
          "total_currency": "USD",
          "board_type": "breakfast",
          "description": "Deluxe King Room with breakfast",
          "available_rooms": 3
        }
      ]
    }
  ]
}
```

### Step 2: Book using quote_id from Step 1
```
POST /api/v1/stays/book
{
  "quote_id": "quo_00001",  <-- From Step 1 response
  "guests": [
    {
      "given_name": "John",
      "family_name": "Doe",
      "email": "john@example.com",
      "type": "adult"
    },
    {
      "given_name": "Jane",
      "family_name": "Doe",
      "type": "adult"
    }
  ],
  "payments": [
    {
      "type": "card",
      "amount": "180.00",
      "currency": "USD"
    }
  ]
}

Response:
{
  "status": "confirmed",
  "order_id": "ord_stay_12345",
  "booking_reference": "DHB123456",
  "total_amount": "180.00",
  "total_currency": "USD",
  "check_in_date": "2026-09-15",
  "check_out_date": "2026-09-22"
}
```

## Key Fields Mapping

| Field | Source | Purpose |
|-------|--------|---------|
| quote_id | /stays/search response > rates[].quote_id | Required for /stays/book endpoint |
| search_request_id | /stays/search response > results[].search_request_id | Optional, for audit trail |
| total_amount | rates[].total_amount | Booking total |
| board_type | rates[].board_type | Room type (breakfast, room_only, etc) |

## Duffel API Adapter Translation

The adapter translates Duffel API responses to REST API format:

Duffel API (/stays/search_requests) → Adapter → REST API (/api/v1/stays/search)

Fields added by adapter for booking:
- quote_id (from Duffel rates)
- search_request_id (from Duffel search request)

These fields are preserved through the entire flow and exposed in API responses
so the UI can pass them to the booking endpoint.
"""

if __name__ == "__main__":
    print(BOOKING_FLOW_DOCUMENTATION)
    unittest.main()
