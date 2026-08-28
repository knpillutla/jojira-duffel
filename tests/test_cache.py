import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.config import DuffelConfig
from duffel.cache import DuffelCache


class TestDuffelCache(unittest.TestCase):
    def test_cache_enabled_get_set(self):
        cfg = DuffelConfig(enable_cache=True, cache_ttl_seconds=60, config_file="")
        cache = DuffelCache(cfg)

        key = "test:key:123"
        val = {"status": "ok", "offers": [{"id": "off_1", "total_amount": "100.00"}]}

        cache.set(key, val)
        retrieved = cache.get(key)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["status"], "ok")
        self.assertEqual(len(retrieved["offers"]), 1)

    def test_cache_disabled(self):
        cfg = DuffelConfig(enable_cache=False, config_file="")
        cache = DuffelCache(cfg)

        key = "test:key:disabled"
        val = {"status": "ok"}

        cache.set(key, val)
        self.assertIsNone(cache.get(key))

    def test_search_optimized_two_days_cache_hits(self):
        """
        Verify search_optimized for min=2, max=2 days duration populates cache
        on first execution and serves 100% from cache on repeat execution without API calls.
        """
        import json
        from unittest.mock import MagicMock, patch
        from duffel import DuffelClient

        cfg = DuffelConfig(api_token="duffel_test_bPastoqe8ihxQjjKiUaJ7g8P-Lz7Y4h0uRHnYfSqX0W", enable_cache=True, postgres_enabled=False, config_file="")
        client = DuffelClient(config=cfg)

        mock_response = {
            "data": {
                "id": "orq_2day_mock",
                "offers": [
                    {
                        "id": "off_2day_mock",
                        "total_amount": "608.33",
                        "total_currency": "USD",
                        "owner": {"name": "Virgin Atlantic", "iata_code": "VS"},
                        "slices": [
                            {"origin": {"iata_code": "LHR"}, "destination": {"iata_code": "JFK"}},
                            {"origin": {"iata_code": "JFK"}, "destination": {"iata_code": "LHR"}},
                        ],
                    }
                ],
            }
        }

        with patch.object(client.http_client, "post", return_value=mock_response) as mock_post:
            client.cache.redis_client = None
            client.cache.clear_metrics()

            # First search run (min=2, max=2) -> triggers mock API calls & populates cache
            offers_run1 = client.flights.search_optimized(
                origin="LHR",
                destination="JFK",
                target_date="2026-09-22",
                target_return_date="2026-09-29",
                min_duration_days=2,
                max_duration_days=2,
                flex_days=0,
            )

            self.assertGreater(len(offers_run1), 0)
            initial_api_calls = mock_post.call_count
            self.assertEqual(initial_api_calls, 6)

            # Reset API mock call count & cache metrics
            mock_post.reset_mock()
            client.cache.clear_metrics()

            # Second search run with EXACT same min=2, max=2 duration parameters -> hits Cache 100%!
            offers_run2 = client.flights.search_optimized(
                origin="LHR",
                destination="JFK",
                target_date="2026-09-22",
                target_return_date="2026-09-29",
                min_duration_days=2,
                max_duration_days=2,
                flex_days=0,
            )

            self.assertEqual(len(offers_run2), len(offers_run1))
            self.assertEqual(offers_run2[0].id, offers_run1[0].id)

            # Second run MUST NOT call Duffel API (mock_post should be 0 calls!)
            self.assertEqual(mock_post.call_count, 0)

            # Verify Cache metrics (Tier-1 instant aggregated cache hit = 1 read)
            cache_summary = client.cache.get_metrics_summary()
            self.assertGreaterEqual(cache_summary["hits"], 1)
            self.assertEqual(cache_summary["misses"], 0)
            self.assertEqual(cache_summary["hit_percentage"], 100.0)

    def test_search_optimized_seven_days_cache_hits(self):
        """
        Verify search_optimized for LHR -> JFK (2026-09-22 to 2026-09-29, min=7, max=7 days duration)
        calls API on first execution, populates cache, and serves 100% from cache on second execution.
        """
        from unittest.mock import patch
        from duffel import DuffelClient

        cfg = DuffelConfig(api_token="duffel_test_bPastoqe8ihxQjjKiUaJ7g8P-Lz7Y4h0uRHnYfSqX0W", enable_cache=True, postgres_enabled=False, config_file="")
        client = DuffelClient(config=cfg)

        mock_response = {
            "data": {
                "id": "orq_7day_mock",
                "offers": [
                    {
                        "id": "off_7day_mock",
                        "total_amount": "613.33",
                        "total_currency": "USD",
                        "owner": {"name": "Virgin Atlantic", "iata_code": "VS"},
                        "slices": [
                            {"origin": {"iata_code": "LHR"}, "destination": {"iata_code": "JFK"}},
                            {"origin": {"iata_code": "JFK"}, "destination": {"iata_code": "LHR"}},
                        ],
                    }
                ],
            }
        }

        with patch.object(client.http_client, "post", return_value=mock_response) as mock_post:
            client.cache.redis_client = None
            client.cache.clear_metrics()

            # First search run (min=7, max=7) -> 1 candidate batch (2026-09-22 -> 2026-09-29)
            offers_run1 = client.flights.search_optimized(
                origin="LHR",
                destination="JFK",
                target_date="2026-09-22",
                target_return_date="2026-09-29",
                min_duration_days=7,
                max_duration_days=7,
                flex_days=0,
            )

            self.assertEqual(len(offers_run1), 1)
            self.assertEqual(mock_post.call_count, 1)

            # Reset API mock call count & cache metrics
            mock_post.reset_mock()
            client.cache.clear_metrics()

            # Second search run with EXACT same parameters -> hits Cache 100%!
            offers_run2 = client.flights.search_optimized(
                origin="LHR",
                destination="JFK",
                target_date="2026-09-22",
                target_return_date="2026-09-29",
                min_duration_days=7,
                max_duration_days=7,
                flex_days=0,
            )

            self.assertEqual(len(offers_run2), 1)
            self.assertEqual(offers_run2[0].id, offers_run1[0].id)
            self.assertEqual(offers_run2[0].total_amount, "613.33")

            # Second run MUST NOT call Duffel API (0 calls)
            self.assertEqual(mock_post.call_count, 0)

            # Verify Cache metrics (1 hit out of 1 batch)
            cache_summary = client.cache.get_metrics_summary()
            self.assertEqual(cache_summary["hits"], 1)
            self.assertEqual(cache_summary["misses"], 0)
            self.assertEqual(cache_summary["hit_percentage"], 100.0)

    def test_cache_eviction_when_offer_expired(self):
        """Verify cache key is evicted and search re-executed live if even 1 offer is expired."""
        from unittest.mock import MagicMock, patch
        from duffel import DuffelClient
        from duffel.models.flights import FlightSliceQuery

        cfg = DuffelConfig(api_token="duffel_test_bPastoqe8ihxQjjKiUaJ7g8P-Lz7Y4h0uRHnYfSqX0W", enable_cache=True, postgres_enabled=False, config_file="")
        client = DuffelClient(config=cfg)

        expired_mock_response = {
            "data": {
                "id": "orq_expired_test",
                "offers": [
                    {
                        "id": "off_expired_1",
                        "total_amount": "150.00",
                        "expires_at": "2020-01-01T00:00:00Z",  # Past expired date
                        "slices": []
                    }
                ]
            }
        }
        fresh_mock_response = {
            "data": {
                "id": "orq_fresh_test",
                "offers": [
                    {
                        "id": "off_fresh_1",
                        "total_amount": "140.00",
                        "expires_at": "2030-01-01T00:00:00Z",
                        "slices": []
                    }
                ]
            }
        }

        from duffel.models.common import Passenger
        passengers = [Passenger(type="adult")]
        slices = [FlightSliceQuery(origin="ATL", destination="MCO", departure_date="2026-10-17")]
        cache_key, _ = client.flights._build_cache_key(slices=slices, passengers=passengers)

        # Pre-seed cache with expired offer response
        client.cache.set(cache_key, {"id": "orq_expired_test", "offers": expired_mock_response["data"]["offers"]})

        with patch.object(client.http_client, "post", return_value=fresh_mock_response) as mock_post:
            # Execute search - expired offer in cache should trigger eviction and live Duffel API call!
            offers = client.flights.search(slices=slices, passengers=passengers, return_offers=True)
            self.assertEqual(mock_post.call_count, 1)
            self.assertEqual(offers[0].id, "off_fresh_1")

    def test_favorite_airline_differentiates_cache_key(self):
        """Verify that searching with different favorite_airline values produces distinct cache keys."""
        from src.duffel.client import DuffelClient
        cfg = DuffelConfig(api_token="duffel_test_bPastoqe8ihxQjjKiUaJ7g8P-Lz7Y4h0uRHnYfSqX0W", enable_cache=True, postgres_enabled=False, config_file="")
        client = DuffelClient(config=cfg)

        key_delta = client.flights._build_optimized_cache_key(
            origin="ATL",
            destination="MCO",
            target_date="2026-09-13",
            target_return_date="2026-09-18",
            favorite_airline="Delta",
        )
        key_southwest = client.flights._build_optimized_cache_key(
            origin="ATL",
            destination="MCO",
            target_date="2026-09-13",
            target_return_date="2026-09-18",
            favorite_airline="Southwest",
        )

        self.assertNotEqual(key_delta, key_southwest)
        self.assertIn('"favorite_airline": "delta"', key_delta)
        self.assertIn('"favorite_airline": "southwest"', key_southwest)

    def test_ai_search_different_prompts_differentiate_cache_key(self):
        """Verify AI Search produces distinct cache keys for prompts specifying different airlines."""
        from src.duffel.client import DuffelClient
        from unittest.mock import MagicMock, patch
        cfg = DuffelConfig(api_token="duffel_test_bPastoqe8ihxQjjKiUaJ7g8P-Lz7Y4h0uRHnYfSqX0W", enable_cache=True, postgres_enabled=False, config_file="")
        client = DuffelClient(config=cfg)

        with patch("src.duffel.services.ai_search.PromptExtractor.extract_natural_intent") as mock_intent:
            mock_intent.side_effect = [
                {
                    "selected_types": ["flights"],
                    "origin": "ATL",
                    "destination": "MCO",
                    "departure_date": "2026-09-15",
                    "return_date": "2026-09-22",
                    "preferred_airline": "Delta",
                },
                {
                    "selected_types": ["flights"],
                    "origin": "ATL",
                    "destination": "MCO",
                    "departure_date": "2026-09-15",
                    "return_date": "2026-09-22",
                    "preferred_airline": "Southwest",
                },
            ]
            client.cache.get = MagicMock(return_value=None)
            client.cache.set = MagicMock()

            # Execute AI search for Delta prompt
            with patch.object(client.ai_search, "_execute_single_service", return_value={"offers": []}):
                client.ai_search.search_ai("cheapest roundtrip from atlanta to orlando from september 15 to september 22 with delta")
                key_delta = client.cache.get.call_args[0][0]

            # Execute AI search for Southwest prompt
            with patch.object(client.ai_search, "_execute_single_service", return_value={"offers": []}):
                client.ai_search.search_ai("cheapest roundtrip from atlanta to orlando from september 15 to september 22 with southwest")
                key_southwest = client.cache.get.call_args[0][0]

            self.assertNotEqual(key_delta, key_southwest)


def tearDownModule():
    """Automatically clean up all test databases and temporary test files upon test completion."""
    import os
    for test_file in ["jojira_duffel.db", "jojira_user_service.db", os.path.join("outputs", "jojira_orders.db")]:
        if os.path.exists(test_file):
            try:
                os.remove(test_file)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
