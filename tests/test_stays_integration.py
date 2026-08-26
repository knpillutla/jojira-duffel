"""
Comprehensive integration tests for Stays API with Duffel format validation.

Tests the full flow:
1. REST API request validation
2. Translation to Duffel format
3. Adapter communication with Duffel API
4. Response parsing
"""

import json
import os
import sys
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient
from duffel.api.routes.stays import normalize_guests, normalize_location
from duffel.models.stays import StaySearchQuery, StaySearchResult


class TestStaysNormalization(unittest.TestCase):
    """Test guest and location normalization helpers."""
    
    def test_normalize_guests_with_explicit_list(self):
        """Test guests parameter with explicit guest list."""
        guests = [
            {"type": "adult"},
            {"type": "child", "age": 8}
        ]
        result = normalize_guests(guests=guests)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "adult")
        self.assertEqual(result[1]["type"], "child")
        self.assertEqual(result[1]["age"], 8)
    
    def test_normalize_guests_with_count(self):
        """Test guests_count parameter creates adult list."""
        result = normalize_guests(guests_count=3)
        self.assertEqual(len(result), 3)
        for guest in result:
            self.assertEqual(guest["type"], "adult")
    
    def test_normalize_guests_default(self):
        """Test default guest when neither parameter provided."""
        result = normalize_guests()
        self.assertEqual(result, [{"type": "adult"}])
    
    def test_normalize_location_with_place_id(self):
        """Test location with place_id format."""
        location = {"place_id": "p_delhi_123"}
        result = normalize_location(location=location)
        self.assertEqual(result["place_id"], "p_delhi_123")
    
    def test_normalize_location_with_coordinates(self):
        """Test location with geographic_coordinates format."""
        location = {
            "geographic_coordinates": {
                "latitude": 28.7041,
                "longitude": 77.1025
            }
        }
        result = normalize_location(location=location)
        self.assertIn("geographic_coordinates", result)
        self.assertEqual(result["geographic_coordinates"]["latitude"], 28.7041)
    
    def test_normalize_location_with_string(self):
        """Test location_string parameter converts to place_id."""
        result = normalize_location(location_string="delhi")
        self.assertEqual(result, {"place_id": "delhi"})
    
    def test_normalize_location_none(self):
        """Test no location returns None."""
        result = normalize_location()
        self.assertIsNone(result)


class TestStaySearchQueryFormat(unittest.TestCase):
    """Test StaySearchQuery format matches Duffel API requirements."""
    
    def test_stay_search_query_structure(self):
        """Test StaySearchQuery creates proper Duffel format."""
        query = StaySearchQuery(
            check_in_date="2026-09-15",
            check_out_date="2026-09-22",
            rooms=1,
            guests=[{"type": "adult"}],
            location={"place_id": "delhi"},
            accommodation_ids=None
        )
        
        query_dict = query.to_dict()
        
        # Verify Duffel format
        self.assertEqual(query_dict["check_in_date"], "2026-09-15")
        self.assertEqual(query_dict["check_out_date"], "2026-09-22")
        self.assertEqual(query_dict["rooms"], 1)
        self.assertEqual(query_dict["guests"], [{"type": "adult"}])
        self.assertEqual(query_dict["location"], {"place_id": "delhi"})
    
    def test_stay_search_query_default_guests(self):
        """Test StaySearchQuery uses default guest when not provided."""
        query = StaySearchQuery(
            check_in_date="2026-09-15",
            check_out_date="2026-09-22",
        )
        
        query_dict = query.to_dict()
        self.assertEqual(query_dict["guests"], [{"type": "adult"}])


class TestStaysServiceIntegration(unittest.TestCase):
    """Test StaysService integration with mocked Duffel adapter."""
    
    def setUp(self):
        """Set up test client with mocked HTTP."""
        self.client = DuffelClient(api_token="test_token_mock")
    
    @patch("urllib.request.urlopen")
    def test_search_stays_full_flow(self, mock_urlopen):
        """Test complete stays search flow with Duffel format."""
        # Mock Duffel API response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "results": [
                    {
                        "id": "sres_00001",
                        "accommodation": {
                            "id": "acc_123",
                            "name": "Grand Palace Hotel",
                            "location": {
                                "city": "Delhi",
                                "latitude": 28.7041,
                                "longitude": 77.1025
                            },
                            "rating": 5,
                            "amenities": ["wifi", "gym", "pool"]
                        },
                        "rates": [
                            {
                                "id": "rate_00001",
                                "quote_id": "quo_00001",
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
                                "quote_id": "quo_00002",
                                "total_amount": "150.00",
                                "total_currency": "USD",
                                "board_type": "room_only",
                                "description": "Deluxe King Room without meals",
                                "cancellation_timeline": [],
                                "available_rooms": 5
                            }
                        ],
                        "created_at": "2026-08-23T10:00:00Z"
                    },
                    {
                        "id": "sres_00002",
                        "accommodation": {
                            "id": "acc_124",
                            "name": "Plaza Hotel",
                            "location": {
                                "city": "Delhi",
                                "latitude": 28.6200,
                                "longitude": 77.1200
                            },
                            "rating": 4,
                            "amenities": ["wifi", "gym"]
                        },
                        "rates": [
                            {
                                "id": "rate_00003",
                                "quote_id": "quo_00003",
                                "total_amount": "120.00",
                                "total_currency": "USD",
                                "board_type": "room_only",
                                "description": "Standard Room",
                                "cancellation_timeline": [],
                                "available_rooms": 10
                            }
                        ],
                        "created_at": "2026-08-23T10:05:00Z"
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute search with Duffel format
        results = self.client.stays.search(
            check_in_date="2026-09-15",
            check_out_date="2026-09-22",
            rooms=1,
            guests=[{"type": "adult"}],
            location={"place_id": "delhi"},
            accommodation_ids=None
        )
        
        # Verify results
        self.assertEqual(len(results), 2)
        
        # First result
        result_0 = results[0]
        self.assertIsInstance(result_0, StaySearchResult)
        self.assertEqual(result_0.id, "sres_00001")
        self.assertEqual(result_0.accommodation["name"], "Grand Palace Hotel")
        self.assertEqual(len(result_0.rates), 2)
        
        # First rate of first result
        rate_0_0 = result_0.rates[0]
        self.assertEqual(rate_0_0.id, "rate_00001")
        self.assertEqual(rate_0_0.total_amount, "180.00")
        self.assertEqual(rate_0_0.total_currency, "USD")
        self.assertEqual(rate_0_0.board_type, "breakfast")
        self.assertEqual(rate_0_0.available_rooms, 3)
        
        # Second result
        result_1 = results[1]
        self.assertEqual(result_1.id, "sres_00002")
        self.assertEqual(result_1.accommodation["name"], "Plaza Hotel")
        self.assertEqual(len(result_1.rates), 1)
        self.assertEqual(result_1.rates[0].total_amount, "120.00")


class TestStaysAPIEndpoint(unittest.TestCase):
    """Test REST API endpoint with request translation."""
    
    def setUp(self):
        """Set up FastAPI test client."""
        from fastapi.testclient import TestClient
        from duffel.api.app import app
        self.client = TestClient(app)
    
    @patch("duffel.api.routes.common.get_duffel_client")
    def test_stays_search_with_guests_count(self, mock_get_client):
        """Test REST API accepts guests_count and converts to list."""
        # Mock the client and stays service
        mock_client = MagicMock()
        mock_results = [
            MagicMock(
                id="sres_00001",
                accommodation={"name": "Test Hotel"},
                rates=[],
                created_at="2026-08-23T10:00:00Z",
                to_dict=MagicMock(return_value={
                    "id": "sres_00001",
                    "accommodation": {"name": "Test Hotel"},
                    "rates": [],
                    "created_at": "2026-08-23T10:00:00Z"
                })
            )
        ]
        mock_client.stays.search.return_value = mock_results
        mock_get_client.return_value = mock_client
        
        # Send request with guests_count instead of guests list
        response = self.client.post(
            "/api/v1/stays/search",
            json={
                "check_in_date": "2026-09-15",
                "check_out_date": "2026-09-22",
                "rooms": 1,
                "guests_count": 2  # Using guests_count instead of explicit list
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the service was called with normalized guests list
        mock_client.stays.search.assert_called_once()
        call_args = mock_client.stays.search.call_args
        
        # Should have converted guests_count to list of adults
        self.assertEqual(
            call_args.kwargs["guests"],
            [{"type": "adult"}, {"type": "adult"}]
        )
    
    @patch("duffel.api.routes.common.get_duffel_client")
    def test_stays_search_with_location_string(self, mock_get_client):
        """Test REST API accepts location_string and converts to place_id."""
        # Mock the client
        mock_client = MagicMock()
        mock_results = [
            MagicMock(
                id="sres_00001",
                accommodation={"name": "Test Hotel"},
                rates=[],
                created_at="2026-08-23T10:00:00Z",
                to_dict=MagicMock(return_value={
                    "id": "sres_00001",
                    "accommodation": {"name": "Test Hotel"},
                    "rates": [],
                    "created_at": "2026-08-23T10:00:00Z"
                })
            )
        ]
        mock_client.stays.search.return_value = mock_results
        mock_get_client.return_value = mock_client
        
        # Send request with location_string
        response = self.client.post(
            "/api/v1/stays/search",
            json={
                "check_in_date": "2026-09-15",
                "check_out_date": "2026-09-22",
                "rooms": 1,
                "location_string": "delhi"  # Using location_string instead of dict
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify location was converted
        mock_client.stays.search.assert_called_once()
        call_args = mock_client.stays.search.call_args
        
        # Should have converted location_string to place_id dict
        self.assertEqual(
            call_args.kwargs["location"],
            {"place_id": "delhi"}
        )
    
    @patch("duffel.api.routes.common.get_duffel_client")
    def test_stays_search_proper_duffel_format(self, mock_get_client):
        """Test REST API with proper Duffel format works."""
        # Mock the client
        mock_client = MagicMock()
        mock_results = [
            MagicMock(
                id="sres_00001",
                accommodation={"name": "Test Hotel"},
                rates=[],
                created_at="2026-08-23T10:00:00Z",
                to_dict=MagicMock(return_value={
                    "id": "sres_00001",
                    "accommodation": {"name": "Test Hotel"},
                    "rates": [],
                    "created_at": "2026-08-23T10:00:00Z"
                })
            )
        ]
        mock_client.stays.search.return_value = mock_results
        mock_get_client.return_value = mock_client
        
        # Send request with proper Duffel format
        response = self.client.post(
            "/api/v1/stays/search",
            json={
                "check_in_date": "2026-09-15",
                "check_out_date": "2026-09-22",
                "rooms": 1,
                "guests": [
                    {"type": "adult"},
                    {"type": "child", "age": 8}
                ],
                "location": {
                    "geographic_coordinates": {
                        "latitude": 28.7041,
                        "longitude": 77.1025
                    }
                }
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_results"], 1)


class TestStaysDataModel(unittest.TestCase):
    """Test data model to_dict conversions for Duffel format."""
    
    def test_stay_search_result_to_dict(self):
        """Test StaySearchResult serialization."""
        from duffel.models.stays import StayRate
        
        rate = StayRate.from_dict({
            "id": "rate_001",
            "total_amount": "180.00",
            "total_currency": "USD",
            "board_type": "breakfast",
            "description": "Deluxe",
            "cancellation_timeline": [],
            "available_rooms": 3
        })
        
        result = StaySearchResult(
            id="sres_001",
            accommodation={"name": "Hotel 1", "rating": 5},
            rates=[rate],
            created_at="2026-08-23T10:00:00Z"
        )
        
        result_dict = result.to_dict() if hasattr(result, 'to_dict') else result.__dict__
        self.assertEqual(result_dict["id"], "sres_001")
        self.assertEqual(result_dict["accommodation"]["name"], "Hotel 1")


# Sample usage documentation
SAMPLE_USAGE_DOCUMENTATION = """
## Duffel Stays API - REST Endpoint Guide

### Correct Request Format for /api/v1/stays/search

#### Option 1: Using explicit guest list (Preferred - Duffel Native)
```json
POST /api/v1/stays/search
{
  "check_in_date": "2026-09-15",
  "check_out_date": "2026-09-22",
  "rooms": 1,
  "guests": [
    {"type": "adult"},
    {"type": "adult"},
    {"type": "child", "age": 8}
  ],
  "location": {
    "place_id": "p_delhi_123"
  }
}
```

#### Option 2: Using guests_count (Simpler - Auto-converts to adults)
```json
POST /api/v1/stays/search
{
  "check_in_date": "2026-09-15",
  "check_out_date": "2026-09-22",
  "rooms": 1,
  "guests_count": 2
}
```

#### Option 3: Using location_string (Simpler - Auto-converts to place_id)
```json
POST /api/v1/stays/search
{
  "check_in_date": "2026-09-15",
  "check_out_date": "2026-09-22",
  "rooms": 1,
  "location_string": "delhi"
}
```

#### Option 4: Using geographic coordinates
```json
POST /api/v1/stays/search
{
  "check_in_date": "2026-09-15",
  "check_out_date": "2026-09-22",
  "rooms": 1,
  "guests": [{"type": "adult"}],
  "location": {
    "geographic_coordinates": {
      "latitude": 28.7041,
      "longitude": 77.1025
    }
  }
}
```

### Required Fields
- check_in_date: string (YYYY-MM-DD) ✓ Required
- check_out_date: string (YYYY-MM-DD) ✓ Required
- rooms: integer (1-10) - Default: 1

### Optional Fields
- guests: array of guest objects - Use if specific guest types/ages needed
- guests_count: integer (1-9) - Use as alternative to guests for count only
- location: object (place_id OR geographic_coordinates)
- location_string: string - Use as alternative to location (e.g., "delhi")
- accommodation_ids: array of strings - Search specific properties

### Response Format
```json
{
  "status": "success",
  "timestamp": "2026-08-26 15:30:45",
  "total_results": 2,
  "results": [
    {
      "id": "sres_00001",
      "accommodation": {
        "id": "acc_123",
        "name": "Grand Palace Hotel",
        "location": {...},
        "rating": 5,
        "amenities": ["wifi", "gym", "pool"]
      },
      "rates": [
        {
          "id": "rate_00001",
          "quote_id": "quo_00001",
          "total_amount": "180.00",
          "total_currency": "USD",
          "board_type": "breakfast",
          "description": "Deluxe King Room with breakfast",
          "available_rooms": 3
        }
      ],
      "created_at": "2026-08-23T10:00:00Z"
    }
  ]
}
```
"""


if __name__ == "__main__":
    print(SAMPLE_USAGE_DOCUMENTATION)
    unittest.main()
