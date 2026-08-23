"""
Natural Language Prompt Extractor for Duffel CLI parameters.
"""

from datetime import datetime, timedelta
import re
from typing import Any, Optional

# Common airport/city IATA mapping for heuristic extraction
CITY_IATA_MAP = {
    "london": "LHR",
    "lhr": "LHR",
    "lgw": "LGW",
    "new york": "JFK",
    "nyc": "JFK",
    "jfk": "JFK",
    "ewr": "EWR",
    "los angeles": "LAX",
    "lax": "LAX",
    "paris": "CDG",
    "cdg": "CDG",
    "tokyo": "HND",
    "hnd": "HND",
    "nrt": "NRT",
    "san francisco": "SFO",
    "sfo": "SFO",
    "chicago": "ORD",
    "ord": "ORD",
    "miami": "MIA",
    "mia": "MIA",
    "dubai": "DXB",
    "dxb": "DXB",
    "singapore": "SIN",
    "sin": "SIN",
    "sydney": "SYD",
    "syd": "SYD",
}


class PromptExtractor:
    """Extracts structured search parameters from natural language prompts."""

    @staticmethod
    def extract_flight_info(prompt: str) -> dict[str, Any]:
        """
        Extract flight search parameters from natural text.

        Returns dict with keys: trip_type, slices, cabin_class, passengers_count
        """
        text = prompt.lower()
        extracted: dict[str, Any] = {
            "trip_type": None,  # "one_way", "round_trip", "multi_city"
            "slices": [],
            "cabin_class": "economy",
            "passengers_count": 1,
        }

        # 1. Trip type detection
        if any(term in text for term in ["round trip", "return", "two way", "2 way", "back and forth"]):
            extracted["trip_type"] = "round_trip"
        elif any(term in text for term in ["multi city", "multicity", "multi-city", "multiple stops"]):
            extracted["trip_type"] = "multi_city"
        elif any(term in text for term in ["one way", "oneway", "single"]):
            extracted["trip_type"] = "one_way"

        # 2. Extract Dates (YYYY-MM-DD or MM/DD/YYYY)
        dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", prompt)

        # 3. Extract IATA / Cities using "from X to Y" pattern
        from_to_matches = re.findall(r"from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)(?=\s+on|\s+for|\s+in|\s+and|\s*$)", text)

        if from_to_matches:
            for idx, (orig_str, dest_str) in enumerate(from_to_matches):
                orig_iata = PromptExtractor._resolve_iata(orig_str.strip())
                dest_iata = PromptExtractor._resolve_iata(dest_str.strip())
                dep_date = dates[idx] if idx < len(dates) else None
                extracted["slices"].append({
                    "origin": orig_iata,
                    "destination": dest_iata,
                    "departure_date": dep_date
                })
        else:
            iata_codes = re.findall(r"\b[a-zA-Z]{3}\b", prompt)
            if len(iata_codes) >= 2:
                orig = iata_codes[0].upper()
                dest = iata_codes[1].upper()
                dep_date = dates[0] if dates else None
                extracted["slices"].append({
                    "origin": orig,
                    "destination": dest,
                    "departure_date": dep_date
                })

        # If round trip detected with 1 slice and 2 dates, auto add return slice
        if extracted["trip_type"] == "round_trip" and len(extracted["slices"]) == 1 and len(dates) >= 2:
            orig_first = extracted["slices"][0]["origin"]
            dest_first = extracted["slices"][0]["destination"]
            extracted["slices"].append({
                "origin": dest_first,
                "destination": orig_first,
                "departure_date": dates[1]
            })

        # 4. Extract Cabin Class
        if "business" in text:
            extracted["cabin_class"] = "business"
        elif "first" in text:
            extracted["cabin_class"] = "first"
        elif "premium" in text:
            extracted["cabin_class"] = "premium_economy"

        # 5. Extract passenger count
        pax_match = re.search(r"(\d+)\s*(adult|passenger|pax|people|person)", text)
        if pax_match:
            extracted["passengers_count"] = int(pax_match.group(1))

        # 6. Extract trip duration (days / weeks)
        duration_match = re.search(r"(?:for\s+(\d+)\s*days?|(\d+)\s*days?\s*trip|for\s+(\d+)\s*weeks?|(\d+)\s*weeks?\s*trip)", text)
        if duration_match:
            if duration_match.group(1):
                extracted["duration_days"] = int(duration_match.group(1))
            elif duration_match.group(2):
                extracted["duration_days"] = int(duration_match.group(2))
            elif duration_match.group(3):
                extracted["duration_days"] = int(duration_match.group(3)) * 7
            elif duration_match.group(4):
                extracted["duration_days"] = int(duration_match.group(4)) * 7
        else:
            extracted["duration_days"] = None

        return extracted

    @staticmethod
    def extract_stay_info(prompt: str) -> dict[str, Any]:
        """
        Extract stay/hotel parameters from text.
        """
        text = prompt.lower()
        extracted: dict[str, Any] = {
            "location": None,
            "check_in_date": None,
            "check_out_date": None,
            "guests_count": 1,
            "rooms": 1,
        }

        loc_match = re.search(r"(?:in|at|around|for)\s+([a-z\s]+?)(?=\s+from|\s+on|\s+for|\s+check|\s*$)", text)
        if loc_match:
            candidate = loc_match.group(1).strip()
            if candidate not in ["hotel", "stay", "accommodation"]:
                extracted["location"] = candidate.title()

        dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", prompt)
        if len(dates) >= 2:
            extracted["check_in_date"] = dates[0]
            extracted["check_out_date"] = dates[1]
        elif len(dates) == 1:
            extracted["check_in_date"] = dates[0]

        guest_match = re.search(r"(\d+)\s*(guest|adult|person|people)", text)
        if guest_match:
            extracted["guests_count"] = int(guest_match.group(1))

        room_match = re.search(r"(\d+)\s*(room)", text)
        if room_match:
            extracted["rooms"] = int(room_match.group(1))

        return extracted

    @staticmethod
    def extract_car_info(prompt: str) -> dict[str, Any]:
        """
        Extract car rental parameters from text.
        """
        text = prompt.lower()
        extracted: dict[str, Any] = {
            "pickup_location": None,
            "dropoff_location": None,
            "pickup_datetime": None,
            "dropoff_datetime": None,
            "driver_age": 30,
        }

        pick_match = re.search(r"(?:at|from|in)\s+([a-z0-9\s]+?)(?=\s+to|\s+from|\s+on|\s+for|\s*$)", text)
        if pick_match:
            extracted["pickup_location"] = PromptExtractor._resolve_iata(pick_match.group(1).strip())

        drop_match = re.search(r"to\s+([a-z0-9\s]+?)(?=\s+on|\s+from|\s+for|\s*$)", text)
        if drop_match:
            extracted["dropoff_location"] = PromptExtractor._resolve_iata(drop_match.group(1).strip())
        elif extracted["pickup_location"]:
            extracted["dropoff_location"] = extracted["pickup_location"]

        dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", prompt)
        if len(dates) >= 2:
            extracted["pickup_datetime"] = f"{dates[0]}T10:00:00Z"
            extracted["dropoff_datetime"] = f"{dates[1]}T10:00:00Z"
        elif len(dates) == 1:
            extracted["pickup_datetime"] = f"{dates[0]}T10:00:00Z"

        age_match = re.search(r"(?:age\s*(\d+)|(\d+)\s*(?:years?\s*old|age|yo))", text)
        if age_match:
            extracted["driver_age"] = int(age_match.group(1) or age_match.group(2))

        return extracted

    @staticmethod
    def _resolve_iata(val: str) -> str:
        clean = val.strip().lower()
        if clean in CITY_IATA_MAP:
            return CITY_IATA_MAP[clean]
        if len(clean) == 3 and clean.isalpha():
            return clean.upper()
        return val.upper()
