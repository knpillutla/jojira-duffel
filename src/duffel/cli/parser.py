"""
Natural Language Prompt Extractor for Duffel CLI parameters.
"""

from datetime import datetime, timedelta
import calendar
import re
from typing import Any, Optional

from ..config import DuffelConfig

# Common airport/city IATA mapping for heuristic extraction
CITY_IATA_MAP = {
    "london": "LHR",
    "lhr": "LHR",
    "lon": "LHR",
    "lgw": "LGW",
    "new york": "JFK",
    "newyork": "JFK",
    "nyc": "JFK",
    "jfk": "JFK",
    "ewr": "EWR",
    "san diego": "SAN",
    "sandiego": "SAN",
    "san diego ca": "SAN",
    "australia": "SYD",
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
    "atlanta": "ATL",
    "atl": "ATL",
    "orlando": "MCO",
    "mco": "MCO",
    "oslo": "OSL",
    "osl": "OSL",
}


class PromptExtractor:
    """Extracts structured search parameters from natural language prompts."""

    @staticmethod
    def extract_natural_intent(prompt: str) -> dict[str, Any]:
        """
        Extract multi-category natural language search intent and parameters.
        Returns dict containing selected_types (list of 'flights', 'hotels', 'cars', 'attractions')
        and extracted search criteria.
        """
        text = prompt.lower()
        selected_types: list[str] = []

        flight_kw = ["flight", "flights", "fly", "flying", "airline", "plane", "nonstop", "one way", "round trip"]
        has_flight_keyword = any(w in text for w in flight_kw)
        
        # Check if 'from <location>' exists (excluding date prepositions like 'from sep', 'from october', 'from 2026-11-12')
        from_match = re.search(r"\bfrom\s+([a-z0-9]+)", text)
        if from_match:
            word = from_match.group(1)
            date_words = {"jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun", "june", "jul", "july", "aug", "august", "sep", "september", "oct", "october", "nov", "november", "dec", "december", "today", "tomorrow", "next", "this"}
            if not word.isdigit() and word not in date_words and "to " in text:
                has_flight_keyword = True

        if has_flight_keyword:
            selected_types.append("flights")


        # Price per night / lodging detection
        max_price_per_night = None
        price_night_match = re.search(r"(?:under|less than|max|up to|below|\$)\s*\$?(\d+(?:\.\d+)?)\s*(?:a|per|\/)?\s*(?:night|day)", text)
        if price_night_match:
            max_price_per_night = float(price_night_match.group(1))
            if "hotels" not in selected_types:
                selected_types.append("hotels")



        if any(w in text for w in ["hotel", "hotels", "stay", "stays", "resort", "resorts", "accommodation", "lodging", "room", "rooms"]):
            if "hotels" not in selected_types:
                selected_types.append("hotels")
        if any(w in text for w in ["car", "cars", "rental car", "car rental", "drive", "vehicle", "hertz", "suv", "auto"]):
            selected_types.append("cars")
        if any(w in text for w in ["attraction", "attractions", "things to do", "sightseeing", "tour", "tours", "activities", "visit", "museum", "landmarks", "itinerary", "places to see"]):
            selected_types.append("attractions")

        flight_info = PromptExtractor.extract_flight_info(prompt)
        stay_info = PromptExtractor.extract_stay_info(prompt)
        car_info = PromptExtractor.extract_car_info(prompt)

        slices = flight_info.get("slices") or []
        first_slice = slices[0] if slices and isinstance(slices[0], dict) else {}
        origin = first_slice.get("origin") or car_info.get("pickup_location")
        destination = first_slice.get("destination") or stay_info.get("location") or car_info.get("dropoff_location")
        
        dep_date = first_slice.get("departure_date") or stay_info.get("check_in_date")
        ret_date = flight_info.get("target_return_date") or stay_info.get("check_out_date")
        if not ret_date and len(slices) > 1:
            ret_date = slices[1].get("departure_date")

        # Extract adults & kids count (defaulting to 1 adult if unlisted)
        adult_match = re.search(r"(\d+)\s*adult", text)
        adults = int(adult_match.group(1)) if adult_match else 0

        child_match = re.search(r"(\d+)\s*(?:kid|child|children)", text)
        children = int(child_match.group(1)) if child_match else 0

        total_explicit = adults + children
        if total_explicit > 0:
            passengers_count = total_explicit
            if adults == 0:
                adults = 1
        else:
            adults = 1
            children = 0
            passengers_count = max(flight_info.get("passengers_count") or 1, 1)


        # Extract excluded airlines
        excluded_airlines = []
        exclude_match = re.search(r"(?:exclude|excluding|without|no)\s+([a-z\s]+?)(?=\s+airlines?|\s+flights|\s+on|\s+for|\s*$)", text)
        if exclude_match:
            ex_name = exclude_match.group(1).strip()
            if "frontier" in ex_name:
                excluded_airlines.append("Frontier Airlines")
            elif "spirit" in ex_name:
                excluded_airlines.append("Spirit Airlines")
            elif "delta" in ex_name:
                excluded_airlines.append("Delta Air Lines")
            elif "american" in ex_name:
                excluded_airlines.append("American Airlines")
            else:
                excluded_airlines.append(ex_name.title())

        # Extract preferred airline
        preferred_airline = None
        airline_code = None
        airlines_map = {
            "southwest airlines": ("Southwest Airlines", "WN"),
            "southwest": ("Southwest Airlines", "WN"),
            "wn": ("Southwest Airlines", "WN"),
            "delta air lines": ("Delta Air Lines", "DL"),
            "delta": ("Delta Air Lines", "DL"),
            "dl": ("Delta Air Lines", "DL"),
            "american airlines": ("American Airlines", "AA"),
            "american": ("American Airlines", "AA"),
            "aa": ("American Airlines", "AA"),
            "united airlines": ("United Airlines", "UA"),
            "united": ("United Airlines", "UA"),
            "ua": ("United Airlines", "UA"),
            "jetblue airways": ("JetBlue Airways", "B6"),
            "jetblue": ("JetBlue Airways", "B6"),
            "b6": ("JetBlue Airways", "B6"),
            "alaska airlines": ("Alaska Airlines", "AS"),
            "alaska": ("Alaska Airlines", "AS"),
            "as": ("Alaska Airlines", "AS"),
            "hawaiian airlines": ("Hawaiian Airlines", "HA"),
            "hawaiian": ("Hawaiian Airlines", "HA"),
            "ha": ("Hawaiian Airlines", "HA"),
            "frontier airlines": ("Frontier Airlines", "F9"),
            "frontier": ("Frontier Airlines", "F9"),
            "f9": ("Frontier Airlines", "F9"),
            "spirit airlines": ("Spirit Airlines", "NK"),
            "spirit": ("Spirit Airlines", "NK"),
            "nk": ("Spirit Airlines", "NK"),
            "allegiant air": ("Allegiant Air", "G4"),
            "allegiant": ("Allegiant Air", "G4"),
            "air canada": ("Air Canada", "AC"),
            "ac": ("Air Canada", "AC"),
            "british airways": ("British Airways", "BA"),
            "ba": ("British Airways", "BA"),
            "virgin atlantic": ("Virgin Atlantic", "VS"),
            "virgin": ("Virgin Atlantic", "VS"),
            "vs": ("Virgin Atlantic", "VS"),
            "lufthansa": ("Lufthansa", "LH"),
            "lh": ("Lufthansa", "LH"),
            "air france": ("Air France", "AF"),
            "af": ("Air France", "AF"),
            "klm": ("KLM Royal Dutch Airlines", "KL"),
            "qantas": ("Qantas", "QF"),
            "qf": ("Qantas", "QF"),
            "emirates": ("Emirates", "EK"),
            "ek": ("Emirates", "EK"),
            "qatar airways": ("Qatar Airways", "QR"),
            "qatar": ("Qatar Airways", "QR"),
            "singapore airlines": ("Singapore Airlines", "SQ"),
            "cathay pacific": ("Cathay Pacific", "CX"),
            "ana": ("All Nippon Airways", "NH"),
            "all nippon airways": ("All Nippon Airways", "NH"),
            "japan airlines": ("Japan Airlines", "JL"),
            "jal": ("Japan Airlines", "JL"),
        }
        for kw, (name, code) in airlines_map.items():
            if name in excluded_airlines:
                continue
            if re.search(r"(?<!exclude\s)(?<!excluding\s)(?<!without\s)(?<!no\s)\b" + re.escape(kw) + r"\b", text):
                preferred_airline = name
                airline_code = code
                break

        # Fallback to regex pattern for 'with/on/by/flying <airline>' if not found in static map
        if not preferred_airline:
            m_air = re.search(r"\b(?:with|on|by|flying|via)\s+([a-z0-9\s]+?)(?=\s+from|\s+to|\s+for|\s+between|\s+on|\s+in|\s+under|\s+over|\s+with|\s*$)", text)
            if m_air:
                cand = m_air.group(1).strip()
                reserved = {"economy", "business", "first", "flights", "hotels", "cars", "roundtrip", "one way", "return"}
                if cand and cand not in reserved and len(cand) > 2:
                    preferred_airline = cand.title()



        # Extract allowed cabin classes
        allowed_cabins = []
        if "premium" in text:
            allowed_cabins.append("premium_economy")
        if "business" in text:
            allowed_cabins.append("business")
        if "first" in text:
            allowed_cabins.append("first")
        if "economy" in text and "premium" not in text:
            allowed_cabins.append("economy")
        elif "economy" in text and "premium" in text and "economy" not in allowed_cabins:
            allowed_cabins.append("economy")

        if not allowed_cabins:
            allowed_cabins = [flight_info.get("cabin_class", "economy")]


        if not selected_types:
            if origin and destination:
                selected_types = ["flights"]
            elif destination:
                selected_types = ["hotels"]
            else:
                selected_types = ["flights"]

        # Deduplicate types while preserving order
        unique_types = []
        for t in selected_types:
            if t not in unique_types:
                unique_types.append(t)

        # Detect if user explicitly used "preferred" or "favorite" keywords
        is_preferred_airline = any(w in text for w in ["preferred", "favorite", "pref", "fav", "prefer"])

        return {
            "selected_types": unique_types,
            "origin": origin,
            "destination": destination,
            "departure_date": dep_date,
            "return_date": ret_date,
            "passengers": {
                "adults": adults,
                "children": children,
                "total": passengers_count,
            },
            "passengers_count": passengers_count,
            "cabin_class": allowed_cabins[0],
            "allowed_cabin_classes": allowed_cabins,
            "preferred_airline": preferred_airline or flight_info.get("preferred_airline"),
            "is_preferred_airline": is_preferred_airline,
            "preferred_hotel_brand": stay_info.get("preferred_hotel_brand"),
            "preferred_car_vendor": car_info.get("preferred_car_vendor"),
            "airline_code": airline_code or flight_info.get("airline_code"),
            "excluded_airlines": excluded_airlines,
            "max_price_per_night": max_price_per_night or flight_info.get("max_price_per_night"),

            "rooms": stay_info.get("rooms", 1),
            "driver_age": car_info.get("driver_age", 30),
            "interests": [],
            "duration_days": flight_info.get("duration_days"),
            "slices": [s.to_dict() if hasattr(s, "to_dict") else s for s in slices],
        }




    @staticmethod
    def missing_flight_fields(extracted: dict[str, Any]) -> list[str]:
        """Return required optimized-search fields that extraction did not resolve."""
        slices = extracted.get("slices") or []
        first_slice = slices[0] if slices and isinstance(slices[0], dict) else {}
        missing = []
        if not first_slice.get("origin"):
            missing.append("origin")
        if not first_slice.get("destination"):
            missing.append("destination")
        if not first_slice.get("departure_date"):
            missing.append("target_date")
        if not extracted.get("duration_days"):
            missing.append("duration_days")
        return missing


    @staticmethod
    def extract_flight_info(prompt: str) -> dict[str, Any]:
        """
        Extract flight search parameters from natural text.

        Returns dict with keys: trip_type, slices, cabin_class, passengers_count
        """
        llm_result = PromptExtractor._extract_flight_info_with_llm(prompt)
        if llm_result is not None:
            return llm_result

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

        # 2. Extract Dates (YYYY-MM-DD, MM/DD/YYYY, ordinal dates like 'oct 17th', or a named month)
        dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", prompt)
        if not dates:
            slash_dates = re.findall(r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b", prompt)
            if slash_dates:
                for m_str, d_str, y_str in slash_dates:
                    try:
                        m_num = int(m_str)
                        d_num = int(d_str)
                        y_num = int(y_str)
                        dates.append(f"{y_num:04d}-{m_num:02d}-{d_num:02d}")
                    except Exception:
                        pass
        if not dates:
            ordinal_dates = re.findall(
                r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(20\d{2}))?\b",
                text
            )

            if ordinal_dates:
                for m_str, d_str, y_str in ordinal_dates:
                    try:
                        m_num = datetime.strptime(m_str[:3], "%b").month
                        y_num = int(y_str) if y_str else datetime.now().year
                        d_num = int(d_str)
                        dates.append(f"{y_num:04d}-{m_num:02d}-{d_num:02d}")
                    except Exception:
                        pass
        if not dates:
            month_match = re.search(
                r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
                r"(?:\s+(20\d{2}))?\b",
                text,
            )
            if month_match:
                month_number = datetime.strptime(month_match.group(1), "%B").month
                year = int(month_match.group(2) or datetime.now().year)
                dates = [f"{year:04d}-{month_number:02d}-01"]
                extracted["target_return_date"] = (
                    f"{year:04d}-{month_number:02d}-{calendar.monthrange(year, month_number)[1]:02d}"
                )

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
            route_match = re.search(
                r"from\s+([a-z][a-z\s]*?)(?=\s+to\s+)"
                r".*?to\s+([a-z][a-z\s]*?)(?=\s+(?:in|on|for|and)|\s*$)",
                text,
            )
            if route_match:
                orig = PromptExtractor._resolve_iata(route_match.group(1).strip())
                dest = PromptExtractor._resolve_iata(route_match.group(2).strip())
                extracted["slices"].append({
                    "origin": orig,
                    "destination": dest,
                    "departure_date": dates[0] if dates else None,
                })
                return_dates = dates[1:] if len(dates) > 1 else []
            else:
                return_dates = []
                origin_match = re.search(
                    r"\bfrom\s+([a-z][a-z\s]*?)(?=\s+(?:to|in|on|for|and)|\s*$)", text
                )
                destination_match = re.search(
                    r"\bto\s+([a-z][a-z\s]*?)(?=\s+(?:in|on|from|for|and)|\s*$)", text
                )
                if origin_match and destination_match:
                    extracted["slices"].append({
                        "origin": PromptExtractor._resolve_iata(origin_match.group(1).strip()),
                        "destination": PromptExtractor._resolve_iata(destination_match.group(1).strip()),
                        "departure_date": dates[0] if dates else None,
                    })
                elif destination_match:
                    extracted["slices"].append({
                        "origin": "",
                        "destination": PromptExtractor._resolve_iata(destination_match.group(1).strip()),
                        "departure_date": dates[0] if dates else None,
                    })
            iata_codes = re.findall(r"\b[a-zA-Z]{3}\b", prompt)
            if not extracted["slices"] and len(iata_codes) >= 2:
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
    def _extract_flight_info_with_llm(prompt: str) -> Optional[dict[str, Any]]:
        """Use the configured LLM provider, falling back to other providers when available."""
        prompt = (prompt or "").lower().strip()
        config = DuffelConfig()
        if config.llm_provider == "openai" and config.openai_enabled and config.openai_api_key:
            result = PromptExtractor._extract_flight_info_with_openai(prompt)
            if result is not None:
                return result
        if config.gemini_enabled and config.gemini_api_key:
            return PromptExtractor._extract_flight_info_with_gemini(prompt)
        return None

    @staticmethod
    def _normalize_flight_result(result: dict[str, Any]) -> dict[str, Any]:
        """Normalize provider output to the field names and enum values used by the CLI."""
        normalized = dict(result)
        trip_type = str(normalized.get("trip_type") or "").lower().replace("-", "_").replace(" ", "_")
        normalized["trip_type"] = {
            "oneway": "one_way",
            "one_way": "one_way",
            "roundtrip": "round_trip",
            "round_trip": "round_trip",
            "multicity": "multi_city",
            "multi_city": "multi_city",
        }.get(trip_type, normalized.get("trip_type"))
        normalized.setdefault("cabin_class", "economy")
        normalized.setdefault("passengers_count", 1)
        for flight_slice in normalized.get("slices", []):
            if isinstance(flight_slice, dict):
                for field in ("origin", "destination"):
                    value = flight_slice.get(field)
                    if value:
                        flight_slice[field] = PromptExtractor._resolve_iata(str(value))
        return normalized

    @staticmethod
    def _extract_flight_info_with_openai(prompt: str) -> Optional[dict[str, Any]]:
        """Ask OpenAI GPT-4.1-mini to normalize a flight request to JSON."""
        config = DuffelConfig()
        if not config.openai_enabled or not config.openai_api_key:
            return None

        import json
        from urllib.request import Request, urlopen

        today = datetime.now().strftime("%Y-%m-%d")
        instruction = (
            f"Today is {today}. Extract the flight request as JSON only. Resolve city names "
            "to primary IATA airport codes. Resolve month names using the current year unless "
            "a year is stated. A named month means target_date is its first day and "
            "target_return_date is its last day. Extract requested trip duration separately. "
            "Return exactly: trip_type, slices, target_return_date, cabin_class, "
            "passengers_count, duration_days. Each slice has origin, destination, "
            "departure_date. Use null for unknown values. User request: " + prompt
        )
        payload = {
            "model": config.openai_model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            request = Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=15) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            content = response_data["choices"][0]["message"]["content"]
            result = json.loads(content)
            if isinstance(result, dict) and isinstance(result.get("slices"), list):
                return PromptExtractor._normalize_flight_result(result)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_flight_info_with_gemini(prompt: str) -> Optional[dict[str, Any]]:
        """Ask the configured Gemini model to normalize a flight request."""
        config = DuffelConfig()
        if not config.gemini_enabled or not config.gemini_api_key:
            return None

        import json
        from urllib.parse import quote
        from urllib.request import Request, urlopen

        today = datetime.now().strftime("%Y-%m-%d")
        instruction = (
            f"Extract this flight request as JSON. Today is {today}. "
            "Resolve city names to primary IATA airport codes. Resolve month names using "
            "the current year unless a year is stated. For 'in October for 4 days', use "
            "October 1 as target departure and October 31 as the target return boundary; use "
            "the requested duration separately as the trip length. Return only these "
            "keys: trip_type, slices, cabin_class, passengers_count, duration_days. "
            "slices must contain origin, destination, and departure_date. Use null for unknown "
            f"dates and one_way unless return travel is explicit. User request: {prompt}"
        )
        payload = {
            "contents": [{"parts": [{"text": instruction}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(config.gemini_model, safe='')}:generateContent"
            f"?key={quote(config.gemini_api_key, safe='')}"
        )
        try:
            request = Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=15) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            response_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(response_text)
            if isinstance(result, dict) and isinstance(result.get("slices"), list):
                return PromptExtractor._normalize_flight_result(result)
        except Exception:
            pass
        return None

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
            "preferred_hotel_brand": None,
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

        hotel_brands_map = {
            "ritz-carlton": "Ritz-Carlton", "ritz carlton": "Ritz-Carlton", "ritz": "Ritz-Carlton",
            "marriott": "Marriott", "hilton": "Hilton", "hyatt": "Hyatt",
            "holiday inn": "Holiday Inn", "intercontinental": "InterContinental",
            "radisson": "Radisson", "sheraton": "Sheraton", "westin": "Westin",
            "four seasons": "Four Seasons", "wyndham": "Wyndham", "best western": "Best Western",
            "accor": "Accor",
        }
        for kw, brand in hotel_brands_map.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                extracted["preferred_hotel_brand"] = brand
                break

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
            "preferred_car_vendor": None,
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

        car_vendors_map = {
            "hertz": "Hertz", "enterprise": "Enterprise", "avis": "Avis",
            "budget": "Budget", "sixt": "Sixt", "national": "National",
            "alamo": "Alamo", "thrifty": "Thrifty", "dollar": "Dollar", "europcar": "Europcar",
        }
        for kw, vendor in car_vendors_map.items():
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                extracted["preferred_car_vendor"] = vendor
                break

        return extracted

    @staticmethod
    def _resolve_iata(val: str) -> str:
        clean = val.strip().lower()
        if clean in CITY_IATA_MAP:
            return CITY_IATA_MAP[clean]
        if len(clean) == 3 and clean.isalpha():
            return clean.upper()
        return val.upper()
