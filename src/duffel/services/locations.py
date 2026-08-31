"""
Service for Location & Geolocation Lookup, Duffel Places Sync, and Config File Persistence.
"""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from ..exceptions import DuffelException


CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "geo_locations.json"

DEFAULT_GEO_MAP: dict[str, dict[str, Any]] = {
    "ZURICH": {"latitude": 47.3769, "longitude": 8.5417, "address": "Zurich, Switzerland", "name": "Zurich City Centre"},
    "ZRH": {"latitude": 47.4582, "longitude": 8.5555, "address": "Zurich Airport (ZRH), Switzerland", "name": "Zurich Airport"},
    "DELHI": {"latitude": 28.6139, "longitude": 77.2090, "address": "New Delhi, India", "name": "New Delhi Centre"},
    "DEL": {"latitude": 28.5562, "longitude": 77.1000, "address": "Indira Gandhi International Airport (DEL), Delhi, India", "name": "Delhi Airport"},
    "MUMBAI": {"latitude": 19.0760, "longitude": 72.8777, "address": "Mumbai, Maharashtra, India", "name": "Mumbai City Centre"},
    "BOM": {"latitude": 19.0896, "longitude": 72.8656, "address": "Chhatrapati Shivaji Maharaj Airport (BOM), Mumbai, India", "name": "Mumbai Airport"},
    "DUBAI": {"latitude": 25.2048, "longitude": 55.2708, "address": "Dubai, United Arab Emirates", "name": "Dubai City Centre"},
    "DXB": {"latitude": 25.2532, "longitude": 55.3657, "address": "Dubai International Airport (DXB), UAE", "name": "Dubai Airport"},
    "CALGARY": {"latitude": 51.0447, "longitude": -114.0719, "address": "Calgary, AB, Canada", "name": "Downtown Calgary"},
    "YYC": {"latitude": 51.1215, "longitude": -114.0076, "address": "Calgary International Airport (YYC), AB, Canada", "name": "Calgary Airport"},
    "AMSTERDAM": {"latitude": 52.3676, "longitude": 4.9041, "address": "Amsterdam, Netherlands", "name": "Amsterdam Centre"},
    "AMS": {"latitude": 52.3105, "longitude": 4.7683, "address": "Amsterdam Airport Schiphol (AMS), Netherlands", "name": "Schiphol Airport"},
    "FRANKFURT": {"latitude": 50.1109, "longitude": 8.6821, "address": "Frankfurt am Main, Germany", "name": "Frankfurt City Centre"},
    "FRA": {"latitude": 50.0379, "longitude": 8.5622, "address": "Frankfurt Airport (FRA), Germany", "name": "Frankfurt Airport"},
    "BERLIN": {"latitude": 52.5200, "longitude": 13.4050, "address": "Berlin, Germany", "name": "Berlin City Centre"},
    "BER": {"latitude": 52.3667, "longitude": 13.5033, "address": "Berlin Brandenburg Airport (BER), Germany", "name": "Berlin Airport"},
    "MADRID": {"latitude": 40.4168, "longitude": -3.7038, "address": "Madrid, Spain", "name": "Madrid City Centre"},
    "MAD": {"latitude": 40.4839, "longitude": -3.5680, "address": "Adolfo Suárez Madrid–Barajas Airport (MAD), Spain", "name": "Madrid Airport"},
    "PARIS": {"latitude": 48.8566, "longitude": 2.3522, "address": "Paris, France", "name": "Paris City Centre"},
    "LONDON": {"latitude": 51.5074, "longitude": -0.1278, "address": "London, UK", "name": "Central London"},
    "NEW YORK": {"latitude": 40.7128, "longitude": -74.0060, "address": "New York, NY, USA", "name": "Manhattan"},
    "TOKYO": {"latitude": 35.6762, "longitude": 139.6503, "address": "Tokyo, Japan", "name": "Tokyo Central"},
    "ROME": {"latitude": 41.9028, "longitude": 12.4964, "address": "Rome, Italy", "name": "Rome Historical Center"},
    "BARCELONA": {"latitude": 41.3851, "longitude": 2.1734, "address": "Barcelona, Spain", "name": "Barcelona Center"},
    "CDG": {"latitude": 49.0097, "longitude": 2.5479, "address": "Paris CDG Airport, France", "name": "Paris CDG Airport"},
    "LHR": {"latitude": 51.4700, "longitude": -0.4543, "address": "London Heathrow Airport, UK", "name": "London Heathrow Airport"},
    "JFK": {"latitude": 40.6413, "longitude": -73.7781, "address": "New York JFK Airport, USA", "name": "New York JFK Airport"},
    "LAX": {"latitude": 33.9416, "longitude": -118.4085, "address": "Los Angeles LAX Airport, USA", "name": "Los Angeles LAX Airport"},
    "ATL": {"latitude": 33.6407, "longitude": -84.4277, "address": "Atlanta ATL Airport, USA", "name": "Atlanta ATL Airport"},
    "ORD": {"latitude": 41.9742, "longitude": -87.9073, "address": "Chicago O'Hare Airport, USA", "name": "Chicago O'Hare Airport"},
    "MCO": {"latitude": 28.4312, "longitude": -81.3081, "address": "Orlando MCO Airport, USA", "name": "Orlando MCO Airport"},
    "HNL": {"latitude": 21.3245, "longitude": -157.9251, "address": "Honolulu HNL Airport, USA", "name": "Honolulu HNL Airport"},
    "ALB": {"latitude": 42.7483, "longitude": -73.8017, "address": "Albany International Airport, NY, USA", "name": "Albany International Airport"},
    "ALBANY": {"latitude": 42.6526, "longitude": -73.7562, "address": "Albany, NY, USA", "name": "Albany City"},
}


def load_geo_locations() -> dict[str, dict[str, Any]]:
    """Loads location mappings from config JSON file merged with defaults."""
    geo_map = dict(DEFAULT_GEO_MAP)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    geo_map.update(loaded)
        except Exception as err:
            print(f"[LOCATION SERVICE WARNING] Could not read {CONFIG_FILE}: {err}")
    return geo_map


def save_geo_locations(locations: dict[str, dict[str, Any]]) -> None:
    """Saves location mappings to config JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(locations, f, indent=2, ensure_ascii=False)


# Initialize shared memory store
GEO_LOCATIONS: dict[str, dict[str, Any]] = load_geo_locations()


def sync_locations_from_duffel(adapter: Any) -> dict[str, Any]:
    """
    Calls Duffel APIs (airports and cities) to retrieve list of places and geolocations,
    saving the result to src/duffel/config/geo_locations.json.
    """
    updated_count = 0
    new_locations = dict(GEO_LOCATIONS)

    # 1. Fetch Airports from Duffel API
    try:
        res = adapter.list_airports(limit=200)
        airports = res.get("data", []) if isinstance(res, dict) else []
        for apt in airports:
            if not isinstance(apt, dict):
                continue
            lat = apt.get("latitude")
            lng = apt.get("longitude")
            iata = apt.get("iata_code")
            name = apt.get("name") or iata
            city_name = apt.get("city_name") or name

            if lat is not None and lng is not None:
                item = {
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "address": f"{name}, {city_name}",
                    "name": name,
                    "iata": iata,
                }
                if iata:
                    new_locations[iata.upper()] = item
                    updated_count += 1
                if city_name:
                    new_locations[city_name.upper()] = item
                    if iata:
                        new_locations[f"{city_name.upper()} ({iata.upper()})"] = item
                    updated_count += 1
                if name:
                    new_locations[name.upper()] = item
                    updated_count += 1
    except Exception as err:
        print(f"[LOCATION SYNC WARNING] Failed fetching airports from Duffel API: {err}")

    # 2. Fetch Cities from Duffel API
    try:
        res = adapter.list_cities(limit=200)
        cities = res.get("data", []) if isinstance(res, dict) else []
        for c in cities:
            if not isinstance(c, dict):
                continue
            lat = c.get("latitude")
            lng = c.get("longitude")
            iata = c.get("iata_code")
            name = c.get("name")

            if lat is not None and lng is not None and name:
                item = {
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "address": f"{name} City",
                    "name": name,
                    "iata": iata,
                }
                new_locations[name.upper()] = item
                if iata:
                    new_locations[iata.upper()] = item
                    new_locations[f"{name.upper()} ({iata.upper()})"] = item
                updated_count += 1
    except Exception as err:
        print(f"[LOCATION SYNC WARNING] Failed fetching cities from Duffel API: {err}")

    # Save to config file and update memory cache
    save_geo_locations(new_locations)
    GEO_LOCATIONS.clear()
    GEO_LOCATIONS.update(new_locations)

    return {
        "status": "success",
        "message": f"Successfully synced locations from Duffel API into {CONFIG_FILE.name}",
        "total_locations": len(GEO_LOCATIONS),
        "synced_records": updated_count,
        "config_file": str(CONFIG_FILE),
    }


def _geocode_nominatim(query: str) -> Optional[dict[str, float]]:
    """Fallback: Dynamic lookup using OpenStreetMap Nominatim API."""
    try:
        clean_q = re.sub(r"\s*\([A-Z0-9]+\)", "", query).strip()
        encoded = urllib.parse.quote(clean_q)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "JojiraDuffelApp/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list):
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                display_name = data[0].get("display_name", clean_q)
                
                res = {"latitude": lat, "longitude": lng, "address": display_name, "name": clean_q}
                # Persist dynamically resolved location
                GEO_LOCATIONS[query.upper()] = res
                GEO_LOCATIONS[clean_q.upper()] = res
                save_geo_locations(GEO_LOCATIONS)
                return res
    except Exception as err:
        print(f"[NOMINATIM GEOCODE WARNING] Failed resolving '{query}': {err}")
    return None


def resolve_geo_location(location: str) -> dict[str, float]:
    """
    Resolves a location string (e.g. 'Albany (ALB)', 'LAX', 'Paris') to geographic coordinates.
    Tries exact lookup, IATA extraction, substring match, and dynamic geocode fallback.
    """
    if not location:
        raise DuffelException("Location parameter cannot be empty.")

    key = location.strip().upper()

    # 1. Exact Match
    if key in GEO_LOCATIONS:
        return {"latitude": GEO_LOCATIONS[key]["latitude"], "longitude": GEO_LOCATIONS[key]["longitude"]}

    # 2. Extract 3-letter IATA code inside parentheses e.g. "Albany (ALB)"
    iata_match = re.search(r"\b([A-Z]{3})\b", key)
    if iata_match:
        iata_code = iata_match.group(1)
        if iata_code in GEO_LOCATIONS:
            return {"latitude": GEO_LOCATIONS[iata_code]["latitude"], "longitude": GEO_LOCATIONS[iata_code]["longitude"]}

    # 3. Clean location name without parentheses e.g. "Albany"
    clean_name = re.sub(r"\s*\([A-Z0-9]+\)", "", key).strip()
    if clean_name in GEO_LOCATIONS:
        return {"latitude": GEO_LOCATIONS[clean_name]["latitude"], "longitude": GEO_LOCATIONS[clean_name]["longitude"]}

    # 4. Partial substring search
    for loc_key, data in GEO_LOCATIONS.items():
        if loc_key in key or key in loc_key or clean_name in loc_key:
            return {"latitude": data["latitude"], "longitude": data["longitude"]}

    # 5. Dynamic Geocode Fallback via OpenStreetMap Nominatim
    geo = _geocode_nominatim(location)
    if geo:
        return {"latitude": geo["latitude"], "longitude": geo["longitude"]}

    raise DuffelException(
        f"Unable to resolve location '{location}' to coordinates. "
        f"Supported sample locations: {sorted(list(GEO_LOCATIONS.keys())[:15])}."
    )
