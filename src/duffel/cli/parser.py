"""
Natural Language Prompt Extractor for Duffel CLI parameters.
"""

from contextvars import ContextVar
from datetime import datetime, timedelta
import calendar
import re
import threading
from typing import Any, Optional

from ..config import DuffelConfig

prompt_parser_meta: ContextVar[dict[str, Any]] = ContextVar("prompt_parser_meta", default={})


class PromptParserTracker:
    """Thread-safe global tracker for recording prompt parsing metadata across sync and async contexts."""
    _meta: dict[int, dict[str, Any]] = {}
    _lock = threading.Lock()
    _latest: dict[str, Any] = {}

    @classmethod
    def set(cls, data: dict[str, Any]):
        thread_id = threading.get_ident()
        with cls._lock:
            cls._meta[thread_id] = data
            cls._latest = dict(data)

    @classmethod
    def get_latest(cls) -> dict[str, Any]:
        with cls._lock:
            return dict(cls._latest)

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._meta.clear()
            cls._latest = {}


def _save_llm_debug_output(category: str, data: dict[str, Any], identifier: str = ""):
    """
    Saves LLM extraction and prompt analysis payloads into output/llm/llm_input_extraction.json for debugging purposes.
    """
    import os
    import json
    filename = "llm_input_extraction.json"
    folder = os.path.join("output", "llm")
    try:
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[LLM DEBUG EXPORT NOTICE] Failed writing debug JSON to '{folder}/{filename}': {e}")


# Common airport/city IATA mapping for heuristic extraction
CITY_IATA_MAP = {
    # Canada
    "calgary": "YYC",
    "yyc": "YYC",
    "vancouver": "YVR",
    "yvr": "YVR",
    "toronto": "YYZ",
    "yyz": "YYZ",
    "montreal": "YUL",
    "yul": "YUL",
    "edmonton": "YEG",
    "yeg": "YEG",
    "ottawa": "YOW",
    "yow": "YOW",
    "winnipeg": "YWG",
    "ywg": "YWG",
    "halifax": "YHZ",
    "yhz": "YHZ",
    "quebec": "YQB",
    "quebec city": "YQB",
    "yqb": "YQB",
    "victoria": "YYJ",
    "yyj": "YYJ",

    "europe": "LHR",
    "europe hub": "LHR",
    "asia": "SIN",
    "india": "DEL",
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
    "melbourne": "MEL",
    "mel": "MEL",
    "atlanta": "ATL",
    "atl": "ATL",
    "orlando": "MCO",
    "mco": "MCO",
    "oslo": "OSL",
    "osl": "OSL",
    "seattle": "SEA",
    "sea": "SEA",
    "boston": "BOS",
    "bos": "BOS",
    "washington": "IAD",
    "iad": "IAD",
    "hyderabad": "HYD",
    "hyderabad,india": "HYD",
    "hyderabad, india": "HYD",
    "hyd": "HYD",
    "delhi": "DEL",
    "del": "DEL",
    "mumbai": "BOM",
    "bom": "BOM",
    "bangalore": "BLR",
    "blr": "BLR",
    "chennai": "MAA",
    "maa": "MAA",
    "kolkata": "CCU",
    "ccu": "CCU",
    "houston": "IAH",
    "iah": "IAH",
    "denver": "DEN",
    "den": "DEN",
    "las vegas": "LAS",
    "las": "LAS",
    "phoenix": "PHX",
    "phx": "PHX",
    "honolulu": "HNL",
    "hnl": "HNL",
    "columbus": "CMH",
    "columbus oh": "CMH",
    "columbus, oh": "CMH",
    "cmh": "CMH",
    "cleveland": "CLE",
    "cle": "CLE",
    "cincinnati": "CVG",
    "cvg": "CVG",
    "detroit": "DTW",
    "dtw": "DTW",
    "pittsburgh": "PIT",
    "pit": "PIT",
    "minneapolis": "MSP",
    "msp": "MSP",
    "salt lake city": "SLC",
    "slc": "SLC",
    "baltimore": "BWI",
    "bwi": "BWI",
    "charlotte": "CLT",
    "clt": "CLT",
    "raleigh": "RDU",
    "rdu": "RDU",
    "nashville": "BNA",
    "bna": "BNA",
    "st louis": "STL",
    "stl": "STL",
    "kansas city": "MCI",
    "mci": "MCI",
    "indianapolis": "IND",
    "ind": "IND",

    # Europe, Asia & World
    "rome": "FCO",
    "fco": "FCO",
    "milan": "MXP",
    "mxp": "MXP",
    "madrid": "MAD",
    "mad": "MAD",
    "barcelona": "BCN",
    "bcn": "BCN",
    "frankfurt": "FRA",
    "fra": "FRA",
    "munich": "MUC",
    "muc": "MUC",
    "amsterdam": "AMS",
    "ams": "AMS",
    "zurich": "ZRH",
    "zrh": "ZRH",
    "vienna": "VIE",
    "vie": "VIE",
    "dublin": "DUB",
    "dub": "DUB",
    "delhi": "DEL",
    "new delhi": "DEL",
    "del": "DEL",
    "mumbai": "BOM",
    "bom": "BOM",
    "bengaluru": "BLR",
    "bangalore": "BLR",
    "blr": "BLR",
    "bangkok": "BKK",
    "bkk": "BKK",
    "seoul": "ICN",
    "icn": "ICN",
    "beijing": "PEK",
    "pek": "PEK",
    "shanghai": "PVG",
    "pvg": "PVG",
    "hong kong": "HKG",
    "hkg": "HKG",
}


class PromptExtractor:
    """Extracts structured search parameters from natural language prompts."""

    @staticmethod
    def extract_natural_intent(prompt: str, user_location: Optional[str] = None) -> dict[str, Any]:
        """
        Extract multi-category natural language search intent and parameters.
        Returns dict containing selected_types (list of 'flights', 'hotels', 'cars', 'attractions')
        and extracted search criteria. Accepts user_location header for nearest origin fallback.
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

        flight_info = PromptExtractor.extract_flight_info(prompt, user_location=user_location)
        stay_info = PromptExtractor.extract_stay_info(prompt)
        car_info = PromptExtractor.extract_car_info(prompt)

        slices = flight_info.get("slices") or []
        first_slice = slices[0] if slices and isinstance(slices[0], dict) else {}
        origin = flight_info.get("origin") or first_slice.get("origin") or car_info.get("pickup_location")
        destination = flight_info.get("destination") or first_slice.get("destination") or stay_info.get("location") or car_info.get("dropoff_location")

        if destination:
            destination_str = re.sub(r"\s+from\s+.*$", "", str(destination), flags=re.IGNORECASE).strip()
            destination_str = re.sub(r"^(?:to|in|for|visit|trip\s+to)\s+", "", destination_str, flags=re.IGNORECASE).strip()
            destination = PromptExtractor._resolve_iata(destination_str) or destination_str

        # Fallback regex search for route e.g. "from Atlanta to Berlin" or "to Berlin from Atlanta"
        if not origin or not destination or (destination and "from" in str(destination).lower()):
            route_match = re.search(r"from\s+([a-z0-9\s,]+?)\s+to\s+([a-z0-9\s,]+?)(?=\s+(?:from|on|for|in|during|departing|returning|between|with|under|\d)|\s*$)", text, re.IGNORECASE)
            if route_match:
                if not origin:
                    origin = PromptExtractor._resolve_iata(route_match.group(1).strip())
                if not destination or "from" in str(destination).lower():
                    destination = PromptExtractor._resolve_iata(route_match.group(2).strip())
            else:
                to_from_match = re.search(r"(?:to|in|visit)\s+([a-z0-9\s,]+?)\s+from\s+([a-z0-9\s,]+?)(?=\s+(?:from|on|for|in|during|departing|returning|between|with|under|\d)|\s*$)", text, re.IGNORECASE)
                if to_from_match:
                    if not destination or "from" in str(destination).lower():
                        destination = PromptExtractor._resolve_iata(to_from_match.group(1).strip())
                    if not origin:
                        origin = PromptExtractor._resolve_iata(to_from_match.group(2).strip())

        # Fallback origin to user's location header if origin is still missing
        if not origin and user_location:
            user_iata = PromptExtractor._resolve_iata(user_location)
            if user_iata and len(user_iata) == 3 and user_iata != destination:
                origin = user_iata
                if slices and isinstance(slices[0], dict):
                    slices[0]["origin"] = user_iata
                else:
                    slices = [{"origin": user_iata, "destination": destination, "departure_date": None}]
                    flight_info["slices"] = slices

        trip_type = flight_info.get("trip_type")
        dep_date = first_slice.get("departure_date") or stay_info.get("check_in_date") or flight_info.get("from_date") or flight_info.get("departure_date")
        ret_date = flight_info.get("to_date") or flight_info.get("target_return_date") or stay_info.get("check_out_date")
        if not ret_date and len(slices) > 1 and isinstance(slices[1], dict):
            ret_date = slices[1].get("departure_date")

        from_date = flight_info.get("from_date") or dep_date
        to_date = flight_info.get("to_date") or ret_date



        duration = flight_info.get("duration") if flight_info.get("duration") is not None else flight_info.get("duration_days")
        if duration is None:
            dur_m = re.search(r"(\d+)\s*(?:-| )?\s*(?:day|days|night|nights|d)\b", text)
            if dur_m:
                try:
                    duration = int(dur_m.group(1))
                except Exception:
                    pass
            elif "week" in text:
                duration = 7

        if from_date and to_date and duration is None:
            try:
                d1 = datetime.strptime(from_date, "%Y-%m-%d")
                d2 = datetime.strptime(to_date, "%Y-%m-%d")
                dur = (d2 - d1).days
                if dur > 0:
                    duration = dur
            except Exception:
                pass

        if from_date and duration and not to_date:
            try:
                d1 = datetime.strptime(from_date, "%Y-%m-%d")
                to_date = (d1 + timedelta(days=int(duration))).strftime("%Y-%m-%d")
                ret_date = to_date
            except Exception:
                pass

        # If no dates are specified in input: start date = today + 15, end date = today + 15 + duration (default 4)
        if not from_date and not dep_date:
            now_base = datetime.now()
            default_dur = int(duration) if (duration is not None and int(duration) > 0) else 4
            duration = default_dur
            start_dt = now_base + timedelta(days=15)
            end_dt = now_base + timedelta(days=15 + default_dur)
            from_date = start_dt.strftime("%Y-%m-%d")
            to_date = end_dt.strftime("%Y-%m-%d")
            dep_date = from_date
            ret_date = to_date
            if slices and isinstance(slices[0], dict) and not slices[0].get("departure_date"):
                slices[0]["departure_date"] = from_date

        is_explicit_one_way = any(w in text for w in ["one way", "oneway", "single"])
        if is_explicit_one_way:
            trip_type = "one_way"
        elif from_date and to_date and not trip_type and ("between" in text or " to " in text):
            trip_type = "round_trip"

        # Extract min and max price range
        min_price = flight_info.get("min_price")
        max_price = flight_info.get("max_price")

        price_range_match = re.search(
            r"(?:price|budget|cost)?\s*(?:between|from)?\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:to|and|-|\s+to\s+)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|\$|\b)",
            text,
            flags=re.IGNORECASE
        )
        if price_range_match:
            try:
                val1 = float(price_range_match.group(1))
                val2 = float(price_range_match.group(2))
                if val1 < 1900 and val2 < 1900 and val1 > 0 and val2 > val1:
                    if min_price is None:
                        min_price = val1
                    if max_price is None:
                        max_price = val2
            except Exception:
                pass

        if max_price is None:
            max_m = re.search(r"(?:under|less than|max|up to|below|budget of)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|\$)?\b", text)
            if max_m:
                try:
                    val = float(max_m.group(1))
                    if val < 1900:
                        max_price = val
                except Exception:
                    pass

        if min_price is None:
            min_m = re.search(r"(?:over|more than|above|min|at least|from \$)\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars|\$)?\b", text)
            if min_m:
                try:
                    val = float(min_m.group(1))
                    if val < 1900:
                        min_price = val
                except Exception:
                    pass

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

        inc_airlines = flight_info.get("included_airlines") or []
        if preferred_airline and preferred_airline not in inc_airlines:
            inc_airlines.insert(0, preferred_airline)

        resolved_trip_type = trip_type or ("round_trip" if (from_date and to_date) else "one_way")
        resolved_dep_date = from_date or dep_date
        resolved_ret_date = to_date if resolved_trip_type != "one_way" else None

        intent = {
            "selected_types": unique_types,
            "trip_type": resolved_trip_type,
            "origin": origin,
            "destination": destination,
            "departure_date": resolved_dep_date,
            "return_date": resolved_ret_date,
            "from_date": from_date or resolved_dep_date,
            "to_date": to_date or resolved_ret_date,
            "min_price": min_price,
            "max_price": max_price,
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
            "included_airlines": inc_airlines,
            "excluded_airlines": excluded_airlines or flight_info.get("excluded_airlines", []),
            "preferred_hotel_brand": stay_info.get("preferred_hotel_brand"),
            "preferred_car_vendor": car_info.get("preferred_car_vendor"),
            "airline_code": airline_code or flight_info.get("airline_code"),
            "max_price_per_night": max_price_per_night or flight_info.get("max_price_per_night"),

            "rooms": stay_info.get("rooms", 1),
            "driver_age": car_info.get("driver_age", 30),
            "interests": [],
            "duration_days": duration,
            "slices": [s.to_dict() if hasattr(s, "to_dict") else s for s in slices],
        }

        # Check if key parameters are missing or unmapped, and call LLM pre-processing enrichment
        needs_enrichment = (
            not intent.get("origin") or len(str(intent.get("origin"))) != 3 or
            not intent.get("destination") or len(str(intent.get("destination"))) != 3 or
            not intent.get("departure_date") or
            intent.get("duration_days") is None
        )
        if needs_enrichment:
            intent = PromptExtractor.enrich_missing_intent_with_llm(prompt, intent, user_location=user_location)

        prev_meta = PromptParserTracker.get_latest()
        if prev_meta and prev_meta.get("llm_used"):
            meta = {
                "engine": prev_meta.get("engine"),
                "llm_used": True,
                "extracted_json": intent,
            }
        else:
            meta = {
                "engine": prev_meta.get("engine", "Local Deterministic Engine (Built-in Regex)"),
                "llm_used": False,
                "extracted_json": intent,
            }
        prompt_parser_meta.set(meta)
        PromptParserTracker.set(meta)

        return intent




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
    def extract_flight_info(prompt: str, user_location: Optional[str] = None) -> dict[str, Any]:
        """
        Extract flight search parameters from natural text.

        Returns dict with keys: trip_type, slices, cabin_class, passengers_count
        """
        llm_result = PromptExtractor._extract_flight_info_with_llm(prompt, user_location=user_location)
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
        from_to_matches = re.findall(
            r"\bfrom\s+([a-z0-9\s,]+?)\s+to\s+([a-z0-9\s,]+?)(?=\s+(?:from|on|for|in|during|departing|returning|between|with|under|\d)|\s*$)",
            text,
            flags=re.IGNORECASE
        )

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

        # If round trip or 2 dates detected with 1 slice, auto add return slice
        if len(dates) >= 2:
            from_date = dates[0]
            to_date = dates[1]
            extracted["from_date"] = from_date
            extracted["to_date"] = to_date
            extracted["target_return_date"] = to_date
            try:
                d1 = datetime.strptime(from_date, "%Y-%m-%d")
                d2 = datetime.strptime(to_date, "%Y-%m-%d")
                dur = (d2 - d1).days
                if dur > 0:
                    extracted["duration"] = dur
                    extracted["duration_days"] = dur
            except Exception:
                pass

            if not extracted.get("trip_type") or extracted.get("trip_type") == "one_way":
                if any(w in text for w in ["round trip", "between", " to ", "return", "back and forth"]) or not any(w in text for w in ["one way", "oneway", "single"]):
                    extracted["trip_type"] = "round_trip"

            if extracted["trip_type"] == "round_trip" and len(extracted["slices"]) == 1:
                orig_first = extracted["slices"][0]["origin"]
                dest_first = extracted["slices"][0]["destination"]
                extracted["slices"].append({
                    "origin": dest_first,
                    "destination": orig_first,
                    "departure_date": to_date
                })
        elif len(dates) == 1:
            extracted["from_date"] = dates[0]

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
        extracted.setdefault("duration", None)
        extracted.setdefault("duration_days", None)
        duration_match = re.search(r"(?:for\s+(\d+)\s*days?|(\d+)\s*days?\s*trip|for\s+(\d+)\s*weeks?|(\d+)\s*weeks?\s*trip)", text)
        if duration_match:
            dur = None
            if duration_match.group(1):
                dur = int(duration_match.group(1))
            elif duration_match.group(2):
                dur = int(duration_match.group(2))
            elif duration_match.group(3):
                dur = int(duration_match.group(3)) * 7
            elif duration_match.group(4):
                dur = int(duration_match.group(4)) * 7
            if dur is not None:
                extracted["duration"] = dur
                extracted["duration_days"] = dur

        if extracted.get("from_date") and extracted.get("duration") and not extracted.get("to_date"):
            try:
                d1 = datetime.strptime(extracted["from_date"], "%Y-%m-%d")
                calculated_to = (d1 + timedelta(days=extracted["duration"])).strftime("%Y-%m-%d")
                extracted["to_date"] = calculated_to
                extracted["target_return_date"] = calculated_to
            except Exception:
                pass

        prompt_parser_meta.set({
            "engine": "Local Deterministic Engine (Built-in Regex)",
            "llm_used": False,
            "extracted_json": extracted,
        })
        return extracted

    @staticmethod
    def _extract_flight_info_with_llm(prompt: str, user_location: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Use the configured LLM extraction provider, falling back to other providers when available."""
        prompt = (prompt or "").lower().strip()
        config = DuffelConfig()
        provider = getattr(config, "llm_extraction_provider", "") or getattr(config, "llm_provider", "openai")
        if provider == "gemini":
            if config.gemini_enabled and config.gemini_api_key:
                result = PromptExtractor._extract_flight_info_with_gemini(prompt)
                if result is not None:
                    return result
            if config.openai_enabled and config.openai_api_key:
                return PromptExtractor._extract_flight_info_with_openai(prompt, user_location=user_location)
        else:
            if config.openai_enabled and config.openai_api_key:
                result = PromptExtractor._extract_flight_info_with_openai(prompt, user_location=user_location)
                if result is not None:
                    return result
            if config.gemini_enabled and config.gemini_api_key:
                return PromptExtractor._extract_flight_info_with_gemini(prompt)
        return None

    @staticmethod
    def _normalize_flight_result(result: dict[str, Any]) -> dict[str, Any]:
        """Normalize provider output to the field names and enum values used by the CLI."""
        normalized = dict(result)
        slices = normalized.get("slices") or []
        first_slice = slices[0] if slices and isinstance(slices[0], dict) else {}

        origin = normalized.get("origin") or first_slice.get("origin")
        destination = normalized.get("destination") or first_slice.get("destination")

        if origin:
            normalized["origin"] = PromptExtractor._resolve_iata(str(origin))
        if destination:
            normalized["destination"] = PromptExtractor._resolve_iata(str(destination))

        from_date = normalized.get("from_date") or first_slice.get("departure_date") or normalized.get("departure_date")
        to_date = normalized.get("to_date") or normalized.get("target_return_date") or normalized.get("return_date")
        if not to_date and len(slices) > 1 and isinstance(slices[1], dict):
            to_date = slices[1].get("departure_date")

        if not slices and normalized.get("origin") and normalized.get("destination"):
            normalized["slices"] = [{
                "origin": normalized["origin"],
                "destination": normalized["destination"],
                "departure_date": from_date
            }]
            slices = normalized["slices"]

        duration = normalized.get("duration") if normalized.get("duration") is not None else normalized.get("duration_days")

        if from_date and to_date and duration is None:
            try:
                d1 = datetime.strptime(from_date, "%Y-%m-%d")
                d2 = datetime.strptime(to_date, "%Y-%m-%d")
                dur = (d2 - d1).days
                if dur > 0:
                    duration = dur
            except Exception:
                pass

        if from_date and duration and not to_date:
            try:
                d1 = datetime.strptime(from_date, "%Y-%m-%d")
                to_date = (d1 + timedelta(days=int(duration))).strftime("%Y-%m-%d")
            except Exception:
                pass

        raw_trip_type = str(normalized.get("trip_type") or "").lower().replace("-", "_").replace(" ", "_")
        normalized["trip_type"] = {
            "oneway": "one_way",
            "one_way": "one_way",
            "single": "one_way",
            "roundtrip": "round_trip",
            "round_trip": "round_trip",
            "multicity": "multi_city",
            "multi_city": "multi_city",
        }.get(raw_trip_type, normalized.get("trip_type") or ("round_trip" if (from_date and to_date) else "one_way"))

        if normalized.get("trip_type") == "one_way" and not (from_date and to_date and "between" in str(result).lower()):
            normalized["target_return_date"] = None
            normalized["to_date"] = None
            if isinstance(normalized.get("slices"), list) and len(normalized["slices"]) > 1:
                normalized["slices"] = [normalized["slices"][0]]
        else:
            normalized["target_return_date"] = to_date

        min_price = normalized.get("min_price")
        max_price = normalized.get("max_price")
        try:
            min_price = float(min_price) if min_price is not None else None
        except Exception:
            min_price = None
        try:
            max_price = float(max_price) if max_price is not None else None
        except Exception:
            max_price = None

        normalized["min_price"] = min_price
        normalized["max_price"] = max_price
        normalized["from_date"] = from_date
        normalized["to_date"] = to_date
        normalized["duration_days"] = duration
        normalized["departure_date"] = from_date
        normalized["return_date"] = to_date if normalized["trip_type"] != "one_way" else None

        # Clean up invalid airline extractions (e.g. dates, months, 'sep 8')
        def _is_valid_airline(val: Any) -> bool:
            if not val or not isinstance(val, str):
                return False
            s = val.strip().lower()
            if any(m in s for m in ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "2026", "2027"]):
                return False
            if any(w in s for w in ["on ", "from ", "to ", "in ", "during ", "departing", "returning"]):
                return False
            return len(s) >= 2

        pref = normalized.get("preferred_airline")
        if pref and not _is_valid_airline(pref):
            normalized["preferred_airline"] = None

        inc = normalized.get("included_airlines")
        if isinstance(inc, list):
            normalized["included_airlines"] = [x for x in inc if _is_valid_airline(x)]

        exc = normalized.get("excluded_airlines")
        if isinstance(exc, list):
            normalized["excluded_airlines"] = [x for x in exc if _is_valid_airline(x)]

        # Extract meal preferences & dietary restrictions from prompt or LLM result
        raw_prefs = result.get("preferences") or {}
        pref_meals = raw_prefs.get("meal_preferences") or normalized.get("meal_preferences") or []
        pref_cuisines = raw_prefs.get("favorite_cuisines") or normalized.get("favorite_cuisines") or []
        pref_dietary = raw_prefs.get("dietary_restrictions") or normalized.get("dietary_restrictions") or []

        normalized["preferences"] = {
            "meal_preferences": pref_meals,
            "favorite_cuisines": pref_cuisines,
            "dietary_restrictions": pref_dietary,
        }
        normalized["meal_preferences"] = pref_meals
        normalized["favorite_cuisines"] = pref_cuisines
        normalized["dietary_restrictions"] = pref_dietary

        normalized.setdefault("cabin_class", "economy")
        normalized.setdefault("passengers_count", 1)
        normalized.setdefault("included_airlines", [])
        normalized.setdefault("excluded_airlines", [])
        for flight_slice in normalized.get("slices", []):
            if isinstance(flight_slice, dict):
                for field in ("origin", "destination"):
                    value = flight_slice.get(field)
                    if value:
                        flight_slice[field] = PromptExtractor._resolve_iata(str(value))
        return normalized

    @staticmethod
    def _extract_flight_info_with_openai(prompt: str, user_location: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Ask OpenAI GPT-4.1-mini to normalize a flight request to JSON."""
        config = DuffelConfig()
        if not config.openai_enabled or not config.openai_api_key:
            return None

        import json
        from urllib.request import Request, urlopen

        today = datetime.now().strftime("%Y-%m-%d")
        instruction = (
            f"Today is {today}. Extract the flight request as JSON only.\n"
            "STRICT RULES:\n"
            "1. trip_type: MUST be 'one_way' if user explicitly says 'one way', 'oneway', or 'single' (even if two dates or date range are specified). MUST be 'round_trip' if user requests roundtrip/return or specifies two dates without saying one way. MUST be 'multi_city' for multiple destinations.\n"
            "2. IATA CODES & SLICES: Resolve all city names strictly to 3-letter IATA airport codes in uppercase (e.g. 'Calgary' -> 'YYC', 'Atlanta' -> 'ATL', 'Columbus' -> 'CMH', 'Paris' -> 'CDG', 'London' -> 'LHR', 'New York' -> 'JFK', 'Zurich' -> 'ZRH'). Set top-level 'origin' to departure IATA code, top-level 'destination' to arrival IATA code, and populate 'slices': [{'origin': 'ATL', 'destination': 'CMH', 'departure_date': 'YYYY-MM-DD'}]. NEVER return city names or empty slices.\n"
            "3. DATES & DURATION: Extract 'from_date' (YYYY-MM-DD start date), 'to_date' (YYYY-MM-DD end date), and 'duration_days' (integer duration of trip in days).\n"
            "4. PRICE RANGE: Extract 'min_price' (float or null) and 'max_price' (float or null) if user specifies budget or price limits.\n"
            "5. AIRLINES: Set 'preferred_airline', 'included_airlines', and 'excluded_airlines' ONLY if user explicitly names a recognized airline or alliance (e.g. 'Delta', 'United', 'American', 'British Airways'). NEVER treat date strings like 'on sep 8' or prepositions as airlines! Set to null or empty array if no airline is explicitly requested.\n"
            "6. STOPOVERS & BREAKS: If user requests a stay in a destination for N days (e.g. 'for 21 days in Hyderabad') with a break in an intermediate city (e.g. 'with a 1 week break in London'), add the break duration (+7 days) to the destination stay duration so the total trip length is 28 days: Slice 1: ATL -> LHR on start date (Oct 1); Slice 2: LHR -> HYD 7 days later (Oct 8); Slice 3: HYD -> ATL 21 days after arriving in HYD (Oct 29, total 28 days from start). Set trip_type: 'multi_city'.\n"
            "7. MEAL PREFERENCES & DIET: Extract meal preferences, favorite cuisines, and dietary restrictions mentioned (e.g. 'vegetarian', 'vegan', 'halal', 'kosher', 'gluten-free', 'Italian', 'French', 'Japanese', 'fine dining', 'street food') in 'preferences': { 'meal_preferences': [...], 'favorite_cuisines': [...], 'dietary_restrictions': [...] }.\n"
            "8. SAFE HOTEL SELECTION: For hotel recommendations, prioritize central, safe, and secure hotels for families, adults, and solo/single travelers. Strictly avoid dangerous neighborhoods, high-crime areas, noisy nightclub strips, or areas with gang activity.\n"
            f"{'10. USER LOCATION & NEAREST ORIGIN AIRPORT: User location is ' + repr(user_location) + '. If prompt does NOT explicitly specify a departure city or origin airport, resolve user location to nearest standard 3-letter IATA origin airport (e.g. New York -> JFK, Atlanta -> ATL, London -> LHR). Set top-level origin and slices.[0].origin to this nearest IATA code.' if user_location else ''}\n"
            "9. Return JSON with keys: trip_type, origin, destination, slices, departure_date, return_date, target_return_date, from_date, to_date, duration_days, min_price, max_price, cabin_class, passengers_count, preferred_airline, included_airlines, excluded_airlines, preferences.\n"
            "User request: " + prompt
        )
        model_name = getattr(config, "openai_extraction_model", "") or getattr(config, "openai_model", "gpt-4o-mini") or "gpt-4o-mini"
        payload = {
            "model": model_name,
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
            import time
            t0 = time.perf_counter()
            with urlopen(request, timeout=15) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            llm_dt_ms = (time.perf_counter() - t0) * 1000.0
            try:
                from ..timing import TimingTracker
                TimingTracker.add_llm_time(llm_dt_ms)
            except Exception:
                pass
            content = response_data["choices"][0]["message"]["content"]
            result = json.loads(content)
            if isinstance(result, dict):
                normalized = PromptExtractor._normalize_flight_result(result)
                meta = {
                    "engine": f"LLM Extractor (OpenAI - {model_name})",
                    "llm_used": True,
                    "extracted_json": normalized,
                }
                prompt_parser_meta.set(meta)
                PromptParserTracker.set(meta)
                _save_llm_debug_output(
                    category="llm_extraction_openai",
                    data={"prompt": prompt, "model": model_name, "raw_response": result, "normalized": normalized},
                    identifier=str(normalized.get("destination") or "flight")
                )
                return normalized
        except Exception as err:
            err_msg = str(err)
            if hasattr(err, "read"):
                try:
                    err_msg += f" | Body: {err.read().decode('utf-8', errors='replace')}"
                except Exception:
                    pass
            print(f"[OPENAI LLM ERROR] Failed calling OpenAI API ({model_name}): {err_msg}", flush=True)
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
            f"Extract this flight request as JSON. Today is {today}.\n"
            "STRICT RULES:\n"
            "1. trip_type: MUST be 'one_way' if user explicitly says 'one way', 'oneway', or 'single'. MUST be 'round_trip' for roundtrip/return. MUST be 'multi_city' for stopovers or multi-city breaks.\n"
            "2. IATA CODES & SLICES: Resolve city names strictly to 3-letter IATA codes in uppercase (e.g. 'Atlanta' -> 'ATL', 'Columbus' -> 'CMH'). Set top-level 'origin', 'destination', and 'slices': [{'origin': 'ATL', 'destination': 'CMH', 'departure_date': 'YYYY-MM-DD'}].\n"
            "3. DATES & DURATION: Extract 'from_date', 'to_date', and 'duration_days'.\n"
            "4. PRICE RANGE: Extract 'min_price' and 'max_price'.\n"
            "5. AIRLINES: Set 'preferred_airline', 'included_airlines', and 'excluded_airlines' ONLY if user explicitly names a recognized airline (e.g. 'Delta', 'United'). NEVER treat date strings like 'sep 8' as airlines.\n"
            "6. STOPOVERS & BREAKS: If user requests a destination stay for N days with a break in an intermediate city (+7 days), sum stay + break duration for total trip length (28 days). Set trip_type: 'multi_city' and populate 'slices' array with sequential flight legs.\n"
            "7. MEAL PREFERENCES & DIET: Extract meal preferences, favorite cuisines, and dietary restrictions in 'preferences': { 'meal_preferences': [...], 'favorite_cuisines': [...], 'dietary_restrictions': [...] }.\n"
            "8. SAFE HOTEL SELECTION: For hotel recommendations, prioritize central, safe, and secure hotels for families, adults, and solo/single travelers. Strictly avoid dangerous neighborhoods, high-crime areas, noisy nightclub strips, or areas with gang activity.\n"
            "9. Return JSON with keys: trip_type, origin, destination, slices, departure_date, return_date, target_return_date, from_date, to_date, duration_days, min_price, max_price, cabin_class, passengers_count, preferred_airline, included_airlines, excluded_airlines, preferences.\n"
            f"User request: {prompt}"
        )
        gemini_model = getattr(config, "gemini_extraction_model", "") or getattr(config, "gemini_model", "gemini-1.5-flash") or "gemini-1.5-flash"
        payload = {
            "contents": [{"parts": [{"text": instruction}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(gemini_model, safe='')}:generateContent"
            f"?key={quote(config.gemini_api_key, safe='')}"
        )
        try:
            request = Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            import time
            t0 = time.perf_counter()
            with urlopen(request, timeout=15) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            llm_dt_ms = (time.perf_counter() - t0) * 1000.0
            try:
                from ..timing import TimingTracker
                TimingTracker.add_llm_time(llm_dt_ms)
            except Exception:
                pass
            response_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(response_text)
            if isinstance(result, dict) and isinstance(result.get("slices"), list):
                normalized = PromptExtractor._normalize_flight_result(result)
                meta = {
                    "engine": f"LLM Extractor (Gemini - {gemini_model})",
                    "llm_used": True,
                    "extracted_json": normalized,
                }
                prompt_parser_meta.set(meta)
                PromptParserTracker.set(meta)
                _save_llm_debug_output(
                    category="llm_extraction_gemini",
                    data={"prompt": prompt, "model": gemini_model, "raw_response": result, "normalized": normalized},
                    identifier=str(normalized.get("destination") or "flight")
                )
                return normalized
        except Exception as err:
            err_msg = str(err)
            if hasattr(err, "read"):
                try:
                    err_msg += f" | Body: {err.read().decode('utf-8', errors='replace')}"
                except Exception:
                    pass
            print(f"[GEMINI LLM ERROR] Failed calling Gemini API ({config.gemini_model}): {err_msg}", flush=True)
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

        loc_match = re.search(r"(?:to|in|at|around|for)\s+([a-z\s]+?)(?=\s+from|\s+on|\s+for|\s+check|\s*$)", text)
        if loc_match:
            candidate = loc_match.group(1).strip()
            candidate = re.sub(r"\s+from\s+.*$", "", candidate, flags=re.IGNORECASE).strip()
            if candidate not in ["hotel", "stay", "accommodation", "trip", "vacation"]:
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
        # Strip parenthetical GPS coordinates e.g. 'New York (40.7128,-74.0060)' -> 'New York'
        val_clean = re.sub(r"\s*\([^)]*\)", "", str(val or "")).strip()
        # Strip trailing date clauses like 'from september 15' or 'on oct 1'
        clean = re.sub(r"\s+(?:from|on|for|in|during|departing|returning)\s+.*$", "", val_clean, flags=re.IGNORECASE)
        clean = clean.strip().lower()

        # Remove trailing state names/abbreviations e.g. 'columbus, oh' -> 'columbus'
        clean_no_state = re.sub(r",?\s*(?:oh|ohio|ca|california|ny|new york|tx|texas|fl|florida|ga|georgia|il|illinois|ma|massachusetts|wa|washington|nc|north carolina|sc|south carolina|va|virginia|pa|pennsylvania|co|colorado|az|arizona|or|oregon)\b", "", clean).strip()

        if clean in CITY_IATA_MAP:
            return CITY_IATA_MAP[clean]
        if clean_no_state in CITY_IATA_MAP:
            return CITY_IATA_MAP[clean_no_state]

        # Fuzzy matching for city typos e.g. 'columnbus' -> 'columbus' (CMH)
        import difflib
        matches = difflib.get_close_matches(clean_no_state, CITY_IATA_MAP.keys(), n=1, cutoff=0.7)
        if matches:
            return CITY_IATA_MAP[matches[0]]

        if len(clean) == 3 and clean.isalpha():
            return clean.upper()
        if len(clean_no_state) == 3 and clean_no_state.isalpha():
            return clean_no_state.upper()

        m_iata = re.search(r"\b([a-zA-Z]{3})\b", val)
        if m_iata:
            return m_iata.group(1).upper()

        # Fallback to LLM for unmapped cities, regions, or obscure location names
        llm_resolved = PromptExtractor.resolve_location_with_llm(val_clean)
        if llm_resolved and len(llm_resolved) == 3 and llm_resolved.isalpha():
            return llm_resolved.upper()

        return val_clean.upper()

    _LLM_IATA_CACHE: dict[str, str] = {}

    @staticmethod
    def resolve_location_with_llm(location: str) -> str:
        """
        Resolves unmapped city, island, region, or landmark string to a 3-letter IATA airport code using LLM.
        """
        if not location:
            return ""
        clean_loc = re.sub(r"\s*\([^)]*\)", "", str(location)).strip()
        clean_loc = re.sub(r"\s+(?:from|on|for|in|during|departing|returning)\s+.*$", "", clean_loc, flags=re.IGNORECASE).strip()
        if len(clean_loc) == 3 and clean_loc.isalpha():
            return clean_loc.upper()

        key = clean_loc.lower()
        if key in PromptExtractor._LLM_IATA_CACHE:
            return PromptExtractor._LLM_IATA_CACHE[key]

        config = DuffelConfig()
        instruction = (
            f"Resolve the city, region, island, or location '{clean_loc}' to its primary commercial 3-letter uppercase IATA airport code.\n"
            "Respond ONLY with a JSON object: {\"iata\": \"XXX\", \"city_name\": \"City Name\"}.\n"
            "Examples:\n"
            "  'Reykjavik' -> {\"iata\": \"KEF\", \"city_name\": \"Reykjavik\"}\n"
            "  'Cochin' -> {\"iata\": \"COK\", \"city_name\": \"Kochi\"}\n"
            "  'Santorini' -> {\"iata\": \"JTR\", \"city_name\": \"Santorini\"}\n"
            "  'Bali' -> {\"iata\": \"DPS\", \"city_name\": \"Bali\"}\n"
            "  'Mahe' -> {\"iata\": \"SEZ\", \"city_name\": \"Mahe\"}"
        )

        try:
            import json
            from urllib.request import Request, urlopen
            if config.openai_enabled and config.openai_api_key:
                payload = {
                    "model": config.openai_model,
                    "messages": [{"role": "system", "content": instruction}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                }
                req = Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Bearer {config.openai_api_key}", "Content-Type": "application/json"},
                    method="POST"
                )
                import time
                t0 = time.perf_counter()
                with urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                llm_dt_ms = (time.perf_counter() - t0) * 1000.0
                try:
                    from ..timing import TimingTracker
                    TimingTracker.add_llm_time(llm_dt_ms)
                except Exception:
                    pass

                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                code = str(parsed.get("iata") or "").strip().upper()
                if len(code) == 3 and code.isalpha():
                    PromptExtractor._LLM_IATA_CACHE[key] = code
                    return code
        except Exception as err:
            print(f"[LLM IATA RESOLVER NOTICE] Failed LLM resolution for '{clean_loc}': {err}", flush=True)

        return clean_loc.upper()

    @staticmethod
    def enrich_missing_intent_with_llm(prompt: str, current_intent: dict[str, Any], user_location: Optional[str] = None) -> dict[str, Any]:
        """
        Dedicated pre-processing LLM call to resolve and enrich missing or unmapped parameters (origin IATA, destination IATA, dates, duration).
        """
        config = DuffelConfig()
        if not ((config.openai_enabled and config.openai_api_key) or (config.gemini_enabled and config.gemini_api_key)):
            return current_intent

        today = datetime.now().strftime("%Y-%m-%d")
        instruction = (
            f"Today is {today}. Analyze this travel query and resolve all missing/unmapped travel parameters as JSON.\n"
            f"User Location: '{user_location or 'Not provided'}'\n"
            f"Current extracted parameters: origin='{current_intent.get('origin')}', destination='{current_intent.get('destination')}', departure_date='{current_intent.get('departure_date')}', duration_days={current_intent.get('duration_days')}\n"
            "STRICT ENRICHMENT RULES:\n"
            "1. ORIGIN IATA: If departure origin is NOT specified in query, resolve the user's location to the nearest standard 3-letter IATA departure airport code (e.g. 'Atlanta' -> 'ATL', 'New York' -> 'JFK', 'London' -> 'LHR').\n"
            "2. DESTINATION IATA & CITY: Resolve destination city to standard 3-letter IATA code and full city title (e.g. 'Paris' -> 'CDG', 'Zurich' -> 'ZRH', 'Cochin' -> 'COK', 'Reykjavik' -> 'KEF', 'Bali' -> 'DPS', 'Santorini' -> 'JTR').\n"
            "3. DATES & DURATION: Extract start departure date (YYYY-MM-DD) and trip duration in days (integer).\n"
            "4. Respond ONLY with JSON: {\"origin_iata\": \"XXX\", \"destination_iata\": \"YYY\", \"destination_city\": \"City Name\", \"departure_date\": \"YYYY-MM-DD\", \"return_date\": \"YYYY-MM-DD\", \"duration_days\": N, \"passengers_count\": N}.\n"
            f"User Query: {prompt}"
        )

        try:
            import json
            import time
            from urllib.request import Request, urlopen
            if config.openai_enabled and config.openai_api_key:
                payload = {
                    "model": config.openai_model,
                    "messages": [{"role": "system", "content": instruction}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                }
                req = Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Bearer {config.openai_api_key}", "Content-Type": "application/json"},
                    method="POST"
                )
                t0 = time.perf_counter()
                with urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                llm_dt_ms = (time.perf_counter() - t0) * 1000.0
                try:
                    from ..timing import TimingTracker
                    TimingTracker.add_llm_time(llm_dt_ms)
                except Exception:
                    pass

                content = data["choices"][0]["message"]["content"]
                enriched = json.loads(content)
                if isinstance(enriched, dict):
                    if enriched.get("origin_iata") and (not current_intent.get("origin") or len(str(current_intent.get("origin"))) != 3):
                        orig_code = str(enriched["origin_iata"]).strip().upper()
                        current_intent["origin"] = orig_code
                        if current_intent.get("slices") and isinstance(current_intent["slices"][0], dict):
                            current_intent["slices"][0]["origin"] = orig_code
                    if enriched.get("destination_iata") and (not current_intent.get("destination") or len(str(current_intent.get("destination"))) != 3):
                        dest_code = str(enriched["destination_iata"]).strip().upper()
                        current_intent["destination"] = dest_code
                        if current_intent.get("slices") and isinstance(current_intent["slices"][0], dict):
                            current_intent["slices"][0]["destination"] = dest_code
                    if enriched.get("destination_city"):
                        current_intent["destination_city"] = enriched["destination_city"]
                    if enriched.get("departure_date") and not current_intent.get("departure_date"):
                        current_intent["departure_date"] = enriched["departure_date"]
                        current_intent["from_date"] = enriched["departure_date"]
                    if enriched.get("return_date") and not current_intent.get("return_date"):
                        current_intent["return_date"] = enriched["return_date"]
                        current_intent["to_date"] = enriched["return_date"]
                    if enriched.get("duration_days") and current_intent.get("duration_days") is None:
                        current_intent["duration_days"] = int(enriched["duration_days"])
        except Exception as err:
            print(f"[ENRICHMENT LLM NOTICE] Pre-processing LLM enrichment notice: {err}", flush=True)

        return current_intent
