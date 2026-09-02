"""
Unit tests for title formatting and contextual bundle title generation.
Ensures acronyms like VIP are always formatted in all-caps (VIP, never Vip).
"""

import unittest
from src.duffel.services.planner.classifier import format_proper_title
from src.duffel.services.planner.titles import generate_contextual_bundle_title


class TestTitleFormatting(unittest.TestCase):
    """Test suite for format_proper_title and generate_contextual_bundle_title."""

    def test_vip_acronym_always_uppercase(self):
        """Test that VIP is strictly formatted in uppercase, even when followed by punctuation or lowercase in input."""
        self.assertEqual(
            format_proper_title("Signature Luxury Vip: Atlanta to Jax Premier Road Trip"),
            "Signature Luxury VIP: Atlanta to Jax Premier Road Trip"
        )
        self.assertEqual(
            format_proper_title("signature luxury vip: atlanta to jax"),
            "Signature Luxury VIP: Atlanta to Jax"
        )
        self.assertEqual(
            format_proper_title("VIP: Exclusive package (vip) & VIP experience"),
            "VIP: Exclusive Package (VIP) & VIP Experience"
        )

    def test_luxury_road_trip_bundle_title_has_vip_uppercase(self):
        """Test that luxury road trip bundle title includes 'Signature Luxury VIP' with uppercase VIP."""
        title = generate_contextual_bundle_title(
            destination="Jacksonville",
            origin="Atlanta",
            tier="luxury",
            index=2,
            prompt="Road trip from Atlanta to Jacksonville",
            activities=["High Falls State Park"],
            is_road_trip=True,
        )
        self.assertIn("Signature Luxury VIP:", title)
        self.assertNotIn("Vip", title)

    def test_luxury_flight_bundle_title_has_vip_uppercase(self):
        """Test that luxury flight bundle title includes 'Signature Luxury VIP' with uppercase VIP."""
        title = generate_contextual_bundle_title(
            destination="Paris",
            origin="Atlanta",
            tier="luxury",
            index=2,
            prompt="Luxury vacation in Paris",
            activities=["Eiffel Tower"],
            is_road_trip=False,
        )
        self.assertIn("Signature Luxury VIP:", title)
        self.assertNotIn("Vip", title)


if __name__ == "__main__":
    unittest.main()
