import re
from typing import Any, Optional
from ..locations import GEO_LOCATIONS as DESTINATION_GEO_MAP


def format_proper_title(text: str) -> str:
    """Formats destination, package, and activity names into professional Title Case regardless of user input casing."""
    if not text:
        return ""
    lowercase_words = {"a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "from", "by", "of", "in", "with", "de", "la", "van", "von"}
    uppercase_words = {"ATL", "CDG", "JFK", "LHR", "LAX", "ORD", "MIA", "SFO", "DXB", "HND", "VIP", "SUV", "AI", "ID", "USD", "TN", "OH", "NY", "CA", "FL", "GA"}

    words = re.split(r'(\s+|-)', str(text).strip())
    result = []
    for i, word in enumerate(words):
        if not word.strip():
            result.append(word)
            continue
        m = re.match(r'^([^a-zA-Z0-9]*)(.*?)([^a-zA-Z0-9]*)$', word)
        if m and m.group(2):
            lead, core, trail = m.group(1), m.group(2), m.group(3)
            core_upper = core.upper()
            if core_upper in uppercase_words:
                formatted_core = core_upper
            elif i == 0 or core.lower() not in lowercase_words:
                formatted_core = core.capitalize()
            else:
                formatted_core = core.lower()
            result.append(f"{lead}{formatted_core}{trail}")
        else:
            w_upper = word.upper()
            if w_upper in uppercase_words:
                result.append(w_upper)
            elif i == 0 or word.lower() not in lowercase_words:
                result.append(word.capitalize())
            else:
                result.append(word.lower())

    formatted = "".join(result)
    return re.sub(r'\b[Vv][Ii][Pp]\b', 'VIP', formatted)


IATA_COUNTRY_MAP = {
    # USA
    "ATL": "US", "JFK": "US", "EWR": "US", "LGA": "US", "LAX": "US", "ORD": "US", "SFO": "US", "MIA": "US",
    "DFW": "US", "DEN": "US", "SEA": "US", "BOS": "US", "LAS": "US", "MCO": "US", "IAD": "US", "DCA": "US",
    "SAN": "US", "PHX": "US", "IAH": "US", "AUS": "US", "BNA": "US", "PHL": "US", "DTW": "US", "MSP": "US",
    "CLT": "US", "SLC": "US", "PDX": "US", "TPA": "US", "HNL": "US", "CMH": "US", "CVG": "US",
    # Canada
    "YYC": "CA", "YVR": "CA", "YYZ": "CA", "YUL": "CA", "YOW": "CA", "YEG": "CA", "YQB": "CA", "YHZ": "CA",
    # UK
    "LHR": "GB", "LGW": "GB", "STN": "GB", "MAN": "GB", "EDI": "GB", "BHX": "GB", "GLA": "GB",
    # France
    "CDG": "FR", "ORY": "FR", "NCE": "FR", "LYS": "FR", "MRS": "FR", "BOD": "FR",
    # Germany
    "FRA": "DE", "MUC": "DE", "BER": "DE", "HAM": "DE", "DUS": "DE", "STR": "DE", "CGN": "DE",
    # Switzerland
    "ZRH": "CH", "GVA": "CH", "BSL": "CH",
    # Italy
    "FCO": "IT", "MXP": "IT", "LIN": "IT", "VCE": "IT", "FLR": "IT", "NAP": "IT", "BLQ": "IT",
    # Spain
    "MAD": "ES", "BCN": "ES", "AGP": "ES", "PMI": "ES", "VLC": "ES", "SVQ": "ES", "IBZ": "ES",
    # Netherlands, Austria, Portugal, Ireland, Belgium, Greece, Turkey, UAE, India, Japan, Australia, New Zealand, Singapore, Thailand
    "AMS": "NL", "VIE": "AT", "LIS": "PT", "OPO": "PT", "DUB": "IE", "SNN": "IE", "BRU": "BE", "ATH": "GR",
    "IST": "TR", "DXB": "AE", "AUH": "AE", "DEL": "IN", "BOM": "IN", "BLR": "IN", "HYD": "IN", "MAA": "IN",
    "HND": "JP", "NRT": "JP", "KIX": "JP", "SYD": "AU", "MEL": "AU", "BNE": "AU", "AKL": "NZ", "WLG": "NZ",
    "SIN": "SG", "BKK": "TH", "HKT": "TH", "HKG": "HK", "ICN": "KR", "MEX": "MX", "CUN": "MX", "GRU": "BR",
}

CITY_COUNTRY_MAP = {
    # US Cities
    "atlanta": "US", "new york": "US", "nyc": "US", "los angeles": "US", "chicago": "US", "san francisco": "US",
    "miami": "US", "orlando": "US", "las vegas": "US", "seattle": "US", "boston": "US", "dallas": "US",
    "houston": "US", "denver": "US", "washington": "US", "san diego": "US", "austin": "US", "nashville": "US",
    "philadelphia": "US", "phoenix": "US", "portland": "US", "new orleans": "US", "honolulu": "US", "tampa": "US",
    "detroit": "US", "minneapolis": "US", "charlotte": "US", "salt lake city": "US", "savannah": "US", "charleston": "US",
    "cincinnati": "US", "columbus": "US", "cleveland": "US", "gatlinburg": "US", "chattanooga": "US", "lexington": "US",
    # Canada, UK, France, Germany, Switzerland, Italy, Spain, India, Japan, Australia, etc.
    "calgary": "CA", "vancouver": "CA", "toronto": "CA", "montreal": "CA", "banff": "CA",
    "london": "GB", "edinburgh": "GB", "manchester": "GB", "paris": "FR", "nice": "FR", "lyon": "FR",
    "berlin": "DE", "munich": "DE", "frankfurt": "DE", "zurich": "CH", "geneva": "CH", "lucerne": "CH",
    "rome": "IT", "milan": "IT", "venice": "IT", "florence": "IT", "madrid": "ES", "barcelona": "ES",
    "amsterdam": "NL", "vienna": "AT", "lisbon": "PT", "dublin": "IE", "brussels": "BE", "athens": "GR",
    "dubai": "AE", "delhi": "IN", "new delhi": "IN", "mumbai": "IN", "bangalore": "IN", "hyderabad": "IN",
    "tokyo": "JP", "kyoto": "JP", "osaka": "JP", "sydney": "AU", "melbourne": "AU", "auckland": "NZ",
    "singapore": "SG", "bangkok": "TH", "phuket": "TH", "mexico city": "MX", "cancun": "MX", "rio de janeiro": "BR"
}

COUNTRY_ALIASES = {
    "us": "US", "usa": "US", "united states": "US", "america": "US",
    "ca": "CA", "canada": "CA", "gb": "GB", "uk": "GB", "united kingdom": "GB", "england": "GB", "scotland": "GB",
    "fr": "FR", "france": "FR", "de": "DE", "germany": "DE", "ch": "CH", "switzerland": "CH", "swiss": "CH",
    "it": "IT", "italy": "IT", "es": "ES", "spain": "ES", "nl": "NL", "netherlands": "NL", "at": "AT", "austria": "AT",
    "pt": "PT", "portugal": "PT", "ie": "IE", "ireland": "IE", "be": "BE", "belgium": "BE", "gr": "GR", "greece": "GR",
    "ae": "AE", "uae": "AE", "in": "IN", "india": "IN", "jp": "JP", "japan": "JP", "au": "AU", "australia": "AU",
    "nz": "NZ", "new zealand": "NZ", "sg": "SG", "singapore": "SG", "th": "TH", "thailand": "TH", "mx": "MX", "mexico": "MX"
}


def resolve_location_country(loc_str: Optional[str]) -> Optional[str]:
    """Resolves 2-letter ISO country code from location string (IATA, city, or country)."""
    if not loc_str:
        return None
    cleaned = str(loc_str).strip()
    upper_c = cleaned.upper()
    lower_c = cleaned.lower()

    if upper_c in IATA_COUNTRY_MAP:
        return IATA_COUNTRY_MAP[upper_c]
    if lower_c in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[lower_c]
    if lower_c in CITY_COUNTRY_MAP:
        return CITY_COUNTRY_MAP[lower_c]

    parts = [p.strip().lower() for p in cleaned.split(",")]
    for p in reversed(parts):
        if p in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[p]
        if p in CITY_COUNTRY_MAP:
            return CITY_COUNTRY_MAP[p]
        if p.upper() in IATA_COUNTRY_MAP:
            return IATA_COUNTRY_MAP[p.upper()]

    for token in re.findall(r"\b[A-Za-z]+\b", lower_c):
        if token in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[token]
        if token in CITY_COUNTRY_MAP:
            return CITY_COUNTRY_MAP[token]
    return None


def classify_travel_scope_and_type(
    prompt: str,
    resolved_origin: str,
    dest_clean: str,
    user_location: Optional[str] = None,
    include_flights: bool = True,
    include_cars: bool = True,
    road_trip: Optional[bool] = None,
    fly_and_drive: Optional[bool] = None,
) -> dict[str, Any]:
    """Classifies trip scope (domestic vs international), trip type, and modality flags."""
    user_home_country = resolve_location_country(user_location) or resolve_location_country(resolved_origin) or "US"
    dest_country = resolve_location_country(dest_clean)
    origin_country = resolve_location_country(resolved_origin) or user_home_country

    is_international = bool(user_home_country and dest_country and user_home_country != dest_country)
    is_domestic = not is_international
    trip_scope = "international" if is_international else "domestic"

    p_lower_check = prompt.lower()
    has_explicit_flight = any(k in p_lower_check for k in ["flight", "flights", "fly", "flying", "plane", "airplane", "airline", "fly to", "fly from"])
    has_explicit_drive = any(k in p_lower_check for k in ["road trip", "roadtrip", "drive", "driving", "by car", "car trip", "drive to", "drive from"])
    is_cruise = any(k in p_lower_check for k in ["cruise", "sailing", "sail", "cruise ship", "caribbean cruise", "alaska cruise", "mediterranean cruise"])

    # 1. Explicit parameter overrides take top precedence
    if fly_and_drive:
        is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, False, True, True
        trip_type_val, base_trip_type = "fly_and_drive", "Fly & Drive"
    elif road_trip is True:
        if is_international:
            is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, False, True, True
            trip_type_val, base_trip_type = "fly_and_drive", "Fly & Drive"
        else:
            is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, True, False, False
            trip_type_val, base_trip_type = "road_trip", "Road Trip"
    elif is_cruise:
        is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = True, False, False, False
        trip_type_val, base_trip_type = "cruise", "Cruise Trip"
    elif has_explicit_drive and road_trip is not False:
        if is_international:
            is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, False, True, True
            trip_type_val, base_trip_type = "fly_and_drive", "Fly & Drive"
        else:
            is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, True, False, False
            trip_type_val, base_trip_type = "road_trip", "Road Trip"
    elif has_explicit_flight:
        is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, False, False, True
        trip_type_val, base_trip_type = "vacation_travel", "Vacation Travel"
    elif not is_international and not has_explicit_flight and not include_flights:
        is_cruise, is_road_trip, is_fly_and_drive, eff_include_flights = False, True, False, False
        trip_type_val, base_trip_type = "road_trip", "Road Trip"
    else:
        is_road_trip = not include_flights
        eff_include_flights = include_flights
        is_cruise, is_fly_and_drive = False, False
        trip_type_val = "road_trip" if is_road_trip else "vacation_travel"
        base_trip_type = "Road Trip" if is_road_trip else "Vacation Travel"

    if not is_fly_and_drive and (eff_include_flights and include_cars and (has_explicit_drive or fly_and_drive)):
        is_fly_and_drive = True
        trip_type_val, base_trip_type = "fly_and_drive", "Fly & Drive"

    return {
        "trip_scope": trip_scope,
        "trip_type": trip_type_val,
        "is_domestic": is_domestic,
        "is_international": is_international,
        "is_road_trip": is_road_trip,
        "is_cruise": is_cruise,
        "is_fly_and_drive": is_fly_and_drive,
        "include_flights": eff_include_flights,
        "trip_category_display": f"{trip_scope.capitalize()} {base_trip_type}",
        "user_home_country": user_home_country,
        "dest_country": dest_country,
        "origin_country": origin_country,
    }
