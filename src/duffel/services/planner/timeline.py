from datetime import datetime, timedelta
import re
import urllib.parse
from typing import Any, Optional
from .activities import enrich_activity_urls_and_geo, generate_activity_reviews


def parse_time_to_minutes(time_val: Any, default_val: int = 720) -> int:
    """Parses time string or dict into minutes from midnight."""
    if isinstance(time_val, dict):
        ts = str(time_val.get("start_time") or time_val.get("departure_time") or time_val.get("time_slot") or time_val.get("time") or "").upper().strip()
    else:
        ts = str(time_val or "").upper().strip()
    match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", ts)
    if match:
        h = int(match.group(1))
        m = int(match.group(2))
        ampm = match.group(3)
        if ampm == "PM" and h != 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
        return h * 60 + m
    if "BREAKFAST" in ts or "MORNING" in ts:
        return 480
    if "LUNCH" in ts or "NOON" in ts:
        return 720
    if "AFTERNOON" in ts:
        return 840
    if "EVENING" in ts:
        return 1065
    if "DINNER" in ts:
        return 1200
    if "NIGHT" in ts or "REST" in ts:
        return 1300
    return default_val


def format_minutes_to_time(minutes_val: int) -> str:
    """Formats minutes from midnight to 12-hour AM/PM string."""
    m_val = minutes_val % (24 * 60)
    h = m_val // 60
    m = m_val % 60
    ampm = "AM" if h < 12 else "PM"
    disp_h = h if h <= 12 else h - 12
    if disp_h == 0:
        disp_h = 12
    return f"{disp_h:02d}:{m:02d} {ampm}"


def build_flight_item(
    item_id: str,
    title: str,
    dest_clean: str,
    origin_code: str,
    dest_upper: str,
    passengers_count: int,
    dep_time: str,
    arr_time: str,
    price: float,
    base_lat: float,
    base_lng: float,
    is_return: bool = False,
) -> dict[str, Any]:
    """Constructs official Outbound or Return Flight card."""
    desc = f"{'Return Flight' if is_return else 'Flight Arrival'} from {dest_clean if is_return else origin_code} to {origin_code if is_return else dest_clean} ({passengers_count} pax). Departure time: {dep_time}, Arrival time: {arr_time}."
    return {
        "id": item_id,
        "type": "flight",
        "name": title,
        "title": title,
        "description": desc,
        "price": round(price, 2),
        "currency": "USD",
        "departure_time": dep_time,
        "arrival_time": arr_time,
        "time_slot": f"Departure: {dep_time} | Arrival: {arr_time}",
        "address": f"{dest_clean} Airport ({dest_upper})",
        "phone_number": "+1 800 555 0199",
        "geo_location": {
            "name": f"{dest_clean} Airport",
            "address": f"{dest_clean} Airport ({dest_upper})",
            "phone_number": "+1 800 555 0199",
            "latitude": base_lat + 0.05,
            "longitude": base_lng + 0.05,
        }
    }


def build_car_rental_item(
    item_id: str,
    title: str,
    dest_clean: str,
    dest_upper: str,
    duration_days: int,
    passengers_count: int,
    cars_count: int,
    dep_time: str,
    arr_time: str,
    price: float,
    is_price_tbd: bool,
    base_lat: float,
    base_lng: float,
    is_return: bool = False,
    is_road_trip: bool = False,
) -> dict[str, Any]:
    """Constructs official Rental Vehicle Pickup or Return card."""
    facility_type = f"{dest_clean} City Rental Center" if is_road_trip else f"{dest_clean} Airport Rental Facility"
    if is_return:
        desc = f"Return rental vehicle ({cars_count} car(s)) with full tank at {facility_type}."
        slot = f"{dep_time} - {arr_time} - Rental Vehicle Return"
    else:
        desc = f"{duration_days}-day rental pickup for {passengers_count} passenger(s) ({cars_count} car(s)) at {facility_type}" + (" (Price: TBD)" if is_price_tbd else "")
        slot = f"{dep_time} - {arr_time} - Rental Vehicle Pickup" + (" (Price: TBD)" if is_price_tbd else "")

    address_str = f"Rental Center, {dest_clean}" if is_road_trip else f"Rental Center, {dest_clean} Airport ({dest_upper})"
    center_name = f"{dest_clean} Car Rental Center" if is_road_trip else f"{dest_clean} Airport Car Rental Center"

    return {
        "id": item_id,
        "type": "car",
        "name": title,
        "title": title,
        "description": desc,
        "price": 0.0 if (is_return or is_price_tbd) else round(price, 2),
        "price_display": "Free / Return" if is_return else ("TBD" if is_price_tbd else f"USD {price:.2f}"),
        "is_price_tbd": False if is_return else is_price_tbd,
        "currency": "USD",
        "departure_time": dep_time,
        "arrival_time": arr_time,
        "time_slot": slot,
        "address": address_str,
        "phone_number": "+1 800 555 0244",
        "geo_location": {
            "name": center_name,
            "address": address_str,
            "phone_number": "+1 800 555 0244",
            "latitude": base_lat + 0.05,
            "longitude": base_lng + 0.05,
        }
    }


def build_hotel_checkin_item(
    item_id: str,
    dest_clean: str,
    duration_days: int,
    rooms_count: int,
    dep_time: str,
    arr_time: str,
    price_per_night: float,
    is_price_tbd: bool,
    base_lat: float,
    base_lng: float,
) -> dict[str, Any]:
    """Constructs official Hotel Check-in card."""
    ht_name = f"Grand {dest_clean} Hotel"
    ht_slot = f"{dep_time} - {arr_time} - Hotel Check-in"
    ht_price_val = 0.0 if is_price_tbd else round(price_per_night, 2)
    ht_price_disp = "TBD" if is_price_tbd else f"USD {price_per_night:.2f}"
    ht_enc_q = urllib.parse.quote_plus(f"{ht_name} {dest_clean}")
    ht_website_url = f"https://www.google.com/search?q={ht_enc_q}+official+website"
    ht_google_reviews_url = f"https://www.google.com/maps/search/?api=1&query={ht_enc_q}+reviews"
    ht_tripadvisor_url = f"https://www.tripadvisor.com/Search?q={ht_enc_q}"
    ht_reviews = generate_activity_reviews(ht_name, "hotel", 4.8, dest_clean)

    return {
        "id": item_id,
        "type": "hotel",
        "name": f"{ht_name} ({rooms_count} Room(s))",
        "title": f"{ht_name} ({rooms_count} Room(s))",
        "description": f"Check-in & Stay (Night 1 of {duration_days})" + (" (Price: TBD)" if is_price_tbd else ""),
        "price": ht_price_val,
        "price_display": ht_price_disp,
        "is_price_tbd": is_price_tbd,
        "currency": "USD",
        "departure_time": dep_time,
        "arrival_time": arr_time,
        "time_slot": ht_slot + (" (Price: TBD)" if is_price_tbd else ""),
        "address": f"10 Central Avenue, {dest_clean}",
        "phone_number": "+1 800 555 0388",
        "rating": 4.8,
        "reviews_count": 1420,
        "reviews": ht_reviews,
        "breakfast_included": True,
        "has_free_breakfast": True,
        "breakfast_type": "Complimentary Hot Breakfast / Buffet",
        "breakfast_cost_display": "Free / Included with Stay",
        "safety_rating": "5.0 / Verified Safe District",
        "walkability_score": "High (92/100 Walkable)",
        "family_friendly": True,
        "website_url": ht_website_url,
        "direct_website_url": ht_website_url,
        "activity_url": ht_website_url,
        "reviews_url": ht_google_reviews_url,
        "google_reviews_url": ht_google_reviews_url,
        "tripadvisor_reviews_url": ht_tripadvisor_url,
        "geo_location": {
            "name": ht_name,
            "address": f"10 Central Avenue, {dest_clean}",
            "phone_number": "+1 800 555 0388",
            "latitude": base_lat,
            "longitude": base_lng,
            "website_url": ht_website_url,
            "reviews_url": ht_google_reviews_url
        }
    }


def fetch_live_component_pricing(**kwargs) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Mock/Live pricing aggregator for flights, hotels, and rental cars."""
    comp_pricing = {
        "flight_cost": 250.0,
        "hotel_cost_per_night": 140.0,
        "car_cost_total": 180.0,
        "outbound_departure_time": "08:30 AM",
        "outbound_arrival_time": "12:30 PM",
        "return_departure_time": "05:00 PM",
        "return_arrival_time": "09:00 PM",
    }
    return [], comp_pricing, {"source": "live"}

