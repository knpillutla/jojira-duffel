"""
Unit tests for Email Confirmation Service.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.config import DuffelConfig
from duffel.services.email_service import EmailService


class TestEmailService(unittest.TestCase):
    def setUp(self):
        self.config = DuffelConfig()
        self.config.email_confirmation_enabled = True
        self.config.smtp_username = ""  # Force dry-run HTML export mode
        self.email_service = EmailService(self.config)

    def test_send_booking_confirmation_html_export(self):
        """Test generating and saving HTML confirmation email to outputs/email_confirmations/."""
        res = self.email_service.send_booking_confirmation(
            order_id="ord_email_123",
            booking_reference="PNREMAIL123",
            total_amount="450.00",
            total_currency="USD",
            passengers=[{"name": "Alice Smith", "type": "adult"}],
            slices=[{"origin": "ATL", "destination": "CDG", "duration": "8h 15m"}],
            recipient_email="alice@example.com"
        )

        self.assertEqual(res["order_id"], "ord_email_123")
        self.assertEqual(res["booking_reference"], "PNREMAIL123")
        self.assertEqual(res["recipient"], "alice@example.com")
        self.assertTrue(os.path.exists(res["html_file_path"]))

        # Read exported HTML file and verify content
        with open(res["html_file_path"], "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("PNREMAIL123", html)
        self.assertIn("Alice Smith", html)
        self.assertIn("ATL &rarr; CDG", html)
        self.assertIn("USD 450.00", html)


if __name__ == "__main__":
    unittest.main()
