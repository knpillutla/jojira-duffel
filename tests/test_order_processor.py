"""
Unit tests for Azure Service Bus Order Processor module.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient
from duffel.processor import OrderProcessor
from duffel.services.service_bus import ServiceBusPublisher


class TestOrderProcessor(unittest.TestCase):
    def setUp(self):
        self.client = DuffelClient(api_token="test_mock_token")
        self.client.config.service_bus_enabled = True
        self.client.config.service_bus_connection_string = ""
        self.processor = OrderProcessor(client=self.client)

    def test_process_order_hold_event(self):
        """Test processing an OrderHoldEvent triggers Duffel pay_order and generates email."""
        self.client.flights.pay_order = MagicMock(return_value={
            "id": "pay_999",
            "order_id": "ord_proc_100",
            "status": "paid",
            "amount": "613.33",
            "currency": "USD"
        })

        event = {
            "event_type": "ORDER_HOLD_CREATED",
            "order_id": "ord_proc_100",
            "booking_reference": "PNRPROC100",
            "total_amount": "613.33",
            "total_currency": "USD",
            "passengers": [{"name": "Charlie Brown", "email": "charlie@example.com"}],
            "slices": [{"origin": "ATL", "destination": "LHR", "duration": "8h 00m"}],
            "payment": {"type": "balance", "amount": "613.33", "currency": "USD"}
        }

        res = self.processor.process_order_hold_event(event)

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["order_id"], "ord_proc_100")
        self.client.flights.pay_order.assert_called_once_with(
            order_id="ord_proc_100",
            payment={"type": "balance", "amount": "613.33", "currency": "USD"},
            amount="613.33",
            currency="USD"
        )
        self.assertTrue(os.path.exists(res["email_confirmation"]["html_file_path"]))

    def test_process_pending_events_queue(self):
        """Test process_pending_events pops events from queue and processes them."""
        self.client.flights.pay_order = MagicMock(return_value={"id": "pay_888", "status": "paid"})

        # Enqueue 2 order hold events into publisher fallback queue
        publisher = ServiceBusPublisher(self.client.config)
        publisher.publish_order_hold_event(
            order_id="ord_queue_1",
            booking_reference="PNRQ1",
            total_amount="120.00",
            total_currency="USD",
            passengers=[{"name": "User One", "email": "user1@example.com"}],
            slices=[{"origin": "ATL", "destination": "MCO", "duration": "1h 30m"}]
        )
        publisher.publish_order_hold_event(
            order_id="ord_queue_2",
            booking_reference="PNRQ2",
            total_amount="220.00",
            total_currency="USD",
            passengers=[{"name": "User Two", "email": "user2@example.com"}],
            slices=[{"origin": "ATL", "destination": "JFK", "duration": "2h 15m"}]
        )

        results = self.processor.process_pending_events(max_messages=10)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["order_id"], "ord_queue_1")
        self.assertEqual(results[1]["order_id"], "ord_queue_2")


if __name__ == "__main__":
    unittest.main()
