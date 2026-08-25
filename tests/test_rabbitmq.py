"""
Unit tests for RabbitMQ and multi-broker EventPublisher module.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.config import DuffelConfig
from duffel.services.event_publisher import EventPublisher


class TestRabbitMQPublisher(unittest.TestCase):
    def setUp(self):
        self.config = DuffelConfig()
        self.config.message_broker = "rabbitmq"
        self.config.rabbitmq_host = "127.0.0.1"
        self.config.rabbitmq_queue_name = "test-order-hold-events"
        self.publisher = EventPublisher(self.config)

    def test_publish_order_hold_event_rabbitmq_structure(self):
        """Test constructing and publishing an OrderHoldEvent payload under RabbitMQ config."""
        res = self.publisher.publish_order_hold_event(
            order_id="ord_rmq_123",
            booking_reference="PNRRMQ123",
            total_amount="480.00",
            total_currency="USD",
            passengers=[{"name": "Alice Green", "email": "alice@example.com"}],
            slices=[{"origin": "JFK", "destination": "LHR", "duration": "6h 50m"}],
        )

        self.assertIn("order_id", res)
        self.assertEqual(res["order_id"], "ord_rmq_123")
        self.assertIn(res["status"], ["published_rabbitmq", "queued_in_memory_fallback"])


if __name__ == "__main__":
    unittest.main()
