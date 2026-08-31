"""
Unit tests for the CLI PromptExtractor natural language parser.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from duffel.cli.parser import PromptExtractor


class TestPromptExtractor(unittest.TestCase):
    def test_missing_flight_fields_reports_unresolved_input(self):
        missing = PromptExtractor.missing_flight_fields({"slices": [{"destination": "OSL"}]})

        self.assertEqual(missing, ["origin", "target_date", "duration_days"])

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "LLM_PROVIDER": "openai"})
    @patch("urllib.request.urlopen")
    def test_extract_flight_info_uses_openai_option(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = (
            '{"choices":[{"message":{"content":"'
            '{\\"trip_type\\":\\"one_way\\",\\"slices\\":[{\\"origin\\":\\"ATL\\",'
            '\\"destination\\":\\"OSL\\",\\"departure_date\\":\\"2026-10-01\\"}],'
            '\\"target_return_date\\":\\"2026-10-31\\",\\"duration_days\\":21}"}}]}'
        ).encode("utf-8")
        response.__enter__.return_value = response
        mock_urlopen.return_value = response

        info = PromptExtractor.extract_flight_info(
            "cheapest nonstop to oslo from atl in october for 21 days"
        )

        self.assertEqual(info["slices"][0]["origin"], "ATL")
        self.assertEqual(info["slices"][0]["destination"], "OSL")
        self.assertEqual(info["target_return_date"], "2026-10-31")
        self.assertEqual(info["duration_days"], 21)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(__import__("json").loads(request.data)["model"], "gpt-4.1-mini")

    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_destination_and_month_without_origin(self, _mock_llm):
        info = PromptExtractor.extract_flight_info(
            "cheapest nonstop to oslo in october for 7 days"
        )

        self.assertEqual(info["slices"][0]["origin"], "")
        self.assertEqual(info["slices"][0]["destination"], "OSL")
        self.assertEqual(info["slices"][0]["departure_date"], "2026-10-01")
        self.assertEqual(info["target_return_date"], "2026-10-31")
        self.assertEqual(info["duration_days"], 7)


    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_flight_info_fallback_handles_month_and_city(self, _mock_llm):
        info = PromptExtractor.extract_flight_info(
            "cheapest nonstop to oslo in october from atl for 4 days"
        )

        self.assertEqual(info["slices"][0]["origin"], "ATL")
        self.assertEqual(info["slices"][0]["destination"], "OSL")
        self.assertEqual(info["slices"][0]["departure_date"], "2026-10-01")
        self.assertEqual(info["target_return_date"], "2026-10-31")
        self.assertEqual(info["duration_days"], 4)

    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_flight_one_way(self, _mock_llm):
        prompt = "I want a one way flight from London to New York on 2026-11-15 for 2 adults in business class"
        info = PromptExtractor.extract_flight_info(prompt)
        self.assertEqual(info["trip_type"], "one_way")
        self.assertEqual(len(info["slices"]), 1)
        self.assertEqual(info["slices"][0]["origin"], "LHR")
        self.assertEqual(info["slices"][0]["destination"], "JFK")
        self.assertEqual(info["slices"][0]["departure_date"], "2026-11-15")
        self.assertEqual(info["cabin_class"], "business")
        self.assertEqual(info["passengers_count"], 2)

    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_flight_round_trip(self, _mock_llm):
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

    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_natural_intent_between_two_dates(self, _mock_llm):
        prompt = "flights from JFK to ZRH between 2026-09-17 and 2026-09-25"
        intent = PromptExtractor.extract_natural_intent(prompt)
        self.assertIn("from_date", intent)
        self.assertIn("to_date", intent)
        self.assertIn("duration_days", intent)
        self.assertEqual(intent["from_date"], "2026-09-17")
        self.assertEqual(intent["to_date"], "2026-09-25")
        self.assertEqual(intent["duration_days"], 8)
        self.assertEqual(intent["departure_date"], "2026-09-17")
        self.assertEqual(intent["return_date"], "2026-09-25")
        self.assertEqual(intent["trip_type"], "round_trip")

    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_natural_intent_one_way(self, _mock_llm):
        prompt = "one way flight from JFK to ZRH on 2026-09-17"
        intent = PromptExtractor.extract_natural_intent(prompt)
        self.assertEqual(intent["from_date"], "2026-09-17")
        self.assertIsNone(intent["to_date"])
        self.assertIsNone(intent["duration_days"])
        self.assertEqual(intent["trip_type"], "one_way")


    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_natural_intent_price_range(self, _mock_llm):
        prompt = "flights from JFK to ZRH between 2026-09-17 and 2026-09-25 between $200 and $500"
        intent = PromptExtractor.extract_natural_intent(prompt)
        self.assertIn("min_price", intent)
        self.assertIn("max_price", intent)
        self.assertEqual(intent["min_price"], 200.0)
        self.assertEqual(intent["max_price"], 500.0)

    @patch("duffel.cli.parser.PromptExtractor._extract_flight_info_with_llm", return_value=None)
    def test_extract_natural_intent_max_price_only(self, _mock_llm):
        prompt = "flights from JFK to ZRH under $350"
        intent = PromptExtractor.extract_natural_intent(prompt)
        self.assertIsNone(intent["min_price"])
        self.assertEqual(intent["max_price"], 350.0)


if __name__ == "__main__":
    unittest.main()


