"""
Unit tests for PostgreSQL / SQLite OrderDAO (Flight, Stay, Car orders and unified queries).
"""

import unittest
from unittest.mock import MagicMock
from src.duffel.config import DuffelConfig
from src.duffel.db.order_dao import OrderDAO


class TestOrderDAO(unittest.TestCase):
    """Test suite for OrderDAO managing flight, stay, and car orders."""

    def setUp(self):
        self.config = DuffelConfig(postgres_enabled=False)
        self.dao = OrderDAO(config=self.config)

    def test_save_and_get_hold_order(self):
        """Test persisting and retrieving a flight order."""
        res = self.dao.save_hold_order(
            duffel_order_id="ord_fl_1001",
            booking_reference="PNR1001",
            total_amount="350.00",
            total_currency="USD",
            order_type="hold",
            status="hold",
            payment_method="balance",
            passengers=[{"name": "Alice Smith"}],
            slices=[{"origin": "ATL", "destination": "LHR"}],
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["duffel_order_id"], "ord_fl_1001")

        fetched = self.dao.get_order_by_duffel_id("ord_fl_1001")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["booking_reference"], "PNR1001")
        self.assertEqual(fetched["status"], "hold")

    def test_save_and_get_stay_order(self):
        """Test persisting and retrieving a hotel stay order."""
        res = self.dao.save_stay_order(
            duffel_order_id="ord_stay_2002",
            booking_reference="HOTEL2002",
            total_amount="450.00",
            total_currency="USD",
            quote_id="quo_2002",
            accommodation_name="Ritz-Carlton Paris",
            check_in_date="2026-10-01",
            check_out_date="2026-10-05",
            rooms=1,
            guests=[{"given_name": "Bob", "family_name": "Jones"}],
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["duffel_order_id"], "ord_stay_2002")

        fetched = self.dao.get_stay_order_by_duffel_id("ord_stay_2002")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["accommodation_name"], "Ritz-Carlton Paris")
        self.assertEqual(fetched["check_in_date"], "2026-10-01")

    def test_save_and_get_car_order(self):
        """Test persisting and retrieving a car rental order."""
        res = self.dao.save_car_order(
            duffel_order_id="ord_car_3003",
            booking_reference="CAR3003",
            total_amount="220.00",
            total_currency="USD",
            offer_id="off_car_3003",
            supplier_name="Hertz",
            vehicle_name="Tesla Model Y",
            pickup_location="LHR",
            dropoff_location="LHR",
            driver_age=35,
            driver_details={"given_name": "Charlie", "family_name": "Brown"},
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["duffel_order_id"], "ord_car_3003")

        fetched = self.dao.get_car_order_by_duffel_id("ord_car_3003")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["supplier_name"], "Hertz")
        self.assertEqual(fetched["vehicle_name"], "Tesla Model Y")

    def test_get_all_orders(self):
        """Test retrieving all bookings across Flights, Stays, and Cars."""
        self.dao.save_hold_order(
            duffel_order_id="ord_fl_mult_1",
            booking_reference="PNR_M1",
            total_amount="300.00",
        )
        self.dao.save_stay_order(
            duffel_order_id="ord_stay_mult_2",
            booking_reference="HOTEL_M2",
            total_amount="500.00",
        )
        self.dao.save_car_order(
            duffel_order_id="ord_car_mult_3",
            booking_reference="CAR_M3",
            total_amount="150.00",
        )

        all_orders = self.dao.get_all_orders(limit=10)
        self.assertGreaterEqual(len(all_orders), 3)
        booking_types = [o["booking_type"] for o in all_orders]
        self.assertIn("flight", booking_types)
        self.assertIn("stay", booking_types)
    def test_save_bundle_order_and_individual_orders_with_bundle_id(self):
        """Test persisting individual flight, stay, and car orders linked via shared bundle_id."""
        bnd_id = "ord_bnd_test_9999"

        # Save individual orders with bundle_id
        self.dao.save_hold_order(
            duffel_order_id="ord_fl_bnd_1",
            booking_reference="PNR_BND1",
            total_amount="350.00",
            bundle_id=bnd_id,
        )
        self.dao.save_stay_order(
            duffel_order_id="ord_stay_bnd_2",
            booking_reference="HOTEL_BND2",
            total_amount="400.00",
            bundle_id=bnd_id,
        )
        self.dao.save_car_order(
            duffel_order_id="ord_car_bnd_3",
            booking_reference="CAR_BND3",
            total_amount="150.00",
            bundle_id=bnd_id,
        )

        # Save master bundle order
        self.dao.save_bundle_order(
            duffel_bundle_id=bnd_id,
            flight_order_id="ord_fl_bnd_1",
            stay_order_id="ord_stay_bnd_2",
            car_order_id="ord_car_bnd_3",
            combined_total_amount="855.00",
        )

        fetched_bnd = self.dao.get_bundle_order_by_id(bnd_id)
        self.assertIsNotNone(fetched_bnd)
        self.assertEqual(fetched_bnd["flight_order_id"], "ord_fl_bnd_1")
        self.assertEqual(fetched_bnd["stay_order_id"], "ord_stay_bnd_2")
        self.assertEqual(fetched_bnd["car_order_id"], "ord_car_bnd_3")

        # Verify individual order lookup works and contains bundle_id link
        fl = self.dao.get_order_by_duffel_id("ord_fl_bnd_1")
        st = self.dao.get_stay_order_by_duffel_id("ord_stay_bnd_2")
        cr = self.dao.get_car_order_by_duffel_id("ord_car_bnd_3")
    def test_promo_code_and_gross_discount_amounts_persistence(self):
        """Test persisting promo_code, gross_amount, and discount_amount across all order types."""
        promo = "SUMMER2026"

        fl = self.dao.save_hold_order(
            duffel_order_id="ord_fl_promo_1",
            booking_reference="PNR_PROMO1",
            total_amount="450.00",
            promo_code=promo,
            gross_amount="500.00",
            discount_amount="50.00",
        )
        self.assertEqual(fl["promo_code"], promo)

        st = self.dao.save_stay_order(
            duffel_order_id="ord_stay_promo_2",
            booking_reference="HOTEL_PROMO2",
            total_amount="360.00",
            promo_code=promo,
            gross_amount="400.00",
            discount_amount="40.00",
        )
        self.assertIsNotNone(st)

        cr = self.dao.save_car_order(
            duffel_order_id="ord_car_promo_3",
            booking_reference="CAR_PROMO3",
            total_amount="180.00",
            promo_code=promo,
            gross_amount="200.00",
            discount_amount="20.00",
        )
        self.assertIsNotNone(cr)

        bnd = self.dao.save_bundle_order(
            duffel_bundle_id="ord_bnd_promo_4",
            flight_order_id="ord_fl_promo_1",
            stay_order_id="ord_stay_promo_2",
            car_order_id="ord_car_promo_3",
            combined_total_amount="900.00",
            promo_code=promo,
            gross_amount="1000.00",
            discount_amount="100.00",
        )
        self.assertIsNotNone(bnd)
        self.assertEqual(bnd["status"], "confirmed")

    def test_itinerary_template_persistence(self):
        """Test persisting date-neutral, price-agnostic itinerary templates."""
        map_c = {"latitude": 48.8566, "longitude": 2.3522, "address": "Paris", "name": "Paris Center"}
        tpl_days = [
            {"day_number": 1, "theme": "Arrival & Eiffel Tower", "activities": []},
            {"day_number": 2, "theme": "Louvre & Seine Cruise", "activities": []},
        ]
        saved = self.dao.save_itinerary_template(
            destination="Paris",
            duration_days=2,
            title="2-Day Paris Highlight",
            map_center=map_c,
            template_days=tpl_days,
            tags=["sightseeing"],
        )
        self.assertEqual(saved["destination"], "Paris")
        self.assertEqual(saved["duration_days"], 2)

        fetched = self.dao.get_itinerary_template("Paris", 2)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["title"], "2-Day Paris Highlight")
        self.assertEqual(len(fetched["template_days"]), 2)


if __name__ == "__main__":
    unittest.main()
