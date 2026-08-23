"""
Unit tests for DuffelClient initialization and configuration.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient, DuffelConfig
from duffel.exceptions import DuffelAuthenticationError, DuffelNotFoundError


class TestDuffelClient(unittest.TestCase):
    def test_client_init_defaults(self):
        client = DuffelClient(api_token="test_token_123")
        self.assertEqual(client.config.api_token, "test_token_123")
        self.assertEqual(client.config.base_url, "https://api.duffel.com")
        self.assertEqual(client.config.api_version, "v2")
        self.assertIsNotNone(client.flights)
        self.assertIsNotNone(client.stays)
        self.assertIsNotNone(client.cars)

    def test_client_headers(self):
        config = DuffelConfig(api_token="test_token_xyz", api_version="v2")
        headers = config.headers
        self.assertEqual(headers["Authorization"], "Bearer test_token_xyz")
        self.assertEqual(headers["Duffel-Version"], "v2")
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
