"""
Unit tests for Provider Adapter pattern and provider switching capabilities.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel import DuffelClient, DuffelConfig
from duffel.adapters import (
    BaseProviderAdapter,
    DuffelProviderAdapter,
    MockProviderAdapter,
    ProviderFactory,
)
from duffel.models.common import CabinClass, Passenger
from duffel.models.flights import FlightOffer, FlightSliceQuery


class TestProviderFactory(unittest.TestCase):
    def test_default_provider_is_duffel(self):
        adapter = ProviderFactory.get_adapter()
        self.assertIsInstance(adapter, DuffelProviderAdapter)

    def test_mock_provider_selection(self):
        adapter = ProviderFactory.get_adapter(provider_name="mock")
        self.assertIsInstance(adapter, MockProviderAdapter)

    def test_env_var_provider_selection(self):
        os.environ["TRAVEL_PROVIDER"] = "mock"
        try:
            adapter = ProviderFactory.get_adapter()
            self.assertIsInstance(adapter, MockProviderAdapter)
        finally:
            os.environ.pop("TRAVEL_PROVIDER", None)

    def test_invalid_provider_raises_value_error(self):
        with self.assertRaises(ValueError):
            ProviderFactory.get_adapter(provider_name="unknown_provider_xyz")

    def test_custom_provider_registration(self):
        class CustomAdapter(BaseProviderAdapter):
            def search_flights(self, payload): return {"data": {}}
            def get_offer_request(self, offer_request_id): return {"data": {}}
            def list_offers(self, offer_request_id, params=None): return {"data": []}
            def get_offer(self, offer_id): return {"data": {}}
            def create_flight_order(self, payload): return {"data": {}}
            def pay_flight_order(self, order_id, payload): return {"data": {}}
            def get_flight_order(self, order_id): return {"data": {}}
            def list_flight_orders(self, limit=50): return {"data": []}
            def cancel_flight_order(self, payload): return {"data": {}}
            def tokenize_card(self, payload): return {"data": {}}
            def create_component_client_key(self): return {"data": {}}
            def create_three_d_secure_session(self, payload): return {"data": {}}
            def search_stays(self, payload): return {"data": {}}
            def get_stay_search_result(self, search_result_id): return {"data": {}}
            def get_stay_rates(self, search_result_id): return {"data": []}
            def create_stay_order(self, payload): return {"data": {}}
            def get_stay_order(self, order_id): return {"data": {}}
            def cancel_stay_order(self, order_id): return {"data": {}}
            def search_cars(self, payload): return {"data": {}}
            def get_car_offer(self, offer_id): return {"data": {}}
            def create_car_order(self, payload): return {"data": {}}
            def get_car_order(self, order_id): return {"data": {}}
            def cancel_car_order(self, offer_id_or_order_id): return {"data": {}}

        ProviderFactory.register_provider("custom", CustomAdapter)
        adapter = ProviderFactory.get_adapter(provider_name="custom")
        self.assertIsInstance(adapter, CustomAdapter)


class TestMockAdapter(unittest.TestCase):
    def test_mock_adapter_flights(self):
        adapter = MockProviderAdapter()
        res = adapter.search_flights({
            "slices": [{"origin": "JFK", "destination": "LHR", "departure_date": "2026-10-01"}],
            "passengers": [{"type": "adult"}]
        })
        self.assertIn("data", res)
        self.assertIn("offers", res["data"])
        self.assertTrue(len(res["data"]["offers"]) > 0)
        first_offer = res["data"]["offers"][0]
        self.assertEqual(first_offer["total_amount"], "450.00")
        self.assertEqual(first_offer["total_currency"], "USD")

    def test_mock_adapter_stays(self):
        adapter = MockProviderAdapter()
        res = adapter.search_stays({"check_in_date": "2026-10-01", "check_out_date": "2026-10-05"})
        self.assertIn("data", res)
        self.assertIn("results", res["data"])

    def test_mock_adapter_cars(self):
        adapter = MockProviderAdapter()
        res = adapter.search_cars({"pickup_location": "JFK"})
        self.assertIn("data", res)


class TestClientProviderSwitching(unittest.TestCase):
    def test_client_with_mock_provider(self):
        config = DuffelConfig(enable_cache=False)
        client = DuffelClient(config=config, provider_name="mock")
        self.assertIsInstance(client.adapter, MockProviderAdapter)

        # Test Flights Search via Service Schema
        slices = [FlightSliceQuery(origin="SFO", destination="JFK", departure_date="2026-10-01")]
        passengers = [Passenger(type="adult")]
        offers = client.flights.search(slices=slices, passengers=passengers)
        self.assertTrue(len(offers) > 0)
        self.assertIsInstance(offers[0], FlightOffer)
        self.assertEqual(offers[0].total_amount, "450.00")

        # Test Stays Search via Service Schema
        stays = client.stays.search(check_in_date="2026-10-01", check_out_date="2026-10-05")
        self.assertTrue(len(stays) > 0)

        # Test Cars Search via Service Schema
        cars = client.cars.search(
            pickup_location="SFO",
            dropoff_location="SFO",
            pickup_datetime="2026-10-01T10:00:00",
            dropoff_datetime="2026-10-05T10:00:00"
        )
        self.assertTrue(len(cars) > 0)


if __name__ == "__main__":
    unittest.main()
