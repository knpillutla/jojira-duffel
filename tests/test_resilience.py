import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from src.duffel.config import DuffelConfig
from src.duffel.exceptions import DuffelAPIError, DuffelException
from src.duffel.http_client import HTTPClient


class TestDuffelResilience(unittest.TestCase):

    def setUp(self):
        self.config = DuffelConfig(
            api_token="duffel_test_123",
            max_retries=3,
            retry_backoff_factor=0.01,
            retry_backoff_max=0.1,
            retry_status_codes=[500, 502, 503, 504, 429]
        )
        self.client = HTTPClient(self.config)

    @patch("urllib.request.urlopen")
    def test_retry_on_503_success_on_second_attempt(self, mock_urlopen):
        """Verify that a 503 error triggers a retry with identical idempotency key and succeeds on attempt 2."""
        err_503 = urllib.error.HTTPError(
            url="https://api.duffel.com/air/orders",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"errors": [{"message": "There is a temporary issue with the server"}]}')
        )

        mock_success_response = MagicMock()
        mock_success_response.status = 200
        mock_success_response.read.return_value = json.dumps({"data": {"id": "ord_resilient_123"}}).encode("utf-8")
        mock_success_response.__enter__.return_value = mock_success_response

        mock_urlopen.side_effect = [err_503, mock_success_response]

        res = self.client.post("/air/orders", data={"selected_offers": ["off_123"]})
        self.assertEqual(res["data"]["id"], "ord_resilient_123")
        self.assertEqual(mock_urlopen.call_count, 2)

        req1 = mock_urlopen.call_args_list[0][0][0]
        req2 = mock_urlopen.call_args_list[1][0][0]
        key1 = req1.headers.get("Duffel-idempotency-key") or req1.headers.get("Duffel-Idempotency-Key")
        key2 = req2.headers.get("Duffel-idempotency-key") or req2.headers.get("Duffel-Idempotency-Key")
        self.assertIsNotNone(key1)
        self.assertEqual(key1, key2)

    @patch("urllib.request.urlopen")
    def test_exhaust_all_retries_raises_duffel_api_error(self, mock_urlopen):
        """Verify that when 503 persists across all attempts, DuffelAPIError is raised after max_retries + 1 calls."""
        err_503 = urllib.error.HTTPError(
            url="https://api.duffel.com/air/orders",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"errors": [{"message": "There is a temporary issue with the server"}]}')
        )

        mock_urlopen.side_effect = err_503

        with self.assertRaises(DuffelAPIError) as ctx:
            self.client.post("/air/orders", data={"selected_offers": ["off_123"]})

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(mock_urlopen.call_count, 4)

    @patch("urllib.request.urlopen")
    def test_retry_on_429_rate_limit(self, mock_urlopen):
        """Verify 429 rate limit triggers retry and respects Retry-After."""
        err_429 = urllib.error.HTTPError(
            url="https://api.duffel.com/air/offers",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "0.01"},
            fp=MagicMock(read=lambda: b'{"errors": [{"message": "Rate limit exceeded"}]}')
        )

        mock_success_response = MagicMock()
        mock_success_response.status = 200
        mock_success_response.read.return_value = b'{"data": []}'
        mock_success_response.__enter__.return_value = mock_success_response

        mock_urlopen.side_effect = [err_429, mock_success_response]

        res = self.client.get("/air/offers")
        self.assertEqual(res, {"data": []})
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("urllib.request.urlopen")
    def test_retry_on_url_error(self, mock_urlopen):
        """Verify network URLError triggers retries."""
        url_err = urllib.error.URLError("Connection reset by peer")

        mock_success_response = MagicMock()
        mock_success_response.status = 200
        mock_success_response.read.return_value = b'{"status": "ok"}'
        mock_success_response.__enter__.return_value = mock_success_response

        mock_urlopen.side_effect = [url_err, mock_success_response]

        res = self.client.get("/air/offers")
        self.assertEqual(res, {"status": "ok"})
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("urllib.request.urlopen")
    def test_search_optimized_no_redundant_outer_retries(self, mock_urlopen):
        """Verify search_optimized stops retrying once HTTPClient retries are exhausted."""
        from src.duffel.client import DuffelClient
        cfg = DuffelConfig(
            api_token="duffel_test_123",
            max_retries=3,
            retry_backoff_factor=0.01,
            retry_backoff_max=0.1,
            enable_cache=False,
        )
        client = DuffelClient(config=cfg)

        mock_urlopen.side_effect = urllib.error.URLError("Read timeout")

        offers = client.flights.search_optimized(
            origin="LHR",
            destination="JFK",
            target_date="2026-09-22",
            target_return_date="2026-09-29",
            min_duration_days=7,
            max_duration_days=7,
            flex_days=0,
        )

        self.assertEqual(offers, [])
        # With flex_days=0, min/max=7, there is 1 query batch.
        # HTTPClient max_retries=3 means 1 initial attempt + 3 retries = 4 urllib calls.
        # Without redundant outer retries, urlopen call count must be exactly 4 (not 12).
        self.assertEqual(mock_urlopen.call_count, 4)


if __name__ == "__main__":
    unittest.main()
