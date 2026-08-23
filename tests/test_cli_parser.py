"""
Unit tests for the CLI PromptExtractor natural language parser.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.cli.parser import PromptExtractor


class TestPromptExtractor(unittest.TestCase):
    def test_extract_flight_one_way(self):
        prompt = "I want a one way flight from London to New York on 2026-11-15 for 2 adults in business class"
        info = PromptExtractor.extract_flight_info(prompt)
        self.assertEqual(info["trip_type"], "one_way")
        self.assertEqual(len(info["slices"]), 1)
        self.assertEqual(info["slices"][0]["origin"], "LHR")
        self.assertEqual(info["slices"][0]["destination"], "JFK")
        self.assertEqual(info["slices"][0]["departure_date"], "2026-11-15")
        self.assertEqual(info["cabin_class"], "business")
        self.assertEqual(info["passengers_count"], 2)

    def test_extract_flight_round_trip(self):
        prompt = "Round trip flight from London to New York on 2026-11-15 and 2026-11-22"
        info = PromptExtractor.extract_flight_info(prompt)
        self.assertEqual(info["trip_type"], "round_trip")
        self.assertEqual(len(info["slices"]), 2)
        self.assertEqual(info["slices"][0]["origin"], "LHR")
        self.assertEqual(info["slices"][0]["destination"], "JFK")
        self.assertEqual(info["slices"][1]["origin"], "JFK")
        self.assertEqual(info["slices"][1]["destination"], "LHR")

    def test_extract_stay_info(self):
        prompt = "Hotel in Paris from 2026-10-01 to 2026-10-05 for 3 guests and 2 rooms"
        info = PromptExtractor.extract_stay_info(prompt)
        self.assertEqual(info["location"], "Paris")
        self.assertEqual(info["check_in_date"], "2026-10-01")
        self.assertEqual(info["check_out_date"], "2026-10-05")
        self.assertEqual(info["guests_count"], 3)
        self.assertEqual(info["rooms"], 2)

    def test_extract_car_info(self):
        prompt = "Car rental at MIA to MIA from 2026-12-01 to 2026-12-07 for driver age 25"
        info = PromptExtractor.extract_car_info(prompt)
        self.assertEqual(info["pickup_location"], "MIA")
        self.assertEqual(info["dropoff_location"], "MIA")
        self.assertEqual(info["pickup_datetime"], "2026-12-01T10:00:00Z")
        self.assertEqual(info["dropoff_datetime"], "2026-12-07T10:00:00Z")
        self.assertEqual(info["driver_age"], 25)


if __name__ == "__main__":
    unittest.main()
