"""
Interactive slot filling module for missing flight, stay, and car search parameters.
"""

from datetime import datetime, timedelta
from typing import Any, Optional


def prompt_input(label: str, default: str = "", required: bool = True) -> str:
    """Prompt user for input with default support and validation."""
    prompt_str = f"{label}"
    if default:
        prompt_str += f" [{default}]"
    prompt_str += ": "

    while True:
        try:
            val = input(prompt_str).strip()
            if not val and default:
                return default
            if not val and required:
                print("  [!] This field is required. Please enter a value.")
                continue
            return val
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            raise SystemExit(0)


def fill_optimized_flight_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Prompt interactively for Optimized Flight Search parameters:
      - Origin & Destination
      - Target departure date
      - Trip duration (number of days to travel)
      - Date flexibility window (+/- flex days)
    """
    extracted_slices = extracted.get("slices", [])
    first_slice = extracted_slices[0] if extracted_slices else {}

    orig = first_slice.get("origin") or ""
    dest = first_slice.get("destination") or ""
    target_date = first_slice.get("departure_date") or ""

    second_slice = extracted_slices[1] if len(extracted_slices) > 1 else {}
    target_return_date = extracted.get("target_return_date") or second_slice.get("departure_date") or ""

    if orig:
        print(f"  * Extracted Origin: {orig}")
    if dest:
        print(f"  * Extracted Destination: {dest}")
    if target_date:
        print(f"  * Extracted Target Date: {target_date}")
    if target_return_date:
        print(f"  * Extracted Target Return Date: {target_return_date}")

    orig = prompt_input("  Enter Origin Airport IATA Code (e.g. LHR, JFK, LAX)", default=orig or "LHR")
    dest = prompt_input("  Enter Destination Airport IATA Code (e.g. JFK, SFO, CDG)", default=dest or "JFK")

    if not target_date:
        default_target = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        target_date = prompt_input("  Enter Target Departure Date (YYYY-MM-DD)", default=default_target)

    target_dep_dt = datetime.strptime(target_date, "%Y-%m-%d")
    duration_days = extracted.get("duration_days")
    default_ret_date = target_return_date or (
        target_dep_dt + timedelta(days=duration_days or 7)
    ).strftime("%Y-%m-%d")
    target_return_date = prompt_input("  Enter Target Return Date (YYYY-MM-DD)", default=default_ret_date)

    target_ret_dt = datetime.strptime(target_return_date, "%Y-%m-%d")
    if target_ret_dt < target_dep_dt:
        print("  [!] Target Return Date cannot be before Target Departure Date. Adjusting return date.")
        target_ret_dt = target_dep_dt + timedelta(days=7)
        target_return_date = target_ret_dt.strftime("%Y-%m-%d")

    max_allowed_duration = (target_ret_dt - target_dep_dt).days
    if max_allowed_duration < 1:
        max_allowed_duration = 1

    flex_days = 0
    requested_duration = extracted.get("duration_days")
    default_duration = (
        int(requested_duration)
        if isinstance(requested_duration, int) and 1 <= requested_duration <= max_allowed_duration
        else max_allowed_duration
    )

    # Prompt and validate MAXIMUM Trip Duration (must be <= max_allowed_duration)
    while True:
        max_dur_str = prompt_input(
            f"  Enter MAXIMUM Trip Duration in Days (1 to {max_allowed_duration})",
            default=str(default_duration)
        )
        try:
            max_duration_days = int(max_dur_str)
            if 1 <= max_duration_days <= max_allowed_duration:
                break
            else:
                print(
                    f"  [!] Error: Maximum trip duration cannot exceed {max_allowed_duration} days "
                    f"(the interval between {target_date} and {target_return_date}). Please try again."
                )
        except ValueError:
            print("  [!] Invalid number. Please enter an integer.")

    # Prompt and validate MINIMUM Trip Duration (must be 1 <= min <= max_duration_days)
    default_min = default_duration
    if default_min > max_duration_days:
        default_min = max_duration_days
    while True:
        min_dur_str = prompt_input(
            f"  Enter MINIMUM Trip Duration in Days (1 to {max_duration_days})",
            default=str(default_min)
        )
        try:
            min_duration_days = int(min_dur_str)
            if 1 <= min_duration_days <= max_duration_days:
                break
            else:
                print(
                    f"  [!] Error: Minimum trip duration must be between 1 and {max_duration_days} days. Please try again."
                )
        except ValueError:
            print("  [!] Invalid number. Please enter an integer.")

    cabin = extracted.get("cabin_class") or "economy"
    cabin_class = prompt_input(
        "  Enter Cabin Class (economy, premium_economy, business, first)", default=cabin, required=False
    ).lower()

    pax_count = str(extracted.get("passengers_count") or 1)
    passengers_count = int(
        prompt_input("  Enter Number of Adult Passengers", default=pax_count, required=False)
    )

    return {
        "origin": orig,
        "destination": dest,
        "target_date": target_date,
        "target_return_date": target_return_date,
        "min_duration_days": min_duration_days,
        "max_duration_days": max_duration_days,
        "flex_days": flex_days,
        "cabin_class": cabin_class,
        "passengers_count": passengers_count,
    }


def fill_stay_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Review extracted stay/hotel parameters and interactively prompt for missing fields.
    """
    print("\n--- Hotel / Stay Search Parameter Extraction ---")
    if extracted.get("location"):
        print(f"  * Extracted Location: {extracted['location']}")
    if extracted.get("check_in_date"):
        print(f"  * Extracted Check-in Date: {extracted['check_in_date']}")
    if extracted.get("check_out_date"):
        print(f"  * Extracted Check-out Date: {extracted['check_out_date']}")

    if not extracted.get("location"):
        extracted["location"] = prompt_input("  Enter City or Airport / Location (e.g. New York, London)", default="New York")

    if not extracted.get("check_in_date"):
        default_in = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        extracted["check_in_date"] = prompt_input("  Enter Check-in Date (YYYY-MM-DD)", default=default_in)

    if not extracted.get("check_out_date"):
        in_dt = datetime.strptime(extracted["check_in_date"], "%Y-%m-%d")
        default_out = (in_dt + timedelta(days=4)).strftime("%Y-%m-%d")
        extracted["check_out_date"] = prompt_input("  Enter Check-out Date (YYYY-MM-DD)", default=default_out)

    guests = str(extracted.get("guests_count") or 1)
    extracted["guests_count"] = int(prompt_input("  Enter Number of Guests", default=guests, required=False))

    rooms = str(extracted.get("rooms") or 1)
    extracted["rooms"] = int(prompt_input("  Enter Number of Rooms", default=rooms, required=False))

    return extracted


def fill_car_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Review extracted car rental parameters and interactively prompt for missing fields.
    """
    print("\n--- Car Rental Search Parameter Extraction ---")
    if extracted.get("pickup_location"):
        print(f"  * Extracted Pickup Location: {extracted['pickup_location']}")
    if extracted.get("dropoff_location"):
        print(f"  * Extracted Dropoff Location: {extracted['dropoff_location']}")
    if extracted.get("pickup_datetime"):
        print(f"  * Extracted Pickup Date: {extracted['pickup_datetime']}")

    if not extracted.get("pickup_location"):
        extracted["pickup_location"] = prompt_input("  Enter Pickup Airport IATA / Location (e.g. LAX, JFK)", default="LAX")

    if not extracted.get("dropoff_location"):
        extracted["dropoff_location"] = prompt_input("  Enter Dropoff Location", default=extracted["pickup_location"])

    if not extracted.get("pickup_datetime"):
        default_pick = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%dT10:00:00Z")
        extracted["pickup_datetime"] = prompt_input("  Enter Pickup Date & Time (YYYY-MM-DDTHH:MM:SSZ)", default=default_pick)

    if not extracted.get("dropoff_datetime"):
        default_drop = (datetime.now() + timedelta(days=25)).strftime("%Y-%m-%dT10:00:00Z")
        extracted["dropoff_datetime"] = prompt_input("  Enter Dropoff Date & Time (YYYY-MM-DDTHH:MM:SSZ)", default=default_drop)

    age = str(extracted.get("driver_age") or 30)
    extracted["driver_age"] = int(prompt_input("  Enter Primary Driver Age", default=age, required=False))

    return extracted


def fill_standard_flight_slots(extracted: dict[str, Any]) -> dict[str, Any]:
    """
    Prompt interactively for Standard Exact-Date Flight Search parameters:
      - Origin & Destination
      - Exact departure date
      - Optional exact return date (for round-trip)
      - Cabin class & Passenger count
    """
    extracted_slices = extracted.get("slices", [])
    first_slice = extracted_slices[0] if extracted_slices else {}

    orig = first_slice.get("origin") or ""
    dest = first_slice.get("destination") or ""
    dep_date = first_slice.get("departure_date") or ""

    second_slice = extracted_slices[1] if len(extracted_slices) > 1 else {}
    ret_date = extracted.get("target_return_date") or second_slice.get("departure_date") or ""

    if orig:
        print(f"  * Extracted Origin: {orig}")
    if dest:
        print(f"  * Extracted Destination: {dest}")
    if dep_date:
        print(f"  * Extracted Departure Date: {dep_date}")
    if ret_date:
        print(f"  * Extracted Return Date: {ret_date}")

    orig = prompt_input("  Enter Origin Airport IATA Code (e.g. LHR, JFK, ATL)", default=orig or "ATL")
    dest = prompt_input("  Enter Destination Airport IATA Code (e.g. JFK, SFO, CDG)", default=dest or "CDG")

    if not dep_date:
        default_dep = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        dep_date = prompt_input("  Enter Exact Departure Date (YYYY-MM-DD)", default=default_dep)

    dep_dt = datetime.strptime(dep_date, "%Y-%m-%d")
    default_ret = ret_date or (dep_dt + timedelta(days=7)).strftime("%Y-%m-%d")
    ret_date = prompt_input("  Enter Exact Return Date (YYYY-MM-DD, or press Enter for one-way)", default=default_ret, required=False)

    cabin = extracted.get("cabin_class") or "economy"
    cabin_class = prompt_input(
        "  Enter Cabin Class (economy, premium_economy, business, first)", default=cabin, required=False
    ).lower()

    pax_count = str(extracted.get("passengers_count") or 1)
    passengers_count = int(
        prompt_input("  Enter Number of Adult Passengers", default=pax_count, required=False)
    )

    return {
        "origin": orig.upper(),
        "destination": dest.upper(),
        "departure_date": dep_date,
        "return_date": ret_date.strip() if ret_date and ret_date.strip() else None,
        "cabin_class": cabin_class,
        "passengers_count": passengers_count,
    }
