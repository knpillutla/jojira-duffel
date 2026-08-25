"""
Unit tests for Azure Service Bus publisher service.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.config import DuffelConfig
from duffel.services.service_bus import ServiceBusPublisher


class TestServiceBusPublisher(unittest.TestCase):
    def setUp(self):
        self.config = DuffelConfig()
        self.config.service_bus_enabled = True
        self.config.service_bus_connection_string = ""
        self.config.service_bus_queue_name = "test-order-hold-events"

    def test_publish_order_hold_event_fallback(self):
        """Test publishing when connection string is empty (uses fallback in-memory queue)."""
        publisher = ServiceBusPublisher(self.config)
        res = publisher.publish_order_hold_event(
            order_id="ord_test_123",
            booking_reference="PNRTEST",
            total_amount="340.00",
            total_currency="USD",
            passengers=[{"name": "Jane Doe", "email": "jane@example.com"}],
            slices=[{"origin": "LHR", "destination": "JFK", "duration": "7h 30m"}],
        )

        self.assertEqual(res["status"], "queued_in_memory_fallback")
        self.assertEqual(res["order_id"], "ord_test_123")

        # Verify event popped from fallback queue
        popped = ServiceBusPublisher.pop_fallback_event(timeout=0.5)
        self.assertIsNotNone(popped)
        self.assertEqual(popped["order_id"], "ord_test_123")
        self.assertEqual(popped["booking_reference"], "PNRTEST")
        self.assertEqual(popped["event_type"], "ORDER_HOLD_CREATED")


if __name__ == "__main__":
    unittest.main()
