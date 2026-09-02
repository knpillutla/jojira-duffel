"""
Live Component Pricing & Flight Search Aggregator for AI Travel Planner.
Delegates flight discovery to AI Search for lowest-fare dynamic scheduling.
"""

from datetime import datetime
import re
from typing import Any, Optional


def format_iso_flight_time(iso_str: Optional[str], default_val: str = "12:30 PM") -> str:
    """Formats an ISO-8601 flight timestamp to 12-hour '03:45 PM'."""
    if not iso_str:
        return default_val
    try:
        clean = re.sub(r"[Zz]|([+-]\d{2}:\d{2})$", "", str(iso_str).strip())
        return datetime.fromisoformat(clean).strftime("%I:%M %p")
    except Exception:
        return default_val


def extract_iso_date(iso_str: Optional[str]) -> Optional[str]:
    """Extracts YYYY-MM-DD date from an ISO timestamp."""
    if not iso_str:
        return None
    try:
        clean = re.sub(r"[Zz]|([+-]\d{2}:\d{2})$", "", str(iso_str).strip())
        return datetime.fromisoformat(clean).strftime("%Y-%m-%d")
    except Exception:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", str(iso_str))
        return m.group(1) if m else None


def fetch_live_component_pricing(**kwargs) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """
    Fetches real live lowest fare flight offers by calling AI Search (or Duffel Flights).
    Discovers lowest price flight, exact departure/arrival dates, carrier, and schedules.
    """
    orig = str(kwargs.get("origin") or "").upper().strip()
    dest = str(kwargs.get("destination") or "").upper().strip()
    dep_date = kwargs.get("departure_date")
    ret_date = kwargs.get("return_date")
    passengers_count = int(kwargs.get("passengers_count") or 1)
    include_flights = bool(kwargs.get("include_flights", True))
    client = kwargs.get("client")
    prompt = str(kwargs.get("prompt") or "").strip()

    # Route-based carrier default
    if dest in ["LHR", "LGW", "MAN"] or orig in ["LHR", "LGW"]:
        air = "British Airways"
    elif dest in ["CDG", "ORY"] or orig in ["CDG", "ORY"]:
        air = "Air France"
    elif dest in ["DUB", "SNN"] or orig in ["DUB", "SNN"]:
        air = "Aer Lingus"
    elif dest in ["DXB"] or orig in ["DXB"]:
        air = "Emirates"
    elif dest in ["HND", "NRT"] or orig in ["HND", "NRT"]:
        air = "All Nippon Airways (ANA)"
    elif orig in ["DFW", "MIA", "CLT"] or dest in ["DFW", "MIA", "CLT"]:
        air = "American Airlines"
    elif orig in ["ORD", "EWR", "SFO", "IAH"] or dest in ["ORD", "EWR", "SFO", "IAH"]:
        air = "United Airlines"
    else:
        air = "Delta Air Lines"

    comp_pricing: dict[str, Any] = {
        "flight_cost": 250.0,
        "airline": air,
        "airline_name": air,
        "hotel_cost_per_night": 140.0,
        "car_cost_total": 180.0,
        "outbound_departure_time": "08:30 AM",
        "outbound_arrival_time": "12:30 PM",
        "return_departure_time": "05:00 PM",
        "return_arrival_time": "09:00 PM",
    }
    source_tag = "deterministic_estimate"

    # 1. Call AI Search for Flights to identify lowest price options
    if include_flights and client and hasattr(client, "ai_search") and prompt:
        try:
            overrides = {"selected_types": ["flights"], "passengers_count": passengers_count}
            if orig and len(orig) == 3:
                overrides["origin"] = orig
            if dest and len(dest) == 3:
                overrides["destination"] = dest
            if dep_date:
                overrides["departure_date"] = dep_date
            if ret_date:
                overrides["return_date"] = ret_date

            ai_res = client.ai_search.search_ai(prompt=prompt, overrides=overrides)
            raw_d = ai_res.get("data", ai_res) if isinstance(ai_res, dict) else {}
            offers = raw_d.get("offers") or []
            if offers:
                lowest = min(offers, key=lambda o: float(o.get("total_amount") or getattr(o, "total_amount", 999999.0)))
                _populate_pricing_from_offer(comp_pricing, lowest)
                source_tag = "live_ai_search_flights"
        except Exception:
            pass

    # 2. Fallback: Query Duffel Flights Service directly if AI Search didn't yield offers
    if source_tag == "deterministic_estimate" and include_flights and client and hasattr(client, "flights") and orig and dest and len(orig) == 3 and len(dest) == 3 and dep_date:
        try:
            from ...models.common import Passenger, CabinClass
            flight_offers = client.flights.search_exact(
                origin=orig, destination=dest, departure_date=dep_date, return_date=ret_date,
                passengers=[Passenger(type="adult") for _ in range(max(1, passengers_count))],
                cabin_class=CabinClass.ECONOMY,
            )
            if flight_offers:
                lowest_exact = min(flight_offers, key=lambda o: float(getattr(o, "total_amount", 999999.0)))
                _populate_pricing_from_offer(comp_pricing, lowest_exact)
                source_tag = "live_duffel_flight_search"
        except Exception:
            pass

    return [], comp_pricing, {"source": source_tag}


def _populate_pricing_from_offer(comp: dict[str, Any], offer: Any):
    """Extracts fare, carrier, dates, and schedules from a flight offer."""
    comp["flight_cost"] = round(float(offer.get("total_amount") if isinstance(offer, dict) else getattr(offer, "total_amount", 250.0)), 2)
    owner = offer.get("owner") if isinstance(offer, dict) else getattr(offer, "owner", {})
    carrier = owner.get("name") if isinstance(owner, dict) else getattr(owner, "name", "")
    if carrier:
        comp["airline"] = comp["airline_name"] = carrier

    slices = offer.get("slices") if isinstance(offer, dict) else getattr(offer, "slices", [])
    if slices and len(slices) > 0:
        s0 = slices[0]
        segs0 = s0.get("segments") if isinstance(s0, dict) else getattr(s0, "segments", [])
        if segs0:
            dep_at = segs0[0].get("departing_at") if isinstance(segs0[0], dict) else getattr(segs0[0], "departing_at", "")
            arr_at = segs0[-1].get("arriving_at") if isinstance(segs0[-1], dict) else getattr(segs0[-1], "arriving_at", "")
            comp["outbound_departure_time"] = format_iso_flight_time(dep_at, "08:30 AM")
            comp["outbound_arrival_time"] = format_iso_flight_time(arr_at, "12:30 PM")
            s_date = extract_iso_date(dep_at)
            if s_date:
                comp["discovered_start_date"] = s_date

    if slices and len(slices) > 1:
        s1 = slices[1]
        segs1 = s1.get("segments") if isinstance(s1, dict) else getattr(s1, "segments", [])
        if segs1:
            dep_ret = segs1[0].get("departing_at") if isinstance(segs1[0], dict) else getattr(segs1[0], "departing_at", "")
            arr_ret = segs1[-1].get("arriving_at") if isinstance(segs1[-1], dict) else getattr(segs1[-1], "arriving_at", "")
            comp["return_departure_time"] = format_iso_flight_time(dep_ret, "05:00 PM")
            comp["return_arrival_time"] = format_iso_flight_time(arr_ret, "09:00 PM")
            e_date = extract_iso_date(dep_ret)
            if e_date:
                comp["discovered_end_date"] = e_date
