"""
Unit tests for OrderDAO PostgreSQL & fallback database module.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.config import DuffelConfig
from duffel.db.order_dao import OrderDAO


class TestOrderDAO(unittest.TestCase):
    def setUp(self):
        self.config = DuffelConfig()
        self.config.postgres_enabled = True
        self.dao = OrderDAO(self.config)

    def test_save_and_update_hold_order_lifecycle(self):
        """Test creating a hold order record in DB, then updating status, payment_status, and email_confirmation_status."""
        duffel_id = "ord_test_dao_999"

        # 1. Save hold order
        saved = self.dao.save_hold_order(
            duffel_order_id=duffel_id,
            booking_reference="PNRDAO999",
            total_amount="340.00",
            total_currency="USD",
            order_type="hold",
            status="hold",
            payment_method="balance",
            payment_required_by="2026-08-30T12:00:00Z",
            email_recipient="testuser@example.com",
            passengers=[{"name": "Jane Doe", "type": "adult"}],
            slices=[{"origin": "ATL", "destination": "LHR", "duration": "8h 10m"}],
            payment_status="pending",
            email_confirmation_status="pending"
        )

        self.assertEqual(saved["duffel_order_id"], duffel_id)
        self.assertEqual(saved["status"], "hold")
        self.assertEqual(saved["payment_status"], "pending")
        self.assertEqual(saved["email_confirmation_status"], "pending")

        # 2. Retrieve order from database
        fetched = self.dao.get_order_by_duffel_id(duffel_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["booking_reference"], "PNRDAO999")
        self.assertEqual(fetched["total_amount"], "340.00")
        self.assertEqual(len(fetched["passengers"]), 1)
        self.assertEqual(fetched["email_recipient"], "testuser@example.com")

        # 3. Update order status once payment confirmed & email sent
        payment_details = {"id": "pay_dao_111", "status": "paid", "amount": "340.00"}
        updated = self.dao.update_order_status(
            duffel_order_id=duffel_id,
            status="confirmed",
            payment_status="paid",
            email_confirmation_status="sent",
            payment_details=payment_details
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "confirmed")
        self.assertEqual(updated["payment_status"], "paid")
        self.assertEqual(updated["email_confirmation_status"], "sent")
        self.assertEqual(updated["payment_details"]["id"], "pay_dao_111")


if __name__ == "__main__":
    unittest.main()
