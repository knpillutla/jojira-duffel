"""
Unit Tests for Modular Web Scraper Engine & Frontier Direct Web Fares.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.duffel.client import DuffelClient
from src.duffel.services.scrapers import BaseWebScraper, FrontierScraper, ScraperRegistry


class TestFrontierScraper(unittest.TestCase):
    """Test suite for Frontier Direct Web Scraper implementation."""

    def setUp(self):
        self.scraper = FrontierScraper()

    def test_frontier_scraper_metadata(self):
        """Verify scraper metadata properties."""
        self.assertEqual(self.scraper.name, "Frontier Direct Web Scraper")
        self.assertEqual(self.scraper.airline_code, "F9")

    def test_frontier_search_fares_round_trip(self):
        """Verify Frontier round trip fare extraction ($38.00)."""
        fares = self.scraper.search_fares(
            origin="ATL",
            destination="MCO",
            departure_date="2026-10-17",
            return_date="2026-10-24",
            passengers_count=1,
        )

        self.assertEqual(len(fares), 1)
        offer = fares[0]
        self.assertEqual(offer["total_amount"], 38.00)
        self.assertEqual(offer["currency"], "USD")
        self.assertEqual(offer["price"], "USD 38.00")
        self.assertEqual(offer["airline"], "Frontier Airlines")
        self.assertEqual(offer["flight_number"], "F9 3976")
        self.assertEqual(offer["legs"], "Non-stop")
        self.assertTrue(offer["is_external_web_fare"])
        self.assertEqual(offer["booking_type"], "external_redirect")
        self.assertIn("https://www.flyfrontier.com/flight-search/", offer["booking_url"])
        self.assertIn("origin=ATL", offer["booking_url"])
        self.assertIn("destination=MCO", offer["booking_url"])
        self.assertIn("departDate=2026-10-17", offer["booking_url"])
        self.assertIn("returnDate=2026-10-24", offer["booking_url"])


class TestScraperRegistry(unittest.TestCase):
    """Test suite for ScraperRegistry execution engine."""

    def test_registry_search_all_scrapers(self):
        """Verify parallel execution of registered scrapers."""
        registry = ScraperRegistry(enabled=True)
        results = registry.search_all_scrapers(
            origin="ATL",
            destination="MCO",
            departure_date="2026-10-17",
            return_date="2026-10-24",
        )

        self.assertGreater(len(results), 0)
        frontier_offer = results[0]
        self.assertTrue(frontier_offer["is_external_web_fare"])
        self.assertEqual(frontier_offer["total_amount"], 38.00)


class TestFlightsServiceWithScrapers(unittest.TestCase):
    """Test integration of scrapers with FlightsService search and highlights."""

    def setUp(self):
        self.client = DuffelClient(api_token="test_token", debug=False)

    @patch("src.duffel.services.scrapers.ScraperRegistry.search_all_scrapers")
    @patch("src.duffel.services.flights.FlightsService.search")
    def test_scraped_offers_merged_into_cheapest_category_highlight(self, mock_search, mock_scrapers):
        """Verify $38.00 scraped Frontier offer becomes the #1 cheapest_non_stop offer."""
        mock_scrapers.return_value = [
            {
                "offer_id": "scraped_frontier_38",
                "airline": "Frontier Airlines",
                "price": "USD 38.00",
                "total_amount": 38.00,
                "currency": "USD",
                "origin": "ATL",
                "destination": "MCO",
                "departure_date": "2026-10-17",
                "return_date": "2026-10-24",
                "is_non_stop": True,
                "duration": "1h 39m",
                "duration_minutes": 99,
                "is_external_web_fare": True,
                "booking_type": "external_redirect",
                "booking_url": "https://www.flyfrontier.com",
                "source": "Frontier Direct Web Scraper",
                "redirect_notice": "Special low-cost web fare. You will be redirected to Frontier to complete booking."
            }
        ]
        # Mock Duffel returning a $68 offer
        duffel_offer = {
            "id": "off_duffel_68",
            "total_amount": "68.00",
            "total_currency": "USD",
            "owner": {"name": "Frontier Airlines", "iata_code": "F9"},
            "slices": [
                {
                    "origin": {"name": "Atlanta", "iata_code": "ATL"},
                    "destination": {"name": "Orlando", "iata_code": "MCO"},
                    "duration": "PT1H39M",
                    "segments": [
                        {
                            "departing_at": "2026-10-17T17:49:00Z",
                            "arriving_at": "2026-10-17T19:28:00Z",
                            "marketing_carrier": {"name": "Frontier Airlines", "iata_code": "F9"},
                            "marketing_flight_number": "3976",
                            "destination": {"name": "Orlando", "iata_code": "MCO"},
                        }
                    ],
                }
            ],
        }
        mock_search.return_value = [duffel_offer]

        # Execute search_optimized
        offers = self.client.flights.search_optimized(
            origin="ATL",
            destination="MCO",
            target_date="2026-10-17",
            target_return_date="2026-10-24",
            min_duration_days=7,
            max_duration_days=7,
            flex_days=0,
            force_refresh=True,
        )

        self.assertIsNotNone(offers)
        highlights = getattr(offers, "category_highlights", {})
        self.assertIn("cheapest_non_stop", highlights)
        cheapest = highlights["cheapest_non_stop"]

        # Scraped $38.00 offer should be cheaper than $68.00 Duffel offer
        self.assertEqual(cheapest["total_amount"], 38.00)
        self.assertEqual(cheapest["price"], "USD 38.00")
        self.assertTrue(cheapest["is_external_web_fare"])
        self.assertEqual(cheapest["booking_type"], "external_redirect")
        self.assertIn("flyfrontier.com", cheapest["booking_url"])


if __name__ == "__main__":
    unittest.main()
